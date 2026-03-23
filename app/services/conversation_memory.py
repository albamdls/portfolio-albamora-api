from collections import defaultdict, deque
from copy import deepcopy

MAX_TURNS = 6

_STORE: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_TURNS))


def get_recent_turns(session_id: str | None) -> list[dict]:
    if not session_id:
        return []
    return deepcopy(list(_STORE[session_id]))


def append_turn(
    session_id: str | None,
    *,
    user_message: str,
    assistant_answer: str,
    topic: str | None,
    section_hint: str | None,
    record_ids: list[str] | None = None,
) -> None:
    if not session_id:
        return

    _STORE[session_id].append(
        {
            "user_message": user_message,
            "assistant_answer": assistant_answer,
            "topic": topic,
            "section_hint": section_hint,
            "record_ids": record_ids or [],
        }
    )

