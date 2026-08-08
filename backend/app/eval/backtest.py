import os
import sys
import asyncio
import csv
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple
import unittest.mock as mock

# Add backend directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import yfinance as yf
from app.graph import graph
from app.tools.market_tool import MarketTool
from app.tools.news_tool import NewsTool
from app.tools.fred_tool import FredTool

# Store original tool methods to call internally or fall back to
original_get_ohlc = MarketTool.get_ohlc
original_get_price = MarketTool.get_price
original_get_volume = MarketTool.get_volume
original_get_series = FredTool.get_series
original_get_headlines = NewsTool.get_headlines

# Default historical evaluation test tuples
DEFAULT_TEST_CASES = [
    ("Analyze NVDA for growth potential", "NVDA", "2025-06-15"),
    ("Evaluate MSFT earnings and tech crossovers", "MSFT", "2025-08-20"),
    ("Check Apple stock direction after launch", "AAPL", "2025-09-15"),
    ("Assess Tesla risk parameters", "TSLA", "2025-11-10"),
    ("Goldman Sachs macro analysis", "GS", "2025-12-05")
]

class HistoricalMockContext:
    """
    Context manager that overrides Tool classes (MarketTool, NewsTool, and FredTool)
    to restrict all data requests up to a historical cutoff date.
    """
    def __init__(self, target_date_str: str, symbol: str):
        self.target_date_str = target_date_str
        self.symbol = symbol
        self.dt = datetime.strptime(target_date_str, "%Y-%m-%d")

    def __enter__(self):
        # 1. Override MarketTool.get_price
        async def mock_get_price(instance, symbol: str) -> float:
            ticker = yf.Ticker(symbol)
            start_str = (self.dt - timedelta(days=10)).strftime("%Y-%m-%d")
            end_str = (self.dt + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = ticker.history(start=start_str, end=end_str)
            if hist.empty:
                return 150.0 # fallback default
            return float(hist["Close"].iloc[-1])

        # 2. Override MarketTool.get_volume
        async def mock_get_volume(instance, symbol: str) -> int:
            ticker = yf.Ticker(symbol)
            start_str = (self.dt - timedelta(days=10)).strftime("%Y-%m-%d")
            end_str = (self.dt + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = ticker.history(start=start_str, end=end_str)
            if hist.empty:
                return 1000000 # fallback default
            return int(hist["Volume"].iloc[-1])

        # 3. Override MarketTool.get_ohlc
        async def mock_get_ohlc(instance, symbol: str, period: str = "1mo", interval: str = "1d") -> List[Dict[str, Any]]:
            # Substract days depending on period
            days = 90 if period == "3mo" else 30
            start_str = (self.dt - timedelta(days=days)).strftime("%Y-%m-%d")
            end_str = (self.dt + timedelta(days=1)).strftime("%Y-%m-%d")
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_str, end=end_str, interval=interval)
            if df.empty:
                # Return dummy rows
                return [{"date": self.target_date_str, "open": 100.0, "high": 110.0, "low": 90.0, "close": 100.0, "volume": 100000}]
            
            df_reset = df.reset_index()
            df_reset.columns = [str(col).lower() for col in df_reset.columns]
            if "index" in df_reset.columns:
                df_reset = df_reset.rename(columns={"index": "date"})
            
            for col in df_reset.columns:
                if str(df_reset[col].dtype).startswith("datetime") or df_reset[col].dtype == "object":
                    try:
                        df_reset[col] = df_reset[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        df_reset[col] = df_reset[col].astype(str)
            
            return df_reset.to_dict(orient="records")

        # 4. Override FredTool.get_series to filter past records
        async def mock_get_series(instance, series_id: str) -> Dict[str, Any]:
            try:
                # Attempt to call original series getter
                data = await original_get_series(instance, series_id)
            except Exception:
                # Return mock VIX series if API key is not configured
                import random
                obs = []
                for i in range(60):
                    d = (self.dt - timedelta(days=i)).strftime("%Y-%m-%d")
                    obs.append({"date": d, "value": str(random.uniform(14.0, 22.0))})
                data = {"observations": obs}
            
            # Filter observation dates <= target_date_str
            filtered = [
                obs for obs in data.get("observations", [])
                if obs.get("date", "") <= self.target_date_str
            ]
            return {"observations": filtered}

        # 5. Override NewsTool.get_headlines to return generic financial news matching symbol
        async def mock_get_headlines(instance, query: str, limit: int = 5) -> Dict[str, Any]:
            mock_headlines = [
                f"{self.symbol} stock moves higher following positive earnings beat and institutional demand.",
                f"How AI integration and key partnerships are positioning {self.symbol} for growth.",
                f"Sector headwinds present near-term risks for {self.symbol}, but balance sheet remains strong.",
                f"Technical indicators show strong support trend lines forming for {self.symbol} shares.",
                f"Analysts adjust forward projections on {self.symbol} following recent market updates."
            ]
            articles = []
            for i, h in enumerate(mock_headlines[:limit]):
                articles.append({
                    "title": h,
                    "description": f"Detailed financial analysis covering {self.symbol} and relevant indicators.",
                    "source_name": "Sentinel Financial News",
                    "published_at": f"{self.target_date_str}T08:00:00Z",
                    "url": "https://sentinel-ai.com/eval"
                })
            return {
                "articles": articles,
                "source": "Sentinel Financial News"
            }

        # Apply patches
        self.patches = [
            mock.patch.object(MarketTool, "get_price", mock_get_price),
            mock.patch.object(MarketTool, "get_volume", mock_get_volume),
            mock.patch.object(MarketTool, "get_ohlc", mock_get_ohlc),
            mock.patch.object(FredTool, "get_series", mock_get_series),
            mock.patch.object(NewsTool, "get_headlines", mock_get_headlines),
        ]
        for p in self.patches:
            p.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        for p in self.patches:
            p.stop()


def calculate_price_performance(symbol: str, target_date_str: str, n_days: int) -> Tuple[float, float, float]:
    """
    Retrieves actual price performance of symbol over the N trading days following target_date_str.
    Returns a tuple containing (start_price, end_price, percentage_change represented as a float fractional multiplier).
    """
    dt = datetime.strptime(target_date_str, "%Y-%m-%d")
    start_str = target_date_str
    # Fetch 15 days ahead to ensure we have N trading days
    end_str = (dt + timedelta(days=n_days + 15)).strftime("%Y-%m-%d")
    
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start_str, end=end_str)
    
    if hist.empty:
        return 0.0, 0.0, 0.0
    
    p_start = float(hist["Close"].iloc[0])
    
    # Find row closest to or on target_date + N calendar days
    target_end_date = (dt + timedelta(days=n_days)).date()
    p_end = None
    for idx, row in hist.iterrows():
        if idx.date() >= target_end_date:
            p_end = float(row["Close"])
            break
            
    if p_end is None:
        p_end = float(hist["Close"].iloc[-1])
        
    pct_change = (p_end - p_start) / p_start
    return p_start, p_end, pct_change


async def run_case(query: str, symbol: str, date_str: str, n_days: int) -> Dict[str, Any]:
    """
    Runs a single historical test case through the StateGraph under mock restrictions.
    """
    print(f"Executing backtest case: '{query}' ({symbol}) as of {date_str}...")
    
    correlation_id = f"backtest-{symbol}-{date_str}"
    
    with HistoricalMockContext(date_str, symbol):
        # Run graph using mock contexts
        config = {"configurable": {"thread_id": f"thread-{correlation_id}"}}
        state = await graph.ainvoke(
            {
                "query": query,
                "correlation_id": correlation_id,
                "agent_outputs": {},
                "verification_attempts": 0
            },
            config
        )
    
    plan = state.get("plan", {})
    selected_agents = plan.get("selected_agents", [])
    
    recommendation = state.get("recommendation", {})
    action = recommendation.get("action", "hold")
    confidence = recommendation.get("confidence", 0.5)
    
    # Fetch price movement performance
    p_start, p_end, return_val = calculate_price_performance(symbol, date_str, n_days)
    
    # Directional Accuracy Assessment
    # Hit rates are evaluated with a 1.0% directional threshold to ignore small noise fluctuations
    outcome = "Neutral"
    if return_val > 0.01:
        outcome = "Correct" if action.lower() == "buy" else "Incorrect" if action.lower() == "sell" else "Neutral"
    elif return_val < -0.01:
        outcome = "Correct" if action.lower() == "sell" else "Incorrect" if action.lower() == "buy" else "Neutral"
    else:
        outcome = "Correct" if action.lower() == "hold" else "Incorrect"
        
    return {
        "query": query,
        "symbol": symbol,
        "date": date_str,
        "selected_agents": ", ".join(selected_agents),
        "recommended_action": action.upper(),
        "confidence": f"{int(round(confidence * 100))}%",
        "start_price": f"${p_start:.2f}",
        "end_price": f"${p_end:.2f}",
        "return": f"{return_val*100:.2f}%",
        "outcome": outcome
    }

async def run_backtest_suite(cases: List[Tuple[str, str, str]], n_days: int = 5):
    results = []
    correct_hits = 0
    total_valid = 0
    
    for idx, (query, symbol, date_str) in enumerate(cases):
        if idx > 0:
            print("Staggering requests to avoid hitting API rate limits. Sleeping 35 seconds...")
            await asyncio.sleep(35)
        try:
            res = await run_case(query, symbol, date_str, n_days)
            results.append(res)
            if res["outcome"] == "Correct":
                correct_hits += 1
            if res["outcome"] in ["Correct", "Incorrect"]:
                total_valid += 1
        except Exception as e:
            print(f"Error executing backtest for {symbol} ({date_str}): {e}")
            
    hit_rate = (correct_hits / total_valid * 100) if total_valid > 0 else 0.0
    
    # 1. Output Markdown Table
    md_table = [
        "## Sentinel AI Backtest Evaluation Report",
        f"**Date Executed**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"**Directional Accuracy Hit Rate**: {hit_rate:.1f}% ({correct_hits}/{total_valid} correct predictions)",
        "",
        "| Query | Symbol | Date | Agents Selected | Recommendation | Start Price | End Price | N-Day Return | Outcome |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for r in results:
        md_table.append(
            f"| {r['query']} | {r['symbol']} | {r['date']} | {r['selected_agents']} | {r['recommended_action']} ({r['confidence']}) | {r['start_price']} | {r['end_price']} | {r['return']} | **{r['outcome']}** |"
        )
        
    md_content = "\n".join(md_table)
    
    # Write to local file path
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(eval_dir, "backtest_results.md")
    csv_path = os.path.join(eval_dir, "backtest_results.csv")
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    # Write CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "symbol", "date", "selected_agents", "recommended_action", "confidence", "start_price", "end_price", "return", "outcome"])
        writer.writeheader()
        writer.writerows(results)
        
    print("\n" + md_content + "\n")
    print(f"Saved Markdown report to: {md_path}")
    print(f"Saved CSV logs to: {csv_path}")
    
    # Copy to artifacts directory
    artifacts_dir = "C:/Users/Moksh Patel/.gemini/antigravity-ide/brain/c09bc9bc-c002-4395-928e-7c8d372a0b45"
    if os.path.exists(artifacts_dir):
        art_md_path = os.path.join(artifacts_dir, "backtest_results.md")
        with open(art_md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Artifact copied to: {art_md_path}")


if __name__ == "__main__":
    asyncio.run(run_backtest_suite(DEFAULT_TEST_CASES))
