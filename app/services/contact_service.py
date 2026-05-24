import logging
import re
from html import escape

import resend
from fastapi import HTTPException

from app.core.config import CONTACT_FROM_EMAIL, CONTACT_TO_EMAIL, RESEND_API_KEY
from app.schemas.contact import ContactRequest, ContactResponse

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_payload(payload: ContactRequest) -> dict[str, str]:
    return {
        "name": payload.name.strip(),
        "email": payload.email.strip(),
        "message": payload.message.strip(),
    }


def _validate_payload(payload: dict[str, str]) -> None:
    if not payload["name"] or not payload["email"] or not payload["message"]:
        raise HTTPException(status_code=400, detail="Please fill in all fields.")
    if not EMAIL_RE.match(payload["email"]):
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")


def _build_email_params(payload: dict[str, str]) -> resend.Emails.SendParams:
    safe_name = escape(payload["name"])
    safe_email = escape(payload["email"])
    safe_message = escape(payload["message"]).replace("\n", "<br />")

    return {
        "from": CONTACT_FROM_EMAIL,
        "to": [CONTACT_TO_EMAIL],
        "reply_to": payload["email"],
        "subject": f"New portfolio message from {payload['name']}",
        "text": (
            f"New contact form message from Alba's portfolio.\n\n"
            f"Name: {payload['name']}\n"
            f"Email: {payload['email']}\n\n"
            f"Message:\n{payload['message']}"
        ),
        "html": (
            "<div style=\"font-family:Arial,sans-serif;line-height:1.6;color:#111827;\">"
            "<h2>New portfolio contact message</h2>"
            f"<p><strong>Name:</strong> {safe_name}</p>"
            f"<p><strong>Email:</strong> {safe_email}</p>"
            f"<p><strong>Message:</strong><br />{safe_message}</p>"
            "</div>"
        ),
    }


def send_contact_message(payload: ContactRequest) -> ContactResponse:
    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Contact service is not configured yet. Please try again later.",
        )

    normalized = _normalize_payload(payload)
    _validate_payload(normalized)

    resend.api_key = RESEND_API_KEY

    try:
        resend.Emails.send(_build_email_params(normalized))
    except resend.exceptions.ResendError as exc:
        logger.error("Resend error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error sending email: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="There was a problem sending your message. Please try again later.",
        ) from exc

    return ContactResponse(success=True, message="Message sent successfully.")
