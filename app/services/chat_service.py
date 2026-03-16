from app.schemas.chat import ChatRequest, ChatResponse


SYSTEM_PROMPT = """You are the portfolio assistant for Alba Mora de la Sen.

Your purpose is to answer questions only about Alba Mora de la Sen, using exclusively the information provided in the retrieved context from her portfolio knowledge base.

You must follow these rules strictly:

1. Scope of answers
- Answer only questions directly related to Alba Mora de la Sen.
- Valid topics include her profile, background, education, certifications, projects, technical stack, experience, and contact-related portfolio information if supported by the context.
- If the user asks about unrelated topics, politely say that you can only answer questions about Alba and her portfolio.

2. Source of truth
- Use only the retrieved context provided to you.
- Do not use outside knowledge, assumptions, or general world knowledge.
- Do not infer unsupported facts.
- If the answer is not clearly supported by the context, say so.

3. No hallucinations
- Never invent projects, skills, roles, dates, companies, certifications, achievements, links, or personal details.
- Never guess missing details.
- If information is missing, clearly say so.

4. Handling missing information
- If the answer is not in the context, say that the information is not available in Alba's portfolio data.
- Do not fill gaps with speculation.

5. Style and tone
- Be clear, professional, concise, and natural.
- Keep answers short by default.
- Prefer answers between 2 and 4 sentences.
- For simple questions, answer in 1 short paragraph.
- Avoid repetition and filler.

6. Language behavior
- Reply in the same language as the user's question unless the user asks otherwise.

7. Perspective
- Do not pretend to be Alba Mora de la Sen.
- Refer to her in the third person as "Alba".
- Do not answer in first person as if you were Alba.

Your job is to be a reliable portfolio assistant for Alba Mora de la Sen.
"""


def build_context(docs) -> str:
    parts = []
    for doc in docs:
        title = doc.metadata.get("title", "Untitled")
        section = doc.metadata.get("section", "unknown")
        parts.append(f"[{section}] {title}\n{doc.page_content}")
    return "\n\n".join(parts)


def build_user_prompt(context: str, user_message: str) -> str:
    return f"""Retrieved context:
{context}

User question:
{user_message}

Instructions:
Answer using only the retrieved context above.
If the answer is not supported by the context, say that the information is not available in Alba's portfolio data.
Keep the answer concise.
"""


def clean_answer(text: str) -> str:
    return "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())


def detect_section_hint(user_message: str, docs) -> str | None:
    text = user_message.lower()

    if any(word in text for word in ["contact", "contactar", "linkedin", "github", "reach", "email"]):
        return "contact"
    if any(word in text for word in ["stack", "skills", "technologies", "tecnologías", "tech"]):
        return "stack"
    if any(word in text for word in ["project", "projects", "proyecto", "proyectos"]):
        return "projects"
    if any(word in text for word in ["experience", "experiencia", "work"]):
        return "experience"
    if any(word in text for word in ["about", "profile", "background", "sobre"]):
        return "about"

    if docs:
        section_counts: dict[str, int] = {}
        for doc in docs:
            section = doc.metadata.get("section")
            if not section:
                continue
            section_counts[section] = section_counts.get(section, 0) + 1

        if section_counts:
            return max(section_counts, key=section_counts.get)

    return None


def build_cta(section_hint: str | None) -> str | None:
    mapping = {
        "contact": "Go to Contact",
        "stack": "View full stack",
        "projects": "View projects",
        "experience": "View experience",
        "about": "Learn more about Alba",
    }
    return mapping.get(section_hint)


def build_stack_structured_data(stack_docs) -> dict | None:
    grouped: dict[str, list[str]] = {}

    for doc in stack_docs:
        title = doc.metadata.get("title", "")
        skills = doc.metadata.get("skills", [])

        if not isinstance(skills, list) or not skills:
            continue

        if "Frontend technologies" in title:
            grouped["Frontend"] = skills[:6]
        elif "Backend technologies" in title:
            grouped["Backend"] = skills[:6]
        elif "AI and data technologies" in title:
            grouped["AI & Data"] = skills[:6]
        elif "Cloud and DevOps technologies" in title:
            grouped["Cloud & DevOps"] = skills[:6]
        elif "Database technologies" in title:
            grouped["Databases"] = skills[:6]
        elif "Software and productivity tools" in title:
            grouped["Tools"] = skills[:6]

    if not grouped:
        return None

    return {
        "type": "stack_groups",
        "groups": grouped,
    }


def build_stack_summary(structured_data: dict | None) -> str:
    if not structured_data or structured_data.get("type") != "stack_groups":
        return "Alba works with a broad technical stack across frontend, backend, AI/data, cloud, databases, and development tools."

    groups = structured_data.get("groups", {})

    ordered_names = ["Frontend", "Backend", "AI & Data", "Cloud & DevOps", "Databases", "Tools"]
    available = [name for name in ordered_names if name in groups]

    if not available:
        return "Alba works with a broad technical stack across frontend, backend, AI/data, cloud, databases, and development tools."

    if len(available) == 1:
        return f"Alba works mainly with {available[0].lower()} technologies. Here is a quick summary of her stack."

    if len(available) == 2:
        return f"Alba works mainly with {available[0].lower()} and {available[1].lower()} technologies. Here is a quick summary of her stack."

    first = ", ".join(name.lower() for name in available[:-1])
    last = available[-1].lower()
    return f"Alba works across {first}, and {last}. Here is a quick summary of her main stack."


def build_experience_structured_data(experience_docs) -> dict | None:
    items = []

    for doc in experience_docs:
        items.append({
            "title": doc.metadata.get("title", ""),
            "subtitle": doc.metadata.get("subtitle", ""),
            "date_range": doc.metadata.get("date_range", ""),
            "skills": doc.metadata.get("skills", [])[:4],
        })

    if not items:
        return None

    return {
        "type": "experience_items",
        "items": items,
    }


def build_experience_summary(experience_docs) -> str:
    if not experience_docs:
        return "I don't have Alba's professional experience details in the portfolio data."

    companies = []
    for doc in experience_docs:
        subtitle = doc.metadata.get("subtitle")
        if subtitle and subtitle not in companies:
            companies.append(subtitle)

    if companies:
        return (
            f"Alba has professional experience in software development, including internship experience at "
            f"{', '.join(companies)}. Here is a quick overview of her experience."
        )

    return "Alba has professional experience in software development. Here is a quick overview of her experience."


def build_special_response(payload: ChatRequest, section_hint: str | None, docs) -> ChatResponse | None:
    from app.services.kb_loader import load_documents_by_section

    if section_hint == "contact":
        return ChatResponse(
            answer="If you want to contact Alba, you can do it through the Contact section of the portfolio.",
            sources=[doc.metadata.get("title", "Untitled") for doc in docs],
            session_id=payload.session_id,
            section_hint="contact",
            suggested_cta="Go to Contact",
            structured_data=None,
        )

    if section_hint == "stack":
        stack_docs = load_documents_by_section("stack")
        structured_data = build_stack_structured_data(stack_docs)
        answer = build_stack_summary(structured_data)

        return ChatResponse(
            answer=answer,
            sources=[doc.metadata.get("title", "Untitled") for doc in stack_docs],
            session_id=payload.session_id,
            section_hint="stack",
            suggested_cta="View full stack",
            structured_data=structured_data,
        )

    if section_hint == "experience":
        experience_docs = load_documents_by_section("experience")
        structured_data = build_experience_structured_data(experience_docs)
        answer = build_experience_summary(experience_docs)

        return ChatResponse(
            answer=answer,
            sources=[doc.metadata.get("title", "Untitled") for doc in experience_docs],
            session_id=payload.session_id,
            section_hint="experience",
            suggested_cta="View experience",
            structured_data=structured_data,
        )

    return None

def generate_chat_response(payload: ChatRequest) -> ChatResponse:
    from app.services.retriever import retrieve_context
    from app.services.llm import generate_hf_chat

    docs = retrieve_context(payload.message, k=3)

    if not docs:
        return ChatResponse(
            answer="I don't have that information in Alba's portfolio data.",
            sources=[],
            session_id=payload.session_id,
            section_hint=None,
            suggested_cta=None,
            structured_data=None,
        )

    section_hint = detect_section_hint(payload.message, docs)

    special_response = build_special_response(payload, section_hint, docs)
    if special_response:
        return special_response

    context = build_context(docs)
    user_prompt = build_user_prompt(context, payload.message)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    answer = clean_answer(generate_hf_chat(messages))
    sources = [doc.metadata.get("title", "Untitled") for doc in docs]

    return ChatResponse(
        answer=answer,
        sources=sources,
        session_id=payload.session_id,
        section_hint=section_hint,
        suggested_cta=build_cta(section_hint),
        structured_data=None,
    )