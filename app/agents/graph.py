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
        if not state["tool_plan"]:
            state["tool_plan_status"] = "fallback_generated"
            state["tool_plan_reason"] = state["tool_plan_reason"] or "LLM tool plan을 사용할 수 없어 intent fallback을 사용했습니다."

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
        state["answer"] = llm_answer or deterministic_answer
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
        "the tool results."
    )
    user_prompt = (
        f"Intent: {state['intent']}\n"
        f"Question: {state['question']}\n"
        f"Tool plan status: {state['tool_plan_status']} ({state['tool_plan_reason'] or 'no reason'})\n"
        f"Tool results:\n{context}\n"
        f"Missing data: {', '.join(state['missing_data']) or 'none'}\n"
        f"Evidence: {'; '.join(state['evidence']) or 'none'}"
    )
    return await LLMClient().answer(system_prompt, user_prompt)


async def _plan_tools_with_llm(state: AgentState) -> tuple[list[dict], str, str | None]:
    recent_turns = "\n".join(f"{item.role}: {item.content}" for item in state["conversation"][-6:])
    system_prompt = (
        "You are a tool planner for a Korean financial analysis agent. Return only valid JSON. "
        "Do not answer the user. Choose the minimal required tools from the catalog. "
        "Return at most 5 tool calls. Never invent tool names or arguments."
    )
    user_prompt = (
        f"Question: {state['question']}\n"
        f"Keyword fallback intent: {state['intent']}\n"
        f"Has analysis result: {state['analysis'] is not None}\n"
        f"Recent conversation:\n{recent_turns or 'none'}\n\n"
        f"Tool catalog:\n{tool_catalog_for_prompt()}\n\n"
        "Return JSON with this exact shape:\n"
        '{"tool_calls":[{"name":"tool_name","arguments":{}}],"reason":"short reason"}'
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
        reason = parsed.get("reason")
        return calls, "llm_planned", reason if isinstance(reason, str) else "LLM이 tool plan을 생성했습니다."
    if invalid_names:
        return [], "invalid_tool", f"허용되지 않은 tool이 포함되어 intent fallback을 사용합니다: {', '.join(invalid_names)}"
    return [], "empty_by_llm", "LLM이 tool call을 생성하지 않아 intent fallback을 사용합니다."


def _fallback_tool_plan(intent: str) -> list[dict]:
    return [{"name": name, "arguments": {}} for name in fallback_tool_names_for_intent(intent)]


async def _generate_llm_suggested_questions(state: AgentState) -> tuple[list[str], str, str | None]:
    if state["analysis"] is None:
        return [], "no_analysis", "분석 결과가 없어 추천 질문을 만들 수 없습니다."
    recent_turns = "\n".join(f"{item.role}: {item.content}" for item in state["conversation"][-6:])
    system_prompt = (
        "You suggest Korean follow-up questions for a financial analysis chat. Always return "
        "only a JSON array with up to 3 short strings. Do not include what-if simulation questions."
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
        return [], "filtered", "LLM 추천 질문이 what-if 제외 규칙, 빈 문자열, 길이 제한, 중복 제거 과정에서 모두 필터링되었습니다."
    return [], "empty_by_llm", "LLM이 빈 추천 질문 배열 또는 문자열이 아닌 항목만 반환했습니다."


def _build_deterministic_answer(state: AgentState) -> str:
    if not state["tool_results"] or not state["evidence"]:
        missing = ", ".join(state["missing_data"]) or "분석 결과"
        return f"답변에 필요한 데이터가 부족합니다. 부족한 데이터: {missing}."

    primary_content = next((result.content for result in state["tool_results"] if result.content), "")
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
        if len(question) > 80:
            question = question[:80].rstrip()
        cleaned.append(question)
    return _dedupe(cleaned)[:3]


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
