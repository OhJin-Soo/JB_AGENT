from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    analysis_id: int | None = None
    conversation: list[ChatHistoryItem] = Field(default_factory=list, max_length=12)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: str = "low"
    intent: str = "general"
    needs_more_data: bool = False
    missing_data: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list, max_length=3)
    suggestion_status: str = "none"
    suggestion_reason: str | None = None
    tool_plan_status: str = "none"
    tool_plan_reason: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
