import pytest
import pandas as pd
from unittest.mock import MagicMock

from app.tools.market_tool import MarketTool
from app.tools.exceptions import ToolUnavailableError

@pytest.mark.asyncio
async def test_get_price_success(mocker):
    tool = MarketTool()
    
    # Mock yfinance Ticker.fast_info
    mock_ticker = MagicMock()
    mock_ticker.fast_info = {"lastPrice": 150.0}
    mock_yf = mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    
    price = await tool.get_price("AAPL")
    assert price == 150.0
    mock_yf.assert_called_once_with("AAPL")


@pytest.mark.asyncio
async def test_get_price_fallback_to_history(mocker):
    tool = MarketTool()
    
    # fast_info returns None, history returns mock dataframe
    mock_ticker = MagicMock()
    mock_ticker.fast_info = {"lastPrice": None}
    
    # Mock history dataframe
    df_mock = pd.DataFrame({"Close": [145.5]})
    mock_ticker.history.return_value = df_mock
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    
    price = await tool.get_price("AAPL")
    assert price == 145.5
    mock_ticker.history.assert_called_once_with(period="1d")


@pytest.mark.asyncio
async def test_get_price_retry_and_fail(mocker):
    tool = MarketTool()
    
    # Force yfinance to raise Exception
    mocker.patch("yfinance.Ticker", side_effect=Exception("yfinance down"))
    
    # Expect ToolUnavailableError after retries are exhausted
    with pytest.raises(ToolUnavailableError):
        await tool.get_price("AAPL")


@pytest.mark.asyncio
async def test_get_ohlc_success(mocker):
    tool = MarketTool()
    
    mock_ticker = MagicMock()
    # Mock history dataframe with datetime index
    index = pd.to_datetime(["2026-08-01"])
    df_mock = pd.DataFrame({"Open": [140.0], "Close": [142.0]}, index=index)
    mock_ticker.history.return_value = df_mock
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    
    ohlc = await tool.get_ohlc("AAPL", period="1mo", interval="1d")
    assert len(ohlc) == 1
    assert ohlc[0]["open"] == 140.0
    assert ohlc[0]["close"] == 142.0
    # The index column should be string formatted
    assert "date" in ohlc[0]


@pytest.mark.asyncio
async def test_get_volume_success(mocker):
    tool = MarketTool()
    
    mock_ticker = MagicMock()
    mock_ticker.fast_info = {"lastVolume": 5000000}
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    
    volume = await tool.get_volume("AAPL")
    assert volume == 5000000


@pytest.mark.asyncio
async def test_market_tool_circuit_breaker_tripping(mocker):
    tool = MarketTool()
    # Set threshold to 5, recovery to 60 for standard test
    tool.circuit_breaker.failure_threshold = 5
    tool.circuit_breaker.recovery_timeout = 60.0
    
    # Force yfinance to always fail
    mocker.patch("yfinance.Ticker", side_effect=Exception("Network error"))
    
    # 5 consecutive failures should trip the circuit breaker
    for _ in range(5):
        with pytest.raises(ToolUnavailableError):
            await tool.get_price("AAPL")
            
    assert tool.circuit_breaker.state == "OPEN"
    
    # 6th call should immediately raise ToolUnavailableError with "OPEN" state
    # without making any calls to yfinance
    mock_yf = mocker.patch("yfinance.Ticker")
    
    with pytest.raises(ToolUnavailableError) as exc_info:
        await tool.get_price("AAPL")
        
    assert "Circuit breaker" in str(exc_info.value)
    assert "is OPEN" in str(exc_info.value)
    mock_yf.assert_not_called()
