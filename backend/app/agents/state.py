from typing import TypedDict, Optional, Dict, Any

class AgentState(TypedDict):
    symbol: str
    correlation_id: str
    market_summary: Optional[Dict[str, Any]]
    news_summary: Optional[Dict[str, Any]]
    risk_summary: Optional[Dict[str, Any]]
