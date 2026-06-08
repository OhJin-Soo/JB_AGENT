from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.tools import retrieve_analysis_context, search_web_context
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm import LLMClient


class AgentState(TypedDict):
    question: str
    analysis_id: int | None
    analysis_context: str
    web_context: str
    sources: list[str]
    answer: str
    needs_more_data: bool


def build_agent_graph(db: Session):
    graph = StateGraph(AgentState)

    async def load_analysis(state: AgentState) -> AgentState:
        state["analysis_context"] = await retrieve_analysis_context(state["analysis_id"], db)
        state["needs_more_data"] = state["analysis_id"] is None or not state["analysis_context"]
        return state

    async def load_search(state: AgentState) -> AgentState:
        web_context, sources = await search_web_context(state["question"])
        state["web_context"] = web_context
        state["sources"] = sources
        return state

    async def generate_answer(state: AgentState) -> AgentState:
        if not state["analysis_context"] and not state["web_context"]:
            state["answer"] = (
                "분석 결과나 외부 검색 근거가 충분하지 않습니다. 먼저 현금흐름 분석을 생성한 뒤 "
                "analysis_id와 함께 질문하거나, Tavily/OpenAI API 키를 설정해 주세요."
            )
            state["needs_more_data"] = True
            return state

        system_prompt = (
            "You are a Korean financial analysis assistant. Answer only from the provided "
            "analysis and search context. If evidence is weak, say what data is missing."
        )
        user_prompt = (
            f"Question:\n{state['question']}\n\n"
            f"Analysis context:\n{state['analysis_context']}\n\n"
            f"Search context:\n{state['web_context']}"
        )
        llm_answer = await LLMClient().answer(system_prompt, user_prompt)
        if llm_answer:
            state["answer"] = llm_answer
            return state

        fallback = "분석 결과 기준으로 보면, "
        if state["analysis_context"]:
            fallback += "저장된 예측 데이터가 있으므로 월별 현금흐름과 순자산 추이를 확인할 수 있습니다. "
        if state["web_context"]:
            fallback += "외부 검색 결과도 함께 조회되었지만 OpenAI API 키가 없어 요약 답변은 생성하지 않았습니다."
        else:
            fallback += "외부 검색 결과는 없습니다."
        state["answer"] = fallback
        return state

    graph.add_node("load_analysis", load_analysis)
    graph.add_node("load_search", load_search)
    graph.add_node("generate_answer", generate_answer)
    graph.add_edge(START, "load_analysis")
    graph.add_edge("load_analysis", "load_search")
    graph.add_edge("load_search", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()


async def run_agent(request: ChatRequest, db: Session) -> ChatResponse:
    graph = build_agent_graph(db)
    final_state = await graph.ainvoke(
        {
            "question": request.question,
            "analysis_id": request.analysis_id,
            "analysis_context": "",
            "web_context": "",
            "sources": [],
            "answer": "",
            "needs_more_data": False,
        }
    )
    return ChatResponse(
        answer=final_state["answer"],
        sources=final_state["sources"],
        needs_more_data=final_state["needs_more_data"],
    )
