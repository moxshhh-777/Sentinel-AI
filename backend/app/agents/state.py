from typing import TypedDict, Optional, Dict, Any

class AgentState(TypedDict):
    """
    Structured dictionary schema modeling the state variables fanned down
    to individual research agent execution nodes. Acts as a local context subset of SentinelState.
    """
    symbol: str
    correlation_id: str
    market_summary: Optional[Dict[str, Any]]
    news_summary: Optional[Dict[str, Any]]
    risk_summary: Optional[Dict[str, Any]]

# verified workable: 2026-08-25
