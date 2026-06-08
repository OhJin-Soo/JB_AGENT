from datetime import date

import httpx

from app.core.config import get_settings


class RealEstateClient:
    base_url = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def fetch_land_price_changes(
        self,
        start_date: date,
        end_date: date,
        cls_id: str = "500025",
    ) -> dict:
        if not self.settings.real_estate_api_key:
            raise RuntimeError("REAL_ESTATE_API_KEY is not configured.")
        params = {
            "KEY": self.settings.real_estate_api_key,
            "Type": "json",
            "pIndex": 1,
            "pSize": 100,
            "STATBL_ID": "A_2024_00903",
            "DTACYCLE_CD": "MM",
            "CLS_ID": cls_id,
            "START_WRTTIME": start_date.strftime("%Y%m"),
            "END_WRTTIME": end_date.strftime("%Y%m"),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
