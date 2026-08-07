import time
import logging
import math
from typing import Dict, Any, List

from app.tools.market_tool import MarketTool
from app.tools.fred_tool import FredTool
from app.tools.exceptions import ToolUnavailableError
from app.llm_client import GeminiClient
from .schemas import RiskSummary
from .state import AgentState

from app.logging_config import get_logger

logger = get_logger("sentinel.agents.risk")

def calculate_historical_volatility(ohlc: List[Dict[str, Any]]) -> float:
    """
    Calculates the annualized historical volatility (standard deviation of daily log returns)
    over the last 30 trading days. Uses sample standard deviation with Bessel's correction.
    """
    closes = [day["close"] for day in ohlc]
    if len(closes) < 2:
        return 0.0

    # Extract last 31 days to get 30 daily returns
    recent_closes = closes[-31:]
    
    # Calculate daily returns
    returns = []
    for i in range(1, len(recent_closes)):
        prev = recent_closes[i - 1]
        curr = recent_closes[i]
        if prev > 0:
            returns.append(math.log(curr / prev))

    if not returns:
        return 0.0

    # Calculate standard deviation
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1) if n > 1 else 0.0
    std_dev = math.sqrt(variance)

    # Annualize (assuming 252 trading days/year representing active trading periods)
    return std_dev * math.sqrt(252)


async def risk_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph agent node that computes price volatility and fetches VIX data
    to produce a structured RiskSummary from the LLM client.
    Does NOT reference or contain crowd/social sentiment.
    """
    symbol = state.get("symbol")
    correlation_id = state.get("correlation_id", "unknown-id")
    start_time = time.time()

    logger.info(f"[{correlation_id}] RiskAgent started for symbol: {symbol}")

    market_tool = MarketTool()
    fred_tool = FredTool()
    llm_client = GeminiClient()

    # Get news tone from state if available
    news_summary = state.get("news_summary")
    news_tone = "Neutral"
    if news_summary:
        news_tone = news_summary.get("overall_tone", "Neutral")

    degraded = False
    confidence_penalty = 0.0
    volatility = 0.0
    vix_val = 20.0  # Default neutral midpoint VIX

    # 1. Fetch Price Volatility
    try:
        ohlc_data = await market_tool.get_ohlc(symbol, period="3mo", interval="1d")
        volatility = calculate_historical_volatility(ohlc_data)
    except ToolUnavailableError as te:
        logger.warning(f"[{correlation_id}] MarketTool unavailable for RiskAgent: {te}")
        degraded = True
        confidence_penalty += 0.4
    except Exception as e:
        logger.error(f"[{correlation_id}] MarketTool failed unexpectedly for RiskAgent: {e}")
        degraded = True
        confidence_penalty += 0.5

    # 2. Fetch CBOE VIX Index (using VIXCLS series ID on FRED API)
    try:
        vix_payload = await fred_tool.get_series("VIXCLS")
        observations = vix_payload.get("observations", [])
        
        # Iterate backwards to find the last valid numeric observation
        for obs in reversed(observations):
            val_str = obs.get("value")
            if val_str and val_str != ".":
                try:
                    vix_val = float(val_str)
                    break
                except ValueError:
                    pass
    except ToolUnavailableError as te:
        logger.warning(f"[{correlation_id}] FredTool unavailable for RiskAgent: {te}")
        degraded = True
        confidence_penalty += 0.3
    except Exception as e:
        logger.error(f"[{correlation_id}] FredTool failed unexpectedly for RiskAgent: {e}")
        degraded = True
        confidence_penalty += 0.4

    # 3. Formulate Prompt and Invoke LLM
    try:
        # If both tools failed, we skip LLM and return a direct degraded state
        if degraded and volatility == 0.0 and vix_val == 20.0:
            raise ToolUnavailableError("All upstream tools failed.")

        prompt = (
            f"Asset: {symbol}\n"
            f"Annualized Price Volatility: {volatility:.2%}\n"
            f"CBOE Volatility Index (VIX): {vix_val:.2f}\n"
            f"News Environment Tone: {news_tone}\n"
            f"Degradation Penalty: {confidence_penalty:.2f}\n\n"
            f"Task: Evaluate the risk level (low, medium, high) and calculate a custom volatility_score (0-100). "
            f"Do not base risk on crowd sentiment or social media inputs. "
            f"Include the required degradation metadata."
        )

        summary: RiskSummary = await llm_client.generate_structured_output(prompt, RiskSummary)
        
        # Override fields if we had a partial degradation
        if degraded:
            summary.degraded = True
            summary.confidence_penalty = max(summary.confidence_penalty, confidence_penalty)

        duration = time.time() - start_time
        logger.info(f"[{correlation_id}] RiskAgent completed successfully in {duration:.3f}s")
        return {"risk_summary": summary.model_dump()}

    except ToolUnavailableError as te:
        duration = time.time() - start_time
        logger.error(f"[{correlation_id}] RiskAgent degraded due to tool unavailability: {te} after {duration:.3f}s")
        
        degraded_summary = RiskSummary(
            risk_level="medium",
            volatility_score=50.0,
            confidence_penalty=1.0,
            degraded=True
        )
        return {"risk_summary": degraded_summary.model_dump()}
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{correlation_id}] RiskAgent unexpected error: {e} after {duration:.3f}s")
        
        degraded_summary = RiskSummary(
            risk_level="medium",
            volatility_score=50.0,
            confidence_penalty=1.0,
            degraded=True
        )
        return {"risk_summary": degraded_summary.model_dump()}
