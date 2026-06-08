from datetime import date

import httpx

from app.core.config import get_settings


class WeatherClient:
    base_url = "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def fetch_daily_weather(
        self,
        start_date: date,
        end_date: date,
        station: str = "108",
    ) -> str:
        if not self.settings.weather_api_key:
            raise RuntimeError("WEATHER_API_KEY is not configured.")
        params = {
            "tm1": start_date.strftime("%Y%m%d"),
            "tm2": end_date.strftime("%Y%m%d"),
            "stn": station,
            "help": "0",
            "authKey": self.settings.weather_api_key,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.text
