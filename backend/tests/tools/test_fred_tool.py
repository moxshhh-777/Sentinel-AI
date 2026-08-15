import pytest
import responses
from app.tools.fred_tool import FredTool
from app.tools.exceptions import ToolUnavailableError

@pytest.mark.asyncio
async def test_get_series_success():
    tool = FredTool()
    tool.api_key = "mock_fred_key"
    
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://api.stlouisfed.org/fred/series/observations",
            json={
                "realtime_start": "2026-08-01",
                "realtime_end": "2026-08-01",
                "observations": [
                    {"date": "2026-08-01", "value": "1.5"}
                ]
            },
            status=200
        )
        
        res = await tool.get_series("GDP")
        assert "observations" in res
        assert len(res["observations"]) == 1
        assert res["observations"][0]["value"] == "1.5"


@pytest.mark.asyncio
async def test_get_series_fail_after_retries():
    tool = FredTool()
    tool.api_key = "mock_fred_key"
    
    with responses.RequestsMock() as rsps:
        # Mock FRED API endpoint returning internal server error (500)
        rsps.add(
            responses.GET,
            "https://api.stlouisfed.org/fred/series/observations",
            status=500
        )
        
        with pytest.raises(ToolUnavailableError):
            await tool.get_series("GDP")
 

@pytest.mark.asyncio
async def test_fred_tool_circuit_breaker_tripping():
    tool = FredTool()
    tool.api_key = "mock_fred_key"
    tool.circuit_breaker.failure_threshold = 5
    tool.circuit_breaker.recovery_timeout = 60.0
    
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://api.stlouisfed.org/fred/series/observations",
            status=500
        )
        
        # Tripping circuit breaker with 5 failures
        for _ in range(5):
            with pytest.raises(ToolUnavailableError):
                await tool.get_series("GDP")
                
        assert tool.circuit_breaker.state == "OPEN"
        
        # 6th call should immediately raise ToolUnavailableError due to open circuit
        with pytest.raises(ToolUnavailableError) as exc_info:
            await tool.get_series("GDP")
            
        assert "Circuit breaker" in str(exc_info.value)
        assert "is OPEN" in str(exc_info.value)
