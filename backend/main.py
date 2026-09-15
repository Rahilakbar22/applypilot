"""
ApplyPilot API - FastAPI backend.

Endpoints:
  POST   /api/cv/upload        upload a PDF/DOCX/TXT resume -> parsed data + ATS analysis
  GET    /api/jobs/search      search live job boards, optionally ranked against a CV
  POST   /api/apply/prepare    generate a tailored cover letter + tailoring tips for one job
  GET    /api/tracker          list every tracked application
  POST   /api/tracker          save/update a job in the tracker
  PATCH  /api/tracker/{job_id} update status/notes for a tracked job
  DELETE /api/tracker/{job_id} remove a tracked job

Parsed CVs live in an in-memory store keyed by a random cv_id (see CV_STORE
below) - there's no user-account system, this is a single-user local tool.
The application tracker is the one thing that's actually persisted, in
applypilot.db (SQLite), so your saved/applied jobs survive a server restart.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import database
from .cv_analyzer import analyze_cv
from .cv_parser import ParsedCV, parse_cv
from .job_sources import Job, search_jobs
from .cover_letter import generate_cover_letter, generate_tailoring_tips
from .matcher import JobMatch, rank_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("applypilot")

app = FastAPI(title="ApplyPilot", description="Your CV, matched to real jobs - and ready to apply.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CV_STORE: dict[str, ParsedCV] = {}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SAMPLE_RESUME_PATH = PROJECT_ROOT / "sample_data" / "sample_resume.txt"


@app.on_event("startup")
def _startup() -> None:
    database.init_db()

# ---------------------------------------------------------------- CV ----

@app.post("/api/cv/upload")
async def upload_cv(file: UploadFile = File(...)):
    file_bytes = await file.read()
    if len(file_bytes) > 8 * 1024 * 1024:
        raise HTTPException(400, "File too large (8MB max).")
    try:
        parsed = parse_cv(file.filename, file_bytes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    cv_id = uuid.uuid4().hex
    CV_STORE[cv_id] = parsed
    analysis = analyze_cv(parsed)

    return {
        "cv_id": cv_id,
        "parsed": parsed.to_dict(),
        "analysis": analysis.to_dict(),
    }


@app.get("/api/cv/{cv_id}")
def get_cv(cv_id: str):
    parsed = _require_cv(cv_id)
    return {"cv_id": cv_id, "parsed": parsed.to_dict(), "analysis": analyze_cv(parsed).to_dict()}


def _require_cv(cv_id: str) -> ParsedCV:
    parsed = CV_STORE.get(cv_id)
    if parsed is None:
        raise HTTPException(404, "Unknown cv_id - upload a resume first (it may have reset if the server restarted).")
    return parsed


# --------------------------------------------------------------- Jobs ----

@app.get("/api/jobs/search")
def search(query: str = "", location: str = "", cv_id: str | None = None):
    jobs: list[Job] = search_jobs(query=query, location=location)

    if cv_id:
        cv = _require_cv(cv_id)
        matches = rank_jobs(cv, jobs, top_n=40)
        return {"count": len(matches), "jobs": [m.to_dict() for m in matches]}

    # No CV yet - still useful as a plain job search.
    return {"count": len(jobs), "jobs": [j.to_dict() for j in jobs[:40]]}


# --------------------------------------------------------- Apply prep ----

class PrepareApplicationRequest(BaseModel):
    cv_id: str
    job: dict

@app.post("/api/apply/prepare")
def prepare_application(req: PrepareApplicationRequest):
    cv = _require_cv(req.cv_id)
    job = Job(
        id=req.job.get("id", uuid.uuid4().hex),
        source=req.job.get("source", "manual"),
        title=req.job.get("title", "Untitled role"),
        company=req.job.get("company", "Unknown company"),
        location=req.job.get("location", ""),
        url=req.job.get("url", ""),
        description=req.job.get("description", ""),
        tags=req.job.get("tags", []),
        salary=req.job.get("salary"),
        posted_at=req.job.get("posted_at"),
    )
    match = JobMatch(
        job=job,
        score=req.job.get("match_score", 0.0),
        matched_skills=req.job.get("matched_skills", []),
        missing_skills=req.job.get("missing_skills", []),
    )
    letter = generate_cover_letter(cv, match)
    tips = generate_tailoring_tips(cv, match)
    return {"cover_letter": letter, "tailoring_tips": tips, "apply_url": job.url}


# ------------------------------------------------------------ Tracker ----

class TrackJobRequest(BaseModel):
    job: dict
    status: str = "saved"
    cover_letter: str | None = None


class UpdateStatusRequest(BaseModel):
    status: str
    notes: str | None = None


@app.get("/api/tracker")
def list_tracker():
    return {"jobs": database.list_tracked_jobs()}


@app.post("/api/tracker")
def save_to_tracker(req: TrackJobRequest):
    try:
        row = database.upsert_tracked_job(req.job, status=req.status, cover_letter=req.cover_letter)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return row


@app.patch("/api/tracker/{job_id}")
def patch_status(job_id: str, req: UpdateStatusRequest):
    try:
        row = database.update_status(job_id, req.status, req.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if row is None:
        raise HTTPException(404, "Job not found in tracker.")
    return row


@app.delete("/api/tracker/{job_id}")
def remove_from_tracker(job_id: str):
    deleted = database.delete_tracked_job(job_id)
    if not deleted:
        raise HTTPException(404, "Job not found in tracker.")
    return {"deleted": True}


# ------------------------------------------------------------- Extras ----

@app.get("/api/sample-resume")
def sample_resume():
    if not SAMPLE_RESUME_PATH.exists():
        raise HTTPException(404, "Sample resume not bundled with this install.")
    return FileResponse(SAMPLE_RESUME_PATH, filename="sample_resume.txt", media_type="text/plain")


# Serve the frontend last, so it doesn't shadow the /api routes above.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

