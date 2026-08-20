/* Sourcing view: criteria bar, echo-back, candidate cards, insufficient strip, analyze streaming. */
MI.views = {};

const AVATAR_GRADIENTS = [
  ["#f97316", "#ec4899"], ["#6366f1", "#06b6d4"], ["#10b981", "#3b82f6"],
  ["#f43f5e", "#f59e0b"], ["#8b5cf6", "#ec4899"], ["#14b8a6", "#6366f1"],
];

function hashString(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

MI.views.avatarHtml = function avatarHtml(candidateId) {
  const [a, b] = AVATAR_GRADIENTS[hashString(candidateId) % AVATAR_GRADIENTS.length];
  const num = (candidateId.match(/\d+/) || [""])[0];
  return `<div class="candidate-avatar" style="background:linear-gradient(135deg, ${a}, ${b})">${num}</div>`;
};

const FLAG_ICON = '<svg class="icon subscore-flag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M12 9v4M12 17v.01M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>';

MI.views.actionErrorMessage = function actionErrorMessage(err) {
  if (err.status === 429) return "Rate limited — please wait a moment and retry.";
  if (err.status === 502) return "The model returned an unusable response — please retry.";
  if (err.status === 400) return `Invalid rubric: ${(err.detail && err.detail.detail && err.detail.detail.join(", ")) || "please adjust your guidance."}`;
  if (err.status === 401) return "Access code no longer valid — reload and re-enter it.";
  return "Something went wrong — please retry.";
};

function actionErrorAnchor(anchorId) {
  const el = MI.el(anchorId);
  return el.closest(".criteria-bar") || el;
}

MI.views.showActionError = function showActionError(anchorId, err) {
  const anchor = actionErrorAnchor(anchorId);
  let box = anchor.parentElement.querySelector(`.action-error[data-for="${anchorId}"]`);
  if (!box) {
    box = document.createElement("p");
    box.className = "error-text action-error";
    box.dataset.for = anchorId;
    anchor.insertAdjacentElement("afterend", box);
  }
  box.textContent = MI.views.actionErrorMessage(err);
};

MI.views.clearActionError = function clearActionError(anchorId) {
  const box = actionErrorAnchor(anchorId).parentElement.querySelector(`.action-error[data-for="${anchorId}"]`);
  if (box) box.remove();
};

/* ---------- criteria bar ---------- */

MI.views.wireCriteriaBar = function wireCriteriaBar() {
  MI.el("criteria-edit-btn").addEventListener("click", () => MI.el("criteria-bar").classList.add("editing"));
};

MI.views.renderCriteriaBar = function renderCriteriaBar(result) {
  MI.el("criteria-bar").classList.remove("editing");
  MI.el("criteria-edit-btn").classList.remove("hidden");
  const text = MI.state.guidance.trim() || "No guidance given — using the default rubric";
  MI.el("criteria-summary-text").textContent = text.length > 100 ? text.slice(0, 97) + "…" : text;
  MI.el("criteria-count-pill").textContent = `+${result.ops_accepted.length} criteria`;
};

/* ---------- session reset (new compile or role switch) ---------- */

MI.views.resetSourcingUI = function resetSourcingUI() {
  MI.state.rubric = null; MI.state.scoreResult = null; MI.state.analyses = {}; MI.state.analysisErrors = {};
  MI.state.rerankResult = null; MI.state.shortlistIds = new Set();
  MI.state.compiledAt = null; MI.state.approvedAt = null; MI.state.rejected = []; MI.state.adjustments = [];
  MI.state.guidance = ""; MI.state.sessionId = null;
  MI.el("guidance-input").value = "";
  MI.el("criteria-bar").classList.add("editing");
  ["echo-section", "score-section"].forEach((id) => MI.el(id).classList.add("hidden"));
  MI.el("candidate-table-body").innerHTML = "";
  MI.el("insufficient-strip").classList.add("hidden");
  MI.el("rerank-summary-line").textContent = "";
  MI.el("rerank-summary-line").className = "rerank-pill";
  MI.drawer.updateShortlistCount();
};

/* ---------- compile / echo-back ---------- */

MI.views.onCompile = async function onCompile() {
  MI.state.guidance = MI.el("guidance-input").value;
  try {
    const result = await MI.api("compile_rubric", { role_id: MI.state.roleId, guidance: MI.state.guidance });
    MI.views.clearActionError("compile-btn");
    const role = MI.state.roles.find((r) => r.role_id === MI.state.roleId);
    const newSessionId = MI.storage.startSession(MI.state.roleId, role.title, MI.state.guidance);
    MI.state.shortlistIds = new Set(MI.storage.getSession(newSessionId).shortlist_ids || []);
    MI.drawer.updateShortlistCount();
    MI.state.rubric = result.rubric;
    MI.state.rejected = result.rejected;
    MI.state.adjustments = result.adjustments;
    MI.state.compiledAt = new Date().toISOString();
    MI.storage.updateSession({
      status: "compiled", rubric: result.rubric,
      compile: { interpretation: result.interpretation, ops_accepted: result.ops_accepted, rejected: result.rejected, adjustments: result.adjustments },
    });
    MI.views.renderCriteriaBar(result);
    MI.views.renderEcho(result);
    MI.el("echo-section").classList.remove("hidden");
  } catch (err) {
    MI.views.showActionError("compile-btn", err);
  }
};

MI.views.renderEcho = function renderEcho(result) {
  MI.el("interpretation-text").textContent = result.interpretation;
  MI.el("ops-list").innerHTML = result.ops_accepted.map((op) => `<span class="chip chip-exact">${op.op}</span>`).join("") || "";
  MI.el("adjustments-list").innerHTML = result.adjustments.length
    ? "<strong>Adjustments:</strong> " + result.adjustments.map((a) => `${a.dimension}: ${a.requested.toFixed(2)} -&gt; ${a.applied.toFixed(2)}`).join(", ")
    : "";
  MI.el("rejections-list").innerHTML = result.rejected.map((r) => {
    const cls = (r.reason === "policy_violation" || r.reason === "injection_suspected") ? "rejection-red" : "rejection-amber";
    const hint = r.closest_supported ? ` (closest supported: ${r.closest_supported})` : "";
    return `<div class="${cls}">${r.text} — ${r.reason}${hint}</div>`;
  }).join("");
};

/* ---------- candidate cards ---------- */

MI.views.bandClass = function bandClass(band) {
  if (band === "strong") return "band-strong";
  if (band === "viable-with-gaps") return "band-viable";
  return "band-stretch";
};

const SUBSCORE_LABELS = {
  required_skills: "Required skills", nice_to_have: "Nice to have", experience_fit: "Experience fit",
  seniority: "Seniority", location: "Location", availability: "Availability",
};

MI.views.subscoreTone = function subscoreTone(pct) {
  return pct >= 80 ? "good" : pct >= 60 ? "warn" : "bad";
};

MI.views.renderSubscores = function renderSubscores(subscores) {
  return Object.keys(SUBSCORE_LABELS).map((key) => {
    const s = subscores[key];
    if (!s) return "";
    const pct = Math.round(s.value * 100);
    return `
      <div class="subscore-row">
        <span class="subscore-label">${SUBSCORE_LABELS[key]}</span>
        <div class="subscore-bar"><div class="subscore-bar-fill tone-${MI.views.subscoreTone(pct)}" style="width:${pct}%"></div></div>
        <span class="subscore-value">${pct}%</span>
        ${s.flags && s.flags.length ? FLAG_ICON : ""}
      </div>`;
  }).join("");
};

function skillChip(hit) {
  const suffix = hit.tier === "semantic" && hit.similarity != null ? ` ~${hit.similarity.toFixed(2)}` : "";
  return `<span class="chip chip-${hit.tier}">${hit.skill} · ${hit.tier}${suffix}</span>`;
}

MI.views.renderSkillChips = function renderSkillChips(subscores) {
  const hits = [...(subscores.required_skills.evidence || []), ...(subscores.nice_to_have.evidence || [])];
  return hits.length ? hits.map(skillChip).join("") : '<span class="text-muted">No skill matches evidenced.</span>';
};

MI.views.rerankMap = function rerankMap(result) {
  const map = {};
  ((result && result.disagreements) || []).forEach((d) => { map[d.candidate_id] = d; });
  return map;
};

MI.views.rerankCellHtml = function rerankCellHtml(entry, rerankMap) {
  const d = rerankMap && rerankMap[entry.candidate_id];
  if (!d) return '<span class="text-muted">—</span>';
  const arrow = d.delta < 0 ? "↑" : "↓";
  return `<span class="pill rerank-move-badge" title="Reranker second opinion: deterministic #${d.det_rank} → LLM #${d.llm_rank} — ${d.rationale}">${arrow}${Math.abs(d.delta)}</span>`;
};

MI.views.rowFlagsHtml = function rowFlagsHtml(entry) {
  const isDup = (entry.dup_members || []).length > 1;
  const shown = entry.flags.slice(0, 2);
  const extra = entry.flags.length - shown.length;
  return `${shown.map((f) => `<span class="pill">${f}</span>`).join("")}${extra > 0 ? `<span class="pill">+${extra}</span>` : ""}${isDup ? `<span class="pill dup-badge">dup ×${entry.dup_members.length}</span>` : ""}`;
};

MI.views.shortlistButtonHtml = function shortlistButtonHtml(candidateId, shortlisted, sessionId, labeled) {
  const icon = shortlisted
    ? `<svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M8 12.5l2.5 2.5L16 9" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    : `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true"><circle cx="12" cy="12" r="9"/></svg>`;
  if (labeled) {
    return `<button type="button" class="btn btn-secondary btn-sm btn-shortlist${shortlisted ? " active" : ""}" data-id="${candidateId}" data-session-id="${sessionId}">${icon} ${shortlisted ? "Shortlisted" : "Shortlist"}</button>`;
  }
  return `
    <button type="button" class="row-shortlist-btn btn-icon btn-shortlist${shortlisted ? " active" : ""}" data-id="${candidateId}" data-session-id="${sessionId}" aria-label="${shortlisted ? "Remove from shortlist" : "Add to shortlist"}">
      ${icon}
    </button>`;
};

MI.views.renderCandidateRow = function renderCandidateRow(entry, opts) {
  const analyzed = Boolean(opts.analyses[entry.candidate_id]);
  const checkboxCell = opts.showCheckbox
    ? `<td><input type="checkbox" class="approve-cb" data-id="${entry.candidate_id}" data-session-id="${opts.sessionId}" aria-label="Approve ${entry.candidate_id}"></td>` : "";
  return `
    <tr class="candidate-row" data-id="${entry.candidate_id}">
      <td>${MI.views.shortlistButtonHtml(entry.candidate_id, opts.shortlistIds.has(entry.candidate_id), opts.sessionId)}</td>
      ${checkboxCell}
      <td>
        <div class="row-id-cell">
          ${MI.views.avatarHtml(entry.candidate_id).replace("candidate-avatar", "candidate-avatar row-avatar")}
          <div>
            <div class="row-headline">${entry.candidate_id} — ${entry.headline || ""}</div>
            <div class="row-status" data-status-for="${entry.candidate_id}">${analyzed ? "" : "Analyzing…"}</div>
          </div>
        </div>
      </td>
      <td class="row-location">${[entry.location && entry.location.city, entry.country].filter(Boolean).join(", ")}</td>
      <td><div class="score-badge score-badge-sm ${entry.band}"><span class="n">${entry.score}</span></div></td>
      <td class="row-rerank-cell">${MI.views.rerankCellHtml(entry, opts.rerankMap)}</td>
      <td class="row-flags-cell">${MI.views.rowFlagsHtml(entry)}</td>
    </tr>`;
};

MI.views.wireApproveCheckboxes = function wireApproveCheckboxes() {
  document.addEventListener("click", (ev) => { if (ev.target.closest(".approve-cb")) ev.stopPropagation(); });
  document.addEventListener("change", (ev) => {
    const cb = ev.target.closest(".approve-cb");
    if (!cb) return;
    const sessionId = cb.dataset.sessionId;
    const session = MI.storage.getSession(sessionId);
    if (!session) return;
    const ids = new Set(session.approved_ids || []);
    if (cb.checked) ids.add(cb.dataset.id); else ids.delete(cb.dataset.id);
    const patch = { approved_ids: Array.from(ids) };
    if (session.status === "reranked" && ids.size > 0) patch.status = "approved";
    MI.storage.updateSessionById(sessionId, patch);
    if (MI.state.view === "shortlist") MI.extras.updateExportGate();
  });
};

MI.views.renderCandidateList = function renderCandidateList(result) {
  MI.el("filtered-out-line").textContent = `filtered out: ${result.filtered_out.length}`;
  const opts = {
    showCheckbox: false, analyses: MI.state.analyses, shortlistIds: MI.state.shortlistIds, sessionId: MI.state.sessionId,
    rerankMap: MI.views.rerankMap(MI.state.rerankResult),
  };
  MI.el("candidate-table-body").innerHTML = result.ranked.map((e) => MI.views.renderCandidateRow(e, opts)).join("");
  if (result.insufficient_data.length) {
    MI.el("insufficient-strip").classList.remove("hidden");
    MI.el("insufficient-ids").textContent = result.insufficient_data.join(", ");
  }
};

MI.views.onConfirmScore = async function onConfirmScore() {
  try {
    const result = await MI.api("score", { role_id: MI.state.roleId, rubric: MI.state.rubric });
    MI.views.clearActionError("confirm-score-btn");
    MI.state.scoreResult = result;
    MI.storage.updateSession({
      status: "scored",
      score: { ranked: result.ranked, insufficient_data: result.insufficient_data, filtered_out: result.filtered_out, pool_countries: result.pool_countries },
    });
    MI.views.renderCandidateList(result);
    MI.el("score-section").classList.remove("hidden");
    await MI.views.analyzeAll(result.ranked);
  } catch (err) {
    MI.views.showActionError("confirm-score-btn", err);
  }
};

/* ---------- analysis (row status text streams as each candidate completes) ---------- */

MI.views.highlightEvidence = function highlightEvidence(text, evidence, tone) {
  if (!text) return "";
  const idx = text.toLowerCase().indexOf(evidence.toLowerCase());
  if (idx === -1) return text;
  return text.slice(0, idx) + `<mark class="mark-${tone || "good"}">${text.slice(idx, idx + evidence.length)}</mark>` + text.slice(idx + evidence.length);
};

MI.views.updateRowStatus = function updateRowStatus(candidateId, text) {
  document.querySelectorAll(`.row-status[data-status-for="${candidateId}"]`).forEach((el) => { el.textContent = text; });
};

MI.views.analyzeOne = async function analyzeOne(entry) {
  try {
    const result = await MI.api("analyze", { role_id: MI.state.roleId, candidate_id: entry.candidate_id, rubric: MI.state.rubric });
    delete MI.state.analysisErrors[entry.candidate_id];
    MI.state.analyses[entry.candidate_id] = result;
    MI.storage.updateSession({ status: "analyzed", analyses: MI.state.analyses });
    MI.views.updateRowStatus(entry.candidate_id, "");
    return result;
  } catch (e) {
    MI.state.analysisErrors[entry.candidate_id] = e;
    MI.views.updateRowStatus(entry.candidate_id, "Analysis failed");
    return null;
  }
};

MI.views.analyzeAll = async function analyzeAll(ranked) {
  if (!ranked.length) return;
  await MI.views.analyzeOne(ranked[0]);
  const rest = ranked.slice(1).map((entry) => () => MI.views.analyzeOne(entry));
  await MI.pool(rest, 4);
  await MI.views.onRerank(ranked);
};

/* ---------- reranker ---------- */

function setRerankPill(text, tone) {
  const line = MI.el("rerank-summary-line");
  line.textContent = text;
  line.className = `rerank-pill ${tone}`;
}

MI.views.onRerank = async function onRerank(ranked) {
  setRerankPill("Getting reranker second opinion…", "pending");
  let result;
  try {
    result = await MI.api("rerank", { role_id: MI.state.roleId, top_ids: ranked.map((e) => e.candidate_id), rubric: MI.state.rubric });
  } catch (err) {
    setRerankPill(`${MI.views.actionErrorMessage(err)} (reranker second opinion unavailable — ranked order above still stands)`, "error");
    return;
  }
  MI.state.rerankResult = result;
  MI.storage.updateSession({ status: "reranked", rerank: result });
  const n = result.disagreements.length;
  setRerankPill(
    n ? `Reranker second opinion: ${n} disagreement${n === 1 ? "" : "s"} — marked ↕ below` : "Reranker second opinion: agrees with the deterministic order",
    n ? "disagree" : "agree",
  );
  MI.views.renderCandidateList(MI.state.scoreResult);
};
