import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    from langchain_core.documents import Document
except Exception:
    @dataclass
    class Document:
        page_content: str
        metadata: dict = field(default_factory=dict)


KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def _flatten_text_values(value) -> list[str]:
    if isinstance(value, dict):
        ordered_keys = ["en", "es"]
        items: list[str] = []
        for key in ordered_keys:
            if key in value:
                items.extend(_flatten_text_values(value[key]))
        for key, nested in value.items():
            if key not in ordered_keys:
                items.extend(_flatten_text_values(nested))
        return _dedupe(items)
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_flatten_text_values(item))
        return _dedupe(items)
    text = _normalize_text(str(value or ""))
    return [text] if text else []


def _preferred_text(value, preferred_language: str = "en") -> str:
    if isinstance(value, dict):
        preferred = _normalize_text(str(value.get(preferred_language, "")))
        if preferred:
            return preferred
        for nested in value.values():
            fallback = _preferred_text(nested, preferred_language)
            if fallback:
                return fallback
        return ""
    if isinstance(value, list):
        for item in value:
            fallback = _preferred_text(item, preferred_language)
            if fallback:
                return fallback
        return ""
    return _normalize_text(str(value or ""))


def _preferred_list(value, preferred_language: str = "en") -> list[str]:
    if isinstance(value, dict):
        preferred = value.get(preferred_language)
        preferred_list = _preferred_list(preferred, preferred_language)
        if preferred_list:
            return preferred_list
        for nested in value.values():
            fallback = _preferred_list(nested, preferred_language)
            if fallback:
                return fallback
        return []
    if isinstance(value, list):
        return _dedupe([_normalize_text(str(item)) for item in value if _normalize_text(str(item))])
    if isinstance(value, str):
        return _content_highlights(value)
    return []


def _first_sentence(value: str) -> str:
    text = _normalize_text(value)
    if not text:
        return ""

    match = re.search(r"(.+?[.!?])(?:\s|$)", text)
    return match.group(1).strip() if match else text


def _extract_links(value) -> list[str]:
    links: list[str] = []
    for text in _flatten_text_values(value):
        links.extend(match.rstrip(".,)") for match in re.findall(r"https?://[^\s)]+", text))
    return _dedupe(links)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        cleaned = _normalize_text(str(item))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)

    return result


def _content_highlights(content: str) -> list[str]:
    text = _normalize_text(content)
    if not text:
        return []

    fragments = re.split(r"\.\s+|,\s+(?=[a-zA-Z])| and ", text)
    highlights = []
    for fragment in fragments:
        cleaned = fragment.strip(" .")
        if len(cleaned) < 12:
            continue
        highlights.append(cleaned[0].upper() + cleaned[1:])

    return _dedupe(highlights[:5])


def _item_type(item: dict) -> str:
    explicit_type = item.get("type")
    if explicit_type:
        return explicit_type
    section = item.get("section")
    if section == "about":
        return "profile"
    if section == "experience":
        if item.get("current") is True:
            return "current_role"
        return "current_role" if "present" in (item.get("date_range", "").lower()) else "past_role"
    if section == "education":
        if item.get("current") is True:
            return "current_study"
        return "current_study" if "present" in (item.get("date_range", "").lower()) or "2026" in (item.get("date_range", "")) else "education_record"
    if section == "certifications":
        if item.get("completed") is True:
            return "completed_certification"
        if item.get("in_progress") is True:
            return "in_progress_certification"
        status = (item.get("status") or "").lower()
        if status == "completed":
            return "completed_certification"
        if status == "in_progress":
            return "in_progress_certification"
        return "certification"
    if section == "projects":
        return "project"
    if section == "stack":
        return "stack_category" if item.get("id") != "stack-summary-1" else "stack_summary"
    if section == "contact":
        return "contact"
    return "record"


def _collect_links(item: dict) -> list[str]:
    links: list[str] = []
    raw_links = item.get("links")

    if isinstance(raw_links, dict):
        links.extend(str(value) for value in raw_links.values() if value)
    elif isinstance(raw_links, list):
        links.extend(str(value) for value in raw_links if value)

    for key in ("github_url", "live_url"):
        value = item.get(key)
        if value:
            links.append(str(value))

    for field_name in ("content", "summary", "highlights"):
        links.extend(_extract_links(item.get(field_name, "")))
    return _dedupe(links)


def _build_keywords(item: dict, highlights: list[str], summary: str, content: str) -> list[str]:
    keywords: list[str] = []

    for key in ("section", "title", "subtitle", "date_range", "status", "code", "company", "institution"):
        value = item.get(key)
        if value:
            keywords.append(str(value))

    for field_name in ("skills", "tags"):
        values = item.get(field_name, [])
        if isinstance(values, list):
            keywords.extend(str(value) for value in values if value)

    raw_keywords = item.get("keywords", [])
    if isinstance(raw_keywords, list):
        keywords.extend(str(value) for value in raw_keywords if value)

    keywords.extend(_flatten_text_values(item.get("summary", "")))
    keywords.extend(_flatten_text_values(item.get("highlights", [])))
    keywords.extend(highlights)
    keywords.append(summary)
    keywords.append(content)
    keywords.extend(_extract_links(item.get("content", "")))
    return _dedupe(keywords)


def _normalize_record(item: dict) -> dict:
    section = item.get("section")
    record_type = _item_type(item)
    content_parts = _flatten_text_values(item.get("content", "")) + _flatten_text_values(item.get("summary", "")) + _flatten_text_values(item.get("highlights", []))
    content = _normalize_text(" ".join(_dedupe(content_parts)))
    primary_content = _preferred_text(item.get("content", ""), "en")
    summary = _preferred_text(item.get("summary", ""), "en") or _first_sentence(primary_content or content)
    highlights = _preferred_list(item.get("highlights", []), "en") or _content_highlights(primary_content or content)
    links = _collect_links(item)
    status = (item.get("status") or "").lower()
    current = bool(item.get("current")) or record_type in {"current_role", "current_study"}
    completed = bool(item.get("completed")) or status == "completed"
    in_progress = bool(item.get("in_progress")) or status == "in_progress"

    record = {
        "id": item.get("id"),
        "section": section,
        "type": record_type,
        "title": item.get("title", ""),
        "subtitle": item.get("subtitle", ""),
        "date_range": item.get("date_range", ""),
        "summary": summary,
        "highlights": highlights,
        "skills": item.get("skills", []),
        "tags": item.get("tags", []),
        "keywords": [],
        "content": content,
        "links": links,
        "current": current,
        "completed": completed,
        "in_progress": in_progress,
        "status": "completed" if completed else "in_progress" if in_progress else (status or None),
        "code": item.get("code"),
        "github_url": item.get("github_url"),
        "live_url": item.get("live_url"),
        "summary_localized": item.get("summary"),
        "highlights_localized": item.get("highlights"),
    }

    if section == "experience":
        record["company"] = item.get("subtitle", "")
    if section == "education":
        record["institution"] = item.get("subtitle", "")
    if section == "certifications":
        record["issuer"] = item.get("subtitle", "")

    record["keywords"] = _build_keywords({**item, **record}, highlights, summary, content)
    return record


def _anchor_record(
    *,
    record_id: str,
    section: str,
    record_type: str,
    title: str,
    summary: str,
    highlights: list[str],
    skills: list[str] | None = None,
    keywords: list[str] | None = None,
    links: list[str] | None = None,
    current: bool = False,
    completed: bool = False,
    in_progress: bool = False,
) -> dict:
    skill_list = _dedupe(skills or [])
    highlight_list = _dedupe(highlights)
    keyword_list = _dedupe((keywords or []) + skill_list + highlight_list + [title, section, record_type])

    return {
        "id": record_id,
        "section": section,
        "type": record_type,
        "title": title,
        "subtitle": "",
        "date_range": "",
        "summary": summary,
        "highlights": highlight_list,
        "skills": skill_list,
        "tags": [],
        "keywords": keyword_list,
        "content": f"{summary} {' '.join(highlight_list)}".strip(),
        "links": _dedupe(links or []),
        "current": current,
        "completed": completed,
        "in_progress": in_progress,
        "status": "completed" if completed else "in_progress" if in_progress else None,
        "code": None,
        "github_url": None,
        "live_url": None,
    }


def _build_anchor_records(records: list[dict]) -> list[dict]:
    about = next(record for record in records if record["section"] == "about")
    current_role = next(record for record in records if record["type"] == "current_role")
    current_study = next(record for record in records if record["type"] == "current_study")
    projects = [record for record in records if record["section"] == "projects"]
    certifications = [record for record in records if record["section"] == "certifications"]
    completed_certs = [record for record in certifications if record["completed"]]
    in_progress_certs = [record for record in certifications if record["in_progress"]]
    stack_records = [record for record in records if record["section"] == "stack"]
    contact = next(record for record in records if record["section"] == "contact")

    return [
        _anchor_record(
            record_id="anchor-professional-summary",
            section="about",
            record_type="anchor_summary",
            title="Professional summary",
            summary="Alba is a Fullstack Developer currently focused on fullstack development, artificial intelligence, and data.",
            highlights=[
                about["summary"],
                current_role["summary"],
                current_study["summary"],
            ],
            skills=["Python", "React", "Angular", "TypeScript", "Docker", "LangChain", "AWS", "Kubernetes"],
            keywords=["background", "summary", "profile", "focus", "professional summary"],
        ),
        _anchor_record(
            record_id="anchor-current-focus",
            section="about",
            record_type="anchor_focus",
            title="Current focus",
            summary="Alba is currently focused on fullstack development, artificial intelligence, and data.",
            highlights=[
                "Her profile highlights current work across fullstack development, AI, and data.",
                "Her stack includes Python, React, Angular, PostgreSQL, Docker, LangChain, AWS, and Kubernetes.",
            ],
            skills=["Python", "React", "Angular", "PostgreSQL", "Docker", "LangChain", "AWS", "Kubernetes"],
            keywords=["focus", "currently focused", "fullstack", "artificial intelligence", "data"],
        ),
        _anchor_record(
            record_id="anchor-current-role",
            section="experience",
            record_type="anchor_current_role",
            title="Current role at Siemens",
            summary=(
                "Alba currently works as a Software Developer Intern at Siemens Mobility S.L.U., "
                "contributing to internal tools, backend APIs, deployments, and AI-related initiatives."
            ),
            highlights=[
                "Develops and maintains backend APIs using Python and Flask.",
                "Builds and supports internal web applications using JavaScript.",
                "Containerizes and deploys applications with Docker, Kubernetes, and Rancher UI.",
                "Contributes to AI-related and data-driven initiatives.",
                "Collaborates with cross-functional teams using modern engineering practices.",
            ],
            skills=["Python", "Flask", "JavaScript", "Docker", "Kubernetes", "Rancher UI", "APIs"],
            keywords=[
                "current role",
                "siemens",
                "current job",
                "present role",
                "what does alba do at siemens",
                "backend",
                "internal tools",
                "ai initiatives",
                "deployments",
            ],
            current=True,
        ),
        _anchor_record(
            record_id="anchor-projects-summary",
            section="projects",
            record_type="anchor_projects_summary",
            title="Projects summary",
            summary=f"Alba has built {len(projects)} portfolio projects covering frontend, backend, AI, cloud, and DevOps.",
            highlights=[project["title"] for project in projects],
            skills=_dedupe([skill for project in projects for skill in project["skills"]])[:18],
            keywords=["projects summary", "all projects", "portfolio projects", "what projects has alba built"],
        ),
        _anchor_record(
            record_id="anchor-certifications-summary",
            section="certifications",
            record_type="anchor_certifications_summary",
            title="Certifications summary",
            summary=(
                f"Alba has {len(completed_certs)} completed certification and {len(in_progress_certs)} certification in progress."
            ),
            highlights=[
                *(f"Completed: {record['title']} ({record['code']})" for record in completed_certs),
                *(f"In progress: {record['title']} ({record['code']})" for record in in_progress_certs),
            ],
            skills=_dedupe([skill for record in certifications for skill in record["skills"]])[:14],
            keywords=["certifications summary", "completed certifications", "in progress certification", "aws certification"],
        ),
        _anchor_record(
            record_id="anchor-contact-summary",
            section="contact",
            record_type="anchor_contact_summary",
            title="Contact summary",
            summary="Alba can be contacted through her portfolio, by email, on GitHub, and on LinkedIn.",
            highlights=[
                "Portfolio: https://albamora.dev",
                "Email: albamora.dev@gmail.com",
                "GitHub: https://github.com/albamdls",
                "LinkedIn: https://www.linkedin.com/in/alba-mora-de-la-sen/",
            ],
            links=contact["links"],
            keywords=["contact", "email", "portfolio", "github", "linkedin", "how can i contact alba"],
        ),
        _anchor_record(
            record_id="anchor-stack-summary",
            section="stack",
            record_type="anchor_stack_summary",
            title="Core stack summary",
            summary="Alba works across fullstack development, artificial intelligence, data, cloud, and DevOps.",
            highlights=[
                "Core technologies include Python, React, Angular, JavaScript, TypeScript, PostgreSQL, Docker, LangChain, AWS, and Kubernetes.",
                "Her stack also includes backend frameworks such as Spring Boot, Django, Flask, and Streamlit.",
            ],
            skills=_dedupe([skill for record in stack_records for skill in record["skills"]]),
            keywords=["stack summary", "core stack", "technologies", "skills", "tech stack"],
        ),
        _anchor_record(
            record_id="anchor-education-summary",
            section="education",
            record_type="anchor_education_summary",
            title="Education summary",
            summary="Alba combines web development, data analysis, and business education in her academic background.",
            highlights=[
                record["summary"] for record in records if record["section"] == "education"
            ],
            skills=["Web development", "Data analysis", "Big Data", "Business administration", "Finance"],
            keywords=["education summary", "studies", "academic background", "what is alba studying"],
        ),
    ]


@lru_cache(maxsize=1)
def load_raw_kb_items() -> list[dict]:
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_portfolio_records() -> list[dict]:
    records = [_normalize_record(item) for item in load_raw_kb_items()]
    return records + _build_anchor_records(records)


def _record_page_content(record: dict) -> str:
    parts = [
        f"Title: {record['title']}",
        f"Section: {record['section']}",
        f"Type: {record['type']}",
        f"Summary: {record['summary']}",
    ]

    if record.get("subtitle"):
        parts.append(f"Subtitle: {record['subtitle']}")
    if record.get("date_range"):
        parts.append(f"Date range: {record['date_range']}")
    if record.get("current"):
        parts.append("Current: true")
    if record.get("completed"):
        parts.append("Completed: true")
    if record.get("in_progress"):
        parts.append("In progress: true")
    if record.get("status"):
        parts.append(f"Status: {record['status']}")
    if record.get("code"):
        parts.append(f"Code: {record['code']}")
    if record.get("skills"):
        parts.append(f"Skills: {', '.join(record['skills'])}")
    if record.get("highlights"):
        parts.append(f"Highlights: {' | '.join(record['highlights'])}")
    if record.get("keywords"):
        parts.append(f"Keywords: {', '.join(record['keywords'])}")
    if record.get("links"):
        parts.append(f"Links: {', '.join(record['links'])}")
    if record.get("content"):
        parts.append(f"Details: {record['content']}")

    return "\n".join(parts)


def _document_metadata(record: dict) -> dict:
    metadata = {
        key: value
        for key, value in record.items()
        if key not in {"content"}
    }
    return metadata


def load_kb_documents() -> list[Document]:
    return [
        Document(
            page_content=_record_page_content(record),
            metadata=_document_metadata(record),
        )
        for record in load_portfolio_records()
    ]


def load_documents_by_section(section: str) -> list[Document]:
    return [doc for doc in load_kb_documents() if doc.metadata.get("section") == section]


def load_records_by_section(section: str) -> list[dict]:
    return [record for record in load_portfolio_records() if record.get("section") == section]
