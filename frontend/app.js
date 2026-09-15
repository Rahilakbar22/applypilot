(function () {
  "use strict";

  /* ---------------- Theme ---------------- */
  function setTheme(mode) {
    document.documentElement.setAttribute("data-theme", mode);
    document.getElementById("theme-light").setAttribute("aria-pressed", String(mode === "light"));
    document.getElementById("theme-dark").setAttribute("aria-pressed", String(mode === "dark"));
    try { localStorage.setItem("applypilot-theme", mode); } catch (e) {}
  }
  document.getElementById("theme-light").addEventListener("click", () => setTheme("light"));
  document.getElementById("theme-dark").addEventListener("click", () => setTheme("dark"));
  (function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem("applypilot-theme"); } catch (e) {}
    if (saved === "light" || saved === "dark") setTheme(saved);
  })();

  /* ---------------- Toast ---------------- */
  let toastTimer = null;
  function toast(msg) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
  }

  /* ---------------- Tabs ---------------- */
  const tabs = {
    cv: { btn: document.getElementById("tab-cv"), panel: document.getElementById("panel-cv") },
    jobs: { btn: document.getElementById("tab-jobs"), panel: document.getElementById("panel-jobs") },
    tracker: { btn: document.getElementById("tab-tracker"), panel: document.getElementById("panel-tracker") },
  };
  function showTab(name) {
    Object.entries(tabs).forEach(([key, t]) => {
      const active = key === name;
      t.btn.setAttribute("aria-selected", String(active));
      t.panel.hidden = !active;
    });
    if (name === "tracker") loadTracker();
  }
  tabs.cv.btn.addEventListener("click", () => showTab("cv"));
  tabs.jobs.btn.addEventListener("click", () => showTab("jobs"));
  tabs.tracker.btn.addEventListener("click", () => showTab("tracker"));
  document.getElementById("btn-goto-jobs").addEventListener("click", () => showTab("jobs"));
  document.getElementById("link-back-to-cv").addEventListener("click", (e) => { e.preventDefault(); showTab("cv"); });

  /* ---------------- State ---------------- */
  let state = {
    cvId: null,
    cvParsed: null,
    lastJobs: [], // most recent search results, keyed by id for the modal lookup
  };

  /* ---------------- CV upload ---------------- */
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); } });
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadCv(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", () => { if (fileInput.files.length) uploadCv(fileInput.files[0]); });

  document.getElementById("btn-sample").addEventListener("click", async () => {
    setUploadStatus("Loading sample resume…", true);
    try {
      const resp = await fetch("/api/sample-resume");
      if (!resp.ok) throw new Error("Sample resume not available");
      const blob = await resp.blob();
      const file = new File([blob], "sample_resume.txt", { type: "text/plain" });
      uploadCv(file);
    } catch (err) {
      setUploadStatus("Couldn't load the sample resume.", false);
    }
  });

  function setUploadStatus(msg, loading) {
    const el = document.getElementById("upload-status");
    el.innerHTML = loading ? `<span class="spinner dark"></span> ${msg}` : msg;
  }

  async function uploadCv(file) {
    setUploadStatus(`Parsing ${file.name}…`, true);
    const form = new FormData();
    form.append("file", file);
    try {
      const resp = await fetch("/api/cv/upload", { method: "POST", body: form });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Upload failed");
      state.cvId = data.cv_id;
      state.cvParsed = data.parsed;
      renderCvResults(data.parsed, data.analysis);
      setUploadStatus(`✓ Parsed ${file.name}`, false);
      document.getElementById("no-cv-note").hidden = true;
      toast("Resume analyzed");
    } catch (err) {
      setUploadStatus(`Error: ${err.message}`, false);
      toast("Couldn't parse that file");
    }
  }

  function renderCvResults(parsed, analysis) {
    document.getElementById("cv-results").hidden = false;
    document.getElementById("cv-name-display").textContent = parsed.name || "Your resume";
    const yrs = parsed.years_experience ? `${parsed.years_experience}+ years experience · ` : "";
    document.getElementById("cv-summary-line").textContent =
      `${yrs}${parsed.skills.length} skills detected · ${parsed.word_count} words`;

    const ring = document.getElementById("score-ring");
    ring.style.setProperty("--pct", analysis.overall_score);
    document.getElementById("score-value").textContent = analysis.overall_score;

    const breakdownEl = document.getElementById("score-breakdown");
    breakdownEl.innerHTML = "";
    analysis.breakdown.forEach((b) => {
      const pct = Math.round((b.points / b.max_points) * 100);
      const div = document.createElement("div");
      div.className = "breakdown-item";
      div.innerHTML = `
        <div class="breakdown-cat">${escapeHtml(b.category)}</div>
        <div class="breakdown-bar"><div style="width:${pct}%"></div></div>
        <div class="breakdown-detail">${escapeHtml(b.detail)} · ${Math.round(b.points)}/${b.max_points}</div>`;
      breakdownEl.appendChild(div);
    });

    const sugg = document.getElementById("suggestions-list");
    sugg.innerHTML = analysis.suggestions.length
      ? analysis.suggestions.map((s) => `<li>${escapeHtml(s)}</li>`).join("")
      : "<li>No major issues found.</li>";
    const strengths = document.getElementById("strengths-list");
    strengths.innerHTML = analysis.strengths.length
      ? analysis.strengths.map((s) => `<li>${escapeHtml(s)}</li>`).join("")
      : "<li>—</li>";

    document.getElementById("skills-count-desc").textContent =
      `${parsed.skills.length} skills recognized across ${Object.keys(parsed.skills_by_category).length} categories.`;
    const chipRow = document.getElementById("skills-chip-row");
    chipRow.innerHTML = parsed.skills.length
      ? parsed.skills.map((s) => `<span class="chip">${escapeHtml(s)}</span>`).join("")
      : "<span class=\"card-desc\">No recognizable skills found — try adding a dedicated Skills section.</span>";
  }

  /* ---------------- Job search ---------------- */
  document.getElementById("btn-search").addEventListener("click", runSearch);
  document.getElementById("search-query").addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });
  document.getElementById("search-location").addEventListener("keydown", (e) => { if (e.key === "Enter") runSearch(); });

  async function runSearch() {
    const query = document.getElementById("search-query").value.trim();
    const location = document.getElementById("search-location").value.trim();
    const resultsEl = document.getElementById("jobs-results");
    resultsEl.innerHTML = `<div class="empty-state"><span class="spinner dark"></span> Searching live job boards…</div>`;
    document.getElementById("no-cv-note").hidden = !!state.cvId;

    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (location) params.set("location", location);
    if (state.cvId) params.set("cv_id", state.cvId);

    try {
      const resp = await fetch(`/api/jobs/search?${params.toString()}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Search failed");
      state.lastJobs = data.jobs;
      renderJobs(data.jobs);
    } catch (err) {
      resultsEl.innerHTML = `<div class="empty-state">Search failed: ${escapeHtml(err.message)}. The job boards may be temporarily unreachable — try again in a moment.</div>`;
    }
  }

  function renderJobs(jobs) {
    const resultsEl = document.getElementById("jobs-results");
    if (!jobs.length) {
      resultsEl.innerHTML = `<div class="empty-state">No jobs found for that search. Try a broader keyword or clear the location filter.</div>`;
      return;
    }
    resultsEl.innerHTML = jobs.map((job) => jobCardHtml(job)).join("");

    resultsEl.querySelectorAll("[data-action='prepare']").forEach((btn) => {
      btn.addEventListener("click", () => openPrepareModal(btn.dataset.jobId));
    });
    resultsEl.querySelectorAll("[data-action='quick-save']").forEach((btn) => {
      btn.addEventListener("click", () => quickSave(btn.dataset.jobId));
    });
  }

  function jobCardHtml(job) {
    const hasScore = typeof job.match_score === "number";
    const matched = (job.matched_skills || []).slice(0, 6).map((s) => `<span class="chip match">${escapeHtml(s)}</span>`).join("");
    const missing = (job.missing_skills || []).slice(0, 4).map((s) => `<span class="chip missing">${escapeHtml(s)}</span>`).join("");
    return `
      <div class="job-card">
        <div class="job-card-head">
          <div>
            <p class="job-title">${escapeHtml(job.title)}</p>
            <p class="job-meta">${escapeHtml(job.company)} · ${escapeHtml(job.location || "Not specified")} · ${escapeHtml(job.source)}</p>
          </div>
          ${hasScore ? `<div class="job-score"><div class="job-score-value">${Math.round(job.match_score)}%</div><div class="job-score-label">match</div></div>` : ""}
        </div>
        <p class="job-desc">${escapeHtml((job.description || "").slice(0, 280))}${job.description && job.description.length > 280 ? "…" : ""}</p>
        ${matched || missing ? `<div class="chip-row">${matched}${missing}</div>` : ""}
        <div class="job-actions">
          <button class="btn btn-primary btn-sm" data-action="prepare" data-job-id="${escapeAttr(job.id)}">Prepare application</button>
          <button class="btn btn-sm" data-action="quick-save" data-job-id="${escapeAttr(job.id)}">Save for later</button>
          <a class="btn btn-sm" href="${escapeAttr(job.url)}" target="_blank" rel="noopener">View posting ↗</a>
        </div>
      </div>`;
  }

  function findJobById(id) {
    return state.lastJobs.find((j) => j.id === id);
  }

  async function quickSave(jobId) {
    const job = findJobById(jobId);
    if (!job) return;
    try {
      await fetch("/api/tracker", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job, status: "saved" }),
      });
      toast("Saved to tracker");
      refreshTrackerBadge();
    } catch (err) {
      toast("Couldn't save that job");
    }
  }

  /* ---------------- Prepare-application modal ---------------- */
  const overlay = document.getElementById("modal-overlay");
  let currentModalJob = null;
  let currentLetter = "";

  document.getElementById("modal-close").addEventListener("click", closeModal);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
  function closeModal() { overlay.hidden = true; }

  async function openPrepareModal(jobId) {
    if (!state.cvId) {
      toast("Upload your CV first");
      showTab("cv");
      return;
    }
    const job = findJobById(jobId);
    if (!job) return;
    currentModalJob = job;

    document.getElementById("modal-job-title").textContent = `${job.title} at ${job.company}`;
    document.getElementById("modal-job-meta").textContent = job.location || "";
    document.getElementById("letter-box").textContent = "Generating your tailored cover letter…";
    document.getElementById("tailoring-tips").innerHTML = "";
    document.getElementById("btn-open-application").href = job.url || "#";
    overlay.hidden = false;

    try {
      const resp = await fetch("/api/apply/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_id: state.cvId, job }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || "Couldn't prepare application");
      currentLetter = data.cover_letter;
      document.getElementById("letter-box").textContent = data.cover_letter;
      document.getElementById("tailoring-tips").innerHTML = data.tailoring_tips.map((t) => `<li>${escapeHtml(t)}</li>`).join("");
    } catch (err) {
      document.getElementById("letter-box").textContent = `Error: ${err.message}`;
    }
  }

  document.getElementById("btn-copy-letter").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(currentLetter);
      toast("Cover letter copied");
    } catch (e) {
      toast("Couldn't copy — select and copy manually");
    }
  });

  document.getElementById("btn-download-letter").addEventListener("click", () => {
    const blob = new Blob([currentLetter], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cover-letter-${(currentModalJob?.company || "job").replace(/\s+/g, "-").toLowerCase()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById("btn-save-tracker").addEventListener("click", async () => {
    if (!currentModalJob) return;
    try {
      await fetch("/api/tracker", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job: currentModalJob, status: "prepared", cover_letter: currentLetter }),
      });
      toast("Saved to tracker as Prepared");
      refreshTrackerBadge();
    } catch (err) {
      toast("Couldn't save to tracker");
    }
  });

  /* ---------------- Tracker ---------------- */
  const STATUS_LABELS = {
    saved: "Saved", prepared: "Prepared", applied: "Applied",
    interviewing: "Interviewing", offer: "Offer", rejected: "Rejected",
  };
  const STATUS_ORDER = ["saved", "prepared", "applied", "interviewing", "offer", "rejected"];

  async function loadTracker() {
    const board = document.getElementById("tracker-board");
    board.innerHTML = `<div class="empty-state"><span class="spinner dark"></span> Loading tracker…</div>`;
    try {
      const resp = await fetch("/api/tracker");
      const data = await resp.json();
      renderTracker(data.jobs || []);
    } catch (err) {
      board.innerHTML = `<div class="empty-state">Couldn't load the tracker.</div>`;
    }
  }

  function renderTracker(jobs) {
    const board = document.getElementById("tracker-board");
    board.innerHTML = "";
    const badge = document.getElementById("tracker-count");
    badge.hidden = jobs.length === 0;
    badge.textContent = jobs.length;

    STATUS_ORDER.forEach((status) => {
      const col = document.createElement("div");
      col.className = "tracker-col";
      const jobsInStatus = jobs.filter((j) => j.status === status);
      col.innerHTML = `
        <div class="tracker-col-head"><span class="dot" style="background:var(--status-${status})"></span>${STATUS_LABELS[status]} (${jobsInStatus.length})</div>
        <div class="tracker-col-body"></div>`;
      const body = col.querySelector(".tracker-col-body");
      if (!jobsInStatus.length) {
        body.innerHTML = `<div class="tracker-empty">—</div>`;
      } else {
        jobsInStatus.forEach((job) => body.appendChild(trackerCardEl(job)));
      }
      board.appendChild(col);
    });
  }

  function trackerCardEl(job) {
    const div = document.createElement("div");
    div.className = "tracker-card";
    const scoreLine = job.match_score ? `${Math.round(job.match_score)}% match · ` : "";
    div.innerHTML = `
      <p class="tracker-card-title">${escapeHtml(job.title)}</p>
      <p class="tracker-card-meta">${scoreLine}${escapeHtml(job.company)}</p>
      <select aria-label="Status">
        ${STATUS_ORDER.map((s) => `<option value="${s}" ${s === job.status ? "selected" : ""}>${STATUS_LABELS[s]}</option>`).join("")}
      </select>
      <div class="tracker-card-actions">
        <a class="btn btn-sm" href="${escapeAttr(job.url || "#")}" target="_blank" rel="noopener">Open ↗</a>
        <button class="btn btn-sm" data-action="delete">Remove</button>
      </div>`;
    div.querySelector("select").addEventListener("change", async (e) => {
      await fetch(`/api/tracker/${encodeURIComponent(job.job_id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: e.target.value }),
      });
      loadTracker();
    });
    div.querySelector("[data-action='delete']").addEventListener("click", async () => {
      await fetch(`/api/tracker/${encodeURIComponent(job.job_id)}`, { method: "DELETE" });
      loadTracker();
    });
    return div;
  }

  async function refreshTrackerBadge() {
    try {
      const resp = await fetch("/api/tracker");
      const data = await resp.json();
      const badge = document.getElementById("tracker-count");
      badge.hidden = (data.jobs || []).length === 0;
      badge.textContent = (data.jobs || []).length;
    } catch (e) {}
  }

  /* ---------------- Utils ---------------- */
  function escapeHtml(str) {
    return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function escapeAttr(str) { return escapeHtml(str); }

  refreshTrackerBadge();
})();

