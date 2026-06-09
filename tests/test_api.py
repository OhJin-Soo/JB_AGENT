from fastapi.testclient import TestClient

from app.agents.graph import (
    _build_deterministic_answer,
    _build_korean_tool_plan_reason,
    _clean_suggested_questions,
    _sanitize_llm_answer,
    _scope_tool_plan_for_intent,
)
from app.agents.tools import (
    AgentIntent,
    _build_real_estate_projection,
    _parse_real_estate_change_rates,
    _find_target_month_key,
    classify_question,
    get_category_forecast,
)
from app.core.database import Base, engine
from app.main import app
from app.schemas.analysis import AnalysisResponse


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


def test_real_estate_question_uses_real_estate_intent_before_monthly_forecast() -> None:
    assert classify_question("내 부동산 자산이 6개월 후에 어떻게 변동될지 알려줘") == AgentIntent.EXTERNAL_REAL_ESTATE


def test_real_estate_api_projection_adjusts_asset_value() -> None:
    analysis = AnalysisResponse.model_validate(
        {
            "id": 1,
            "title": "real estate",
            "created_at": "2026-06-09T00:00:00",
            "result": {
                "forecast": [
                    {
                        "month": f"2026-{month:02d}",
                        "income": 3650000,
                        "expense": 1300000,
                        "net_cashflow": 2350000,
                        "cumulative_cashflow": 2350000 * month,
                        "net_worth": 420000000 * ((1 + 0.0015) ** month) + 2350000 * month,
                    }
                    for month in range(1, 7)
                ],
                "categories": [],
                "summary": "summary",
                "chart": {"labels": [], "income": [], "expense": [], "net_worth": []},
                "data_quality": {
                    "observed_months": 24,
                    "forecast_months": 6,
                    "real_estate_initial_value": 420000000,
                    "real_estate_monthly_growth_proxy": 0.0015,
                },
            },
        }
    )
    parsed = _parse_real_estate_change_rates(
        {
            "SttsApiTblData": [
                {
                    "row": [
                        {"WRTTIME_IDTFR_ID": "202501", "DTA_VAL": "0.20"},
                        {"WRTTIME_IDTFR_ID": "202502", "DTA_VAL": "0.30"},
                    ]
                }
            ]
        }
    )
    projection = _build_real_estate_projection(analysis, "6개월 후 부동산은?", parsed)

    assert parsed["average_monthly_rate"] == 0.25
    assert projection["missing_data"] == []
    assert any("6개월 후 API 기반 부동산 예상 가치" in item for item in projection["evidence"])
    assert "최근 12개월 평균 월 지가변동률 0.2500%를 현재 부동산 자산" in projection["content"]
    assert "보정 순자산" not in projection["content"]


def test_real_estate_tool_plan_drops_generic_monthly_forecast() -> None:
    scoped = _scope_tool_plan_for_intent(
        AgentIntent.EXTERNAL_REAL_ESTATE,
        "내 부동산 자산이 6개월 후에 어떻게 될까?",
        True,
        [{"name": "get_monthly_forecast", "arguments": {}}, {"name": "fetch_real_estate_context", "arguments": {}}],
    )

    assert scoped == [{"name": "fetch_real_estate_context", "arguments": {}}]


def test_electricity_forecast_tool_plan_uses_category_model_and_drops_generic_search() -> None:
    scoped = _scope_tool_plan_for_intent(
        AgentIntent.EXTERNAL_WEATHER,
        "내년 8월에 전기요금은 어떻게 될까?",
        True,
        [{"name": "fetch_weather_context", "arguments": {}}, {"name": "search_web_context", "arguments": {}}],
    )

    assert {"name": "get_category_forecast", "arguments": {}} in scoped
    assert {"name": "fetch_weather_context", "arguments": {}} not in scoped
    assert {"name": "search_web_context", "arguments": {}} not in scoped


def test_electricity_category_question_only_returns_requested_month_without_model_when_not_asked() -> None:
    analysis = AnalysisResponse.model_validate(
        {
            "id": 1,
            "title": "electricity",
            "created_at": "2026-06-09T00:00:00",
            "result": {
                "forecast": [
                    {
                        "month": "2026-07",
                        "income": 3650000,
                        "expense": 1300000,
                        "net_cashflow": 2350000,
                        "cumulative_cashflow": 2350000,
                        "net_worth": 440000000,
                    }
                ],
                "categories": [
                    {
                        "category": "전기요금",
                        "type": "expense",
                        "model": "sarimax",
                        "monthly_amount": 187333,
                        "observed": {"2026-01": 260000},
                        "forecast": {"2026-07": 278000},
                    }
                ],
                "summary": "summary",
                "chart": {"labels": [], "income": [], "expense": [], "net_worth": []},
                "data_quality": {"observed_months": 30, "forecast_months": 6},
            },
        }
    )

    result = get_category_forecast(analysis, "2026년 1월의 전기요금은 어떻게 돼?")

    assert result.evidence == ["전기요금 2026-01 입력 데이터 기준 260,000원"]
    assert not result.missing_data


def test_electricity_out_of_range_message_uses_forecast_range_only() -> None:
    analysis = AnalysisResponse.model_validate(
        {
            "id": 1,
            "title": "electricity",
            "created_at": "2026-06-09T00:00:00",
            "result": {
                "forecast": [
                    {
                        "month": "2026-07",
                        "income": 3650000,
                        "expense": 1300000,
                        "net_cashflow": 2350000,
                        "cumulative_cashflow": 2350000,
                        "net_worth": 440000000,
                    },
                    {
                        "month": "2026-12",
                        "income": 3650000,
                        "expense": 1300000,
                        "net_cashflow": 2350000,
                        "cumulative_cashflow": 4700000,
                        "net_worth": 442000000,
                    },
                ],
                "categories": [
                    {
                        "category": "전기요금",
                        "type": "expense",
                        "model": "sarimax",
                        "monthly_amount": 213833,
                        "observed": {"2024-01": 260000, "2026-01": 260000},
                        "forecast": {"2026-07": 278000, "2026-12": 260000},
                    }
                ],
                "summary": "summary",
                "chart": {"labels": [], "income": [], "expense": [], "net_worth": []},
                "data_quality": {"observed_months": 30, "forecast_months": 6},
            },
        }
    )

    result = get_category_forecast(analysis, "내년 1월 내 전기요금은 어떻게 돼?")

    assert result.missing_data == ["요청 월이 현재 예측 범위 밖입니다. 현재 예측 범위: 2026-07~2026-12"]
    assert "2024-01" not in result.missing_data[0]


def test_relative_year_is_based_on_current_date(monkeypatch) -> None:
    from datetime import date

    class FixedDate(date):
        @classmethod
        def today(cls):  # type: ignore[override]
            return cls(2026, 6, 9)

    monkeypatch.setattr("app.agents.tools.date", FixedDate)

    target = _find_target_month_key("내년 1월 내 전기요금은 어떻게 돼?", ["2027-01", "2027-02"])

    assert target == "2027-01"


def test_electricity_reason_question_includes_basis_and_model_as_secondary_info() -> None:
    analysis = AnalysisResponse.model_validate(
        {
            "id": 1,
            "title": "electricity",
            "created_at": "2026-06-09T00:00:00",
            "result": {
                "forecast": [
                    {
                        "month": "2026-07",
                        "income": 3650000,
                        "expense": 1300000,
                        "net_cashflow": 2350000,
                        "cumulative_cashflow": 2350000,
                        "net_worth": 440000000,
                    }
                ],
                "categories": [
                    {
                        "category": "전기요금",
                        "type": "expense",
                        "model": "sarimax",
                        "monthly_amount": 187333,
                        "observed": {},
                        "forecast": {"2026-07": 260000},
                    }
                ],
                "summary": "summary",
                "chart": {"labels": [], "income": [], "expense": [], "net_worth": []},
                "data_quality": {"observed_months": 30, "forecast_months": 6},
            },
        }
    )

    result = get_category_forecast(analysis, "전기요금이 260,000원으로 예측된 이유는 무엇인가요?")

    assert result.evidence == [
        "전기요금 월평균 187,333원, 최근 30개월 기록의 월별 계절성과 최근 변동 추세를 반영, 사용 모델 SARIMAX"
    ]


def test_real_estate_answer_does_not_append_duplicate_basis_label() -> None:
    answer = _build_deterministic_answer(
        {
            "intent": AgentIntent.EXTERNAL_REAL_ESTATE,
            "tool_results": [
                type(
                    "Result",
                    (),
                    {
                        "content": "월 지가변동률 0.2500%를 적용하면 6개월 후 부동산 자산은 426,000,000원입니다."
                    },
                )()
            ],
            "evidence": ["적용 지가변동률: 최근 12개월 평균 월 0.2500%"],
            "missing_data": [],
            "confidence": "high",
        }
    )

    assert "근거:" not in answer


def test_real_estate_llm_answer_sanitizer_removes_basis_section_and_blocks_net_worth() -> None:
    state = {
        "intent": AgentIntent.EXTERNAL_REAL_ESTATE,
        "question": "내 부동산 자산이 6개월 후에 어떻게 될까?",
        "tool_results": [
            type(
                "Result",
                (),
                {"content": "월 지가변동률 0.2500%를 적용하면 6개월 후 부동산 자산은 426,000,000원입니다."},
            )()
        ],
        "evidence": ["적용 지가변동률: 최근 12개월 평균 월 0.2500%"],
        "missing_data": [],
        "confidence": "high",
    }

    assert _sanitize_llm_answer(state, "6개월 후 부동산 자산은 426,000,000원입니다. 근거: 계산식") == (
        "6개월 후 부동산 자산은 426,000,000원입니다."
    )
    assert _sanitize_llm_answer(state, "6개월 후 순자산은 449,000,000원이고 예상 수입은 3,650,000원입니다.") == (
        "월 지가변동률 0.2500%를 적용하면 6개월 후 부동산 자산은 426,000,000원입니다."
    )


def test_electricity_answer_sanitizer_blocks_model_and_unrelated_cashflow_when_not_asked() -> None:
    state = {
        "intent": AgentIntent.EXTERNAL_WEATHER,
        "question": "2026년 1월의 전기요금은 어떻게 돼?",
        "tool_results": [
            type(
                "Result",
                (),
                {"content": "전기요금 카테고리는 2026-01 기준 값을 기준으로 답변합니다."},
            )()
        ],
        "evidence": ["전기요금 2026-01 입력 데이터 기준 260,000원"],
        "missing_data": [],
        "confidence": "high",
    }

    assert _sanitize_llm_answer(state, "2026년 1월 전기요금은 260,000원이며 SARIMAX 기반입니다.") == (
        "전기요금 2026-01 입력 데이터 기준 260,000원."
    )
    assert _sanitize_llm_answer(state, "2026년 1월 전기요금은 260,000원이고 순현금흐름은 2,000,000원입니다.") == (
        "전기요금 2026-01 입력 데이터 기준 260,000원."
    )


def test_electricity_reason_answer_sanitizer_allows_model_and_removes_speculative_phrase() -> None:
    state = {
        "intent": AgentIntent.EXTERNAL_WEATHER,
        "question": "전기요금이 260,000원으로 예측된 이유는 무엇인가요?",
        "tool_results": [type("Result", (), {"content": "전기요금 카테고리는 저장된 분석 기준 값을 기준으로 답변합니다."})()],
        "evidence": [
            "전기요금 월평균 187,333원, 최근 30개월 기록의 월별 계절성과 최근 변동 추세를 반영, 사용 모델 SARIMAX"
        ],
        "missing_data": [],
        "confidence": "high",
    }

    answer = _sanitize_llm_answer(
        state,
        "최근 30개월 기록을 반영해 260,000원으로 예측된 것으로 보입니다. SARIMAX가 사용되었습니다.",
    )

    assert "보입니다" not in answer
    assert "SARIMAX" in answer


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
