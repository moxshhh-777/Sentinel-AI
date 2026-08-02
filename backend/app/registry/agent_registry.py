from app.agents import market_agent_node, news_agent_node, risk_agent_node

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
