from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.tools import (
    AgentIntent,
    ToolResult,
    build_suggested_actions,
    classify_question,
    confidence_from,
    fetch_real_estate_context,
    fetch_weather_context,
    get_analysis_summary,
    get_category_forecast,
    get_monthly_forecast,
    retrieve_analysis,
    search_web_context,
    validate_data_sufficiency,
)
from app.schemas.analysis import AnalysisResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import LLMClient


class AgentState(TypedDict):
    question: str
    analysis_id: int | None
    intent: str
    analysis: AnalysisResponse | None
    tool_results: list[ToolResult]
    sources: list[str]
    evidence: list[str]
    missing_data: list[str]
    answer: str
    confidence: str
    needs_more_data: bool
    suggested_actions: list[str]


def build_agent_graph(db: Session):
    graph = StateGraph(AgentState)

    async def classify(state: AgentState) -> AgentState:
        state["intent"] = classify_question(state["question"])
        return state

    async def load_analysis(state: AgentState) -> AgentState:
        state["analysis"] = retrieve_analysis(state["analysis_id"], db)
        return state

    async def execute_tools(state: AgentState) -> AgentState:
        analysis = state["analysis"]
        intent = state["intent"]
        results: list[ToolResult] = []

        if intent == AgentIntent.MONTHLY_FORECAST:
            results.append(get_monthly_forecast(analysis, state["question"]))
        elif intent == AgentIntent.CATEGORY_ANALYSIS:
            results.append(get_category_forecast(analysis, state["question"]))
        else:
            results.append(get_analysis_summary(analysis))

        if intent == AgentIntent.EXTERNAL_WEATHER:
            results.append(await fetch_weather_context())
        elif intent == AgentIntent.EXTERNAL_REAL_ESTATE:
            results.append(await fetch_real_estate_context())
        elif intent == AgentIntent.EXTERNAL_SEARCH:
            results.append(await search_web_context(state["question"]))

        results.append(validate_data_sufficiency(analysis, intent))
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

    graph.add_node("classify", classify)
    graph.add_node("load_analysis", load_analysis)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("validate_evidence", validate_evidence)
    graph.add_node("generate_answer", generate_answer)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "load_analysis")
    graph.add_edge("load_analysis", "execute_tools")
    graph.add_edge("execute_tools", "validate_evidence")
    graph.add_edge("validate_evidence", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()


async def run_agent(request: ChatRequest, db: Session) -> ChatResponse:
    graph = build_agent_graph(db)
    final_state = await graph.ainvoke(
        {
            "question": request.question,
            "analysis_id": request.analysis_id,
            "intent": AgentIntent.GENERAL,
            "analysis": None,
            "tool_results": [],
            "sources": [],
            "evidence": [],
            "missing_data": [],
            "answer": "",
            "confidence": "low",
            "needs_more_data": False,
            "suggested_actions": [],
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
    )


async def _generate_llm_answer(state: AgentState) -> str:
    context = "\n".join(
        f"[{result.name}]\n{result.content}\nEvidence: {'; '.join(result.evidence)}"
        for result in state["tool_results"]
    )
    system_prompt = (
        "You are a Korean financial analysis assistant. Answer concisely using only the "
        "provided tool results. Include uncertainty when missing_data is present. Do not "
        "invent calculations or sources."
    )
    user_prompt = (
        f"Intent: {state['intent']}\n"
        f"Question: {state['question']}\n"
        f"Tool results:\n{context}\n"
        f"Missing data: {', '.join(state['missing_data']) or 'none'}\n"
        f"Evidence: {'; '.join(state['evidence']) or 'none'}"
    )
    return await LLMClient().answer(system_prompt, user_prompt)


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


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            output.append(value)
            seen.add(value)
    return output
