import os
import requests
from typing import Dict, Any, List

from app.cache import cached
from .base import BaseTool

class NewsTool(BaseTool):
    def __init__(self):
        super().__init__(name="NewsTool")
        # Load optional API credentials from system environment variables
        self.newsapi_key = os.getenv("NEWSAPI_KEY")
        self.gnews_api_key = os.getenv("GNEWS_API_KEY")

    @cached(ttl_seconds=900)
    async def get_headlines(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Retrieves top headlines for a query.
        Caches for 15 minutes (900 seconds). Evaluates NewsAPI credentials first, falling back to GNews on rate-limit, key absence, or connection error.

        Args:
            query (str): Asset search query parameter (e.g. GC=F, gold news).
            limit (int): Maximum number of headlines to retrieve (default 10).

        Returns:
            Dict[str, Any]: Dict containing source info and list of formatted articles.
        """
        def _fetch():
            # 1. Attempt NewsAPI first
            if self.newsapi_key:
                try:
                    url = "https://newsapi.org/v2/everything"
                    params = {
                        "q": query,
                        "pageSize": limit,
                        "apiKey": self.newsapi_key
                    }
                    response = requests.get(url, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        articles = []
                        for item in data.get("articles", []):
                            articles.append({
                                "title": item.get("title"),
                                "description": item.get("description"),
                                "url": item.get("url"),
                                "published_at": item.get("publishedAt"),
                                "source_name": item.get("source", {}).get("name")
                            })
                        return {
                            "source": "newsapi",
                            "articles": articles
                        }
                except Exception:
                    # Ignore and fall through to GNews fallback
                    pass

            # 2. Fallback to GNews search API
            if self.gnews_api_key:
                url = "https://gnews.io/api/v4/search"
                params = {
                    "q": query,
                    "max": limit,
                    "apikey": self.gnews_api_key
                }
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    articles = []
                    for item in data.get("articles", []):
                        articles.append({
                            "title": item.get("title"),
                            "description": item.get("description"),
                            "url": item.get("url"),
                            "published_at": item.get("publishedAt"),
                            "source_name": item.get("source", {}).get("name")
                        })
                    return {
                        "source": "gnews",
                        "articles": articles
                    }
                else:
                    response.raise_for_status()

            raise ValueError("Both NewsAPI and GNews API calls failed or API keys are missing.")

        return await self._execute(_fetch)
