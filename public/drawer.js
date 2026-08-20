/* Detail drawer, shortlist toggle, toasts, Shortlist-view export rendering. */
MI.drawer = {};

/* ---------- wiring ---------- */

MI.drawer.wire = function wire() {
  MI.el("drawer-close").addEventListener("click", MI.drawer.closeDetail);
  MI.el("drawer-overlay").addEventListener("click", MI.drawer.closeDetail);
  MI.el("drawer-prev").addEventListener("click", () => MI.drawer.stepDetail(-1));
  MI.el("drawer-next").addEventListener("click", () => MI.drawer.stepDetail(1));
  MI.el("shortlist-export-btn").addEventListener("click", () => {
    const session = MI.extras.currentShortlistSession();
    if (session) MI.drawer.exportSession(session.id);
  });
  document.addEventListener("keydown", (ev) => {
    if (MI.el("detail-drawer").classList.contains("hidden")) return;
    if (ev.key === "Escape") MI.drawer.closeDetail();
    if (ev.key === "ArrowUp") MI.drawer.stepDetail(-1);
    if (ev.key === "ArrowDown") MI.drawer.stepDetail(1);
  });
  document.addEventListener("click", (ev) => {
    const shortlistBtn = ev.target.closest(".btn-shortlist");
    if (shortlistBtn) { MI.drawer.toggleShortlist(shortlistBtn.dataset.id, shortlistBtn.dataset.sessionId); return; }
    const retryBtn = ev.target.closest("#drawer-retry-analysis");
    if (retryBtn) { MI.drawer.retryAnalysis(retryBtn.dataset.id); return; }
    const row = ev.target.closest(".candidate-row");
    if (!row || ev.target.closest(".approve-cb")) return;
    const inSourcing = row.closest("#candidate-table-body");
    const context = inSourcing ? MI.drawer.sourcingContext() : MI.drawer.shortlistRowContext();
    if (context) MI.drawer.openDetail(row.dataset.id, context);
  });
};

MI.drawer.sourcingContext = function sourcingContext() {
  if (!MI.state.scoreResult) return null;
  return { ranked: MI.state.scoreResult.ranked, analyses: MI.state.analyses, rerank: MI.state.rerankResult, sessionId: MI.state.sessionId };
};

MI.drawer.shortlistRowContext = function shortlistRowContext() {
  const session = MI.extras.currentShortlistSession();
  if (!session) return null;
  const ranked = (session.score && session.score.ranked) || [];
  const ids = new Set(session.shortlist_ids || []);
  return { ranked: ranked.filter((e) => ids.has(e.candidate_id)), analyses: session.analyses || {}, rerank: session.rerank, sessionId: session.id };
};

/* ---------- toast ---------- */

let toastTimer = null;

MI.drawer.showToast = function showToast(message, undoFn) {
  clearTimeout(toastTimer);
  MI.el("toast-message").textContent = message;
  const undoBtn = MI.el("toast-undo");
  undoBtn.classList.toggle("hidden", !undoFn);
  undoBtn.onclick = undoFn ? () => { undoFn(); MI.el("toast").classList.add("hidden"); } : null;
  MI.el("toast").classList.remove("hidden");
  toastTimer = setTimeout(() => MI.el("toast").classList.add("hidden"), 5000);
};

/* ---------- shortlist (role/session-scoped) ---------- */

MI.drawer.updateShortlistCount = function updateShortlistCount() {
  const total = MI.storage.listSessions().reduce((sum, s) => sum + ((s.shortlist_ids || []).length), 0);
  MI.el("count-shortlist").textContent = total;
};

MI.drawer.toggleShortlist = function toggleShortlist(candidateId, sessionId) {
  const session = MI.storage.getSession(sessionId);
  if (!session) return;
  const ids = new Set(session.shortlist_ids || []);
  const wasShortlisted = ids.has(candidateId);
  if (wasShortlisted) ids.delete(candidateId); else ids.add(candidateId);
  MI.storage.updateSessionById(sessionId, { shortlist_ids: Array.from(ids) });
  if (sessionId === MI.state.sessionId) {
    if (wasShortlisted) MI.state.shortlistIds.delete(candidateId); else MI.state.shortlistIds.add(candidateId);
  }
  MI.drawer.showToast(`${wasShortlisted ? "Removed" : "Added"} ${candidateId} ${wasShortlisted ? "from" : "to"} shortlist`,
    () => MI.drawer.toggleShortlist(candidateId, sessionId));
  MI.drawer.refreshShortlistButtons(candidateId, sessionId);
  MI.drawer.updateShortlistCount();
  if (MI.state.view === "shortlist") MI.extras.renderShortlistView();
};

MI.drawer.refreshShortlistButtons = function refreshShortlistButtons(candidateId, sessionId) {
  const session = MI.storage.getSession(sessionId);
  const shortlisted = (session.shortlist_ids || []).includes(candidateId);
  document.querySelectorAll(`.btn-shortlist[data-id="${candidateId}"][data-session-id="${sessionId}"]`).forEach((btn) => {
    const labeled = btn.classList.contains("btn-sm");
    btn.outerHTML = MI.views.shortlistButtonHtml(candidateId, shortlisted, sessionId, labeled);
  });
};

/* ---------- detail drawer ---------- */

function renderFiredOps(label, ops) {
  if (!ops || !ops.length) return "";
  return `
    <div class="drawer-section">
      <span class="section-label">${label}</span>
      <div class="chip-row">${ops.map((o) => {
        const snippets = o.evidence.map((e) => `${e.field}: "${e.snippet}"`).join(", ");
        return `<span class="chip">${o.concept} · ${snippets}</span>`;
      }).join("")}</div>
    </div>`;
}

function renderDupSection(entry) {
  if (!entry.dup_members || entry.dup_members.length <= 1) return "";
  const conflicts = entry.dup_conflicts || {};
  const rows = Object.keys(conflicts).map((field) => `
    <tr><td>${field}</td><td>${conflicts[field].join(" vs ")}</td></tr>`).join("");
  return `
    <div class="drawer-section">
      <span class="section-label">Duplicate group</span>
      <p class="text-muted">Members: ${entry.dup_members.join(", ")}</p>
      ${rows ? `<table class="conflict-table"><thead><tr><th>Field</th><th>Conflicting values</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
    </div>`;
}

function renderAnalysisSection(candidateId, ctx) {
  const result = ctx.analyses[candidateId];
  if (!result) {
    const failed = ctx.sessionId === MI.state.sessionId && MI.state.analysisErrors[candidateId];
    if (failed) {
      return `<div class="drawer-section"><span class="section-label">Analyst</span><p class="error-text">${MI.views.actionErrorMessage(failed)}</p><button type="button" class="btn btn-secondary btn-sm" id="drawer-retry-analysis" data-id="${candidateId}">Retry analysis</button></div>`;
    }
    return `<div class="drawer-section"><span class="section-label">Analyst</span><p class="text-muted">Analysis still in progress…</p></div>`;
  }
  const a = result.analysis;
  const overlaps = a.overlaps.map((o) => `<li>${o.requirement}: "${MI.views.highlightEvidence(o.evidence, o.evidence)}" (${o.source_field}, ${o.tier})</li>`).join("");
  const gaps = a.gaps.map((g) => `<li>${g.requirement} (${g.severity}): ${g.note}</li>`).join("");
  const questions = a.clarifying_questions.map((q) => `<li>${q.text}</li>`).join("");
  const cacheHit = result.meta.usage && result.meta.usage.cache_read_input_tokens > 0;
  return `
    <div class="drawer-section">
      <span class="section-label">Fit brief ${cacheHit ? '<span class="pill cache-hit">cache hit</span>' : ""}</span>
      <p class="drawer-fit-brief">${a.fit_brief}</p>
    </div>
    <div class="drawer-section"><span class="section-label">Overlaps</span><ul>${overlaps}</ul></div>
    <div class="drawer-section"><span class="section-label">Gaps</span><ul>${gaps}</ul></div>
    <div class="drawer-section"><span class="section-label">Clarifying questions</span><ul>${questions}</ul></div>
    <div class="drawer-section"><span class="section-label">Data flags</span><p>${a.data_flags.join(", ") || "none"} · Confidence: ${a.confidence}</p></div>`;
}

function renderRerankSection(candidateId, ctx) {
  if (!ctx.rerank) return "";
  const verdict = ctx.rerank.disagreements.find((d) => d.candidate_id === candidateId);
  return `
    <div class="drawer-section">
      <span class="section-label">Reranker verdict</span>
      ${verdict
        ? `<span class="rerank-badge">det #${verdict.det_rank} → llm #${verdict.llm_rank} — ${verdict.rationale}</span>`
        : "<p class=\"text-muted\">Reranker agrees with the deterministic rank.</p>"}
    </div>`;
}

MI.drawer.renderDetail = function renderDetail(candidateId) {
  const ctx = MI.drawer.context;
  const entry = ctx.ranked.find((e) => e.candidate_id === candidateId);
  if (!entry) return;
  MI.state.drawerCandidateId = candidateId;
  const session = MI.storage.getSession(ctx.sessionId);
  const shortlisted = Boolean(session && (session.shortlist_ids || []).includes(candidateId));
  MI.el("drawer-body").innerHTML = `
    <div class="candidate-card">
      <div class="candidate-card-header">
        <div class="candidate-identity">
          ${MI.views.avatarHtml(entry.candidate_id)}
          <div>
            <div class="candidate-title">${entry.candidate_id} — ${entry.headline || ""}</div>
            <div class="candidate-location">${[entry.location && entry.location.city, entry.country].filter(Boolean).join(", ")}</div>
          </div>
        </div>
        <div class="score-badge ${entry.band}"><span class="n">${entry.score}</span><span class="label">FIT SCORE</span></div>
      </div>
      <div class="candidate-action-row">${MI.views.shortlistButtonHtml(candidateId, shortlisted, ctx.sessionId, true)}</div>
    </div>
    <div class="drawer-section"><span class="section-label">Criteria</span>${MI.views.renderSubscores(entry.subscores)}</div>
    <div class="drawer-section"><span class="section-label">Matched skills</span><div class="chip-row">${MI.views.renderSkillChips(entry.subscores)}</div></div>
    ${renderFiredOps("Boosts fired", entry.boosts_fired)}
    ${renderFiredOps("Penalties fired", entry.penalties_fired)}
    ${renderDupSection(entry)}
    ${renderAnalysisSection(candidateId, ctx)}
    ${renderRerankSection(candidateId, ctx)}`;
};

MI.drawer.retryAnalysis = function retryAnalysis(candidateId) {
  const ctx = MI.drawer.context;
  const entry = ctx.ranked.find((e) => e.candidate_id === candidateId);
  if (!entry) return;
  MI.views.analyzeOne(entry).then(() => MI.drawer.renderDetail(candidateId));
};

MI.drawer.openDetail = function openDetail(candidateId, context) {
  MI.drawer.context = context;
  MI.drawer.renderDetail(candidateId);
  MI.el("drawer-overlay").classList.remove("hidden");
  MI.el("detail-drawer").classList.remove("hidden");
  MI.el("detail-drawer").setAttribute("aria-hidden", "false");
};

MI.drawer.closeDetail = function closeDetail() {
  MI.el("drawer-overlay").classList.add("hidden");
  MI.el("detail-drawer").classList.add("hidden");
  MI.el("detail-drawer").setAttribute("aria-hidden", "true");
  MI.state.drawerCandidateId = null;
};

MI.drawer.stepDetail = function stepDetail(delta) {
  const ranked = MI.drawer.context.ranked;
  const i = ranked.findIndex((e) => e.candidate_id === MI.state.drawerCandidateId);
  const next = ranked[(i + delta + ranked.length) % ranked.length];
  if (next) MI.drawer.renderDetail(next.candidate_id);
};

/* ---------- export (built from a stored session — live or historical, same code path) ---------- */

MI.drawer.download = function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

MI.drawer.paintExportOutput = function paintExportOutput(result, roleId) {
  const mdName = `shortlist_${roleId}.md`;
  const auditName = `audit_${roleId}.json`;
  MI.el("shortlist-export-output").classList.remove("hidden");
  const mdBtn = MI.el("shortlist-download-md-btn");
  mdBtn.textContent = `Download ${mdName}`;
  mdBtn.onclick = () => MI.drawer.download(mdName, result.markdown, "text/markdown");
  const auditBtn = MI.el("shortlist-download-audit-btn");
  auditBtn.textContent = `Download ${auditName}`;
  auditBtn.onclick = () => MI.drawer.download(auditName, JSON.stringify(result.audit_json, null, 1), "application/json");
};

MI.drawer.exportSession = async function exportSession(sessionId) {
  const session = MI.storage.getSession(sessionId);
  if (!session) return;
  const body = {
    role_id: session.role_id, rubric: session.rubric, approved_ids: session.approved_ids || [],
    analyses: session.analyses || {}, rerank: session.rerank,
    session_meta: {
      guidance: session.guidance, rejected: (session.compile && session.compile.rejected) || [],
      adjustments: (session.compile && session.compile.adjustments) || [],
      decomposition: {}, compiled_at: session.created_at, approved_at: new Date().toISOString(),
    },
  };
  let result;
  try {
    result = await MI.api("export", body);
  } catch (err) {
    MI.views.showActionError("shortlist-export-btn", err);
    return;
  }
  MI.views.clearActionError("shortlist-export-btn");
  MI.storage.updateSessionById(sessionId, { status: "exported", export: { markdown: result.markdown, audit_json: result.audit_json } });
  MI.drawer.paintExportOutput(result, session.role_id);
};
