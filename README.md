# ApplyPilot

**Upload your resume, find the jobs you're actually qualified for, and walk into every application prepared — not blindly spammed.**

ApplyPilot parses any resume (PDF, DOCX, or TXT), scores it against what ATS software and recruiters actually look for, searches live public job boards, ranks every listing against *your* specific skills, and generates a tailored cover letter plus concrete tailoring tips for each one. It also tracks every application through a saved → applied → interviewing → offer pipeline.

It runs entirely on your own machine. No account, no API keys, no data ever leaves your computer except the job search requests themselves.

---

## Why there's no "auto-apply" button

A version of this project could try to auto-submit applications on your behalf. It doesn't, on purpose:

- Most job boards and ATS platforms (Greenhouse, Lever, Workday, LinkedIn Easy Apply, etc.) explicitly prohibit automated submission in their Terms of Service — a bot that does this can get your account or IP banned.
- Blind auto-apply produces low-quality, generic applications at scale, which is exactly what burns your reputation with recruiters and wastes everyone's time.
- You should see and approve what's being said on your behalf before it goes out.

Instead, ApplyPilot does the **prepare + open for you** model: it does all the hard work (finding the job, checking the fit, writing a tailored cover letter, telling you exactly what to tweak on your resume) and then opens the real application page for you to review and submit in one click. You stay in control; ApplyPilot just removes the busywork.

---

## Features

- **Resume parsing** — PDF, DOCX, and TXT support. Extracts contact info, skills (140+ recognized skills across 11 categories), years of experience, education, and section structure.
- **ATS/resume scoring** — a transparent 0–100 score across five weighted categories (contact completeness, skill coverage, structure, bullet-point impact, length), with specific, actionable suggestions and a list of what's already strong. Fully rule-based and deterministic — every point is explainable, nothing is a black box.
- **Live job search** — pulls real, current listings from Remotive and Arbeitnow, two free public job board APIs that need no signup or key.
- **Smart matching** — ranks every job against your resume using a blend of TF-IDF text similarity and explicit skill-overlap scoring, and shows exactly which skills matched and which are missing for each listing — not just a mystery percentage.
- **Tailored cover letters** — generated per job from your actual matched skills, detected role category, and years of experience. Not the same boilerplate letter re-used for every application.
- **Resume tailoring tips** — per-job, concrete suggestions: which of your skills to surface higher, which genuinely-held skills to add, whether to state your years of experience, whether to echo the job title's own wording.
- **Application tracker** — a lightweight local "mini-ATS" (SQLite) that tracks every job you've saved or prepared, with a status pipeline (Saved → Prepared → Applied → Interviewing → Offer/Rejected) and a Kanban-style board.
- **Works for anyone** — this isn't wired to any one person's resume. Upload your own, or click "Try sample resume" to see it in action first.

---

## Quick start

Requires **Python 3.10+**.

```bash
# 1. Clone the repo
git clone https://github.com/Rahilakbar22/applypilot.git
cd applypilot

# 2. (Recommended) create a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run it
uvicorn backend.main:app --reload

# 5. Open your browser to:
#    http://127.0.0.1:8000
```

That's it — no database setup, no API keys, no config file. The SQLite tracker database (`applypilot.db`) is created automatically on first run.

### Try it instantly

Click **"Try sample resume"** on the first screen to see a full run-through (parsing, scoring, job matching, cover letter generation) using a bundled sample resume, before uploading your own.

---

## How it works

1. **`backend/cv_parser.py`** extracts raw text (via `pdfplumber` / `python-docx`) and pulls out contact info, skills, years of experience, and section structure using regex + a curated skill taxonomy (word-boundary matched, so short tokens like "R" or "Go" don't false-positive inside other words).
2. **`backend/cv_analyzer.py`** scores the parsed resume across 5 weighted categories and generates specific suggestions — this is intentionally rule-based, not an LLM call, so every point lost is traceable to a concrete cause.
3. **`backend/job_sources.py`** fetches live listings from Remotive and Arbeitnow's public APIs, merges and deduplicates them.
4. **`backend/matcher.py`** ranks jobs against your CV with a blend of TF-IDF cosine similarity (overall topical fit) and explicit skill-overlap scoring (exact keyword fit), and reports matched vs. missing skills per job.
5. **`backend/cover_letter.py`** generates a tailored cover letter and tailoring tips per job, template-based and filled in with your actual matched skills and detected role category — no LLM, no API key, fully offline.
6. **`backend/database.py`** persists your application tracker in a local SQLite file so it survives restarts.
7. **`frontend/`** is a dependency-free vanilla JS single-page app (no build step) that ties it all together with a 3-tab flow: Your CV → Find Jobs → Tracker.

---

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn
- **CV parsing:** `pdfplumber` (PDF), `python-docx` (DOCX)
- **Matching:** `scikit-learn` (TF-IDF + cosine similarity)
- **Job data:** Remotive and Arbeitnow public APIs
- **Storage:** SQLite (stdlib `sqlite3`, no ORM)
- **Frontend:** vanilla HTML/CSS/JS, no framework, no build step

## Limitations, honestly

- **CV storage is in-memory.** Uploaded/parsed resumes live in server memory (`CV_STORE`) and reset if you restart the server — re-upload after a restart. The application *tracker*, by contrast, is persisted to SQLite and survives restarts.
- **Job coverage depends on two free public APIs.** Remotive skews remote/tech roles; Arbeitnow skews broader/European listings. Coverage for some industries or regions will be thinner than a paid job aggregator. The `job_sources.py` module is written so adding another source (Adzuna, USAJobs, Jooble, etc.) is a single new function.
- **Skill/role detection is keyword-based, not a language model.** It's fast, transparent, and fully offline, but it won't catch every synonym or unusual phrasing — the taxonomy in `skills_taxonomy.py` is easy to extend if you want to broaden it.
- **This is a single-user local tool** — there's no login system or multi-user support by design, since it's meant to run on your own machine.
- **No auto-apply**, deliberately — see the section above.

## Extending it

- Add more skills or categories: `backend/skills_taxonomy.py`
- Add another job source: `backend/job_sources.py` — add a `_fetch_from_x()` function returning `list[Job]` and plug it into `search_jobs()`
- Tune the match scoring weights: `SKILL_WEIGHT` / `TEXT_SIMILARITY_WEIGHT` in `backend/matcher.py`
- Add a new cover-letter role category: `ROLE_VALUE_PROPS` / `ROLE_KEYWORDS` in `backend/cover_letter.py`

## License

MIT — see [LICENSE](LICENSE).

