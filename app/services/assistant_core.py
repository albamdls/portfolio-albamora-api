from collections import Counter
import re

from app.services.kb_loader import load_portfolio_records

PRESET_INTENTS = {
    "tell me about alba's professional experience.": "experience_summary",
    "tell me about alba's background and profile.": "background",
    "what technologies does alba use?": "stack_summary",
    "how can i contact alba?": "contact",
}

OUT_OF_SCOPE_HINTS = (
    "weather",
    "champions league",
    "quantum",
    "recipe",
    "paella",
    "capital of",
    "latest openai news",
    "openai news",
    "debug my linux server",
    "linux server",
    "react vs vue",
)

SPANISH_MARKERS = (
    "¿",
    " qué ",
    " cómo ",
    " cual ",
    " cuál ",
    " dónde ",
    " tecnologías ",
    " experiencia ",
    " certificaciones ",
    " proyectos ",
    " contacto ",
)

TECH_ALIASES = {
    "react": "ReactJS",
    "reactjs": "ReactJS",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "python": "Python",
    "angular": "Angular",
    "docker": "Docker",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "aws": "AWS",
    "kubernetes": "Kubernetes",
    "langchain": "LangChain",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "hugging face": "Hugging Face",
    "openai": "OpenAI",
    "redis": "Redis",
    "azure": "Azure",
    "tensorflow": "TensorFlow",
    ".net": ".NET",
    "go": "Go",
    "gcp": "GCP",
}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def clean_answer(text: str) -> str:
    return "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())


def poor_answer(text: str) -> bool:
    normalized = normalize_text(text)
    return any(
        phrase in normalized
        for phrase in (
            "retrieved context",
            "provided context",
            "according to the context",
            "the context does not provide",
        )
    )


def detect_language(user_message: str) -> str:
    normalized = f" {normalize_text(user_message)} "
    if normalized.startswith(" answer in spanish") or " en español" in normalized:
        return "es"
    if normalized.startswith(" answer in english") or " en inglés" in normalized or " en ingles" in normalized:
        return "en"
    if any(marker in normalized or marker == "¿" and "¿" in user_message for marker in SPANISH_MARKERS):
        return "es"
    return "en"


def strip_language_instruction(user_message: str) -> str:
    stripped = re.sub(r"^(answer in spanish|answer in english)\s*:\s*", "", user_message, flags=re.IGNORECASE)
    stripped = re.sub(r"^(responde en español|responde en ingles|responde en inglés)\s*:\s*", "", stripped, flags=re.IGNORECASE)
    return stripped.strip()


def detect_style(user_message: str) -> str:
    normalized = normalize_text(user_message)
    if "bullet point" in normalized or "bullet points" in normalized:
        return "bullets"
    if "one sentence" in normalized:
        return "one_sentence"
    if "under 20 words" in normalized or "very short" in normalized or "keep it under 20 words" in normalized:
        return "very_short"
    if "concise" in normalized or "short summary" in normalized:
        return "concise"
    return "default"


def natural_unavailable(language: str) -> str:
    return "Esa información no aparece en el portfolio de Alba." if language == "es" else "That information is not included in Alba's portfolio."


def natural_out_of_scope(language: str) -> str:
    return (
        "Solo puedo ayudar con preguntas sobre Alba Mora de la Sen y su portfolio."
        if language == "es"
        else "I can only help with questions about Alba Mora de la Sen and her portfolio."
    )


def records() -> list[dict]:
    return load_portfolio_records()


def raw_records(section: str | None = None) -> list[dict]:
    base = [record for record in records() if not str(record.get("id", "")).startswith("anchor-")]
    return [record for record in base if record.get("section") == section] if section else base


def anchor(record_id: str) -> dict:
    return next(record for record in records() if record["id"] == record_id)


def current_role_record() -> dict:
    return anchor("anchor-current-role")


def contact_summary_record() -> dict:
    return anchor("anchor-contact-summary")


def current_study_record() -> dict:
    return next(record for record in raw_records("education") if record.get("current"))


def certifications_records() -> list[dict]:
    return raw_records("certifications")


def project_records() -> list[dict]:
    return raw_records("projects")


def stack_records() -> list[dict]:
    return raw_records("stack")


def technology_map() -> dict[str, str]:
    technologies = {}
    for record in records():
        for skill in record.get("skills", []):
            technologies[normalize_text(skill)] = skill
    technologies.update({alias: canonical for alias, canonical in TECH_ALIASES.items()})
    return technologies


def find_technology(user_message: str) -> str | None:
    normalized = normalize_text(user_message)
    for alias, canonical in sorted(technology_map().items(), key=lambda item: len(item[0]), reverse=True):
        if contains_term(normalized, alias):
            return canonical
    return None


def technology_records(technology: str) -> list[dict]:
    canonical = normalize_text(technology)
    matched = []
    for record in records():
        haystack = " ".join(
            [
                normalize_text(record.get("title", "")),
                normalize_text(record.get("summary", "")),
                " ".join(normalize_text(skill) for skill in record.get("skills", [])),
                " ".join(normalize_text(keyword) for keyword in record.get("keywords", [])),
                " ".join(normalize_text(highlight) for highlight in record.get("highlights", [])),
            ]
        )
        if contains_term(haystack, canonical):
            matched.append(record)
    return matched


def project_records_for_technology(technology: str) -> list[dict]:
    matches = technology_records(technology)
    return [record for record in project_records() if record in matches]


def join_items(items: list[str], language: str) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} y {items[1]}" if language == "es" else f"{items[0]} and {items[1]}"
    separator = ", "
    ending = " y " if language == "es" else ", and "
    return separator.join(items[:-1]) + ending + items[-1]


def record_titles(record_list: list[dict]) -> list[str]:
    return [record["title"] for record in record_list]


def latest_topic(turns: list[dict]) -> str | None:
    return turns[-1]["topic"] if turns else None


def latest_relevant_turn(turns: list[dict]) -> dict | None:
    skip_topics = {"open_qa", "out_of_scope", "status_follow_up"}
    for turn in reversed(turns):
        if turn.get("topic") not in skip_topics:
            return turn
    return turns[-1] if turns else None


def serialize_history(turns: list[dict]) -> str:
    lines = []
    for turn in turns[-4:]:
        lines.append(f"User: {turn['user_message']}")
        lines.append(f"Assistant: {turn['assistant_answer']}")
    return "\n".join(lines)


def build_context(docs) -> str:
    parts = []
    for doc in docs:
        title = doc.metadata.get("title", "Untitled")
        section = doc.metadata.get("section", "unknown")
        parts.append(f"[{section}] {title}\n{doc.page_content}")
    return "\n\n".join(parts)


def resolve_follow_up(user_message: str, turns: list[dict]) -> str:
    normalized = normalize_text(user_message)
    turn = latest_relevant_turn(turns)
    topic = turn["topic"] if turn else None

    if normalized in {"tell me more.", "tell me more", "can you expand on that?", "can you expand on that"}:
        mapping = {
            "experience_summary": "Tell me more about Alba's professional experience.",
            "current_role": "Tell me more about Alba's current role at Siemens.",
            "current_role_tech": "Tell me more about Alba's current role at Siemens.",
            "current_role_tasks": "Tell me more about Alba's current role at Siemens.",
            "stack_summary": "Tell me more about Alba's stack.",
            "projects_summary": "Tell me more about Alba's projects.",
            "certifications_summary": "Tell me more about Alba's certifications.",
        }
        return mapping.get(topic, user_message)

    if normalized in {"and her stack?", "and her stack", "what about her stack?", "what about her stack"}:
        return "What technologies does Alba use?"
    if "current role" in normalized:
        return "What is Alba doing at Siemens right now?"
    if normalized in {"what else has she done?", "what else has she done"} and topic in {"current_role", "experience_summary"}:
        return "Tell me about Alba's professional experience."
    if normalized in {"what does she use there?", "what does she use there"} and topic in {"current_role", "experience_summary", "current_role_tech"}:
        return "What technologies does Alba use in her current role?"
    return user_message


def is_out_of_scope(user_message: str, turns: list[dict]) -> bool:
    normalized = normalize_text(user_message)
    if any(hint in normalized for hint in OUT_OF_SCOPE_HINTS):
        return True
    if re.search(r"\b(weather|recipe|capital of|champions league|quantum computing)\b", normalized):
        return True
    if "alba" in normalized or "portfolio" in normalized or " her " in f" {normalized} ":
        return False
    if latest_topic(turns):
        return False
    return False


def classify_query(user_message: str, turns: list[dict]) -> dict:
    language = detect_language(user_message)
    style = detect_style(user_message)
    stripped = strip_language_instruction(user_message)
    resolved = resolve_follow_up(stripped, turns)
    normalized = normalize_text(resolved)
    technology = find_technology(normalized)
    relevant_turn = latest_relevant_turn(turns)
    last_topic = relevant_turn["topic"] if relevant_turn else None

    if is_out_of_scope(normalized, turns):
        intent = "out_of_scope"
    elif normalized in PRESET_INTENTS:
        intent = PRESET_INTENTS[normalized]
    elif "how can i contact" in normalized or "cómo puedo contactar" in normalized:
        intent = "contact"
    elif "what is alba focused on" in normalized or "en qué está enfocada alba" in normalized or "focused on right now" in normalized:
        intent = "current_focus"
    elif "what is alba doing at siemens" in normalized or "qué hace alba actualmente en siemens" in normalized or "tell me about alba's current role" in normalized or "tell me more about alba's current role" in normalized:
        intent = "current_role"
    elif "what technologies does alba use in her current role" in normalized:
        intent = "current_role_tech"
    elif "what does alba do in the siemens eda environment" in normalized:
        intent = "current_role_tasks"
    elif "tell me about alba's professional experience" in normalized or "tell me more about alba's professional experience" in normalized or "qué experiencia profesional tiene alba" in normalized or "tell me about alba's experience" in normalized:
        intent = "experience_summary"
    elif "tell me about alba's education" in normalized or "qué formación tiene alba" in normalized:
        intent = "education_summary"
    elif "what is alba studying right now" in normalized:
        intent = "current_study"
    elif "what certifications does alba have" in normalized or "qué certificaciones tiene alba" in normalized:
        intent = "certifications_summary"
    elif "which certification has alba already completed" in normalized or "qué certificación ha completado" in normalized:
        intent = "completed_certification"
    elif "what aws certification is alba preparing" in normalized or "qué certificación aws está preparando" in normalized:
        intent = "in_progress_certification"
    elif "what projects has alba built" in normalized or "tell me more about alba's projects" in normalized or "qué proyectos ha desarrollado alba" in normalized:
        intent = "projects_summary"
    elif "which project is related to" in normalized or "qué proyecto está relacionado con" in normalized:
        intent = "project_by_technology"
    elif "which technologies appear across alba's projects most often" in normalized:
        intent = "project_technology_frequency"
    elif "is alba more focused on fullstack" in normalized:
        intent = "focus_preference"
    elif "what backend technologies" in normalized:
        intent = "stack_backend"
    elif "what frontend technologies" in normalized:
        intent = "stack_frontend"
    elif "ai or data tools" in normalized:
        intent = "stack_ai_data"
    elif "cloud and devops tools" in normalized:
        intent = "stack_cloud_devops"
    elif "what databases does alba know" in normalized:
        intent = "stack_databases"
    elif "what technologies does alba use" in normalized or "tell me more about alba's stack" in normalized or "qué tecnologías principales usa alba" in normalized or "and her stack" in normalized:
        intent = "stack_summary"
    elif normalized.startswith("does alba use ") and technology:
        intent = "technology_presence"
    elif normalized.startswith("does alba know ") and technology:
        intent = "technology_presence"
    elif normalized.startswith("does alba work with ") and technology:
        intent = "technology_presence"
    elif normalized.startswith("has alba worked with ") and technology:
        intent = "technology_presence"
    elif normalized.startswith("does alba have experience with ") and technology:
        intent = "technology_presence"
    elif "background" in normalized or "summary of alba" in normalized or "summarize alba" in normalized or "tell me about alba's background" in normalized:
        intent = "background"
    elif normalized in {"what about her current role?", "what about her current role"}:
        intent = "current_role"
    elif normalized in {"is that current or past?", "is that current or past"} and last_topic in {
        "current_role",
        "current_role_tech",
        "current_role_tasks",
        "current_study",
        "completed_certification",
        "in_progress_certification",
    }:
        intent = "status_follow_up"
    elif normalized in {"which one is the most relevant?", "which one is the most relevant"} and last_topic in {"projects_summary", "project_by_technology"}:
        intent = "most_relevant_project"
    else:
        intent = "open_qa"

    return {
        "intent": intent,
        "language": language,
        "style": style,
        "message": stripped,
        "resolved_message": resolved,
        "technology": technology,
    }


def intent_to_section(intent: str) -> str | None:
    mapping = {
        "background": "about",
        "current_focus": "about",
        "current_role": "experience",
        "current_role_tasks": "experience",
        "current_role_tech": "experience",
        "experience_summary": "experience",
        "stack_summary": "stack",
        "stack_backend": "stack",
        "stack_frontend": "stack",
        "stack_ai_data": "stack",
        "stack_cloud_devops": "stack",
        "stack_databases": "stack",
        "technology_presence": "stack",
        "projects_summary": "projects",
        "project_by_technology": "projects",
        "project_technology_frequency": "projects",
        "contact": "contact",
    }
    return mapping.get(intent)


def intent_to_cta(intent: str, language: str) -> str | None:
    mapping = {
        "about": "Learn more about Alba",
        "experience": "View experience",
        "stack": "View full stack",
        "projects": "View projects",
        "contact": "Go to Contact",
    }
    es_mapping = {
        "about": "Ver más sobre Alba",
        "experience": "Ver experiencia",
        "stack": "Ver stack completo",
        "projects": "Ver proyectos",
        "contact": "Ir a contacto",
    }
    section = intent_to_section(intent)
    if not section:
        return None
    return es_mapping[section] if language == "es" else mapping[section]


def relevant_record_ids(intent: str, technology: str | None) -> list[str]:
    if intent == "background":
        return ["anchor-professional-summary", "anchor-current-focus"]
    if intent == "current_focus":
        return ["anchor-current-focus"]
    if intent in {"current_role", "current_role_tasks", "current_role_tech"}:
        return ["anchor-current-role"]
    if intent == "experience_summary":
        return [record["id"] for record in raw_records("experience")] + ["anchor-current-role"]
    if intent.startswith("stack_") or intent == "stack_summary":
        return ["anchor-stack-summary"]
    if intent == "projects_summary":
        return [record["id"] for record in project_records()] + ["anchor-projects-summary"]
    if intent == "project_by_technology" and technology:
        return [record["id"] for record in project_records_for_technology(technology)]
    if intent == "project_technology_frequency":
        return [record["id"] for record in project_records()]
    if intent in {"certifications_summary", "completed_certification", "in_progress_certification"}:
        return [record["id"] for record in certifications_records()] + ["anchor-certifications-summary"]
    if intent == "contact":
        return ["anchor-contact-summary", "contact-1", "profile-1"]
    if intent in {"education_summary", "current_study"}:
        return [record["id"] for record in raw_records("education")]
    return []


def project_technology_counts() -> list[str]:
    aliases = {
        "AWS ECS": "AWS",
        "ECR": "AWS",
        "API Gateway": "AWS",
        "Lambda": "AWS",
        "DynamoDB": "AWS",
        "Docker Compose": "Docker",
        "ReactJS": "React",
    }
    counts = Counter()
    for project in project_records():
        counts.update({aliases.get(skill, skill) for skill in project.get("skills", [])})
    return [name for name, _ in counts.most_common(5)]
