/* Drawer, shortlist flow, toasts, modal, Shortlist view, export rendering. */
MI.drawer = {};

/* ---------- wiring ---------- */

MI.drawer.wire = function wire() {
  MI.el("drawer-close").addEventListener("click", MI.drawer.closeDetail);
  MI.el("drawer-overlay").addEventListener("click", MI.drawer.closeDetail);
  MI.el("drawer-prev").addEventListener("click", () => MI.drawer.stepDetail(-1));
  MI.el("drawer-next").addEventListener("click", () => MI.drawer.stepDetail(1));
  MI.el("shortlist-export-btn").addEventListener("click", () => MI.drawer.onExport());
  document.addEventListener("keydown", (ev) => {
    if (MI.el("detail-drawer").classList.contains("hidden")) return;
    if (ev.key === "Escape") MI.drawer.closeDetail();
    if (ev.key === "ArrowUp") MI.drawer.stepDetail(-1);
    if (ev.key === "ArrowDown") MI.drawer.stepDetail(1);
  });
  document.addEventListener("click", (ev) => {
    const shortlistBtn = ev.target.closest(".btn-shortlist");
    if (shortlistBtn) MI.drawer.toggleShortlist(shortlistBtn.dataset.id);
    const detailsBtn = ev.target.closest(".btn-details");
    if (detailsBtn && !detailsBtn.disabled) MI.drawer.openDetail(detailsBtn.dataset.id);
  });
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

/* ---------- shortlist ---------- */

MI.drawer.updateShortlistButtons = function updateShortlistButtons(candidateId) {
  const shortlisted = MI.state.shortlistIds.has(candidateId);
  document.querySelectorAll(`.btn-shortlist[data-id="${candidateId}"]`).forEach((btn) => {
    btn.textContent = shortlisted ? "Shortlisted ✓" : "Shortlist";
  });
};

MI.drawer.updateShortlistCount = function updateShortlistCount() {
  MI.el("count-shortlist").textContent = MI.state.shortlistIds.size;
};

MI.drawer.toggleShortlist = function toggleShortlist(candidateId) {
  const wasShortlisted = MI.state.shortlistIds.has(candidateId);
  if (wasShortlisted) {
    MI.state.shortlistIds.delete(candidateId);
    MI.drawer.showToast(`Removed ${candidateId} from shortlist`, () => {
      MI.state.shortlistIds.add(candidateId);
      MI.drawer.updateShortlistButtons(candidateId);
      MI.drawer.updateShortlistCount();
      MI.drawer.renderShortlistView();
    });
  } else {
    MI.state.shortlistIds.add(candidateId);
    MI.drawer.showToast(`Added ${candidateId} to shortlist`, () => {
      MI.state.shortlistIds.delete(candidateId);
      MI.drawer.updateShortlistButtons(candidateId);
      MI.drawer.updateShortlistCount();
      MI.drawer.renderShortlistView();
    });
  }
  MI.drawer.updateShortlistButtons(candidateId);
  MI.drawer.updateShortlistCount();
  MI.drawer.renderShortlistView();
};

MI.drawer.renderShortlistView = function renderShortlistView() {
  const ranked = (MI.state.scoreResult && MI.state.scoreResult.ranked) || [];
  const entries = ranked.filter((e) => MI.state.shortlistIds.has(e.candidate_id));
  MI.el("shortlist-empty").classList.toggle("hidden", entries.length > 0);
  MI.el("shortlist-content").classList.toggle("hidden", entries.length === 0);
  if (!entries.length) return;
  MI.el("shortlist-list").innerHTML = entries.map(MI.views.renderCandidateCard).join("");
  MI.views.wireApproveCheckboxes();
};

/* ---------- detail drawer ---------- */

function renderFiredOps(label, ops) {
  if (!ops || !ops.length) return "";
  return `
    <div class="drawer-section">
      <span class="section-label">${label}</span>
      <div class="chip-row">${ops.map((o) => `<span class="chip">${o.concept} · ${o.evidence}</span>`).join("")}</div>
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

function renderAnalysisSection(candidateId) {
  const result = MI.state.analyses[candidateId];
  if (!result) return `<div class="drawer-section"><span class="section-label">Analyst</span><p class="text-muted">Analysis still in progress…</p></div>`;
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

function renderRerankSection(candidateId) {
  const rr = MI.state.rerankResult;
  if (!rr) return "";
  const verdict = rr.disagreements.find((d) => d.candidate_id === candidateId);
  return `
    <div class="drawer-section">
      <span class="section-label">Reranker verdict</span>
      ${verdict
        ? `<span class="rerank-badge">det #${verdict.det_rank} → llm #${verdict.llm_rank} — ${verdict.rationale}</span>`
        : "<p class=\"text-muted\">Reranker agrees with the deterministic rank.</p>"}
    </div>`;
}

MI.drawer.renderDetail = function renderDetail(candidateId) {
  const entry = MI.state.scoreResult.ranked.find((e) => e.candidate_id === candidateId);
  if (!entry) return;
  MI.state.drawerCandidateId = candidateId;
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
      ${MI.views.candidateActionRow(entry.candidate_id)}
    </div>
    <div class="drawer-section"><span class="section-label">Criteria</span>${MI.views.renderSubscores(entry.subscores)}</div>
    <div class="drawer-section"><span class="section-label">Matched skills</span><div class="chip-row">${MI.views.renderSkillChips(entry.subscores)}</div></div>
    ${renderFiredOps("Boosts fired", entry.boosts_fired)}
    ${renderFiredOps("Penalties fired", entry.penalties_fired)}
    ${renderDupSection(entry)}
    ${renderAnalysisSection(candidateId)}
    ${renderRerankSection(candidateId)}`;
};

MI.drawer.openDetail = function openDetail(candidateId) {
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
  const ranked = MI.state.scoreResult.ranked;
  const i = ranked.findIndex((e) => e.candidate_id === MI.state.drawerCandidateId);
  const next = ranked[(i + delta + ranked.length) % ranked.length];
  if (next) MI.drawer.renderDetail(next.candidate_id);
};

/* ---------- export rendering (unchanged payload assembly, moved verbatim) ---------- */

MI.drawer.mdToHtml = function mdToHtml(md) {
  return md.split("\n").map((line) => {
    if (line.startsWith("# ")) return `<h1>${line.slice(2)}</h1>`;
    if (line.startsWith("## ")) return `<h2>${line.slice(3)}</h2>`;
    if (line.startsWith("| ")) return `<div class="md-row">${line}</div>`;
    return `<p>${line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</p>`;
  }).join("");
};

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

function paintExportOutput(prefix, result) {
  MI.el(`${prefix}export-output`).classList.remove("hidden");
  MI.el(`${prefix}markdown-preview`).innerHTML = MI.drawer.mdToHtml(result.markdown);
  MI.el(`${prefix}download-md-btn`).onclick = () => MI.drawer.download(`shortlist_${MI.state.roleId}.md`, result.markdown, "text/markdown");
  MI.el(`${prefix}download-audit-btn`).onclick = () => MI.drawer.download(`audit_${MI.state.roleId}.json`, JSON.stringify(result.audit_json, null, 1), "application/json");
}

MI.drawer.onExport = async function onExport() {
  MI.state.approvedAt = new Date().toISOString();
  const body = {
    role_id: MI.state.roleId, rubric: MI.state.rubric, approved_ids: Array.from(MI.state.approvedIds),
    analyses: MI.state.analyses, rerank: MI.state.rerankResult,
    session_meta: {
      guidance: MI.state.guidance, rejected: MI.state.rejected, adjustments: MI.state.adjustments,
      decomposition: MI.state.scoreResult.decomposition, compiled_at: MI.state.compiledAt, approved_at: MI.state.approvedAt,
    },
  };
  const result = await MI.api("export", body);
  MI.storage.updateSession({ status: "exported", export: { markdown: result.markdown, audit_json: result.audit_json } });
  paintExportOutput("", result);
  paintExportOutput("shortlist-", result);
};
