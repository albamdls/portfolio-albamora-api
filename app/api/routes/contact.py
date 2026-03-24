from fastapi import APIRouter

from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact_service import send_contact_message

router = APIRouter()


@router.post("/contact", response_model=ContactResponse)
async def contact(payload: ContactRequest):
    return send_contact_message(payload)
