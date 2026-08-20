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

/* ---------- Shortlist (role-scoped: every role keeps its own) ---------- */

MI.extras.currentShortlistRoleId = null;

MI.extras.wireShortlistRoleSwitcher = function wireShortlistRoleSwitcher() {
  MI.el("shortlist-role-switcher").addEventListener("click", () => MI.el("shortlist-role-menu").classList.toggle("hidden"));
  MI.el("shortlist-role-menu").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".role-menu-item");
    if (btn) MI.extras.selectShortlistRole(btn.dataset.roleId);
  });
  document.addEventListener("click", (ev) => {
    if (!ev.target.closest("#shortlist-role-switcher") && !ev.target.closest("#shortlist-role-menu")) {
      MI.el("shortlist-role-menu").classList.add("hidden");
    }
  });
};

MI.extras.renderShortlistRoleMenu = function renderShortlistRoleMenu() {
  MI.el("shortlist-role-menu").innerHTML = MI.state.roles.map((r) => `
    <button class="role-menu-item${r.role_id === MI.extras.currentShortlistRoleId ? " active" : ""}" data-role-id="${r.role_id}">
      <span>${r.title}</span><span class="role-menu-id">${r.role_id}</span>
    </button>`).join("");
  const current = MI.state.roles.find((r) => r.role_id === MI.extras.currentShortlistRoleId);
  MI.el("shortlist-role-switcher-title").textContent = current ? current.title : "Select role";
};

MI.extras.selectShortlistRole = function selectShortlistRole(roleId) {
  MI.extras.currentShortlistRoleId = roleId;
  MI.extras.renderShortlistRoleMenu();
  MI.el("shortlist-role-menu").classList.add("hidden");
  MI.extras.renderShortlistView();
};

MI.extras.enterShortlistView = function enterShortlistView() {
  if (!MI.extras.currentShortlistRoleId) {
    MI.extras.currentShortlistRoleId = MI.state.roleId || (MI.state.roles[0] && MI.state.roles[0].role_id);
  }
  MI.extras.renderShortlistRoleMenu();
  MI.extras.renderShortlistView();
};

MI.extras.currentShortlistSession = function currentShortlistSession() {
  const sessions = MI.storage.listSessions().filter((s) => s.role_id === MI.extras.currentShortlistRoleId);
  return sessions[0] || null;
};

MI.extras.updateExportGate = function updateExportGate() {
  const session = MI.extras.currentShortlistSession();
  const ready = Boolean(session && ["reranked", "approved", "exported"].includes(session.status));
  MI.el("shortlist-export-btn").disabled = !ready;
  MI.el("shortlist-export-wait").classList.toggle("hidden", ready);
};

MI.extras.renderShortlistView = function renderShortlistView() {
  const session = MI.extras.currentShortlistSession();
  MI.el("shortlist-no-role").classList.toggle("hidden", Boolean(session));
  if (!session) {
    MI.el("shortlist-empty").classList.add("hidden");
    MI.el("shortlist-content").classList.add("hidden");
    return;
  }
  const ranked = (session.score && session.score.ranked) || [];
  const shortlistIds = new Set(session.shortlist_ids || []);
  const entries = ranked.filter((e) => shortlistIds.has(e.candidate_id));
  MI.el("shortlist-empty").classList.toggle("hidden", entries.length > 0);
  MI.el("shortlist-content").classList.toggle("hidden", entries.length === 0);
  if (!entries.length) return;
  const opts = {
    showCheckbox: true, analyses: session.analyses || {}, shortlistIds, sessionId: session.id,
    rerankMap: MI.views.rerankMap(session.rerank),
  };
  MI.el("shortlist-table-body").innerHTML = entries.map((e) => MI.views.renderCandidateRow(e, opts)).join("");
  const approved = session.approved_ids || [];
  document.querySelectorAll("#shortlist-table-body .approve-cb").forEach((cb) => { cb.checked = approved.includes(cb.dataset.id); });
  if (session.status === "exported" && session.export) MI.drawer.paintExportOutput(session.export, session.role_id);
  else MI.el("shortlist-export-output").classList.add("hidden");
  MI.extras.updateExportGate();
};

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
      MI.confirmModal("Delete this saved search? This only removes the local trace, not any approved export already downloaded.", "Delete").then((ok) => {
        if (!ok) return;
        MI.storage.deleteSession(delBtn.dataset.id);
        MI.extras.renderSearches();
        MI.extras.renderReports();
      });
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

/* ---------- Overview ---------- */

MI.extras.renderOverview = function renderOverview() {
  const sessions = MI.storage.listSessions();
  MI.el("overview-empty").classList.toggle("hidden", sessions.length > 0);
  MI.el("overview-content").classList.toggle("hidden", sessions.length === 0);
  if (!sessions.length) return;
  const candidatesAnalyzed = sessions.reduce((sum, s) => sum + Object.keys(s.analyses || {}).length, 0);
  const exportsMade = sessions.filter((s) => s.status === "exported").length;
  let cacheTokens = "—";
  for (const s of sessions) {
    const vals = Object.values(s.analyses || {});
    if (!vals.length) continue;
    const last = vals[vals.length - 1];
    if (last.meta && last.meta.usage && last.meta.usage.cache_read_input_tokens != null) cacheTokens = last.meta.usage.cache_read_input_tokens;
    break;
  }
  MI.el("overview-stats").innerHTML = [
    ["Searches run", sessions.length], ["Candidates analyzed", candidatesAnalyzed],
    ["Exports made", exportsMade], ["Cache-read tokens (last analyze)", cacheTokens],
  ].map(([label, n]) => `<div class="stat-card"><span class="n">${n}</span><span class="label">${label}</span></div>`).join("");
  MI.el("overview-recent").innerHTML = sessions.slice(0, 5).map((s) => `
    <div class="recent-row"><span>${s.role_title} — ${s.guidance ? s.guidance.slice(0, 50) : "default rubric"}</span>${statusPill(s.status)}</div>`).join("");
};

/* ---------- Outreach demo (static, no LLM/network call) ---------- */

const OUTREACH_STEPS = [
  { id: 1, label: "New Email", day: "Day 1", body: "Hi {{candidate_id}}, I'm reaching out about the {{role_title}} opportunity — your experience with {{top_overlap}} stood out. Do you have time for a quick call this week?" },
  { id: 2, label: "Send Email Reply", day: "Day 4", body: "Hi {{candidate_id}}, just following up on the {{role_title}} role. Your background in {{top_overlap}} looks like a strong match. Any interest in chatting?" },
  { id: 3, label: "Send Email Reply", day: "Day 8", body: "Hi {{candidate_id}}, I'll keep this brief — the {{role_title}} role is still open, and your {{top_overlap}} experience would be a strong fit. Let me know if the timing works." },
];

const ADD_STEP_OPTIONS = ["New Email Reply", "New Email Thread", "LinkedIn Message", "Connection Request", "Send Text Message", "Cold Call / Voicemail", "Custom Task"];

function outreachTopOverlap(entry, analysis) {
  const overlap = analysis && analysis.analysis.overlaps[0];
  if (overlap) return overlap.requirement;
  const hit = entry.subscores.required_skills.evidence[0] || entry.subscores.nice_to_have.evidence[0];
  return hit ? hit.skill : "your background";
}

function fillTemplate(template, tokens) {
  return template.replace(/\{\{(\w+)\}\}/g, (_, key) => `<span class="chip chip-semantic">${tokens[key]}</span>`);
}

MI.extras.renderAddStepMenu = function renderAddStepMenu() {
  MI.el("outreach-add-step-menu").innerHTML = ADD_STEP_OPTIONS.map((o) =>
    `<div class="outreach-add-step" title="Not in scope — integration point">${o}</div>`).join("");
};

MI.extras.outreachSession = function outreachSession() {
  return MI.storage.listSessions().find((s) => s.role_id === MI.state.roleId) || null;
};

MI.extras.renderStepCard = function renderStepCard(stepId) {
  const step = OUTREACH_STEPS.find((s) => s.id === stepId);
  const session = MI.extras.outreachSession();
  if (!session) return;
  const candidateId = MI.el("outreach-candidate-select").value;
  const entry = (session.score.ranked || []).find((e) => e.candidate_id === candidateId);
  const roleTitle = session.role_title;
  const tokens = { candidate_id: entry.candidate_id, role_title: roleTitle, top_overlap: outreachTopOverlap(entry, (session.analyses || {})[candidateId]) };
  MI.el("outreach-step-card").innerHTML = `
    <span class="section-label">Step ${step.id}: ${step.label}</span>
    <p style="margin:.75rem 0 0; font-size:13px;"><strong style="display:inline-block;width:60px;">From</strong> <span class="no-accounts">No accounts connected</span></p>
    <p style="margin:.5rem 0 0; font-size:13px;"><strong style="display:inline-block;width:60px;">Subject</strong> ${roleTitle} opportunity</p>
    <p style="margin:.5rem 0 0; font-size:13px; display:flex; align-items:center; gap:.6rem;">
      <strong style="width:60px;">Type</strong>
      <span class="write-toggle"><span class="active">Written by AI</span><span>Manual Email</span></span>
    </p>
    <div class="outreach-body">${fillTemplate(step.body, tokens)}</div>`;
};

MI.extras.renderOutreach = function renderOutreach() {
  const session = MI.extras.outreachSession();
  const ranked = (session && session.score && session.score.ranked) || [];
  const shortlistIds = new Set((session && session.shortlist_ids) || []);
  const shortlisted = ranked.filter((e) => shortlistIds.has(e.candidate_id));
  MI.el("outreach-empty").classList.toggle("hidden", shortlisted.length > 0);
  MI.el("outreach-content").classList.toggle("hidden", shortlisted.length === 0);
  if (!shortlisted.length) return;
  MI.el("outreach-candidate-select").innerHTML = shortlisted.map((e) => `<option value="${e.candidate_id}">${e.candidate_id} — ${e.headline || ""}</option>`).join("");
  MI.extras.renderAddStepMenu();
  document.querySelectorAll(".outreach-step-row").forEach((r) => r.classList.remove("active"));
  document.querySelector('.outreach-step-row[data-step="1"]').classList.add("active");
  MI.extras.renderStepCard(1);
};

MI.extras.wireOutreach = function wireOutreach() {
  MI.el("outreach-candidate-select").addEventListener("change", () => {
    const active = document.querySelector(".outreach-step-row.active");
    MI.extras.renderStepCard(Number(active.dataset.step));
  });
  document.querySelectorAll(".outreach-step-row").forEach((row) => row.addEventListener("click", () => {
    document.querySelectorAll(".outreach-step-row").forEach((r) => r.classList.remove("active"));
    row.classList.add("active");
    MI.extras.renderStepCard(Number(row.dataset.step));
  }));
};
