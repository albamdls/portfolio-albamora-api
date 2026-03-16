from pydantic import BaseModel
from typing import Optional, Any


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    session_id: Optional[str] = None
    section_hint: Optional[str] = None
    suggested_cta: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None