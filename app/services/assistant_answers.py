import calendar
from datetime import date

from app.services.assistant_core import (
    build_context,
    certifications_records,
    clean_answer,
    contact_summary_record,
    current_role_record,
    current_study_record,
    join_items,
    latest_relevant_turn,
    natural_out_of_scope,
    natural_unavailable,
    poor_answer,
    project_records,
    project_records_for_technology,
    project_technology_counts,
    raw_records,
    record_titles,
    serialize_history,
    stack_records,
    technology_records,
)
from app.services.llm import generate_hf_chat

SYSTEM_PROMPT = """You are the portfolio assistant for Alba Mora de la Sen.

Answer only with information that is supported by Alba's portfolio records.

Rules:
- Answer naturally and directly. Do not mention "retrieved context" or "the provided context".
- If the information is present, answer it clearly.
- If only part of the answer is present, answer only the supported part.
- If the information is not included in the portfolio, say that clearly and briefly.
- If the question is outside Alba's portfolio scope, politely redirect and say you can only help with Alba and her portfolio.
- Keep the answer concise by default.
- Reply in the same language as the user unless the user explicitly requests another language.
- Use conversation history when resolving follow-up references like "her", "that", "there", "current role", or "that project".
- Distinguish completed certifications from certifications in progress.
- Do not invent technologies, roles, employers, dates, responsibilities, certifications, or projects.
"""


def response_style_adjust(answer: str, style: str, language: str) -> str:
    text = clean_answer(answer)
    if style == "very_short":
        if language == "es":
            return "Alba se centra en desarrollo fullstack, IA y datos." if "focus" in text.lower() or "enfoc" in text.lower() else text.split(".")[0][:90].strip()
        return "Alba focuses on fullstack development, AI, and data." if "focus" in text.lower() else text.split(".")[0][:90].strip()
    if style == "one_sentence":
        return text.split(". ")[0].rstrip(".") + "."
    return text


def build_user_prompt(context: str, user_message: str, history_text: str, style: str, language: str) -> str:
    style_instruction = {
        "bullets": "Use concise bullet points.",
        "one_sentence": "Answer in exactly one sentence.",
        "very_short": "Answer in under 20 words if possible.",
        "concise": "Keep the answer very concise.",
        "default": "Keep the answer concise.",
    }[style]
    language_instruction = "Reply in Spanish." if language == "es" else "Reply in English."

    return f"""Portfolio history:
{history_text or "No previous turns."}

Portfolio facts:
{context}

Current user question:
{user_message}

Instructions:
- Answer only from the portfolio facts above.
- {style_instruction}
- {language_instruction}
- If the answer is missing, say so naturally.
- If the question is outside scope, redirect naturally.
"""


def background_answer(language: str) -> str:
    if language == "es":
        return (
            "Alba es Fullstack Developer y ahora mismo está centrada en desarrollo fullstack, inteligencia artificial y datos. "
            "Combina experiencia profesional en Siemens con formación en desarrollo web, análisis de datos y negocio."
        )
    return (
        "Alba is a Fullstack Developer currently focused on fullstack development, artificial intelligence, and data. "
        "She combines professional experience at Siemens with a background in web development, data analysis, and business."
    )


def current_focus_answer(language: str) -> str:
    return (
        "Alba ahora mismo está enfocada en desarrollo fullstack, inteligencia artificial y datos."
        if language == "es"
        else "Alba is currently focused on fullstack development, artificial intelligence, and data."
    )


def current_role_answer(language: str, style: str) -> str:
    if style == "bullets":
        if language == "es":
            return (
                "• Desarrolla y mantiene APIs backend con Python y Flask.\n"
                "• Construye y da soporte a aplicaciones internas con JavaScript.\n"
                "• Despliega aplicaciones con Docker, Kubernetes y Rancher UI.\n"
                "• Colabora en iniciativas de IA y datos."
            )
        return (
            "• Develops and maintains backend APIs with Python and Flask.\n"
            "• Builds and supports internal web applications with JavaScript.\n"
            "• Deploys applications with Docker, Kubernetes, and Rancher UI.\n"
            "• Contributes to AI and data initiatives."
        )

    if language == "es":
        return (
            "Alba trabaja actualmente como Software Developer Intern en Siemens Mobility S.L.U., donde desarrolla y mantiene APIs backend, "
            "da soporte a aplicaciones internas, participa en despliegues con Docker y Kubernetes, y colabora en iniciativas de IA y datos."
        )
    return (
        "Alba is currently working as a Software Developer Intern at Siemens Mobility S.L.U., where she develops and maintains backend APIs, "
        "supports internal applications, helps with Docker and Kubernetes deployments, and contributes to AI and data initiatives."
    )


def current_role_tasks_answer(language: str) -> str:
    return (
        "En el entorno Siemens EDA, Alba desarrolla y mantiene APIs backend, da soporte a aplicaciones internas y colabora con equipos técnicos en despliegues e iniciativas de IA y datos."
        if language == "es"
        else "In the Siemens EDA environment, Alba develops and maintains backend APIs, supports internal applications, and collaborates with technical teams on deployments and AI/data initiatives."
    )


def current_role_tech_answer(language: str) -> str:
    techs = current_role_record()["skills"]
    return (
        f"En su rol actual aparecen tecnologías como {join_items(techs, 'es')}."
        if language == "es"
        else f"In her current role, technologies mentioned include {join_items(techs, 'en')}."
    )


def experience_summary_answer(language: str) -> str:
    if language == "es":
        return (
            "Alba tiene experiencia profesional en Siemens Mobility S.L.U. en dos etapas. Actualmente trabaja como Software Developer Intern centrada en APIs backend, aplicaciones internas, despliegues e iniciativas de IA y datos; anteriormente trabajó más enfocada en front-end y UI."
        )
    return (
        "Alba has professional experience at Siemens Mobility S.L.U. across two internship periods. She is currently working on backend APIs, internal applications, deployments, and AI/data initiatives, and her earlier role was more focused on front-end and UI work."
    )


def projects_summary_answer(language: str) -> str:
    titles = record_titles(project_records())
    return (
        f"Alba ha desarrollado {len(titles)} proyectos en su portfolio: {join_items(titles, 'es')}."
        if language == "es"
        else f"Alba has built {len(titles)} portfolio projects: {join_items(titles, 'en')}."
    )


def project_technology_frequency_answer(language: str) -> str:
    top = project_technology_counts()
    return (
        f"Las tecnologías que más se repiten en los proyectos de Alba son {join_items(top, 'es')}."
        if language == "es"
        else f"The technologies that appear most often across Alba's projects are {join_items(top, 'en')}."
    )


def project_by_technology_answer(language: str, technology: str | None) -> str:
    if not technology:
        return natural_unavailable(language)
    matches = project_records_for_technology(technology)
    if not matches:
        return natural_unavailable(language)
    titles = record_titles(matches)
    return (
        f"Los proyectos relacionados con {technology} son {join_items(titles, 'es')}."
        if language == "es"
        else f"The projects related to {technology} are {join_items(titles, 'en')}."
    )


def stack_summary_answer(language: str) -> str:
    return (
        "El stack de Alba gira sobre todo en torno a desarrollo fullstack, IA y datos. Entre sus tecnologías principales están Python, React, Angular, JavaScript, TypeScript, PostgreSQL, Docker, LangChain, AWS y Kubernetes."
        if language == "es"
        else "Alba's stack is centered on fullstack development, AI, and data. Her main technologies include Python, React, Angular, JavaScript, TypeScript, PostgreSQL, Docker, LangChain, AWS, and Kubernetes."
    )


def stack_category_answer(language: str, category_key: str) -> str:
    title_map = {
        "stack_backend": "Backend technologies",
        "stack_frontend": "Frontend technologies",
        "stack_ai_data": "AI and data technologies",
        "stack_cloud_devops": "Cloud and DevOps technologies",
        "stack_databases": "Database technologies",
    }
    intros_en = {
        "stack_backend": "On the backend side, Alba works with",
        "stack_frontend": "On the frontend side, Alba works with",
        "stack_ai_data": "For AI and data work, Alba uses",
        "stack_cloud_devops": "For cloud and DevOps work, Alba uses",
        "stack_databases": "For databases, Alba works with",
    }
    intros_es = {
        "stack_backend": "En backend, Alba trabaja con",
        "stack_frontend": "En frontend, Alba trabaja con",
        "stack_ai_data": "En IA y datos, Alba trabaja con",
        "stack_cloud_devops": "En cloud y DevOps, Alba trabaja con",
        "stack_databases": "En bases de datos, Alba trabaja con",
    }
    record = next(record for record in stack_records() if record["title"] == title_map[category_key])
    return (
        f"{intros_es[category_key]} {join_items(record['skills'], 'es')}."
        if language == "es"
        else f"{intros_en[category_key]} {join_items(record['skills'], 'en')}."
    )


def technology_presence_answer(language: str, technology: str | None) -> str:
    if not technology:
        return natural_unavailable(language)
    matches = technology_records(technology)
    if not matches:
        return (
            f"{technology} no aparece en el portfolio de Alba."
            if language == "es"
            else f"{technology} is not included in Alba's portfolio."
        )
    project_matches = [record for record in matches if record["section"] == "projects"]
    role_matches = [record for record in matches if record["type"] in {"current_role", "anchor_current_role"}]
    stack_matches = [record for record in matches if record["section"] == "stack"]
    if language == "es":
        if role_matches:
            return f"Sí. {technology} forma parte del stack de Alba y también aparece en la información de su rol actual."
        if project_matches:
            return f"Sí. {technology} forma parte del stack de Alba y aparece en proyectos como {join_items(record_titles(project_matches[:2]), 'es')}."
        if stack_matches:
            return f"Sí. {technology} aparece explícitamente en el stack de Alba."
    else:
        if role_matches:
            return f"Yes. {technology} is part of Alba's stack and it is also mentioned in her current-role information."
        if project_matches:
            return f"Yes. {technology} is part of Alba's stack and it appears in projects such as {join_items(record_titles(project_matches[:2]), 'en')}."
        if stack_matches:
            return f"Yes. {technology} is explicitly listed in Alba's stack."
    return natural_unavailable(language)


def education_summary_answer(language: str) -> str:
    education = raw_records("education")
    items_en = [f"{record['title']} at {record.get('institution', record.get('subtitle', ''))}" for record in education]
    items_es = [f"{record['title']} en {record.get('institution', record.get('subtitle', ''))}" for record in education]
    return (
        f"La formación de Alba combina {join_items(items_es, 'es')}."
        if language == "es"
        else f"Alba's education combines {join_items(items_en, 'en')}."
    )


def current_study_answer(language: str) -> str:
    study = current_study_record()
    return (
        f"Alba está estudiando {study['title']} en {study['institution']} ({study['date_range']})."
        if language == "es"
        else f"Alba is currently studying {study['title']} at {study['institution']} ({study['date_range']})."
    )


def certifications_summary_answer(language: str) -> str:
    completed = next(record for record in certifications_records() if record["completed"])
    in_progress = next(record for record in certifications_records() if record["in_progress"])
    if language == "es":
        return f"Alba tiene una certificación completada y otra en progreso. Ya ha completado {completed['title']} ({completed['code']}) y actualmente está preparando {in_progress['title']} ({in_progress['code']})."
    return f"Alba has one completed certification and one in progress. She has completed {completed['title']} ({completed['code']}) and is currently preparing {in_progress['title']} ({in_progress['code']})."


def completed_certification_answer(language: str) -> str:
    certification = next(record for record in certifications_records() if record["completed"])
    return (
        f"La certificación que Alba ya ha completado es {certification['title']} ({certification['code']})."
        if language == "es"
        else f"The certification Alba has already completed is {certification['title']} ({certification['code']})."
    )


def in_progress_certification_answer(language: str) -> str:
    certification = next(record for record in certifications_records() if record["in_progress"])
    return (
        f"Alba está preparando {certification['title']} ({certification['code']})."
        if language == "es"
        else f"Alba is preparing {certification['title']} ({certification['code']})."
    )


def contact_answer(language: str) -> str:
    record = contact_summary_record()
    portfolio = next((link for link in record["links"] if "albamora.dev" in link), None)
    email = next((link for link in record["links"] if link.startswith("mailto:")), None)
    github = next((link for link in record["links"] if "github.com" in link), None)
    linkedin = next((link for link in record["links"] if "linkedin.com" in link), None)
    email_text = email.replace("mailto:", "") if email else None
    return (
        f"Puedes contactar con Alba a través de su portfolio ({portfolio}), por email ({email_text}), GitHub ({github}) o LinkedIn ({linkedin})."
        if language == "es"
        else f"You can contact Alba through her portfolio ({portfolio}), by email ({email_text}), on GitHub ({github}), or on LinkedIn ({linkedin})."
    )


def focus_preference_answer(language: str) -> str:
    return (
        "Ahora mismo, el foco de Alba está más alineado con fullstack, inteligencia artificial y datos que con cloud como eje principal."
        if language == "es"
        else "Right now, Alba's focus is more aligned with fullstack development, artificial intelligence, and data than with cloud as the primary emphasis."
    )


MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parse_month_token(value: str) -> int:
    return MONTHS[value.strip()[:3].lower()]


def _parse_date_range(date_range: str) -> tuple[date, date] | None:
    if " - " not in date_range:
        return None

    start_text, end_text = [part.strip() for part in date_range.split(" - ", 1)]
    start_parts = start_text.split()
    if len(start_parts) != 2:
        return None

    start_month = _parse_month_token(start_parts[0])
    start_year = int(start_parts[1])
    start_date = date(start_year, start_month, 1)

    if end_text.lower() == "present":
        return start_date, date.today()

    end_parts = end_text.split()
    if len(end_parts) != 2:
        return None

    end_month = _parse_month_token(end_parts[0])
    end_year = int(end_parts[1])
    last_day = calendar.monthrange(end_year, end_month)[1]
    end_date = date(end_year, end_month, last_day)
    return start_date, end_date


def _experience_duration_stats() -> tuple[date | None, int]:
    intervals: list[tuple[date, date]] = []
    for record in raw_records("experience"):
        parsed = _parse_date_range(record.get("date_range", ""))
        if parsed:
            intervals.append(parsed)

    if not intervals:
        return None, 0

    earliest_start = min(start for start, _ in intervals)
    total_days = sum((end - start).days + 1 for start, end in intervals)
    return earliest_start, total_days


def _format_date_for_answer(value: date, language: str) -> str:
    months_es = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    months_en = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    if language == "es":
        return f"{value.day} de {months_es[value.month - 1]} de {value.year}"
    return f"{months_en[value.month - 1]} {value.day}, {value.year}"


def experience_duration_answer(language: str) -> str:
    start_date, total_days = _experience_duration_stats()
    if not start_date or total_days <= 0:
        return natural_unavailable(language)

    approx_months = round(total_days / 30.44)
    as_of = _format_date_for_answer(date.today(), language)
    started = _format_date_for_answer(start_date, language)

    if language == "es":
        return (
            f"Alba empezó a trabajar como desarrolladora en {started}. "
            f"Sumando sus dos etapas en Siemens, acumula aproximadamente {approx_months} meses de experiencia profesional a fecha de {as_of}."
        )
    return (
        f"Alba started working as a developer in {started}. "
        f"Across her two Siemens periods, she has approximately {approx_months} months of professional experience as of {as_of}."
    )


def status_follow_up_answer(language: str, turns: list[dict]) -> str:
    last = latest_relevant_turn(turns)
    if not last:
        return natural_unavailable(language)
    mapping = {
        "current_role": "Es actual." if language == "es" else "It's current.",
        "current_role_tech": "Es actual." if language == "es" else "It's current.",
        "current_role_tasks": "Es actual." if language == "es" else "It's current.",
        "current_study": "Es actual." if language == "es" else "It's current.",
        "completed_certification": "Es una certificación ya completada." if language == "es" else "It's a completed certification.",
        "in_progress_certification": "Está en progreso." if language == "es" else "It's still in progress.",
    }
    return mapping.get(last["topic"], natural_unavailable(language))


def most_relevant_project_answer(language: str) -> str:
    return (
        "Si el foco es fullstack, IA y datos, uno de los proyectos más relevantes es AI Knowledge Assistant."
        if language == "es"
        else "If the focus is fullstack, AI, and data, one of the most relevant projects is AI Knowledge Assistant."
    )


def deterministic_answer(query: dict, turns: list[dict]) -> str | None:
    intent = query["intent"]
    language = query["language"]
    style = query["style"]
    technology = query["technology"]

    direct_answers = {
        "out_of_scope": natural_out_of_scope(language),
        "background": background_answer(language),
        "current_focus": current_focus_answer(language),
        "current_role": current_role_answer(language, style),
        "current_role_tasks": current_role_tasks_answer(language),
        "current_role_tech": current_role_tech_answer(language),
        "experience_duration": experience_duration_answer(language),
        "experience_summary": experience_summary_answer(language),
        "projects_summary": projects_summary_answer(language),
        "project_technology_frequency": project_technology_frequency_answer(language),
        "stack_summary": stack_summary_answer(language),
        "education_summary": education_summary_answer(language),
        "current_study": current_study_answer(language),
        "certifications_summary": certifications_summary_answer(language),
        "completed_certification": completed_certification_answer(language),
        "in_progress_certification": in_progress_certification_answer(language),
        "contact": contact_answer(language),
        "focus_preference": focus_preference_answer(language),
        "status_follow_up": status_follow_up_answer(language, turns),
        "most_relevant_project": most_relevant_project_answer(language),
    }
    if intent in direct_answers:
        return response_style_adjust(direct_answers[intent], style, language)
    if intent in {"stack_backend", "stack_frontend", "stack_ai_data", "stack_cloud_devops", "stack_databases"}:
        return response_style_adjust(stack_category_answer(language, intent), style, language)
    if intent == "technology_presence":
        return response_style_adjust(technology_presence_answer(language, technology), style, language)
    if intent == "project_by_technology":
        return response_style_adjust(project_by_technology_answer(language, technology), style, language)
    return None


def llm_answer(query: dict, docs, turns: list[dict]) -> str | None:
    prompt = build_user_prompt(
        context=build_context(docs),
        user_message=query["resolved_message"],
        history_text=serialize_history(turns),
        style=query["style"],
        language=query["language"],
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    answer = generate_hf_chat(messages)
    if not answer:
        return None
    cleaned = response_style_adjust(clean_answer(answer), query["style"], query["language"])
    return None if poor_answer(cleaned) else cleaned


def fallback_open_answer(query: dict, docs) -> str:
    language = query["language"]
    technology = query["technology"]
    if query["intent"] == "open_qa" and technology:
        return technology_presence_answer(language, technology)
    if docs:
        title = docs[0].metadata.get("title", "")
        summary = docs[0].metadata.get("summary") or docs[0].metadata.get("title", "")
        if language == "es":
            return f"La mejor coincidencia en el portfolio es {title}. {summary}"
        return f"The closest match in Alba's portfolio is {title}. {summary}"
    return natural_unavailable(language)
