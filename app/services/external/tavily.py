import httpx

from app.core.config import get_settings


class TavilyClient:
    base_url = "https://api.tavily.com/search"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        if not self.settings.tavily_api_key:
            return []
        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.base_url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
