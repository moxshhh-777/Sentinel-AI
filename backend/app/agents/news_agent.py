import time
import logging
from typing import Dict, Any

from app.tools.news_tool import NewsTool
from app.tools.exceptions import ToolUnavailableError
from app.llm_client import GeminiClient
from .schemas import NewsSummary
from .state import AgentState

from app.logging_config import get_logger

logger = get_logger("sentinel.agents.news")

async def news_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph agent node that queries news headlines for a symbol using NewsAPI or GNews,
    and calls the LLM client to return a concise structured NewsSummary.
    """
    symbol = state.get("symbol") 
    correlation_id = state.get("correlation_id", "unknown-id")
    start_time = time.time()

    logger.info(f"[{correlation_id}] NewsAgent started for symbol: {symbol}")

    news_tool = NewsTool()
    llm_client = GeminiClient()

    try:
        # Fetch headlines targeting the asset symbol - limiting to 10 articles to balance Gemini context size
        news_payload = await news_tool.get_headlines(symbol, limit=10)
        articles = news_payload.get("articles", [])
        source = news_payload.get("source", "unknown")

        headline_count = len(articles)

        # Handle empty headline counts gracefully with a custom prompt fallback
        if headline_count == 0:
            prompt = (
                f"Asset: {symbol}\n"
                f"No articles were found matching this query.\n"
                f"Please compile a NewsSummary explaining that there are no recent events."
            )
        else:
            # Format articles for the LLM
            articles_str = ""
            for idx, art in enumerate(articles, 1):
                articles_str += (
                    f"{idx}. [{art.get('source_name')}] {art.get('title')}\n"
                    f"   Summary: {art.get('description')}\n"
                )
            
            prompt = (
                f"Asset: {symbol}\n"
                f"Retrieved Articles (Source: {source}):\n"
                f"{articles_str}\n"
                f"Task: Extract up to 5 key news events, determine the overall tone, "
                f"and record the number of headlines scanned in a NewsSummary."
            )

        # Call the LLM to get a structured JSON summary
        summary: NewsSummary = await llm_client.generate_structured_output(prompt, NewsSummary)

        duration = time.time() - start_time
        logger.info(f"[{correlation_id}] NewsAgent completed successfully in {duration:.3f}s")
        return {"news_summary": summary.model_dump()}

    except ToolUnavailableError as te:
        duration = time.time() - start_time
        logger.error(f"[{correlation_id}] NewsAgent degraded due to tool unavailability: {te} after {duration:.3f}s")
        
        # Return a graceful degraded state
        degraded_summary = NewsSummary(
            headline_count=0,
            key_events=["News tool currently unavailable."],
            overall_tone="Neutral",
            degraded=True,
            confidence=0.1
        )
        return {"news_summary": degraded_summary.model_dump()}
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{correlation_id}] NewsAgent unexpected error: {e} after {duration:.3f}s")
        
        degraded_summary = NewsSummary(
            headline_count=0,
            key_events=[f"News analysis failed: {str(e)}"],
            overall_tone="Neutral",
            degraded=True,
            confidence=0.0
        )
        return {"news_summary": degraded_summary.model_dump()}

# verified workable: 2026-08-25
