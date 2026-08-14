import time
import logging
from typing import Dict, Any, List

from app.tools.market_tool import MarketTool
from app.tools.exceptions import ToolUnavailableError
from app.llm_client import GeminiClient
from .schemas import MarketSummary
from .state import AgentState
 
from app.logging_config import get_logger

logger = get_logger("sentinel.agents.market")

def calculate_indicators(ohlc: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Computes SMA20, SMA50, and RSI14 from historical OHLC records.
    Expects a list of dictionaries containing daily close prices.
    """
    closes = [day["close"] for day in ohlc]
    n = len(closes)

    # 1. SMA50
    if n < 50:
        sma50 = sum(closes) / n if n > 0 else 0.0
    else:
        sma50 = sum(closes[-50:]) / 50.0

    # 2. SMA20
    if n < 20:
        sma20 = sum(closes) / n if n > 0 else 0.0
    else:
        sma20 = sum(closes[-20:]) / 20.0

    # 3. RSI14 (Relative Strength Index)
    rsi14 = 50.0  # Default neutral midpoint (used when there are insufficient records to compute returns)
    if n >= 15:
        deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
        gains = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]

        # Initial averages
        avg_gain = sum(gains[:14]) / 14.0
        avg_loss = sum(losses[:14]) / 14.0

        if avg_loss == 0:
            rsi14 = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi14 = 100.0 - (100.0 / (1.0 + rs))

        # Wilder's smoothing for subsequent periods
        for i in range(14, len(deltas)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14.0
            avg_loss = (avg_loss * 13 + losses[i]) / 14.0
            if avg_loss == 0:
                rsi14 = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi14 = 100.0 - (100.0 / (1.0 + rs))

    return {"sma20": sma20, "sma50": sma50, "rsi14": rsi14}


async def market_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph agent node that queries market metrics, computes technical indicators,
    and calls the LLM client to return a concise structured MarketSummary.
    """
    symbol = state.get("symbol")
    correlation_id = state.get("correlation_id", "unknown-id")
    start_time = time.time()

    logger.info(f"[{correlation_id}] MarketAgent started for symbol: {symbol}")

    market_tool = MarketTool()
    llm_client = GeminiClient()

    try:
        # Fetch 3 months of data to ensure we can compute SMA50 correctly
        ohlc_data = await market_tool.get_ohlc(symbol, period="3mo", interval="1d")
        current_price = await market_tool.get_price(symbol)
        volume = await market_tool.get_volume(symbol)

        # Compute technical indicators
        indicators = calculate_indicators(ohlc_data)

        # Formulate LLM prompt
        prompt = (
            f"Asset: {symbol}\n"
            f"Current Price: ${current_price:.2f}\n"
            f"Trading Volume: {volume}\n"
            f"Computed Indicators:\n"
            f" - SMA20: ${indicators['sma20']:.2f}\n"
            f" - SMA50: ${indicators['sma50']:.2f}\n"
            f" - RSI14: {indicators['rsi14']:.2f}\n\n"
            f"Please compile these metrics into a MarketSummary."
        )

        # Invoke Gemini Client
        summary: MarketSummary = await llm_client.generate_structured_output(prompt, MarketSummary)
        
        duration = time.time() - start_time
        logger.info(f"[{correlation_id}] MarketAgent completed successfully in {duration:.3f}s")
        return {"market_summary": summary.model_dump()}

    except ToolUnavailableError as te:
        duration = time.time() - start_time
        logger.error(f"[{correlation_id}] MarketAgent degraded due to tool unavailability: {te} after {duration:.3f}s")
        
        # Return graceful degraded state
        degraded_summary = MarketSummary(
            trend="Unknown",
            volatility_note="Market data source is currently unavailable.",
            key_levels=[],
            degraded=True,
            confidence=0.1
        )
        return {"market_summary": degraded_summary.model_dump()}
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{correlation_id}] MarketAgent unexpected error: {e} after {duration:.3f}s")
        
        # General fallback degradation
        degraded_summary = MarketSummary(
            trend="Unknown",
            volatility_note=f"Analysis failed due to unexpected error: {str(e)}",
            key_levels=[],
            degraded=True,
            confidence=0.0
        )
        return {"market_summary": degraded_summary.model_dump()} 
