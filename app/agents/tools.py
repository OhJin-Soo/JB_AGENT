from sqlalchemy.orm import Session

from app.services.analysis import get_analysis
from app.services.external.tavily import TavilyClient


async def retrieve_analysis_context(analysis_id: int | None, db: Session) -> str:
    if analysis_id is None:
        return ""
    analysis = get_analysis(analysis_id, db)
    if analysis is None:
        return ""
    return analysis.result.model_dump_json()


async def search_web_context(question: str) -> tuple[str, list[str]]:
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
    return "\n".join(snippets), sources
