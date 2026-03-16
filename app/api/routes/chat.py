from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import generate_chat_response

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    return generate_chat_response(payload)