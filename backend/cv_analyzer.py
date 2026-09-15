"""
Rule-based ATS / resume-quality analyzer.

Produces a 0-100 score across five weighted categories plus a prioritized,
concrete list of suggestions. This is intentionally transparent and
deterministic (no black-box model) so every point lost is explainable.
"""
from dataclasses import dataclass, field

from .cv_parser import ParsedCV
from .skills_taxonomy import STRONG_VERBS, WEAK_PHRASES

IDEAL_WORD_RANGE = (350, 900)  # roughly one to two pages of prose


@dataclass
class ScoreBreakdown:
    category: str
    points: float
    max_points: float
    detail: str


@dataclass
class CVAnalysis:
    overall_score: int
    breakdown: list[ScoreBreakdown]
    suggestions: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "breakdown": [
                {
                    "category": b.category,
                    "points": round(b.points, 1),
                    "max_points": b.max_points,
                    "detail": b.detail,
                }
                for b in self.breakdown
            ],
            "suggestions": self.suggestions,
            "strengths": self.strengths,
        }

def analyze_cv(cv: ParsedCV) -> CVAnalysis:
    breakdown: list[ScoreBreakdown] = []
    suggestions: list[str] = []
    strengths: list[str] = []

    # 1. Contact completeness (15 pts)
    contact_points = 0.0
    missing_contact = []
    if cv.email:
        contact_points += 6
    else:
        missing_contact.append("email address")
    if cv.phone:
        contact_points += 4
    else:
        missing_contact.append("phone number")
    if cv.linkedin:
        contact_points += 3
    else:
        missing_contact.append("LinkedIn URL")
    if cv.github:
        contact_points += 2
    if missing_contact:
        suggestions.append(f"Add your {', '.join(missing_contact)} near the top so recruiters and ATS parsers can find them instantly.")
    else:
        strengths.append("Contact details are complete and easy to find.")
    breakdown.append(ScoreBreakdown("Contact info", contact_points, 15, f"{len(missing_contact)} field(s) missing"))

    # 2. Skills coverage (20 pts)
    skill_count = len(cv.skills)
    skill_points = min(20.0, skill_count * 1.2)
    if skill_count < 8:
        suggestions.append(
            f"Only {skill_count} recognizable skills were found. List your tools, languages, "
            "and platforms explicitly (a dedicated Skills section helps ATS keyword matching a lot)."
        )
    else:
        strengths.append(f"Strong, diverse skill footprint detected ({skill_count} skills across {len(cv.skills_by_category)} categories).")
    breakdown.append(ScoreBreakdown("Skills coverage", skill_points, 20, f"{skill_count} skills detected"))

    # 3. Structure / sections (20 pts)
    expected_sections = {"experience", "education", "skills"}
    found_lower = {s for s in cv.sections_found}
    has_experience = any("experience" in s for s in found_lower)
    has_education = "education" in found_lower
    has_skills = any("skill" in s for s in found_lower)
    section_points = 0.0
    missing_sections = []
    if has_experience:
        section_points += 8
    else:
        missing_sections.append("Experience")
    if has_education:
        section_points += 6
    else:
        missing_sections.append("Education")
    if has_skills:
        section_points += 6
    else:
        missing_sections.append("Skills")
    if missing_sections:
        suggestions.append(
            f"Add clearly labeled section header(s) for: {', '.join(missing_sections)}. "
            "Standard headers are what ATS software looks for to parse your resume correctly."
        )
    else:
        strengths.append("All core sections (Experience, Education, Skills) are clearly labeled.")
    breakdown.append(ScoreBreakdown("Structure", section_points, 20, f"{len(missing_sections)} section(s) missing"))

    # 4. Bullet point impact: strong verbs vs weak phrases, quantified results (30 pts)
    bullets = cv.bullet_lines
    bullet_points = 0.0
    if bullets:
        strong_count = sum(
            1 for b in bullets if b.strip().split(" ")[0].lower().rstrip(",:") in STRONG_VERBS
        )
        weak_count = sum(1 for b in bullets if any(b.lower().startswith(w) for w in WEAK_PHRASES))
        quantified_count = sum(1 for b in bullets if any(ch.isdigit() for ch in b) or "%" in b)

        strong_ratio = strong_count / len(bullets)
        quantified_ratio = quantified_count / len(bullets)

        bullet_points += min(15.0, strong_ratio * 15)
        bullet_points += min(15.0, quantified_ratio * 15)

        if weak_count:
            examples = ", ".join(f'"{w}"' for w in WEAK_PHRASES if any(b.lower().startswith(w) for b in bullets))
            suggestions.append(
                f"{weak_count} bullet(s) open with a weak phrase (e.g. {examples[:80]}...). "
                f"Rewrite them to start with a strong action verb like "
                f"\"{STRONG_VERBS[0]}\", \"{STRONG_VERBS[2]}\", or \"{STRONG_VERBS[8]}\"."
            )
        if quantified_ratio < 0.3:
            suggestions.append(
                "Fewer than a third of your bullet points include a number, percentage, or metric. "
                "Quantified results (\"cut load time by 40%\", \"managed a $2M budget\") are what make a resume stand out."
            )
        else:
            strengths.append("Good use of quantified, measurable results in your bullet points.")
        if strong_ratio >= 0.5:
            strengths.append("Most bullet points lead with strong action verbs.")
    else:
        suggestions.append(
            "No bullet points were detected. Use \"-\" or bullet characters under each role to list "
            "achievements - ATS systems and recruiters both expect scannable bullets, not paragraphs."
        )
    breakdown.append(ScoreBreakdown("Bullet point impact", bullet_points, 30, f"{len(bullets)} bullets analyzed"))

    # 5. Length (15 pts)
    wc = cv.word_count
    low, high = IDEAL_WORD_RANGE
    if low <= wc <= high:
        length_points = 15.0
        strengths.append("Resume length is in the ideal one-to-two-page range.")
    elif wc < low:
        length_points = max(0.0, 15 * (wc / low))
        suggestions.append(
            f"At ~{wc} words, this resume may be too thin. Add more detail to your experience "
            "bullets and consider including a Projects or Achievements section."
        )
    else:
        overflow_ratio = min(1.0, (wc - high) / high)
        length_points = max(0.0, 15 * (1 - overflow_ratio))
        suggestions.append(
            f"At ~{wc} words, this resume is likely running past two pages. Trim older or less "
            "relevant experience and tighten bullet points to one line each."
        )
    breakdown.append(ScoreBreakdown("Length", length_points, 15, f"~{wc} words"))

    overall = sum(b.points for b in breakdown)
    overall_score = round(overall)

    # Cap suggestions to the most impactful, keep it actionable rather than overwhelming.
    return CVAnalysis(
        overall_score=overall_score,
        breakdown=breakdown,
        suggestions=suggestions[:8],
        strengths=strengths[:6],
    )

