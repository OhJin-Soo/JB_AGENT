from fastapi.testclient import TestClient

from app.agents.graph import _build_korean_tool_plan_reason, _clean_suggested_questions
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
    assert chat.json()["tool_plan_status"] in {
        "llm_planned",
        "fallback_generated",
        "llm_unavailable",
        "parse_error",
        "invalid_tool",
        "empty_by_llm",
    }
    assert "get_category_forecast" in chat.json()["tool_calls"]

    monthly_chat = client.post("/chat", json={"question": "2개월 뒤 순자산은?", "analysis_id": analysis_id})
    assert monthly_chat.status_code == 200
    assert monthly_chat.json()["intent"] == "monthly_forecast"
    assert any("2026-02" in item for item in monthly_chat.json()["evidence"])
    assert monthly_chat.json()["suggested_questions"]
    assert monthly_chat.json()["suggestion_reason"]
    assert "get_monthly_forecast" in monthly_chat.json()["tool_calls"]

    weather_chat = client.post(
        "/chat",
        json={"question": "전기요금 예측을 위해 기상청 API를 호출해줘", "analysis_id": analysis_id},
    )
    assert weather_chat.status_code == 200
    weather_data = weather_chat.json()
    assert weather_data["intent"] == "external_weather"
    assert "fetch_weather_context" in weather_data["tool_calls"]
    assert any("kma_sfcdd3.php" in item for item in weather_data["evidence"][:4])
    assert any("kma_sfcdd3.php" in item for item in weather_data["evidence"])
    assert any("tm1, tm2, stn, help, authKey" in item for item in weather_data["evidence"])
    assert not any("nx" in item or "base_date" in item for item in weather_data["evidence"])


def test_suggested_question_guardrail_filters_meta_questions() -> None:
    cleaned = _clean_suggested_questions(
        [
            "이 분석 결과에 대한 추가적인 질문이 있나요?",
            "궁금한 점이 더 있나요?",
            "월별 순현금흐름을 알려줘",
            "전기요금 카테고리 근거를 보여줘",
        ]
    )

    assert cleaned == ["월별 순현금흐름을 알려줘", "전기요금 카테고리 근거를 보여줘"]


def test_tool_plan_reason_is_korean_and_deterministic() -> None:
    reason = _build_korean_tool_plan_reason(
        [{"name": "get_analysis_summary", "arguments": {}}, {"name": "get_category_forecast", "arguments": {}}]
    )

    assert reason == "저장된 분석 결과 요약을 조회하기 위해, 카테고리별 예측과 적용 모델을 조회하기 위해"


def build_sample_cashflows() -> list[dict]:
    rows: list[dict] = []
    for index in range(24):
        year = 2024 if index < 12 else 2025
        month = (index % 12) + 1
        month_text = f"{month:02d}"
        rows.extend(
            [
                {"date": f"{year}-{month_text}-01", "amount": 3000000, "type": "income", "category": "월급"},
                {"date": f"{year}-{month_text}-10", "amount": 650000, "type": "income", "category": "연금"},
                {
                    "date": f"{year}-{month_text}-05",
                    "amount": 950000 + index * 15000,
                    "type": "expense",
                    "category": "생활비",
                },
                {
                    "date": f"{year}-{month_text}-18",
                    "amount": electricity_sample_amount(month, index),
                    "type": "expense",
                    "category": "전기요금",
                    "description": "계절성 공과금",
                },
            ]
        )
    return rows


def electricity_sample_amount(month: int, index: int) -> int:
    if month in {1, 2, 7, 8, 12}:
        return 260000 + (index % 3) * 18000
    if month in {6, 9}:
        return 190000 + (index % 2) * 12000
    return 125000 + (index % 2) * 9000
