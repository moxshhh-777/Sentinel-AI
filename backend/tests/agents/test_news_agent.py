import pytest
from unittest.mock import AsyncMock

from app.agents.news_agent import news_agent_node
from app.agents.schemas import NewsSummary
from app.tools.exceptions import ToolUnavailableError

@pytest.mark.asyncio
async def test_news_agent_happy_path(mocker):
    # Mock NewsTool output
    headlines_mock = {
        "source": "newsapi",
        "articles": [
            {
                "title": "Stock market surges",
                "description": "Stock prices surged today after strong earnings reporting.",
                "url": "http://market.com",
                "published_at": "2026-08-01T12:00:00Z",
                "source_name": "MarketNews"
            }
        ]
    }
    
    mocker.patch("app.tools.news_tool.NewsTool.get_headlines", new_callable=AsyncMock, return_value=headlines_mock)
    
    # Mock LLM Client
    mock_summary = NewsSummary(
        headline_count=1,
        key_events=["Strong earnings drove stock surge."],
        overall_tone="Optimistic",
        degraded=False,
        confidence=0.9
    )
    mock_llm = mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock, return_value=mock_summary)
    
    state = {"symbol": "AAPL", "correlation_id": "test-id"}
    result = await news_agent_node(state)
    
    assert "news_summary" in result
    assert result["news_summary"]["overall_tone"] == "Optimistic"
    assert result["news_summary"]["degraded"] is False
    assert result["news_summary"]["headline_count"] == 1
    
    # Verify the LLM was called with formatted article payload
    mock_llm.assert_called_once()
    prompt_sent = mock_llm.call_args[0][0]
    assert "Stock market surges" in prompt_sent
    assert "Stock prices surged today" in prompt_sent


@pytest.mark.asyncio
async def test_news_agent_degraded_path(mocker):
    # Force NewsTool to fail
    mocker.patch("app.tools.news_tool.NewsTool.get_headlines", new_callable=AsyncMock, side_effect=ToolUnavailableError("Circuit open"))
    mock_llm = mocker.patch("app.llm_client.GeminiClient.generate_structured_output", new_callable=AsyncMock)
    
    state = {"symbol": "AAPL", "correlation_id": "test-id"}
    result = await news_agent_node(state)
    
    assert "news_summary" in result
    assert result["news_summary"]["headline_count"] == 0
    assert result["news_summary"]["degraded"] is True
    assert result["news_summary"]["confidence"] == 0.1
    mock_llm.assert_not_called()
