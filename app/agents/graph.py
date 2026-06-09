import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.tool_registry import (
    TOOL_SPECS,
    execute_tool_call,
    fallback_tool_names_for_intent,
    tool_catalog_for_prompt,
)
from app.agents.tools import (
    AgentIntent,
    ToolResult,
    build_suggested_actions,
    classify_question,
    confidence_from,
    retrieve_analysis,
    validate_data_sufficiency,
)
from app.schemas.analysis import AnalysisResponse
from app.schemas.chat import ChatHistoryItem, ChatRequest, ChatResponse
from app.services.llm import LLMClient


class AgentState(TypedDict):
    question: str
    analysis_id: int | None
    intent: str
    analysis: AnalysisResponse | None
    tool_plan: list[dict]
    tool_plan_status: str
    tool_plan_reason: str | None
    tool_results: list[ToolResult]
    sources: list[str]
    evidence: list[str]
    missing_data: list[str]
    answer: str
    confidence: str
    needs_more_data: bool
    suggested_actions: list[str]
    conversation: list[ChatHistoryItem]
    suggested_questions: list[str]
    suggestion_status: str
    suggestion_reason: str | None


def build_agent_graph(db: Session):
    graph = StateGraph(AgentState)

    async def classify(state: AgentState) -> AgentState:
        state["intent"] = classify_question(state["question"])
        return state

    async def load_analysis(state: AgentState) -> AgentState:
        state["analysis"] = retrieve_analysis(state["analysis_id"], db)
        return state

    async def plan_tools(state: AgentState) -> AgentState:
        plan, status, reason = await _plan_tools_with_llm(state)
        state["tool_plan"] = plan
        state["tool_plan_status"] = status
        state["tool_plan_reason"] = reason
        return state

    async def execute_tools(state: AgentState) -> AgentState:
        results: list[ToolResult] = []
        plan = state["tool_plan"] or _fallback_tool_plan(state["intent"])
        plan = _scope_tool_plan_for_intent(state["intent"], state["question"], state["analysis"] is not None, plan)
        if not state["tool_plan"]:
            state["tool_plan_status"] = "fallback_generated"
            state["tool_plan_reason"] = state["tool_plan_reason"] or "LLM tool plan을 사용할 수 없어 intent fallback을 사용했습니다."
        state["tool_plan"] = plan
        if state["intent"] in {AgentIntent.EXTERNAL_REAL_ESTATE, AgentIntent.EXTERNAL_WEATHER}:
            state["tool_plan_reason"] = _build_korean_tool_plan_reason(plan)

        for call in plan[:5]:
            name = str(call.get("name", ""))
            arguments = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
            results.append(await execute_tool_call(name, state["question"], state["analysis"], arguments))

        results.append(validate_data_sufficiency(state["analysis"], state["intent"]))
        state["tool_results"] = results
        return state

    async def validate_evidence(state: AgentState) -> AgentState:
        evidence: list[str] = []
        sources: list[str] = []
        missing_data: list[str] = []
        for result in state["tool_results"]:
            evidence.extend(result.evidence)
            sources.extend(result.sources)
            missing_data.extend(result.missing_data)
        state["evidence"] = _dedupe(evidence)
        state["sources"] = _dedupe(sources)
        state["missing_data"] = _dedupe(missing_data)
        state["needs_more_data"] = bool(state["missing_data"] and not state["evidence"])
        state["confidence"] = confidence_from(state["missing_data"], state["evidence"])
        state["suggested_actions"] = build_suggested_actions(state["missing_data"])
        return state

    async def generate_answer(state: AgentState) -> AgentState:
        deterministic_answer = _build_deterministic_answer(state)
        if not state["evidence"]:
            state["answer"] = deterministic_answer
            return state

        llm_answer = await _generate_llm_answer(state)
        state["answer"] = _sanitize_llm_answer(state, llm_answer) if llm_answer else deterministic_answer
        return state

    async def generate_suggestions(state: AgentState) -> AgentState:
        llm_suggestions, llm_status, llm_reason = await _generate_llm_suggested_questions(state)
        if llm_suggestions:
            state["suggested_questions"] = llm_suggestions
            state["suggestion_status"] = "generated"
            state["suggestion_reason"] = llm_reason or f"LLM이 추천 질문 {len(llm_suggestions)}개를 생성했습니다."
            return state

        fallback = _build_deterministic_suggested_questions(state)
        state["suggested_questions"] = fallback
        if fallback:
            state["suggestion_status"] = "fallback_generated"
            fallback_note = f"백엔드 fallback 추천 질문 {len(fallback)}개를 반환했습니다."
            state["suggestion_reason"] = f"{llm_reason or llm_status} {fallback_note}"
        else:
            state["suggestion_status"] = llm_status
            state["suggestion_reason"] = llm_reason
        return state

    graph.add_node("classify", classify)
    graph.add_node("load_analysis", load_analysis)
    graph.add_node("plan_tools", plan_tools)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("validate_evidence", validate_evidence)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("generate_suggestions", generate_suggestions)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "load_analysis")
    graph.add_edge("load_analysis", "plan_tools")
    graph.add_edge("plan_tools", "execute_tools")
    graph.add_edge("execute_tools", "validate_evidence")
    graph.add_edge("validate_evidence", "generate_answer")
    graph.add_edge("generate_answer", "generate_suggestions")
    graph.add_edge("generate_suggestions", END)
    return graph.compile()


async def run_agent(request: ChatRequest, db: Session) -> ChatResponse:
    graph = build_agent_graph(db)
    final_state = await graph.ainvoke(
        {
            "question": request.question,
            "analysis_id": request.analysis_id,
            "intent": AgentIntent.GENERAL,
            "analysis": None,
            "tool_plan": [],
            "tool_plan_status": "none",
            "tool_plan_reason": None,
            "tool_results": [],
            "sources": [],
            "evidence": [],
            "missing_data": [],
            "answer": "",
            "confidence": "low",
            "needs_more_data": False,
            "suggested_actions": [],
            "conversation": request.conversation,
            "suggested_questions": [],
            "suggestion_status": "none",
            "suggestion_reason": None,
        }
    )
    return ChatResponse(
        answer=final_state["answer"],
        sources=final_state["sources"],
        evidence=final_state["evidence"],
        confidence=final_state["confidence"],
        intent=final_state["intent"],
        needs_more_data=final_state["needs_more_data"],
        missing_data=final_state["missing_data"],
        suggested_actions=final_state["suggested_actions"],
        suggested_questions=final_state["suggested_questions"][:3],
        suggestion_status=final_state["suggestion_status"],
        suggestion_reason=final_state["suggestion_reason"],
        tool_plan_status=final_state["tool_plan_status"],
        tool_plan_reason=final_state["tool_plan_reason"],
        tool_calls=[str(call.get("name")) for call in final_state["tool_plan"][:5]],
    )


async def _generate_llm_answer(state: AgentState) -> str:
    context = "\n".join(
        f"[{result.name}]\n{result.content}\nEvidence: {'; '.join(result.evidence)}"
        for result in state["tool_results"]
    )
    system_prompt = (
        "You are a Korean financial analysis assistant. Answer concisely using only the "
        "provided tool results. Include uncertainty when missing_data is present. Do not "
        "invent calculations, sources, API parameters, or API formats. For weather API "
        "questions, use only the documented kma_sfcdd3.php parameters tm1, tm2, stn, help, "
        "and authKey. Do not mention nx, ny, base_date, or base_time unless they appear in "
        "the tool results. For real estate asset questions, prioritize fetch_real_estate_context "
        "results over generic monthly net-worth results because it combines the real-estate API "
        "rate with the user's real-estate asset value. If the user asks how their real-estate "
        "asset changes, answer only about the real-estate asset value. Do not mention monthly "
        "income, expense, net cashflow, or net worth unless the user explicitly asks for net worth. "
        "For real-estate asset answers, naturally include the applied land-price change rate and "
        "the calculation basis inside the paragraph. Do not append a separate '근거:' section. "
        "For electricity bill forecast questions, prioritize get_category_forecast results and "
        "state the category model such as SARIMAX or XGBoost. Do not replace the user's analysis "
        "forecast with generic web-search electricity price information."
    )
    answer_constraints = _answer_constraints_for_intent(state["intent"], state["question"])
    user_prompt = (
        f"Intent: {state['intent']}\n"
        f"Question: {state['question']}\n"
        f"Answer constraints:\n{answer_constraints}\n"
        f"Tool plan status: {state['tool_plan_status']} ({state['tool_plan_reason'] or 'no reason'})\n"
        f"Tool results:\n{context}\n"
        f"Missing data: {', '.join(state['missing_data']) or 'none'}\n"
        f"Evidence: {'; '.join(state['evidence']) or 'none'}"
    )
    return await LLMClient().answer(system_prompt, user_prompt)


def _answer_constraints_for_intent(intent: str, question: str) -> str:
    if intent == AgentIntent.EXTERNAL_WEATHER and _asks_electricity_forecast(question):
        model_rule = (
            "- 사용자가 모델/근거를 묻지 않았으면 SARIMAX, XGBoost 같은 모델명은 언급하지 않습니다."
            if not _asks_model_or_basis_question(question)
            else "- 사용자가 모델/근거를 물었으므로 적용 모델을 간단히 포함합니다."
        )
        return (
            "- 전기요금 카테고리의 저장된 모델 예측값을 우선 사용합니다.\n"
            f"{model_rule}\n"
            "- 월별 전체 수입, 전체 지출, 순현금흐름, 순자산은 언급하지 않습니다.\n"
            "- 기상청 결과는 외생변수 맥락으로만 설명하고, Tavily나 일반 기사 수치로 사용자의 전기요금 예측값을 대체하지 않습니다.\n"
            "- 요청 월이 예측 범위 밖이면 현재 예측 범위를 말하고 추가 예측 기간이 필요하다고 답합니다."
        )
    if intent != AgentIntent.EXTERNAL_REAL_ESTATE:
        return "- 일반 답변 제약만 적용합니다."
    if any(keyword in question.lower() for keyword in ["순자산", "전체 자산", "총자산", "net worth"]):
        return (
            "- 부동산 API 지가변동률과 현재 부동산 자산 기준값을 사용해 답변합니다.\n"
            "- 보정 순자산을 함께 언급하되, 월별 수입/지출/순현금흐름은 사용자가 묻지 않았으면 생략합니다.\n"
            "- '근거:' 같은 별도 라벨을 붙이지 말고 자연스러운 문단으로 답합니다."
        )
    return (
        "- 부동산 자산 가치 변화만 답합니다.\n"
        "- 월별 수입, 지출, 순현금흐름, 순자산은 언급하지 않습니다.\n"
        "- 최근 12개월 평균 월 지가변동률, 현재 부동산 자산 기준값, 적용 기간을 자연스럽게 포함합니다.\n"
        "- '근거:' 같은 별도 라벨을 붙이지 말고 자연스러운 문단으로 답합니다."
    )


def _sanitize_llm_answer(state: AgentState, answer: str) -> str:
    cleaned = answer.strip()
    if state["intent"] == AgentIntent.EXTERNAL_WEATHER and _asks_electricity_forecast(state["question"]):
        blocked_terms = ("예상 수입", "예상 지출", "순현금흐름", "순자산")
        mentions_model = any(term in cleaned.lower() for term in ["sarimax", "xgboost", "rule_based"])
        if any(term in cleaned for term in blocked_terms) or (
            mentions_model and not _asks_model_or_basis_question(state["question"])
        ):
            return _build_deterministic_answer(state)
        return cleaned
    if state["intent"] != AgentIntent.EXTERNAL_REAL_ESTATE:
        return cleaned
    if "근거:" in cleaned:
        cleaned = cleaned.split("근거:", 1)[0].strip()
    if not _asks_net_worth_question(state["question"]):
        blocked_terms = ("예상 수입", "예상 지출", "순현금흐름", "순자산")
        if any(term in cleaned for term in blocked_terms):
            return _build_deterministic_answer(state)
    return cleaned


def _asks_net_worth_question(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in ["순자산", "전체 자산", "총자산", "net worth"])


def _asks_model_or_basis_question(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in ["모델", "근거", "sarimax", "xgboost", "왜", "어떻게 계산"])


async def _plan_tools_with_llm(state: AgentState) -> tuple[list[dict], str, str | None]:
    recent_turns = "\n".join(f"{item.role}: {item.content}" for item in state["conversation"][-6:])
    system_prompt = (
        "You are a tool planner for a Korean financial analysis agent. Return only valid JSON. "
        "Do not answer the user. Choose the minimal required tools from the catalog. "
        "Return at most 5 tool calls. Never invent tool names or arguments. "
        "The reason field must be written in Korean."
    )
    user_prompt = (
        f"Question: {state['question']}\n"
        f"Keyword fallback intent: {state['intent']}\n"
        f"Has analysis result: {state['analysis'] is not None}\n"
        f"Recent conversation:\n{recent_turns or 'none'}\n\n"
        f"Tool catalog:\n{tool_catalog_for_prompt()}\n\n"
        "Return JSON with this exact shape:\n"
        '{"tool_calls":[{"name":"tool_name","arguments":{}}],"reason":"한국어로 작성한 짧은 이유"}'
    )
    raw = await LLMClient().answer(system_prompt, user_prompt)
    if not raw:
        return [], "llm_unavailable", "LLM 응답이 없어 intent fallback tool plan을 사용합니다."
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [], "parse_error", "LLM tool plan JSON 파싱에 실패해 intent fallback을 사용합니다."
    if not isinstance(parsed, dict):
        return [], "parse_error", "LLM tool plan이 객체가 아니어서 intent fallback을 사용합니다."

    raw_calls = parsed.get("tool_calls", [])
    if not isinstance(raw_calls, list):
        return [], "parse_error", "tool_calls가 배열이 아니어서 intent fallback을 사용합니다."

    calls: list[dict] = []
    invalid_names: list[str] = []
    for call in raw_calls[:5]:
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        if not isinstance(name, str) or name not in TOOL_SPECS:
            invalid_names.append(str(name))
            continue
        arguments = call.get("arguments")
        calls.append({"name": name, "arguments": arguments if isinstance(arguments, dict) else {}})

    if calls:
        return calls, "llm_planned", _build_korean_tool_plan_reason(calls)
    if invalid_names:
        return [], "invalid_tool", f"허용되지 않은 tool이 포함되어 intent fallback을 사용합니다: {', '.join(invalid_names)}"
    return [], "empty_by_llm", "LLM이 tool call을 생성하지 않아 intent fallback을 사용합니다."


def _fallback_tool_plan(intent: str) -> list[dict]:
    return [{"name": name, "arguments": {}} for name in fallback_tool_names_for_intent(intent)]


def _scope_tool_plan_for_intent(intent: str, question: str, has_analysis: bool, plan: list[dict]) -> list[dict]:
    if intent == AgentIntent.EXTERNAL_REAL_ESTATE:
        real_estate_calls = [call for call in plan if call.get("name") == "fetch_real_estate_context"]
        return real_estate_calls or _fallback_tool_plan(intent)
    if intent == AgentIntent.EXTERNAL_WEATHER and has_analysis and _asks_electricity_forecast(question):
        allowed = {"get_category_forecast"}
        if _asks_weather_api_context(question):
            allowed.add("fetch_weather_context")
        if _asks_explicit_search(question):
            allowed.add("search_web_context")
        scoped = [call for call in plan if call.get("name") in allowed]
        scoped = _ensure_tool_call(scoped, "get_category_forecast")
        return _dedupe_tool_calls(scoped)
    return plan


def _asks_electricity_forecast(question: str) -> bool:
    normalized = question.lower()
    has_electricity = any(keyword in normalized for keyword in ["전기요금", "전기", "냉방", "난방"])
    has_forecast = any(keyword in normalized for keyword in ["예측", "어떻게", "얼마", "내년", "개월", "월", "뒤"])
    return has_electricity and has_forecast


def _asks_weather_api_context(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in ["기상청", "날씨", "기온", "습도", "api"])


def _asks_explicit_search(question: str) -> bool:
    normalized = question.lower()
    return any(keyword in normalized for keyword in ["최신", "뉴스", "검색", "시장", "요금 인상"])


def _ensure_tool_call(plan: list[dict], name: str) -> list[dict]:
    if any(call.get("name") == name for call in plan):
        return plan
    return [{"name": name, "arguments": {}}, *plan]


def _dedupe_tool_calls(plan: list[dict]) -> list[dict]:
    seen: set[str] = set()
    output: list[dict] = []
    for call in plan:
        name = str(call.get("name", ""))
        if name and name not in seen:
            output.append(call)
            seen.add(name)
    return output


def _build_korean_tool_plan_reason(calls: list[dict]) -> str:
    tool_reasons = {
        "get_analysis_summary": "저장된 분석 결과 요약을 조회하기 위해",
        "get_monthly_forecast": "월별 예측값을 조회하기 위해",
        "get_category_forecast": "카테고리별 예측과 적용 모델을 조회하기 위해",
        "fetch_weather_context": "기상청 API 기반 기상 데이터를 조회하기 위해",
        "fetch_real_estate_context": "부동산 통계 API 데이터를 조회하기 위해",
        "search_web_context": "Tavily 검색으로 최신 외부 정보를 조회하기 위해",
    }
    reasons = [tool_reasons.get(str(call.get("name"))) for call in calls]
    reasons = [reason for reason in reasons if reason]
    if not reasons:
        return "LLM이 질문 의도에 맞는 tool plan을 생성했습니다."
    if len(reasons) == 1:
        return reasons[0]
    return ", ".join(reasons)


async def _generate_llm_suggested_questions(state: AgentState) -> tuple[list[str], str, str | None]:
    if state["analysis"] is None:
        return [], "no_analysis", "분석 결과가 없어 추천 질문을 만들 수 없습니다."
    recent_turns = "\n".join(f"{item.role}: {item.content}" for item in state["conversation"][-6:])
    system_prompt = (
        "You suggest Korean follow-up questions for a financial analysis chat. Always return "
        "only a JSON array with up to 3 short strings. Each string must be a concrete question "
        "the user can send to analyze the current financial result. Do not include what-if "
        "simulation questions. Do not ask whether the user has additional questions, needs more "
        "help, or wants more explanation."
    )
    user_prompt = (
        f"Current question: {state['question']}\n"
        f"Intent: {state['intent']}\n"
        f"Answer: {state['answer']}\n"
        f"Evidence: {'; '.join(state['evidence'][:6])}\n"
        f"Missing data: {', '.join(state['missing_data']) or 'none'}\n"
        f"Recent conversation:\n{recent_turns or 'none'}"
    )
    raw = await LLMClient().answer(system_prompt, user_prompt)
    if not raw:
        return [], "llm_unavailable", "LLM 추천 호출 응답이 비어 있습니다. OPENAI_API_KEY가 서버에 없거나 LLM 호출이 실패했을 수 있습니다."
    try:
        parsed = _loads_llm_json(raw)
    except json.JSONDecodeError:
        return [], "parse_error", f"LLM 추천 질문 응답을 JSON 배열로 파싱하지 못했습니다. 응답 일부: {_preview_llm_output(raw)}"
    if not isinstance(parsed, list):
        return [], "parse_error", f"LLM 추천 질문 응답이 배열 형식이 아닙니다. 실제 형식: {type(parsed).__name__}"
    raw_questions = [item for item in parsed if isinstance(item, str)]
    cleaned = _clean_suggested_questions(raw_questions)
    if cleaned:
        return cleaned, "generated", f"LLM이 추천 질문 {len(cleaned)}개를 생성했습니다."
    if raw_questions:
        return [], "filtered", "LLM 추천 질문이 what-if 제외, 메타 질문 제외, 빈 문자열, 길이 제한, 중복 제거 과정에서 모두 필터링되었습니다."
    return [], "empty_by_llm", "LLM이 빈 추천 질문 배열 또는 문자열이 아닌 항목만 반환했습니다."


def _build_deterministic_answer(state: AgentState) -> str:
    if not state["tool_results"] or not state["evidence"]:
        missing = ", ".join(state["missing_data"]) or "분석 결과"
        return f"답변에 필요한 데이터가 부족합니다. 부족한 데이터: {missing}."

    primary_content = next((result.content for result in state["tool_results"] if result.content), "")
    if state["intent"] == AgentIntent.EXTERNAL_WEATHER and _asks_electricity_forecast(state["question"]):
        category_evidence = next((item for item in state["evidence"] if "전기요금" in item), "")
        return f"{category_evidence}." if category_evidence else primary_content
    if state["intent"] == AgentIntent.EXTERNAL_REAL_ESTATE:
        return primary_content

    evidence_text = " / ".join(state["evidence"][:4])
    missing_text = ""
    if state["missing_data"]:
        missing_text = f" 다만 {', '.join(state['missing_data'])}가 부족해 신뢰도는 {state['confidence']}입니다."
    return f"{primary_content} 근거: {evidence_text}.{missing_text}"


def _build_deterministic_suggested_questions(state: AgentState) -> list[str]:
    if state["analysis"] is None:
        return []
    if state["conversation"]:
        suggestions_by_intent = {
            AgentIntent.MONTHLY_FORECAST: [
                "카테고리별 지출도 보여줘",
                "전체 분석 요약을 다시 알려줘",
                "데이터 신뢰도는 어느 정도야?",
            ],
            AgentIntent.CATEGORY_ANALYSIS: [
                "예측 종료 시점 순자산은 얼마야?",
                "월별 순현금흐름을 알려줘",
                "분석 데이터가 충분한지 알려줘",
            ],
            AgentIntent.EXTERNAL_WEATHER: [
                "전기요금 카테고리 근거를 보여줘",
                "기상 데이터 없이 계산된 부분은 뭐야?",
                "월별 지출 예측을 알려줘",
            ],
            AgentIntent.EXTERNAL_REAL_ESTATE: [
                "순자산 예측 근거를 보여줘",
                "부동산 데이터 없이 계산된 부분은 뭐야?",
                "예측 종료 시점 순자산은 얼마야?",
            ],
            AgentIntent.EXTERNAL_SEARCH: [
                "검색 근거를 요약해줘",
                "내 분석 결과와 연결해서 설명해줘",
                "데이터 신뢰도는 어느 정도야?",
            ],
        }
        return suggestions_by_intent.get(
            state["intent"],
            [
                "월별 순현금흐름을 알려줘",
                "카테고리별 지출을 보여줘",
                "예측 종료 시점 순자산은 얼마야?",
            ],
        )[:3]
    return [
        "월별 순현금흐름을 알려줘",
        "카테고리별 지출을 보여줘",
        "예측 종료 시점 순자산은 얼마야?",
    ]


def _clean_suggested_questions(values: list[str]) -> list[str]:
    blocked_keywords = ("what-if", "what if", "시뮬레이션", "줄이면", "오르면", "하락하면", "상승하면")
    cleaned: list[str] = []
    for value in values:
        question = value.strip().strip('"').strip("'")
        if not question or any(keyword in question.lower() for keyword in blocked_keywords):
            continue
        if _is_meta_suggestion(question):
            continue
        if len(question) > 80:
            question = question[:80].rstrip()
        cleaned.append(question)
    return _dedupe(cleaned)[:3]


def _is_meta_suggestion(question: str) -> bool:
    normalized = "".join(question.lower().split())
    blocked_fragments = (
        "추가적인질문",
        "추가질문",
        "질문이있",
        "질문있",
        "궁금한점",
        "궁금하신점",
        "더알고싶",
        "더궁금",
        "도움이필요",
        "더도와",
        "설명이필요",
        "더설명",
        "문의하",
    )
    return any(fragment in normalized for fragment in blocked_fragments)


def _loads_llm_json(raw: str):
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _preview_llm_output(raw: str) -> str:
    text = " ".join(raw.strip().split())
    if len(text) > 120:
        return f"{text[:120]}..."
    return text or "(empty)"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            output.append(value)
            seen.add(value)
    return output
