"""
Ranks job listings against a parsed CV using a blend of:

  1. TF-IDF cosine similarity between the full CV text and each job description
     (captures overall topical/contextual overlap, not just exact keywords).
  2. Explicit skill-keyword overlap (captures the "do I actually have the tools
     this job asks for" signal, which recruiters and ATS systems weight heavily).

The two are combined into one 0-100 match score, and each job also reports
its matched vs. missing skills so the UI can explain *why* it ranked where
it did - no black box.
"""
from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .cv_parser import ParsedCV
from .job_sources import Job
from .skills_taxonomy import ALL_SKILLS, find_skills_in_text

SKILL_WEIGHT = 0.6
TEXT_SIMILARITY_WEIGHT = 0.4


@dataclass
class JobMatch:
    job: Job
    score: float
    matched_skills: list[str]
    missing_skills: list[str]

    def to_dict(self) -> dict:
        d = self.job.to_dict()
        d["match_score"] = round(self.score, 1)
        d["matched_skills"] = self.matched_skills
        d["missing_skills"] = self.missing_skills
        return d


def rank_jobs(cv: ParsedCV, jobs: list[Job], top_n: int = 25) -> list[JobMatch]:
    if not jobs:
        return []

    cv_skills = set(cv.skills)
    job_texts = [f"{j.title} {j.description} {' '.join(j.tags)}" for j in jobs]

    # TF-IDF similarity across the whole corpus (CV text + all job texts) so
    # the vectorizer's vocabulary and IDF weights reflect this exact batch.
    corpus = [cv.raw_text] + job_texts
    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(corpus)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    except ValueError:
        # Degenerate corpus (e.g. empty text) - fall back to zero similarity rather than crashing.
        similarities = [0.0] * len(jobs)

    matches: list[JobMatch] = []
    for job, text, similarity in zip(jobs, job_texts, similarities):
        job_skills = find_skills_in_text(text.lower()) | (set(job.tags) & set(ALL_SKILLS))
        matched = sorted(cv_skills & job_skills)
        missing = sorted(job_skills - cv_skills)

        if job_skills:
            skill_score = len(matched) / len(job_skills)
        else:
            skill_score = 0.0

        combined = (skill_score * SKILL_WEIGHT + similarity * TEXT_SIMILARITY_WEIGHT) * 100
        # Small bonus for having *some* matched skills at all, so a thin job
        # description with 1-2 exact tag matches doesn't get buried under noise.
        if matched:
            combined = min(100.0, combined + 3)

        matches.append(JobMatch(job=job, score=combined, matched_skills=matched, missing_skills=missing[:8]))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:top_n]

