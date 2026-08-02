import pytest
import responses
from app.tools.news_tool import NewsTool
from app.tools.exceptions import ToolUnavailableError

@pytest.mark.asyncio
async def test_get_headlines_newsapi_success():
    tool = NewsTool()
    tool.newsapi_key = "mock_newsapi_key"
    tool.gnews_api_key = "mock_gnews_key"
    
    with responses.RequestsMock() as rsps:
        # Mock NewsAPI response
        rsps.add(
            responses.GET,
            "https://newsapi.org/v2/everything",
            json={
                "status": "ok",
                "articles": [
                    {
                        "title": "NewsAPI Title",
                        "description": "NewsAPI Desc",
                        "url": "http://newsapi.org/test",
                        "publishedAt": "2026-08-01T00:00:00Z",
                        "source": {"name": "NewsAPI Source"}
                    }
                ]
            },
            status=200
        )
        
        res = await tool.get_headlines("bitcoin", limit=1)
        assert res["source"] == "newsapi"
        assert len(res["articles"]) == 1
        assert res["articles"][0]["title"] == "NewsAPI Title"
        assert res["articles"][0]["source_name"] == "NewsAPI Source"


@pytest.mark.asyncio
async def test_get_headlines_gnews_fallback():
    tool = NewsTool()
    tool.newsapi_key = "mock_newsapi_key"
    tool.gnews_api_key = "mock_gnews_key"
    
    with responses.RequestsMock() as rsps:
        # NewsAPI returns rate limit error (429)
        rsps.add(
            responses.GET,
            "https://newsapi.org/v2/everything",
            status=429
        )
        
        # GNews fallback returns success
        rsps.add(
            responses.GET,
            "https://gnews.io/api/v4/search",
            json={
                "articles": [
                    {
                        "title": "GNews Title",
                        "description": "GNews Desc",
                        "url": "http://gnews.io/test",
                        "publishedAt": "2026-08-01T01:00:00Z",
                        "source": {"name": "GNews Source"}
                    }
                ]
            },
            status=200
        )
        
        res = await tool.get_headlines("bitcoin", limit=1)
        assert res["source"] == "gnews"
        assert len(res["articles"]) == 1
        assert res["articles"][0]["title"] == "GNews Title"


@pytest.mark.asyncio
async def test_get_headlines_both_fail():
    tool = NewsTool()
    tool.newsapi_key = "mock_newsapi_key"
    tool.gnews_api_key = "mock_gnews_key"
    
    with responses.RequestsMock() as rsps:
        # Both APIs fail
        rsps.add(responses.GET, "https://newsapi.org/v2/everything", status=500)
        rsps.add(responses.GET, "https://gnews.io/api/v4/search", status=500)
        
        with pytest.raises(ToolUnavailableError):
            await tool.get_headlines("bitcoin", limit=1)


@pytest.mark.asyncio
async def test_news_tool_circuit_breaker_tripping():
    tool = NewsTool()
    tool.newsapi_key = "mock_newsapi_key"
    tool.gnews_api_key = "mock_gnews_key"
    tool.circuit_breaker.failure_threshold = 5
    tool.circuit_breaker.recovery_timeout = 60.0
    
    with responses.RequestsMock() as rsps:
        # Register generic failures
        rsps.add(responses.GET, "https://newsapi.org/v2/everything", status=500)
        rsps.add(responses.GET, "https://gnews.io/api/v4/search", status=500)
        
        # Fail 5 times to trip the breaker
        for _ in range(5):
            with pytest.raises(ToolUnavailableError):
                await tool.get_headlines("bitcoin", limit=1)
                
        assert tool.circuit_breaker.state == "OPEN"
        
        # 6th call should short-circuit immediately without sending any network request
        with pytest.raises(ToolUnavailableError) as exc_info:
            await tool.get_headlines("bitcoin", limit=1)
            
        assert "Circuit breaker" in str(exc_info.value)
        assert "is OPEN" in str(exc_info.value)
