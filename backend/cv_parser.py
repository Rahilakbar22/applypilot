"""
CV parsing: turns an uploaded PDF / DOCX / TXT resume into structured data
(raw text, contact info, detected skills, years of experience, education,
and section boundaries) that the rest of ApplyPilot builds on.

No external NLP models are used on purpose - everything here is regex and
keyword-taxonomy based, so parsing is instant, dependency-light, and fully
offline (no API keys, no network calls).
"""
import io
import re
from dataclasses import dataclass, field

import docx
import pdfplumber

from .skills_taxonomy import ALL_SKILLS, EDUCATION_KEYWORDS, find_skills_in_text

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{3,4}")
LINKEDIN_RE = re.compile(r"(linkedin\.com/in/[A-Za-z0-9\-_/]+)")
GITHUB_RE = re.compile(r"(github\.com/[A-Za-z0-9\-_/]+)")
YEARS_EXPERIENCE_RE = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", re.I)

SECTION_HEADERS = [
    "experience", "work experience", "professional experience", "employment history",
    "education", "skills", "technical skills", "projects", "certifications",
    "summary", "objective", "profile", "achievements", "awards", "publications",
]


@dataclass
class ParsedCV:
    raw_text: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    skills: list[str] = field(default_factory=list)
    skills_by_category: dict[str, list[str]] = field(default_factory=dict)
    years_experience: int | None = None
    education_lines: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)
    bullet_lines: list[str] = field(default_factory=list)
    word_count: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "linkedin": self.linkedin,
            "github": self.github,
            "skills": self.skills,
            "skills_by_category": self.skills_by_category,
            "years_experience": self.years_experience,
            "education_lines": self.education_lines,
            "sections_found": self.sections_found,
            "word_count": self.word_count,
        }


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Dispatch to the right extractor based on file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _extract_pdf(file_bytes)
    if lower.endswith(".docx"):
        return _extract_docx(file_bytes)
    if lower.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {filename}. Use PDF, DOCX, or TXT.")


def _extract_pdf(file_bytes: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_docx(file_bytes: bytes) -> str:
    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs)

def _guess_name(lines: list[str]) -> str | None:
    """Heuristic: the first non-empty line that looks like a human name
    (2-4 title-cased words, no digits, no @, not a section header)."""
    for line in lines[:6]:
        candidate = line.strip()
        if not candidate or "@" in candidate:
            continue
        if candidate.lower() in SECTION_HEADERS:
            continue
        words = candidate.split()
        if 1 < len(words) <= 4 and not any(ch.isdigit() for ch in candidate):
            if sum(w[0].isupper() for w in words if w) >= len(words) - 1:
                return candidate
    return None


def _find_skills(text_lower: str) -> tuple[list[str], dict[str, list[str]]]:
    found = find_skills_in_text(text_lower)
    by_category: dict[str, list[str]] = {}
    for skill in found:
        by_category.setdefault(ALL_SKILLS[skill], []).append(skill)
    for category in by_category:
        by_category[category].sort()
    return sorted(found), by_category


def _find_years_experience(text: str) -> int | None:
    matches = YEARS_EXPERIENCE_RE.findall(text)
    if not matches:
        return None
    return max(int(m) for m in matches)


def _find_bullets(lines: list[str]) -> list[str]:
    bullets = []
    for line in lines:
        stripped = line.strip()
        if stripped[:1] in ("-", "*", "•", "◦", "‣") or re.match(r"^\d+[.)]\s", stripped):
            cleaned = re.sub(r"^[-*•◦‣]\s*|^\d+[.)]\s*", "", stripped)
            if cleaned:
                bullets.append(cleaned)
    return bullets


def parse_cv(filename: str, file_bytes: bytes) -> ParsedCV:
    raw_text = extract_text(filename, file_bytes)
    if not raw_text.strip():
        raise ValueError(
            "Couldn't extract any text from this file. If it's a scanned/image PDF, "
            "try exporting a text-based PDF or DOCX instead."
        )

    lines = [l for l in raw_text.splitlines()]
    non_empty_lines = [l for l in lines if l.strip()]
    text_lower = raw_text.lower()

    email_match = EMAIL_RE.search(raw_text)
    phone_match = PHONE_RE.search(raw_text)
    linkedin_match = LINKEDIN_RE.search(text_lower)
    github_match = GITHUB_RE.search(text_lower)

    skills, skills_by_category = _find_skills(text_lower)
    sections_found = [h for h in SECTION_HEADERS if re.search(rf"\b{re.escape(h)}\b", text_lower)]
    education_lines = [
        l.strip() for l in non_empty_lines
        if any(kw in l.lower() for kw in EDUCATION_KEYWORDS)
    ]

    return ParsedCV(
        raw_text=raw_text,
        name=_guess_name(non_empty_lines),
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0).strip() if phone_match else None,
        linkedin=linkedin_match.group(1) if linkedin_match else None,
        github=github_match.group(1) if github_match else None,
        skills=skills,
        skills_by_category=skills_by_category,
        years_experience=_find_years_experience(raw_text),
        education_lines=education_lines[:5],
        sections_found=sections_found,
        bullet_lines=_find_bullets(non_empty_lines),
        word_count=len(raw_text.split()),
    )

