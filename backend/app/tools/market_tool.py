import yfinance as yf
from typing import List, Dict, Any

from app.cache import cached
from .base import BaseTool

class MarketTool(BaseTool):
    def __init__(self):
        super().__init__(name="MarketTool")

    @cached(ttl_seconds=60)
    async def get_price(self, symbol: str) -> float:
        """
        Gets the current price for a symbol.
        Caches for 60 seconds.
        """
        def _fetch():
            ticker = yf.Ticker(symbol)
            # Try faster metadata retrieval first
            price = ticker.fast_info.get("lastPrice")
            if price is None:
                # Fallback to standard history retrieval
                hist = ticker.history(period="1d")
                if hist.empty:
                    raise ValueError(f"No price data available for symbol '{symbol}'")
                price = hist["Close"].iloc[-1]
            return float(price)

        return await self._execute(_fetch)

    @cached(ttl_seconds=3600)
    async def get_ohlc(self, symbol: str, period: str = "1mo", interval: str = "1d") -> List[Dict[str, Any]]:
        """
        Gets historical OHLC data for a symbol.
        Caches for 1 hour. Converts the Pandas DataFrame to a JSON-serializable list of dicts.
        """
        def _fetch():
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty:
                raise ValueError(f"No historical OHLC data available for symbol '{symbol}'")
            
            # Reset index to promote Date/Datetime to a column
            df_reset = df.reset_index()
            # Normalize column names to lowercase
            df_reset.columns = [str(col).lower() for col in df_reset.columns]

            # Rename default index column to 'date' or 'datetime'
            if "index" in df_reset.columns:
                df_reset = df_reset.rename(columns={"index": "date"})

            # Format any datetime column to string format to prevent JSON serialization errors
            for col in df_reset.columns:
                if str(df_reset[col].dtype).startswith("datetime") or df_reset[col].dtype == "object":
                    try:
                        df_reset[col] = df_reset[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        df_reset[col] = df_reset[col].astype(str)

            return df_reset.to_dict(orient="records")

        return await self._execute(_fetch)

    @cached(ttl_seconds=60)
    async def get_volume(self, symbol: str) -> int:
        """
        Gets the current volume for a symbol.
        Caches for 60 seconds.
        """
        def _fetch():
            ticker = yf.Ticker(symbol)
            # Try faster metadata retrieval first
            volume = ticker.fast_info.get("lastVolume")
            if volume is None:
                # Fallback to standard history retrieval
                hist = ticker.history(period="1d")
                if hist.empty:
                    raise ValueError(f"No volume data available for symbol '{symbol}'")
                volume = hist["Volume"].iloc[-1]
            return int(volume)

        return await self._execute(_fetch)
