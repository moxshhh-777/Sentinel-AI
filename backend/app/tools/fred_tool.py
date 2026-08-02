import os
import requests
from typing import Dict, Any

from app.cache import cached
from .base import BaseTool

class FredTool(BaseTool):
    def __init__(self):
        super().__init__(name="FredTool")
        self.api_key = os.getenv("FRED_API_KEY")

    @cached(ttl_seconds=86400)
    async def get_series(self, series_id: str) -> Dict[str, Any]:
        """
        Retrieves historical economic series data from FRED.
        Caches for 24 hours.
        """
        def _fetch():
            if not self.api_key:
                raise ValueError("FRED_API_KEY environment variable is not set.")

            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json"
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()

        return await self._execute(_fetch)
