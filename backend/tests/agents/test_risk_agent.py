import pytest
import math
from unittest.mock import AsyncMock

from app.agents.risk_agent import risk_agent_node, calculate_historical_volatility
from app.agents.schemas import RiskSummary
from app.tools.exceptions import ToolUnavailableError

def test_calculate_historical_volatility():
    # Constant closes: volatility should be 0.0
    ohlc_flat = [{"close": 100.0} for _ in range(35)]
    assert calculate_historical_volatility(ohlc_flat) == 0.0
    
    # Alternating prices (simulating daily returns)  
    ohlc_alternating = []
    # Log returns: alternate between math.log(1.02) and math.log(0.98)
    curr = 100.0
    for i in range(35):
        ohlc_alternating.append({"close": curr})
        if i % 2 == 0:
            curr *= 1.02
        else:
            curr *= 0.98
            
    vol = calculate_historical_volatility(ohlc_alternating)
    assert vol > 0.0
    assert isinstance(vol, float)


@pytest.mark.asyncio
async def test_risk_agent_happy_path(mocker):
    # Mock MarketTool price observations (35 days)
    ohlc_mock = [{"close": 100.0} for _ in range(35)]
    mocker.patch("app.tools.market_tool.MarketTool.get_ohlc", new_callable=AsyncMock, return_value=ohlc_mock)
    
    # Mock FRED VIX payload
    vix_mock = {
        "observations": [
            {"date": "2026-07-31", "value": "18.5"},
            {"date": "2026-08-01", "value": "19.2"},
            {"date": "2026-08-02", "value": "."}  # Holiday observation
        ]
    }
    mocker.patch("app.tools.fred_tool.FredTool.get_series", new_callable=AsyncMock, return_value=vix_mock)
    
    # Mock LLM Client
    mock_summary = RiskSummary(
        risk_level="medium",
        volatility_score=45.0,
        confidence_penalty=0.0,
        degraded=False
    )
    mock_llm = mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock, return_value=mock_summary)
    
    # Provide news_summary in state to verify cross-agent parsing
    state = {
        "symbol": "AAPL",
        "correlation_id": "test-id",
        "news_summary": {"overall_tone": "Neutral"}
    }
    
    result = await risk_agent_node(state)
    
    assert "risk_summary" in result
    assert result["risk_summary"]["risk_level"] == "medium"
    assert result["risk_summary"]["volatility_score"] == 45.0
    assert result["risk_summary"]["degraded"] is False
    
    # Verify LLM call parameters (it should select the last valid VIX observation: 19.2)
    mock_llm.assert_called_once()
    prompt_sent = mock_llm.call_args[0][0]
    assert "19.20" in prompt_sent
    assert "News Environment Tone: Neutral" in prompt_sent


@pytest.mark.asyncio
async def test_risk_agent_degraded_market_tool(mocker):
    # MarketTool fails, FredTool succeeds
    mocker.patch("app.tools.market_tool.MarketTool.get_ohlc", new_callable=AsyncMock, side_effect=ToolUnavailableError("Price error"))
    
    vix_mock = {"observations": [{"date": "2026-08-01", "value": "15.0"}]}
    mocker.patch("app.tools.fred_tool.FredTool.get_series", new_callable=AsyncMock, return_value=vix_mock)
    
    mock_summary = RiskSummary(
        risk_level="low",
        volatility_score=20.0,
        confidence_penalty=0.0,
        degraded=False
    )
    mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock, return_value=mock_summary)
    
    state = {"symbol": "AAPL", "correlation_id": "test-id"}
    result = await risk_agent_node(state)
    
    assert "risk_summary" in result
    # The agent should enforce degraded status and apply confidence penalty
    assert result["risk_summary"]["degraded"] is True
    assert result["risk_summary"]["confidence_penalty"] >= 0.4


@pytest.mark.asyncio
async def test_risk_agent_degraded_all_tools(mocker):
    # Both tools fail
    mocker.patch("app.tools.market_tool.MarketTool.get_ohlc", new_callable=AsyncMock, side_effect=ToolUnavailableError("Error"))
    mocker.patch("app.tools.fred_tool.FredTool.get_series", new_callable=AsyncMock, side_effect=ToolUnavailableError("Error"))
    
    mock_llm = mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock)
    
    state = {"symbol": "AAPL", "correlation_id": "test-id"}
    result = await risk_agent_node(state)
    
    assert "risk_summary" in result
    assert result["risk_summary"]["degraded"] is True
    assert result["risk_summary"]["confidence_penalty"] == 1.0
    mock_llm.assert_not_called()
