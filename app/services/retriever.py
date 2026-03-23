from functools import lru_cache
import re

from app.services.kb_loader import load_kb_documents

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

SECTION_HINTS: dict[str, tuple[str, ...]] = {
    "about": ("about", "background", "profile", "summary", "sobre", "perfil", "resumen"),
    "experience": ("experience", "role", "work", "siemens", "experiencia", "trabajo", "rol"),
    "education": ("education", "study", "studying", "degree", "formacion", "formación", "estudios"),
    "certifications": ("certification", "certifications", "certificate", "certificacion", "certificación"),
    "projects": ("project", "projects", "portfolio", "proyecto", "proyectos"),
    "stack": ("stack", "skills", "technology", "technologies", "tech", "tecnologías", "habilidades"),
    "contact": ("contact", "github", "linkedin", "email", "contacto"),
}

TYPE_BOOSTS: dict[str, tuple[str, ...]] = {
    "anchor_current_role": ("current", "currently", "right now", "present", "actualmente", "ahora", "siemens"),
    "current_role": ("current", "currently", "right now", "present", "actualmente", "ahora", "siemens"),
    "anchor_projects_summary": ("all projects", "what projects", "proyectos", "projects"),
    "project": ("which project", "project related", "qué proyecto", "proyecto relacionado"),
    "anchor_certifications_summary": ("what certifications", "certifications", "certificaciones"),
    "completed_certification": ("completed certification", "already completed", "completada", "terminada"),
    "in_progress_certification": ("in progress", "preparing", "preparando", "en progreso"),
    "anchor_contact_summary": ("contact", "linkedin", "github", "contacto"),
    "anchor_stack_summary": ("stack", "technologies", "skills", "tech", "habilidades", "tecnologías"),
}


@lru_cache(maxsize=1)
def get_vectorstore():
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings

    documents = load_kb_documents()
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return FAISS.from_documents(documents, embeddings)


def normalize_query(text: str) -> str:
    return " ".join(text.strip().lower().split())


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9+#.-]+", text.lower()) if len(token) > 1}


def _field_text(metadata: dict, field_name: str) -> str:
    value = metadata.get(field_name)
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _match_score(query: str, query_tokens: set[str], value: str, weight: int, *, exact_bonus: int = 0) -> int:
    field_text = normalize_query(value)
    if not field_text:
        return 0

    score = 0
    if query == field_text:
        score += weight + exact_bonus

    overlap = query_tokens & tokenize(field_text)
    score += len(overlap) * weight

    if query in field_text:
        score += exact_bonus

    return score


def _section_boost(query: str, metadata: dict) -> int:
    section = metadata.get("section")
    boost = 0
    for candidate, hints in SECTION_HINTS.items():
        if section == candidate and any(hint in query for hint in hints):
            boost += 15
    return boost


def _type_boost(query: str, metadata: dict) -> int:
    record_type = metadata.get("type")
    boost = 0
    for candidate, hints in TYPE_BOOSTS.items():
        if record_type == candidate and any(hint in query for hint in hints):
            boost += 18

    if metadata.get("current") and any(token in query for token in ("current", "currently", "right now", "actualmente", "ahora")):
        boost += 16

    return boost


def _document_score(query: str, doc) -> int:
    metadata = doc.metadata
    query_tokens = tokenize(query)

    score = 0
    score += _match_score(query, query_tokens, _field_text(metadata, "title"), 14, exact_bonus=35)
    score += _match_score(query, query_tokens, _field_text(metadata, "skills"), 11, exact_bonus=28)
    score += _match_score(query, query_tokens, _field_text(metadata, "keywords"), 10, exact_bonus=24)
    score += _match_score(query, query_tokens, _field_text(metadata, "summary"), 8, exact_bonus=14)
    score += _match_score(query, query_tokens, _field_text(metadata, "highlights"), 6, exact_bonus=10)
    score += _match_score(query, query_tokens, doc.page_content, 2, exact_bonus=4)
    score += _section_boost(query, metadata)
    score += _type_boost(query, metadata)

    if metadata.get("section") == "projects" and any(token in query for token in ("project", "projects", "proyecto", "proyectos")):
        score += 12
    if metadata.get("section") == "certifications" and any(token in query for token in ("certification", "certifications", "certificación", "certificaciones")):
        score += 12

    return score


def _lexical_search(query: str, k: int = 6):
    documents = load_kb_documents()
    normalized_query = normalize_query(query)
    ranked = sorted(documents, key=lambda doc: _document_score(normalized_query, doc), reverse=True)
    filtered = [doc for doc in ranked if _document_score(normalized_query, doc) > 0]
    return (filtered or ranked)[:k]


def _hybrid_search(query: str, k: int = 6):
    normalized_query = normalize_query(query)
    lexical_docs = _lexical_search(normalized_query, k=max(k * 2, 8))

    try:
        vector_docs = get_vectorstore().similarity_search(query, k=max(k, 4))
    except Exception:
        return lexical_docs[:k]

    combined: dict[str, object] = {}
    for doc in lexical_docs + vector_docs:
        doc_id = doc.metadata.get("id")
        if doc_id not in combined:
            combined[doc_id] = doc

    reranked = sorted(
        combined.values(),
        key=lambda doc: _document_score(normalized_query, doc),
        reverse=True,
    )
    return reranked[:k]


def retrieve_context(query: str, k: int = 6):
    return _hybrid_search(query, k=k)

