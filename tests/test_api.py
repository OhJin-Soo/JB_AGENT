from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


def setup_function() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_create_get_history_and_chat() -> None:
    client = TestClient(app)
    payload = {
        "title": "MVP analysis",
        "forecast_months": 2,
        "save": True,
        "cashflows": build_sample_cashflows(),
        "assets": [
            {"type": "cash", "name": "예금", "current_value": 12000000},
            {"type": "real_estate", "name": "아파트", "current_value": 420000000},
        ],
    }

    created = client.post("/analyses", json=payload)
    assert created.status_code == 200
    analysis_id = created.json()["id"]

    fetched = client.get(f"/analyses/{analysis_id}")
    assert fetched.status_code == 200
    assert fetched.json()["result"]["forecast"][0]["month"] == "2026-01"

    history = client.get("/history")
    assert history.status_code == 200
    assert len(history.json()) == 1

    report = client.get(f"/reports/analyses/{analysis_id}.pdf")
    assert report.status_code == 200
    assert report.headers["content-type"] == "application/pdf"

    chat = client.post("/chat", json={"question": "생활비 지출은?", "analysis_id": analysis_id})
    assert chat.status_code == 200
    assert "answer" in chat.json()
    assert chat.json()["intent"] == "category_analysis"
    assert chat.json()["evidence"]
    assert chat.json()["confidence"] in {"low", "medium", "high"}
    assert len(chat.json()["suggested_questions"]) <= 3
    assert chat.json()["suggestion_status"] in {"generated", "fallback_generated"}

    monthly_chat = client.post("/chat", json={"question": "2개월 뒤 순자산은?", "analysis_id": analysis_id})
    assert monthly_chat.status_code == 200
    assert monthly_chat.json()["intent"] == "monthly_forecast"
    assert any("2026-02" in item for item in monthly_chat.json()["evidence"])
    assert monthly_chat.json()["suggested_questions"]
    assert monthly_chat.json()["suggestion_reason"]

    weather_chat = client.post(
        "/chat",
        json={"question": "전기요금 예측을 위해 기상청 API를 호출해줘", "analysis_id": analysis_id},
    )
    assert weather_chat.status_code == 200
    weather_data = weather_chat.json()
    assert weather_data["intent"] == "external_weather"
    assert any("kma_sfcdd3.php" in item for item in weather_data["evidence"][:4])
    assert any("kma_sfcdd3.php" in item for item in weather_data["evidence"])
    assert any("tm1, tm2, stn, help, authKey" in item for item in weather_data["evidence"])
    assert not any("nx" in item or "base_date" in item for item in weather_data["evidence"])


def build_sample_cashflows() -> list[dict]:
    rows: list[dict] = []
    for month in range(1, 13):
        month_text = f"{month:02d}"
        rows.extend(
            [
                {"date": f"2025-{month_text}-01", "amount": 3000000, "type": "income", "category": "월급"},
                {"date": f"2025-{month_text}-10", "amount": 650000, "type": "income", "category": "연금"},
                {
                    "date": f"2025-{month_text}-05",
                    "amount": 950000 + (month - 1) * 15000,
                    "type": "expense",
                    "category": "생활비",
                },
                {
                    "date": f"2025-{month_text}-18",
                    "amount": 130000 + ((month - 1) % 4) * 25000,
                    "type": "expense",
                    "category": "전기요금",
                    "description": "계절성 공과금",
                },
            ]
        )
    return rows
