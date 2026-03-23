from app.schemas.chat import ChatRequest, ChatResponse
from app.services.assistant_answers import deterministic_answer, fallback_open_answer, llm_answer
from app.services.assistant_core import classify_query, intent_to_cta, intent_to_section, records, relevant_record_ids
from app.services.conversation_memory import append_turn, get_recent_turns
from app.services.retriever import retrieve_context


def generate_chat_response(payload: ChatRequest) -> ChatResponse:
    turns = get_recent_turns(payload.session_id)
    query = classify_query(payload.message, turns)
    docs = retrieve_context(query["resolved_message"], k=6)

    answer = deterministic_answer(query, turns)
    if answer is None:
        answer = llm_answer(query, docs, turns)
    if answer is None:
        answer = fallback_open_answer(query, docs)

    intent = query["intent"]
    section_hint = intent_to_section(intent)
    suggested_cta = intent_to_cta(intent, query["language"])
    record_ids = relevant_record_ids(intent, query["technology"]) or [
        doc.metadata.get("id") for doc in docs[:4] if doc.metadata.get("id")
    ]
    record_map = {record["id"]: record["title"] for record in records()}
    source_titles = [record_map[record_id] for record_id in record_ids if record_id in record_map][:6]
    if not source_titles:
        source_titles = [doc.metadata.get("title", "Untitled") for doc in docs[:6]]

    append_turn(
        payload.session_id,
        user_message=payload.message,
        assistant_answer=answer,
        topic=intent,
        section_hint=section_hint,
        record_ids=record_ids,
    )

    return ChatResponse(
        answer=answer,
        sources=source_titles,
        session_id=payload.session_id,
        section_hint=section_hint,
        suggested_cta=suggested_cta,
        structured_data=None,
    )
