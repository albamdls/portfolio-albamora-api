import json
import re
from html import escape
from urllib import error, request

from fastapi import HTTPException

from app.core.config import CONTACT_FROM_EMAIL, CONTACT_TO_EMAIL, RESEND_API_KEY
from app.schemas.contact import ContactRequest, ContactResponse

RESEND_API_URL = "https://api.resend.com/emails"
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


def _build_email_body(payload: dict[str, str]) -> dict:
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


def _send_resend_email(body: dict) -> None:
    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Contact service is not configured yet. Please try again later.",
        )

    req = request.Request(
        RESEND_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=15) as response:
            if response.status not in {200, 201, 202}:
                raise HTTPException(
                    status_code=502,
                    detail="The email provider returned an unexpected response.",
                )
    except error.HTTPError as exc:
        detail = "There was a problem sending your message."
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            detail = payload.get("message") or payload.get("error", {}).get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=detail) from exc
    except error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail="The contact service is temporarily unavailable. Please try again later.",
        ) from exc


def send_contact_message(payload: ContactRequest) -> ContactResponse:
    normalized = _normalize_payload(payload)
    _validate_payload(normalized)
    _send_resend_email(_build_email_body(normalized))
    return ContactResponse(success=True, message="Message sent successfully.")
