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

/* ---------- compile / echo-back ---------- */

MI.views.onCompile = async function onCompile() {
  MI.state.guidance = MI.el("guidance-input").value;
  const result = await MI.api("compile_rubric", { role_id: MI.state.roleId, guidance: MI.state.guidance });
  MI.state.rubric = result.rubric;
  MI.state.rejected = result.rejected;
  MI.state.adjustments = result.adjustments;
  MI.state.compiledAt = new Date().toISOString();
  MI.views.renderCriteriaBar(result);
  MI.views.renderEcho(result);
  MI.el("echo-section").classList.remove("hidden");
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

MI.views.renderSubscores = function renderSubscores(subscores) {
  return Object.keys(SUBSCORE_LABELS).map((key) => {
    const s = subscores[key];
    if (!s) return "";
    const pct = Math.round(s.value * 100);
    return `
      <div class="subscore-row">
        <span class="subscore-label">${SUBSCORE_LABELS[key]}</span>
        <div class="subscore-bar"><div class="subscore-bar-fill" style="width:${pct}%"></div></div>
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

MI.views.candidateActionRow = function candidateActionRow(candidateId) {
  const shortlisted = MI.state.shortlistIds.has(candidateId);
  const analyzed = Boolean(MI.state.analyses[candidateId]);
  return `
    <div class="candidate-action-row">
      <button type="button" class="btn btn-secondary btn-sm btn-shortlist" data-id="${candidateId}">${shortlisted ? "Shortlisted ✓" : "Shortlist"}</button>
      <button type="button" class="btn btn-ghost btn-sm btn-details" data-id="${candidateId}" ${analyzed ? "" : "disabled"}>${analyzed ? "Details →" : "Analyzing…"}</button>
    </div>`;
};

MI.views.renderCandidateCard = function renderCandidateCard(entry) {
  const isDup = (entry.dup_members || []).length > 1;
  const flags = entry.flags.length
    ? `<div class="card-flags">${entry.flags.map((f) => `<span class="pill">${f}</span>`).join("")}${isDup ? `<span class="pill dup-badge">dup ×${entry.dup_members.length}</span>` : ""}</div>`
    : (isDup ? `<div class="card-flags"><span class="pill dup-badge">dup ×${entry.dup_members.length}</span></div>` : "");
  return `
    <div class="candidate-card" id="candidate-${entry.candidate_id}">
      <input type="checkbox" class="approve-cb card-checkbox" data-id="${entry.candidate_id}" aria-label="Approve ${entry.candidate_id}">
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
      ${flags}
      <div class="card-section">
        <span class="section-label">Criteria</span>
        ${MI.views.renderSubscores(entry.subscores)}
      </div>
      <div class="card-section">
        <span class="section-label">Matched skills</span>
        <div class="chip-row">${MI.views.renderSkillChips(entry.subscores)}</div>
      </div>
      <div class="card-section">
        <span class="section-label">Profile</span>
        <div class="profile-row">
          <span><strong>${entry.experience_years ?? "—"}</strong> yrs experience</span>
          <span>Seniority <strong>${entry.seniority_level ?? "—"}</strong></span>
          <span>Notice <strong>${entry.notice_days ?? "—"}</strong>d</span>
          <span><strong>${entry.country || "—"}</strong></span>
        </div>
      </div>
    </div>`;
};

MI.views.wireApproveCheckboxes = function wireApproveCheckboxes() {
  document.querySelectorAll(".approve-cb").forEach((cb) => {
    cb.checked = MI.state.approvedIds.has(cb.dataset.id);
    if (cb.dataset.wired) return;
    cb.dataset.wired = "1";
    cb.addEventListener("change", (ev) => {
      if (ev.target.checked) MI.state.approvedIds.add(ev.target.dataset.id);
      else MI.state.approvedIds.delete(ev.target.dataset.id);
    });
  });
};

MI.views.renderCandidateList = function renderCandidateList(result) {
  MI.el("filtered-out-line").textContent = `filtered out: ${result.filtered_out.length}`;
  MI.el("candidate-list").innerHTML = result.ranked.map(MI.views.renderCandidateCard).join("");
  MI.views.wireApproveCheckboxes();
  if (result.insufficient_data.length) {
    MI.el("insufficient-strip").classList.remove("hidden");
    MI.el("insufficient-ids").textContent = result.insufficient_data.join(", ");
  }
};

MI.views.onConfirmScore = async function onConfirmScore() {
  MI.el("shortlist-export-btn").disabled = true;
  MI.el("shortlist-export-wait").classList.remove("hidden");
  const result = await MI.api("score", { role_id: MI.state.roleId, rubric: MI.state.rubric });
  MI.state.scoreResult = result;
  MI.views.renderCandidateList(result);
  MI.el("score-section").classList.remove("hidden");
  await MI.views.analyzeAll(result.ranked);
};

/* ---------- analyst cards (skeleton while streaming) ---------- */

function skeletonCard(id) {
  return `
    <div class="skeleton-card" id="card-${id}">
      <div class="skeleton skeleton-line w-40"></div>
      <div class="skeleton skeleton-line w-90"></div>
      <div class="skeleton skeleton-line w-60"></div>
    </div>`;
}

MI.views.renderSkeletons = function renderSkeletons(ranked) {
  MI.el("analyst-cards").innerHTML = ranked.map((e) => skeletonCard(e.candidate_id)).join("");
};

MI.views.highlightEvidence = function highlightEvidence(text, evidence) {
  if (!text) return "";
  const idx = text.toLowerCase().indexOf(evidence.toLowerCase());
  if (idx === -1) return text;
  return text.slice(0, idx) + `<mark>${text.slice(idx, idx + evidence.length)}</mark>` + text.slice(idx + evidence.length);
};

MI.views.renderCard = function renderCard(entry, result) {
  const a = result.analysis;
  const cacheHit = result.meta.usage && result.meta.usage.cache_read_input_tokens > 0;
  const overlaps = a.overlaps.map((o) => `<li>${o.requirement}: "${MI.views.highlightEvidence(o.evidence, o.evidence)}" (${o.source_field}, ${o.tier})</li>`).join("");
  const gaps = a.gaps.map((g) => `<li>${g.requirement} (${g.severity}): ${g.note}</li>`).join("");
  const questions = a.clarifying_questions.map((q) => `<li>${q.text}</li>`).join("");
  const card = document.createElement("div");
  card.className = "analyst-card";
  card.id = `card-${entry.candidate_id}`;
  card.innerHTML = `
    <h3>${entry.candidate_id} — ${entry.headline || ""} ${cacheHit ? '<span class="pill cache-hit">cache hit</span>' : ""}</h3>
    <p>${a.fit_brief}</p>
    <strong>Overlaps</strong><ul>${overlaps}</ul>
    <strong>Gaps</strong><ul>${gaps}</ul>
    <strong>Questions</strong><ul>${questions}</ul>
    <p><strong>Flags:</strong> ${a.data_flags.join(", ") || "none"} · <strong>Confidence:</strong> ${a.confidence}</p>`;
  MI.views.replaceOrAppend(card);
};

MI.views.renderErrorCard = function renderErrorCard(entry, err) {
  const card = document.createElement("div");
  card.className = "analyst-card";
  card.id = `card-${entry.candidate_id}`;
  card.innerHTML = `
    <h3>${entry.candidate_id} — ${entry.headline || ""}</h3>
    <p class="error-text">Analysis failed (${err.status || "error"}).</p>
    <button class="btn btn-secondary retry-btn">Retry</button>`;
  card.querySelector(".retry-btn").addEventListener("click", () => MI.views.analyzeOne(entry));
  MI.views.replaceOrAppend(card);
};

MI.views.replaceOrAppend = function replaceOrAppend(card) {
  const existing = document.getElementById(card.id);
  if (existing) existing.replaceWith(card);
  else MI.el("analyst-cards").appendChild(card);
};

MI.views.markDetailsReady = function markDetailsReady(candidateId) {
  document.querySelectorAll(`.btn-details[data-id="${candidateId}"]`).forEach((btn) => {
    btn.disabled = false;
    btn.textContent = "Details →";
  });
};

MI.views.analyzeOne = async function analyzeOne(entry) {
  try {
    const result = await MI.api("analyze", { role_id: MI.state.roleId, candidate_id: entry.candidate_id, rubric: MI.state.rubric });
    MI.state.analyses[entry.candidate_id] = result;
    MI.views.renderCard(entry, result);
    MI.views.markDetailsReady(entry.candidate_id);
    return result;
  } catch (e) {
    MI.views.renderErrorCard(entry, e);
    return null;
  }
};

MI.views.analyzeAll = async function analyzeAll(ranked) {
  MI.el("cards-section").classList.remove("hidden");
  if (!ranked.length) return;
  MI.views.renderSkeletons(ranked);
  await MI.views.analyzeOne(ranked[0]);
  const rest = ranked.slice(1).map((entry) => () => MI.views.analyzeOne(entry));
  await MI.pool(rest, 4);
  await MI.views.onRerank(ranked);
};

/* ---------- reranker ---------- */

MI.views.onRerank = async function onRerank(ranked) {
  const result = await MI.api("rerank", { role_id: MI.state.roleId, top_ids: ranked.map((e) => e.candidate_id), rubric: MI.state.rubric });
  MI.state.rerankResult = result;
  MI.el("rerank-section").classList.remove("hidden");
  MI.el("rerank-disagreements").innerHTML = result.disagreements.length
    ? result.disagreements.map((d) => `<span class="rerank-badge"><strong>${d.candidate_id}</strong>: det #${d.det_rank} → llm #${d.llm_rank} — ${d.rationale}</span>`).join("")
    : "<p>Reranker agrees with the deterministic order.</p>";
  MI.el("export-section").classList.remove("hidden");
  MI.el("shortlist-export-btn").disabled = false;
  MI.el("shortlist-export-wait").classList.add("hidden");
};
