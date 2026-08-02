import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.market_agent import market_agent_node, calculate_indicators
from app.agents.schemas import MarketSummary
from app.tools.exceptions import ToolUnavailableError

def test_calculate_indicators():
    # Construct 60 days of closes to calculate SMA50
    # Closes are [1, 2, ..., 60]
    ohlc = [{"close": float(i)} for i in range(1, 61)]
    
    indicators = calculate_indicators(ohlc)
    
    # SMA20: average of closes [41, 42, ..., 60]
    # Sum: 41 + ... + 60 = 1010. Average: 1010/20 = 50.5
    assert indicators["sma20"] == 50.5
    
    # SMA50: average of closes [11, 12, ..., 60]
    # Sum: 11 + ... + 60 = 1775. Average: 1775/50 = 35.5
    assert indicators["sma50"] == 35.5
    
    # RSI14 should be returned as float
    assert isinstance(indicators["rsi14"], float)


@pytest.mark.asyncio
async def test_market_agent_happy_path(mocker):
    # Mock Ticker data
    ohlc_mock = [{"close": float(i)} for i in range(1, 60)]
    
    mocker.patch("app.tools.market_tool.MarketTool.get_ohlc", new_callable=AsyncMock, return_value=ohlc_mock)
    mocker.patch("app.tools.market_tool.MarketTool.get_price", new_callable=AsyncMock, return_value=60.0)
    mocker.patch("app.tools.market_tool.MarketTool.get_volume", new_callable=AsyncMock, return_value=100000)
    
    # Mock LLM Client
    mock_summary = MarketSummary(
        trend="Bullish",
        volatility_note="Normal",
        key_levels=[55.0, 65.0],
        degraded=False,
        confidence=0.85
    )
    mock_llm = mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock, return_value=mock_summary)
    
    state = {"symbol": "AAPL", "correlation_id": "test-id"}
    result = await market_agent_node(state)
    
    assert "market_summary" in result
    assert result["market_summary"]["trend"] == "Bullish"
    assert result["market_summary"]["degraded"] is False
    assert result["market_summary"]["confidence"] == 0.85
    
    # Verify the LLM was called with details
    mock_llm.assert_called_once()
    prompt_sent = mock_llm.call_args[0][0]
    assert "Asset: AAPL" in prompt_sent
    assert "Current Price: $60.00" in prompt_sent


@pytest.mark.asyncio
async def test_market_agent_degraded_path(mocker):
    # Force MarketTool to throw ToolUnavailableError
    mocker.patch("app.tools.market_tool.MarketTool.get_ohlc", new_callable=AsyncMock, side_effect=ToolUnavailableError("Circuit open"))
    
    # Mock LLM Client to ensure it is NOT called when yfinance fails
    mock_llm = mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock)
    
    state = {"symbol": "AAPL", "correlation_id": "test-id"}
    result = await market_agent_node(state)
    
    assert "market_summary" in result
    assert result["market_summary"]["trend"] == "Unknown"
    assert result["market_summary"]["degraded"] is True
    assert result["market_summary"]["confidence"] == 0.1
    mock_llm.assert_not_called()
