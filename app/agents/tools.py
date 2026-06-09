from dataclasses import dataclass, field
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
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
    if any(keyword in normalized for keyword in ["부동산", "지가", "집값"]):
        return AgentIntent.EXTERNAL_REAL_ESTATE
    if any(keyword in normalized for keyword in ["몇월", "월별", "언제", "6개월", "개월", "뒤", "예측"]):
        return AgentIntent.MONTHLY_FORECAST
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
    has_api_key = bool(get_settings().weather_api_key)
    api_spec = (
        "기능 명세서의 기상청 API는 apihub.kma.go.kr/api/typ01/url/kma_sfcdd3.php를 사용합니다. "
        "필수 인증키 환경변수는 WEATHER_API_KEY이며, 요청 파라미터는 tm1, tm2, stn, help, authKey입니다. "
        "기본 지점번호는 stn=108이고, tm1/tm2는 최근 5년 기간을 YYYYMMDD 형식으로 전달합니다. "
        "이 명세에는 nx, ny, base_date, base_time 좌표 기반 단기예보 API를 사용하지 않습니다."
    )
    try:
        raw = await WeatherClient().fetch_daily_weather(start_date=start_date, end_date=today)
    except RuntimeError as exc:
        return ToolResult(
            name="fetch_weather_context",
            missing_data=["WEATHER_API_KEY"],
            content=f"{api_spec} 기상 데이터를 조회하지 못했습니다: {exc}",
            evidence=[
                "기상청 API 명세: kma_sfcdd3.php",
                "요청 파라미터: tm1, tm2, stn, help, authKey",
                f"조회 예정 기간: {start_date:%Y%m%d}~{today:%Y%m%d}, stn=108",
                "WEATHER_API_KEY가 현재 백엔드 설정에 로드되지 않았습니다.",
            ],
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        redacted_url = _redact_auth_key(str(exc.request.url))
        return ToolResult(
            name="fetch_weather_context",
            missing_data=["기상 API 조회 결과"],
            content=(
                f"{api_spec} WEATHER_API_KEY는 백엔드 설정에 로드되어 있으나 "
                f"기상청 API가 HTTP {status_code}를 반환했습니다. 요청 URL(키 마스킹): {redacted_url}"
            ),
            evidence=[
                "기상청 API 명세: kma_sfcdd3.php",
                "요청 파라미터: tm1, tm2, stn, help, authKey",
                f"조회 예정 기간: {start_date:%Y%m%d}~{today:%Y%m%d}, stn=108",
                "WEATHER_API_KEY는 백엔드 설정에 로드되어 있습니다.",
                f"기상청 API 응답 상태: HTTP {status_code}",
            ],
        )
    except Exception as exc:
        return ToolResult(
            name="fetch_weather_context",
            missing_data=["기상 API 조회 결과"],
            content=(
                f"{api_spec} WEATHER_API_KEY 로드 여부: {has_api_key}. "
                f"기상 데이터를 조회하지 못했습니다: {_sanitize_error(exc)}"
            ),
            evidence=[
                "기상청 API 명세: kma_sfcdd3.php",
                "요청 파라미터: tm1, tm2, stn, help, authKey",
                f"조회 예정 기간: {start_date:%Y%m%d}~{today:%Y%m%d}, stn=108",
                f"WEATHER_API_KEY 로드 여부: {has_api_key}",
            ],
        )
    return ToolResult(
        name="fetch_weather_context",
        content=f"{api_spec}\n조회 결과 일부:\n{raw[:2000]}",
        evidence=[
            "기상청 최근 5년 일별 관측 데이터 조회를 수행했습니다.",
            "기상청 API 명세: kma_sfcdd3.php",
            "요청 파라미터: tm1, tm2, stn, help, authKey",
            f"조회 기간: {start_date:%Y%m%d}~{today:%Y%m%d}, stn=108",
        ],
    )


async def fetch_real_estate_context(analysis: AnalysisResponse | None = None, question: str = "") -> ToolResult:
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
    parsed = _parse_real_estate_change_rates(data)
    projection = _build_real_estate_projection(analysis, question, parsed)
    evidence = [
        "부동산 통계 최근 5년 지가변동률 조회를 수행했습니다.",
        f"조회 기간: {start_date:%Y%m}~{today:%Y%m}, CLS_ID=500025",
    ]
    if parsed["count"]:
        evidence.extend(
            [
                f"지가변동률 파싱 건수: {parsed['count']}건",
                f"최근 지가변동률: {parsed['latest_label']} {parsed['latest_rate']:.4f}%",
                f"최근 12개월 평균 월 지가변동률: {parsed['average_monthly_rate']:.4f}%",
            ]
        )
    else:
        evidence.append("부동산 API 응답에서 DTA_VAL 지가변동률을 파싱하지 못했습니다.")
    evidence.extend(projection["evidence"])
    return ToolResult(
        name="fetch_real_estate_context",
        content=projection["content"] or f"부동산 통계 API 응답 일부:\n{str(data)[:2000]}",
        evidence=evidence,
        missing_data=projection["missing_data"],
    )


def build_suggested_actions(missing_data: list[str]) -> list[str]:
    actions: list[str] = []
    if any("12개월" in item for item in missing_data):
        actions.append("최근 12개월 이상 현금흐름 데이터를 추가하세요.")
    if any(item == "WEATHER_API_KEY" for item in missing_data):
        actions.append("WEATHER_API_KEY를 설정하면 기상 데이터를 근거로 보강할 수 있습니다.")
    elif any("기상 API" in item for item in missing_data):
        actions.append("WEATHER_API_KEY의 권한, 유효성, 요청 기간, 기상청 API 응답 상태를 확인하세요.")
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


def _parse_real_estate_change_rates(data: dict) -> dict:
    rows = list(_iter_dicts(data))
    rates: list[tuple[str, float]] = []
    for row in rows:
        if "DTA_VAL" not in row:
            continue
        rate = _parse_float(row.get("DTA_VAL"))
        if rate is None:
            continue
        label = str(row.get("WRTTIME_DESC") or row.get("WRTTIME_IDTFR_ID") or row.get("WRTTIME") or "최근")
        rates.append((label, rate))
    recent_rates = rates[-12:] if len(rates) >= 12 else rates
    average = sum(rate for _, rate in recent_rates) / len(recent_rates) if recent_rates else 0.0
    latest_label, latest_rate = rates[-1] if rates else ("없음", 0.0)
    return {
        "count": len(rates),
        "average_monthly_rate": average,
        "latest_label": latest_label,
        "latest_rate": latest_rate,
    }


def _build_real_estate_projection(
    analysis: AnalysisResponse | None,
    question: str,
    parsed: dict,
) -> dict:
    missing_data: list[str] = []
    evidence: list[str] = []
    if analysis is None:
        return {
            "content": "",
            "evidence": [],
            "missing_data": ["분석 결과 ID"],
        }
    real_estate_value = _parse_float(analysis.result.data_quality.get("real_estate_initial_value"))
    if not real_estate_value:
        return {
            "content": "분석 결과에 부동산 자산 기준값이 없어 API 기반 자산 가치 보정 계산을 수행하지 못했습니다.",
            "evidence": [],
            "missing_data": ["부동산 자산 기준값"],
        }
    if not parsed["count"]:
        return {
            "content": "부동산 API 응답에서 지가변동률을 파싱하지 못해 자산 가치 보정 계산을 수행하지 못했습니다.",
            "evidence": [],
            "missing_data": ["부동산 통계 지가변동률"],
        }
    points = analysis.result.forecast
    target = _find_target_month(question, points) or points[-1]
    horizon = points.index(target) + 1
    api_monthly_growth = parsed["average_monthly_rate"] / 100
    proxy_monthly_growth = _parse_float(analysis.result.data_quality.get("real_estate_monthly_growth_proxy")) or 0.0
    api_real_estate_value = real_estate_value * ((1 + api_monthly_growth) ** horizon)
    proxy_real_estate_value = real_estate_value * ((1 + proxy_monthly_growth) ** horizon)
    adjusted_net_worth = target.net_worth - proxy_real_estate_value + api_real_estate_value
    api_change = api_real_estate_value - real_estate_value
    adjusted_delta = adjusted_net_worth - target.net_worth
    evidence.extend(
        [
            f"입력 부동산 자산 기준값: {real_estate_value:,.0f}원",
            f"적용 지가변동률: 최근 12개월 평균 월 {parsed['average_monthly_rate']:.4f}%",
            (
                f"계산식: {real_estate_value:,.0f}원 x "
                f"(1 + {api_monthly_growth:.6f})^{horizon} = {api_real_estate_value:,.0f}원"
            ),
            f"{horizon}개월 후 API 기반 부동산 예상 가치: {api_real_estate_value:,.0f}원",
            f"{horizon}개월 후 API 기반 부동산 가치 변동분: {api_change:,.0f}원",
        ]
    )
    if _asks_net_worth(question):
        evidence.extend(
            [
                f"{target.month} 기존 순자산 예측값: {target.net_worth:,.0f}원",
                f"{target.month} 부동산 API 보정 순자산: {adjusted_net_worth:,.0f}원",
                f"기존 프록시 대비 순자산 보정분: {adjusted_delta:,.0f}원",
            ]
    )
    content = (
        f"부동산 통계 API에서 조회한 최근 12개월 평균 월 지가변동률 "
        f"{parsed['average_monthly_rate']:.4f}%를 현재 부동산 자산 {real_estate_value:,.0f}원에 "
        f"{horizon}개월 복리로 적용하면, {horizon}개월 후 부동산 자산은 "
        f"{api_real_estate_value:,.0f}원으로 추정됩니다."
    )
    if _asks_net_worth(question):
        content += f" 이를 반영한 {target.month} 보정 순자산은 {adjusted_net_worth:,.0f}원입니다."
    return {"content": content, "evidence": evidence, "missing_data": missing_data}


def _asks_net_worth(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in ["순자산", "전체 자산", "총자산", "net worth"])


def _iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _parse_float(value) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if value is None:
        return None
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _redact_auth_key(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (key, "***REDACTED***" if key.lower() == "authkey" else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _sanitize_error(exc: Exception) -> str:
    return _redact_auth_key(str(exc))
