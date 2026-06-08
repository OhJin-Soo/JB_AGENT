from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    analysis_id: int | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: str = "low"
    intent: str = "general"
    needs_more_data: bool = False
    missing_data: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
