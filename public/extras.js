/* Searches, Reports, Outreach demo, Overview — all powered by MI.storage (localStorage), no API calls. */
MI.extras = {};

const STATUS_LABEL = {
  compiled: "Compiled", scored: "Scored", analyzed: "Analyzed",
  reranked: "Reranked", approved: "Approved", exported: "Exported",
};

function statusPill(status) {
  const cls = status === "exported" ? "chip-exact" : status === "approved" ? "chip-alias" : "";
  return `<span class="pill ${cls}">${STATUS_LABEL[status] || status}</span>`;
}

function relativeTime(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/* ---------- Searches ---------- */

function sessionRowHtml(session) {
  const count = (session.score && session.score.ranked && session.score.ranked.length) || 0;
  const snippet = session.guidance ? session.guidance.slice(0, 80) : "No guidance — default rubric";
  return `
    <div class="candidate-card session-row" data-id="${session.id}">
      <div class="candidate-card-header">
        <div class="candidate-identity">
          <div>
            <div class="candidate-title">${session.role_title}</div>
            <div class="candidate-location">${snippet}</div>
          </div>
        </div>
        <div style="text-align:right;">
          ${statusPill(session.status)}
          <div class="text-muted" style="margin-top:.35rem;">${relativeTime(session.updated_at)} · ${count} candidates</div>
        </div>
      </div>
      <div class="candidate-action-row">
        <button type="button" class="btn btn-secondary btn-sm btn-open-session" data-id="${session.id}">Open</button>
        <button type="button" class="btn btn-ghost btn-sm btn-delete-session" data-id="${session.id}">Delete</button>
      </div>
    </div>`;
}

MI.extras.renderSearches = function renderSearches() {
  const sessions = MI.storage.listSessions();
  MI.el("searches-empty").classList.toggle("hidden", sessions.length > 0);
  MI.el("searches-list").classList.toggle("hidden", sessions.length === 0);
  MI.el("searches-list").innerHTML = sessions.map(sessionRowHtml).join("");
  MI.el("searches-detail").classList.add("hidden");
};

function candidateSummaryRow(entry, analysis) {
  return `
    <div class="subscore-row" style="border-bottom:1px solid var(--border); padding:.5rem 0;">
      <span class="subscore-label" style="width:auto; flex:1;">
        <strong>${entry.candidate_id}</strong> — ${entry.headline || ""}
        ${analysis ? `<div class="text-muted">${analysis.analysis.fit_brief}</div>` : ""}
      </span>
      <span class="pill ${MI.views.bandClass(entry.band)}">${entry.score}</span>
    </div>`;
}

MI.extras.renderSessionDetail = function renderSessionDetail(id) {
  const session = MI.storage.getSession(id);
  if (!session) return;
  const ranked = (session.score && session.score.ranked) || [];
  MI.el("searches-list").classList.add("hidden");
  const detail = MI.el("searches-detail");
  detail.classList.remove("hidden");
  detail.innerHTML = `
    <div class="card">
      <button type="button" class="btn btn-ghost btn-sm" id="searches-back-btn">← Back to searches</button>
      <h2 style="margin:.75rem 0 0;">${session.role_title}</h2>
      <p class="text-muted">${session.guidance || "No guidance — default rubric"} · ${statusPill(session.status)} · saved ${relativeTime(session.updated_at)}</p>
      <button type="button" class="btn btn-secondary btn-sm" id="searches-rerun-btn" data-role="${session.role_id}" data-guidance="${(session.guidance || "").replace(/"/g, "&quot;")}">Re-run this search</button>
    </div>
    <div class="card">
      <span class="section-label">Candidates (${ranked.length})</span>
      ${ranked.map((e) => candidateSummaryRow(e, session.analyses[e.candidate_id])).join("") || '<p class="text-muted">Not scored.</p>'}
    </div>`;
  MI.el("searches-back-btn").addEventListener("click", MI.extras.renderSearches);
  MI.el("searches-rerun-btn").addEventListener("click", (ev) => {
    const btn = ev.target;
    MI.views.resetSourcingUI();
    selectRole(btn.dataset.role, true);
    MI.el("guidance-input").value = btn.dataset.guidance;
    location.hash = "#/sourcing";
  });
};

MI.extras.wireSearches = function wireSearches() {
  document.addEventListener("click", (ev) => {
    const openBtn = ev.target.closest(".btn-open-session");
    if (openBtn) MI.extras.renderSessionDetail(openBtn.dataset.id);
    const delBtn = ev.target.closest(".btn-delete-session");
    if (delBtn) {
      if (confirm("Delete this saved search? This only removes the local trace, not any approved export already downloaded.")) {
        MI.storage.deleteSession(delBtn.dataset.id);
        MI.extras.renderSearches();
        MI.extras.renderReports();
      }
    }
  });
};

/* ---------- Reports ---------- */

function reportRowHtml(session) {
  const count = (session.score && session.score.ranked && session.score.ranked.length) || 0;
  return `
    <div class="candidate-card">
      <div class="candidate-card-header">
        <div class="candidate-identity">
          <div>
            <div class="candidate-title">${session.role_title}</div>
            <div class="candidate-location">${statusPill(session.status)} · ${relativeTime(session.updated_at)} · ${count} candidates</div>
          </div>
        </div>
      </div>
      <div class="candidate-action-row">
        <button type="button" class="btn btn-secondary btn-sm btn-trace" data-id="${session.id}">Download session trace (JSON)</button>
        ${session.status === "exported" ? `
          <button type="button" class="btn btn-secondary btn-sm btn-audit" data-id="${session.id}">Download audit.json</button>
          <button type="button" class="btn btn-secondary btn-sm btn-md" data-id="${session.id}">Download shortlist.md</button>` : ""}
      </div>
    </div>`;
}

MI.extras.renderReports = function renderReports() {
  const sessions = MI.storage.listSessions();
  MI.el("reports-empty").classList.toggle("hidden", sessions.length > 0);
  MI.el("reports-list").classList.toggle("hidden", sessions.length === 0);
  MI.el("reports-list").innerHTML = sessions.map(reportRowHtml).join("");
};

MI.extras.wireReports = function wireReports() {
  document.addEventListener("click", (ev) => {
    const traceBtn = ev.target.closest(".btn-trace");
    if (traceBtn) {
      const s = MI.storage.getSession(traceBtn.dataset.id);
      MI.drawer.download(`session_trace_${s.id}.json`, JSON.stringify(s, null, 2), "application/json");
    }
    const auditBtn = ev.target.closest(".btn-audit");
    if (auditBtn) {
      const s = MI.storage.getSession(auditBtn.dataset.id);
      MI.drawer.download(`audit_${s.role_id}.json`, JSON.stringify(s.export.audit_json, null, 1), "application/json");
    }
    const mdBtn = ev.target.closest(".btn-md");
    if (mdBtn) {
      const s = MI.storage.getSession(mdBtn.dataset.id);
      MI.drawer.download(`shortlist_${s.role_id}.md`, s.export.markdown, "text/markdown");
    }
  });
};

/* ---------- Overview (full stats in step 5) ---------- */

MI.extras.renderOverview = function renderOverview() {};
