"""
Generates a tailored cover letter and resume-tailoring tips for one specific
job, using the CV's parsed data plus the matcher's matched/missing skills.

This is template-based, not an LLM call: ApplyPilot ships with zero API keys
and works fully offline. The templates are chosen by role category (detected
from the job title/tags) and filled in with the candidate's own matched
skills and experience, so the output is genuinely specific to that CV +
that job, not generic boilerplate repeated for every application.
"""
from __future__ import annotations

from datetime import date

from .cv_parser import ParsedCV
from .matcher import JobMatch

ROLE_VALUE_PROPS = {
    "engineering": "building reliable, well-tested software and shipping features that hold up in production",
    "data": "turning raw data into decisions, from exploratory analysis through to production pipelines",
    "design": "designing interfaces that are both easy to use and a pleasure to look at",
    "product": "translating user needs and business goals into a roadmap the whole team can rally behind",
    "marketing": "growing audiences and pipeline through campaigns that are measured, not just launched",
    "sales": "building relationships that turn into long-term revenue, not just closed-won deals",
    "finance": "bringing rigor and clarity to numbers that other people make decisions on",
    "general": "bringing consistent, dependable execution to everything I take on",
}

ROLE_KEYWORDS = {
    "engineering": ["engineer", "developer", "software", "backend", "frontend", "full stack", "devops", "sre"],
    "data": ["data scientist", "data analyst", "data engineer", "machine learning", "analytics", "bi "],
    "design": ["designer", "ux", "ui", "product design"],
    "product": ["product manager", "product owner"],
    "marketing": ["marketing", "seo", "growth", "content"],
    "sales": ["sales", "account executive", "business development", "bdr", "sdr"],
    "finance": ["finance", "accountant", "financial analyst", "controller"],
}


def _detect_role_category(job_title: str, tags: list[str]) -> str:
    haystack = f"{job_title} {' '.join(tags)}".lower()
    for category, keywords in ROLE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return category
    return "general"

def generate_cover_letter(cv: ParsedCV, match: JobMatch) -> str:
    job = match.job
    candidate_name = cv.name or "[Your Name]"
    role_category = _detect_role_category(job.title, job.tags)
    value_prop = ROLE_VALUE_PROPS[role_category]

    top_matched = match.matched_skills[:5]
    skills_sentence = (
        f"In particular, my experience with {', '.join(top_matched[:-1])}"
        f"{' and ' + top_matched[-1] if len(top_matched) > 1 else top_matched[0] if top_matched else ''} "
        "lines up directly with what you're looking for."
        if top_matched
        else "I'd welcome the chance to walk through how my background lines up with this role."
    )

    experience_sentence = (
        f"With {cv.years_experience}+ years of hands-on experience, "
        if cv.years_experience
        else "Across my career so far, "
    )

    today = date.today().strftime("%B %d, %Y")

    letter = f"""{today}

Dear {job.company} Hiring Team,

I'm writing to apply for the {job.title} role at {job.company}. {experience_sentence}I've focused on {value_prop}, and this opening looks like a strong match for where I want to keep growing.

{skills_sentence}

What draws me to this specific role is the chance to apply that background somewhere it can have real impact - not just add another line to a resume. I'd welcome the opportunity to talk through how I could contribute to your team.

Thank you for your time and consideration.

Sincerely,
{candidate_name}
""".strip()

    return letter


def generate_tailoring_tips(cv: ParsedCV, match: JobMatch) -> list[str]:
    tips = []
    if match.matched_skills:
        tips.append(
            f"Move these matched skills higher in your Skills section or first bullet of your most "
            f"relevant role: {', '.join(match.matched_skills[:6])}."
        )
    if match.missing_skills:
        tips.append(
            "This posting also mentions: " + ", ".join(match.missing_skills[:6]) +
            ". If you genuinely have experience with any of these, add them explicitly - ATS "
            "keyword matching rewards exact terms, not synonyms."
        )
    if cv.years_experience is None:
        tips.append(
            "Consider stating your total years of experience explicitly near the top of your resume "
            "or in your summary - many ATS filters screen on this number directly."
        )
    title_words = [w.lower() for w in match.job.title.split()]
    if cv.raw_text and not any(w in cv.raw_text.lower() for w in title_words if len(w) > 3):
        tips.append(
            f"Your resume doesn't currently contain the exact phrase \"{match.job.title}\". "
            "Consider echoing the job title's own wording somewhere in your summary or most recent role."
        )
    if not tips:
        tips.append("This resume already covers this job's key requirements well - no major changes needed.")
    return tips

