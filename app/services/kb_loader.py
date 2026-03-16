import json
from pathlib import Path
from langchain_core.documents import Document


KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"


def load_kb_documents() -> list[Document]:
    with KB_PATH.open("r", encoding="utf-8") as f:
        raw_items = json.load(f)

    documents: list[Document] = []

    for item in raw_items:
        documents.append(
            Document(
                page_content=item["content"],
                metadata={
                    "id": item.get("id"),
                    "section": item.get("section"),
                    "title": item.get("title"),
                    "subtitle": item.get("subtitle"),
                    "date_range": item.get("date_range"),
                    "skills": item.get("skills", []),
                    "links": item.get("links"),
                    "github_url": item.get("github_url"),
                    "live_url": item.get("live_url"),
                },
            )
        )

    return documents


def load_documents_by_section(section: str) -> list[Document]:
    return [doc for doc in load_kb_documents() if doc.metadata.get("section") == section]