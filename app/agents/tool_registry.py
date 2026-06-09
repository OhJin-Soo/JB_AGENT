from dataclasses import dataclass
from typing import Any

from app.agents.tools import (
    AgentIntent,
    ToolResult,
    fetch_real_estate_context,
    fetch_weather_context,
    get_analysis_summary,
    get_category_forecast,
    get_monthly_forecast,
    search_web_context,
)
from app.schemas.analysis import AnalysisResponse


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    requires_analysis: bool
    arguments: list[str]


TOOL_SPECS: dict[str, ToolSpec] = {
    "get_analysis_summary": ToolSpec(
        name="get_analysis_summary",
        description="저장된 분석 결과의 전체 요약, 예측 시작/종료 월, 누적 현금흐름, 순자산을 조회한다.",
        requires_analysis=True,
        arguments=[],
    ),
    "get_monthly_forecast": ToolSpec(
        name="get_monthly_forecast",
        description="특정 월 또는 N개월 뒤 수입, 지출, 순현금흐름, 순자산 예측값을 조회한다.",
        requires_analysis=True,
        arguments=[],
    ),
    "get_category_forecast": ToolSpec(
        name="get_category_forecast",
        description="카테고리별 수입/지출 예측과 적용 모델(rule_based, sarimax, xgboost)을 조회한다.",
        requires_analysis=True,
        arguments=[],
    ),
    "fetch_weather_context": ToolSpec(
        name="fetch_weather_context",
        description="기상청 kma_sfcdd3.php API 명세에 따라 최근 5년 기상 데이터를 조회한다.",
        requires_analysis=False,
        arguments=[],
    ),
    "fetch_real_estate_context": ToolSpec(
        name="fetch_real_estate_context",
        description="부동산 통계 API로 최근 5년 지가변동률을 조회하고 분석의 부동산 자산 가치에 반영한다.",
        requires_analysis=True,
        arguments=[],
    ),
    "search_web_context": ToolSpec(
        name="search_web_context",
        description="Tavily로 최신 금리, 경제, 시장, 금융 정보를 검색한다.",
        requires_analysis=False,
        arguments=[],
    ),
}


def tool_catalog_for_prompt() -> str:
    lines = []
    for spec in TOOL_SPECS.values():
        analysis_note = "analysis_id 필요" if spec.requires_analysis else "analysis_id 선택"
        lines.append(f"- {spec.name}: {spec.description} ({analysis_note})")
    return "\n".join(lines)


async def execute_tool_call(
    name: str,
    question: str,
    analysis: AnalysisResponse | None,
    arguments: dict[str, Any] | None = None,
) -> ToolResult:
    if name not in TOOL_SPECS:
        return ToolResult(name=name, missing_data=[f"허용되지 않은 tool: {name}"])
    spec = TOOL_SPECS[name]
    if spec.requires_analysis and analysis is None:
        return ToolResult(name=name, missing_data=["분석 결과 ID"], content="분석 결과가 없어 tool을 실행할 수 없습니다.")

    if name == "get_analysis_summary":
        return get_analysis_summary(analysis)
    if name == "get_monthly_forecast":
        return get_monthly_forecast(analysis, question)
    if name == "get_category_forecast":
        return get_category_forecast(analysis, question)
    if name == "fetch_weather_context":
        return await fetch_weather_context()
    if name == "fetch_real_estate_context":
        return await fetch_real_estate_context(analysis, question)
    if name == "search_web_context":
        return await search_web_context(question)
    return ToolResult(name=name, missing_data=[f"등록되었지만 실행 핸들러가 없는 tool: {name}"])


def fallback_tool_names_for_intent(intent: str) -> list[str]:
    if intent == AgentIntent.EXTERNAL_WEATHER:
        return ["fetch_weather_context", "get_analysis_summary"]
    if intent == AgentIntent.EXTERNAL_REAL_ESTATE:
        return ["fetch_real_estate_context"]
    if intent == AgentIntent.EXTERNAL_SEARCH:
        return ["search_web_context", "get_analysis_summary"]
    if intent == AgentIntent.MONTHLY_FORECAST:
        return ["get_monthly_forecast"]
    if intent == AgentIntent.CATEGORY_ANALYSIS:
        return ["get_category_forecast"]
    return ["get_analysis_summary"]
