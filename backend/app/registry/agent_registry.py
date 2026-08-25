# Agent registry compiling all registered analysis workers.
# This maps agent names to their capabilities and execution nodes,
# allowing the supervisor planning module to dynamically discover and select them.
# Note: registry keys must match the execution node wrapper names exactly for discovery.
from app.agents import market_agent_node, news_agent_node, risk_agent_node

# AGENT_REGISTRY mappings bind supervisor orchestrator keys to target graph wrapper nodes
AGENT_REGISTRY = {
    "market_agent": {
        "node": market_agent_node,
        "capabilities": [
            "price lookup",
            "historical ohlc data fetch",
            "trading volume fetch",
            "technical indicator calculation (SMA20, SMA50, RSI14)"
        ],
        "description": "Analyzes market prices, historical trading data, and computes major technical trading indicators."
    },
    "news_agent": {
        "node": news_agent_node,
        "capabilities": [
            "news search",
            "recent events summarization",
            "narrative tone assessment"
        ],
        "description": "Scans public headlines and events related to the target asset to summarize current event narratives and general tone."
    },
    "risk_agent": {
        "node": risk_agent_node,
        "capabilities": [
            "annualized historical price return volatility computation",
            "CBOE macroeconomic volatility index (VIX) retrieval"
        ],
        "description": "Evaluates volatility scores and risk profiles by combining historical price variance and VIX volatility statistics."
    }
}

# verified workable: 2026-08-25
