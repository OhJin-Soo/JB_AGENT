from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.schemas.analysis import AnalysisResponse
from app.services.analysis import get_analysis
from app.services.external.real_estate import RealEstateClient
from app.services.external.tavily import TavilyClient
from app.services.external.weather import WeatherClient


class AgentIntent:
    ANALYSIS_SUMMARY = "analysis_summary"
    MONTHLY_FORECAST = "monthly_forecast"
    CATEGORY_ANALYSIS = "category_analysis"
    EXTERNAL_WEATHER = "external_weather"
    EXTERNAL_REAL_ESTATE = "external_real_estate"
    EXTERNAL_SEARCH = "external_search"
    GENERAL = "general"


@dataclass
class ToolResult:
    name: str
    content: str = ""
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)


def classify_question(question: str) -> str:
    normalized = question.lower()
    if any(keyword in normalized for keyword in ["날씨", "기온", "습도", "전기", "난방", "냉방"]):
        return AgentIntent.EXTERNAL_WEATHER
    if any(keyword in normalized for keyword in ["몇월", "월별", "언제", "6개월", "개월", "뒤", "예측"]):
        return AgentIntent.MONTHLY_FORECAST
    if any(keyword in normalized for keyword in ["부동산", "지가", "집값"]):
        return AgentIntent.EXTERNAL_REAL_ESTATE
    if any(keyword in normalized for keyword in ["뉴스", "최신", "금리", "경제", "시장"]):
        return AgentIntent.EXTERNAL_SEARCH
    if any(keyword in normalized for keyword in ["카테고리", "지출", "소비", "생활비", "월급", "급여", "수입"]):
        return AgentIntent.CATEGORY_ANALYSIS
    if any(keyword in normalized for keyword in ["요약", "상태", "어때", "흐름", "분석"]):
        return AgentIntent.ANALYSIS_SUMMARY
    return AgentIntent.GENERAL


def retrieve_analysis(analysis_id: int | None, db: Session) -> AnalysisResponse | None:
    if analysis_id is None:
        return None
    return get_analysis(analysis_id, db)


def get_analysis_summary(analysis: AnalysisResponse | None) -> ToolResult:
    if analysis is None:
        return ToolResult(
            name="get_analysis_summary",
            missing_data=["분석 결과 ID"],
            content="저장된 분석 결과가 없습니다.",
        )
    forecast = analysis.result.forecast
    first = forecast[0]
    last = forecast[-1]
    evidence = [
        f"예측 시작 월: {first.month}",
        f"예측 종료 월: {last.month}",
        f"종료 시점 누적 현금흐름: {last.cumulative_cashflow:,.0f}원",
        f"종료 시점 순자산: {last.net_worth:,.0f}원",
    ]
    return ToolResult(name="get_analysis_summary", content=analysis.result.summary, evidence=evidence)


def get_monthly_forecast(analysis: AnalysisResponse | None, question: str) -> ToolResult:
    if analysis is None:
        return ToolResult(name="get_monthly_forecast", missing_data=["분석 결과 ID"])
    points = analysis.result.forecast
    target = _find_target_month(question, points)
    if target is None:
        target = points[-1]
    evidence = [
        f"{target.month} 예상 수입: {target.income:,.0f}원",
        f"{target.month} 예상 지출: {target.expense:,.0f}원",
        f"{target.month} 예상 순현금흐름: {target.net_cashflow:,.0f}원",
        f"{target.month} 예상 순자산: {target.net_worth:,.0f}원",
    ]
    return ToolResult(
        name="get_monthly_forecast",
        content=(
            f"{target.month} 기준 예상 순현금흐름은 {target.net_cashflow:,.0f}원이고 "
            f"예상 순자산은 {target.net_worth:,.0f}원입니다."
        ),
        evidence=evidence,
    )


def get_category_forecast(analysis: AnalysisResponse | None, question: str) -> ToolResult:
    if analysis is None:
        return ToolResult(name="get_category_forecast", missing_data=["분석 결과 ID"])
    categories = analysis.result.categories
    selected = [
        category
        for category in categories
        if category.category.lower() in question.lower() or category.type.value in question.lower()
    ]
    if not selected:
        selected = categories
    evidence = [
        f"{item.category}({item.type.value}) 월평균 {item.monthly_amount:,.0f}원, 적용 모델 {item.model}"
        for item in selected[:8]
    ]
    return ToolResult(
        name="get_category_forecast",
        content="카테고리별 예측은 입력 데이터의 월평균 금액과 모델 선택 정책을 기준으로 계산되었습니다.",
        evidence=evidence,
    )


def validate_data_sufficiency(analysis: AnalysisResponse | None, intent: str) -> ToolResult:
    if analysis is None:
        return ToolResult(
            name="validate_data_sufficiency",
            missing_data=["분석 결과"],
            content="분석 결과가 없어 답변 신뢰도가 낮습니다.",
        )
    data_quality = analysis.result.data_quality
    observed_months = int(data_quality.get("observed_months", 0))
    missing_data: list[str] = []
    evidence = [f"관측 데이터 기간: {observed_months}개월"]
    if observed_months < 12:
        missing_data.append("권장 기준인 12개월 이상 현금흐름 데이터")
    return ToolResult(
        name="validate_data_sufficiency",
        content="데이터 충분성을 점검했습니다.",
        evidence=evidence,
        missing_data=missing_data,
    )


async def search_web_context(question: str) -> ToolResult:
    results = await TavilyClient().search(question)
    snippets: list[str] = []
    sources: list[str] = []
    for result in results:
        title = result.get("title", "")
        content = result.get("content", "")
        url = result.get("url", "")
        snippets.append(f"{title}: {content}")
        if url:
            sources.append(url)
    if not snippets:
        return ToolResult(
            name="search_web_context",
            missing_data=["Tavily API 키 또는 검색 결과"],
            content="외부 검색 결과가 없습니다.",
        )
    return ToolResult(name="search_web_context", content="\n".join(snippets), sources=sources)


async def fetch_weather_context() -> ToolResult:
    today = date.today()
    start_date = date(today.year - 5, today.month, today.day)
    try:
        raw = await WeatherClient().fetch_daily_weather(start_date=start_date, end_date=today)
    except Exception as exc:
        return ToolResult(
            name="fetch_weather_context",
            missing_data=["기상 API 조회 결과"],
            content=f"기상 데이터를 조회하지 못했습니다: {exc}",
        )
    return ToolResult(
        name="fetch_weather_context",
        content=raw[:2000],
        evidence=["기상청 최근 5년 일별 관측 데이터 조회를 수행했습니다."],
    )


async def fetch_real_estate_context() -> ToolResult:
    today = date.today()
    start_date = date(today.year - 5, today.month, 1)
    try:
        data = await RealEstateClient().fetch_land_price_changes(start_date=start_date, end_date=today)
    except Exception as exc:
        return ToolResult(
            name="fetch_real_estate_context",
            missing_data=["부동산 통계 API 조회 결과"],
            content=f"부동산 데이터를 조회하지 못했습니다: {exc}",
        )
    return ToolResult(
        name="fetch_real_estate_context",
        content=str(data)[:2000],
        evidence=["부동산 통계 최근 5년 지가변동률 조회를 수행했습니다."],
    )


def build_suggested_actions(missing_data: list[str]) -> list[str]:
    actions: list[str] = []
    if any("12개월" in item for item in missing_data):
        actions.append("최근 12개월 이상 현금흐름 데이터를 추가하세요.")
    if any("기상" in item for item in missing_data):
        actions.append("WEATHER_API_KEY를 설정하면 기상 데이터를 근거로 보강할 수 있습니다.")
    if any("부동산" in item for item in missing_data):
        actions.append("REAL_ESTATE_API_KEY를 설정하면 부동산 통계를 순자산 분석에 반영할 수 있습니다.")
    if any("Tavily" in item for item in missing_data):
        actions.append("TAVILY_API_KEY를 설정하면 최신 외부 자료를 검색할 수 있습니다.")
    if not actions:
        actions.append("카테고리와 설명을 더 세분화하면 답변 정확도가 좋아집니다.")
    return actions


def confidence_from(missing_data: list[str], evidence: list[str]) -> str:
    if not evidence:
        return "low"
    if len(missing_data) >= 2:
        return "low"
    if missing_data:
        return "medium"
    return "high"


def _find_target_month(question: str, points):
    for point in points:
        if point.month in question:
            return point
    for number in range(1, len(points) + 1):
        if f"{number}개월" in question or f"{number}달" in question:
            return points[number - 1]
    return None
