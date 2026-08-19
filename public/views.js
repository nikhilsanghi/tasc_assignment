/* Sourcing view: criteria bar, echo-back, candidate cards, insufficient strip, analyze streaming. */
MI.views = {};

MI.views.onCompile = async function onCompile() {
  MI.state.guidance = MI.el("guidance-input").value;
  const result = await MI.api("compile_rubric", { role_id: MI.state.roleId, guidance: MI.state.guidance });
  MI.state.rubric = result.rubric;
  MI.state.rejected = result.rejected;
  MI.state.adjustments = result.adjustments;
  MI.state.compiledAt = new Date().toISOString();
  MI.views.renderEcho(result);
  MI.el("echo-section").classList.remove("hidden");
};

MI.views.renderEcho = function renderEcho(result) {
  MI.el("interpretation-text").textContent = result.interpretation;
  MI.el("ops-list").innerHTML = "<strong>Accepted:</strong> " +
    (result.ops_accepted.map((op) => `<span class="pill">${op.op}</span>`).join(" ") || "none");
  MI.el("adjustments-list").innerHTML = result.adjustments.length
    ? "<strong>Adjustments:</strong> " + result.adjustments.map((a) => `${a.dimension}: ${a.requested.toFixed(2)} -&gt; ${a.applied.toFixed(2)}`).join(", ")
    : "";
  MI.el("rejections-list").innerHTML = result.rejected.map((r) => {
    const cls = (r.reason === "policy_violation" || r.reason === "injection_suspected") ? "rejection-red" : "rejection-amber";
    const hint = r.closest_supported ? ` (closest supported: ${r.closest_supported})` : "";
    return `<div class="${cls}">${r.text} — ${r.reason}${hint}</div>`;
  }).join("");
};

MI.views.bandClass = function bandClass(band) {
  if (band === "strong") return "band-strong";
  if (band === "viable-with-gaps") return "band-viable";
  return "band-stretch";
};

MI.views.renderScoreTable = function renderScoreTable(result) {
  MI.el("filtered-out-line").textContent = `filtered out: ${result.filtered_out.length}`;
  const tbody = document.querySelector("#score-table tbody");
  tbody.innerHTML = result.ranked.map((e, i) => `
    <tr>
      <td><input type="checkbox" class="approve-cb" data-id="${e.candidate_id}"></td>
      <td>${i + 1}</td>
      <td>${e.candidate_id}</td>
      <td>${e.headline || ""}</td>
      <td>${e.score}</td>
      <td><span class="pill ${MI.views.bandClass(e.band)}">${e.band}</span></td>
      <td>${e.flags.join(", ")}${(e.dup_members || []).length > 1 ? ' <span class="pill">dup</span>' : ""}</td>
    </tr>`).join("");
  document.querySelectorAll(".approve-cb").forEach((cb) => cb.addEventListener("change", (ev) => {
    if (ev.target.checked) MI.state.approvedIds.add(ev.target.dataset.id);
    else MI.state.approvedIds.delete(ev.target.dataset.id);
  }));
  if (result.insufficient_data.length) {
    MI.el("insufficient-strip").classList.remove("hidden");
    MI.el("insufficient-ids").textContent = result.insufficient_data.join(", ");
  }
};

MI.views.onConfirmScore = async function onConfirmScore() {
  const result = await MI.api("score", { role_id: MI.state.roleId, rubric: MI.state.rubric });
  MI.state.scoreResult = result;
  MI.views.renderScoreTable(result);
  MI.el("score-section").classList.remove("hidden");
  await MI.views.analyzeAll(result.ranked);
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

MI.views.analyzeOne = async function analyzeOne(entry) {
  try {
    const result = await MI.api("analyze", { role_id: MI.state.roleId, candidate_id: entry.candidate_id, rubric: MI.state.rubric });
    MI.state.analyses[entry.candidate_id] = result;
    MI.views.renderCard(entry, result);
    return result;
  } catch (e) {
    MI.views.renderErrorCard(entry, e);
    return null;
  }
};

MI.views.analyzeAll = async function analyzeAll(ranked) {
  MI.el("cards-section").classList.remove("hidden");
  if (!ranked.length) return;
  await MI.views.analyzeOne(ranked[0]);
  const rest = ranked.slice(1).map((entry) => () => MI.views.analyzeOne(entry));
  await MI.pool(rest, 4);
  await MI.views.onRerank(ranked);
};

MI.views.onRerank = async function onRerank(ranked) {
  const result = await MI.api("rerank", { role_id: MI.state.roleId, top_ids: ranked.map((e) => e.candidate_id), rubric: MI.state.rubric });
  MI.state.rerankResult = result;
  MI.el("rerank-section").classList.remove("hidden");
  MI.el("rerank-disagreements").innerHTML = result.disagreements.length
    ? result.disagreements.map((d) => `<div class="pill rejection-amber">${d.candidate_id}: det #${d.det_rank} -&gt; llm #${d.llm_rank} — ${d.rationale}</div>`).join("")
    : "<p>Reranker agrees with the deterministic order.</p>";
  MI.el("export-section").classList.remove("hidden");
};
