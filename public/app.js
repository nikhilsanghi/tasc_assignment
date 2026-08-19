/* Candidate-Role Match Intelligence — vanilla JS, renders JSON only. All behavior lives in /core. */
const state = {
  accessCode: null, roles: [], roleId: null, rubric: null, scoreResult: null,
  analyses: {}, rerankResult: null, approvedIds: new Set(),
  compiledAt: null, approvedAt: null, rejected: [], adjustments: [], guidance: "",
};

function el(id) { return document.getElementById(id); }

function showTransientMessage(text) {
  const line = el("status-line");
  line.textContent = text;
  line.classList.remove("hidden");
  setTimeout(() => line.classList.add("hidden"), 4000);
}

async function api(name, body, method = "POST", retried = false) {
  const headers = { "Content-Type": "application/json", "X-Access-Code": state.accessCode };
  const opts = { method, headers };
  if (method !== "GET" && method !== "HEAD") opts.body = JSON.stringify(body || {});
  const res = await fetch(`/api/${name}`, opts);
  if (res.status === 429 && !retried) {
    const data = await res.json();
    const wait = data.retry_after || 5;
    showTransientMessage(`rate limited, retrying in ${wait}s`);
    await new Promise((r) => setTimeout(r, wait * 1000));
    return api(name, body, method, true);
  }
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || "request_failed");
    err.status = res.status;
    err.detail = data;
    throw err;
  }
  return data;
}

function pool(tasks, n = 4) {
  return new Promise((resolve) => {
    const results = new Array(tasks.length);
    let next = 0;
    let done = 0;
    function runNext() {
      if (next >= tasks.length) return;
      const i = next++;
      tasks[i]().then((r) => { results[i] = r; }).finally(() => {
        done++;
        if (done === tasks.length) resolve(results);
        else runNext();
      });
    }
    for (let i = 0; i < Math.min(n, tasks.length); i++) runNext();
  });
}

function initAccessCode() {
  const stored = sessionStorage.getItem("access_code");
  if (stored) {
    state.accessCode = stored;
    el("access-overlay").classList.add("hidden");
    el("app").classList.remove("hidden");
    boot();
    return;
  }
  el("access-submit").addEventListener("click", async () => {
    const code = el("access-input").value.trim();
    if (!code) return;
    state.accessCode = code;
    try {
      await api("health", {}, "POST");
      sessionStorage.setItem("access_code", code);
      el("access-overlay").classList.add("hidden");
      el("app").classList.remove("hidden");
      boot();
    } catch (e) {
      el("access-error").textContent = "Invalid access code.";
      state.accessCode = null;
    }
  });
}

async function boot() {
  const health = await api("health", {}, "GET");
  state.roles = health.roles;
  el("role-select").innerHTML = state.roles.map((r) => `<option value="${r.role_id}">${r.title} (${r.role_id})</option>`).join("");
  el("compile-btn").addEventListener("click", onCompile);
  el("confirm-score-btn").addEventListener("click", onConfirmScore);
  el("export-btn").addEventListener("click", onExport);
}

async function onCompile() {
  state.roleId = el("role-select").value;
  state.guidance = el("guidance-input").value;
  const result = await api("compile_rubric", { role_id: state.roleId, guidance: state.guidance });
  state.rubric = result.rubric;
  state.rejected = result.rejected;
  state.adjustments = result.adjustments;
  state.compiledAt = new Date().toISOString();
  renderEcho(result);
  el("echo-section").classList.remove("hidden");
}

function renderEcho(result) {
  el("interpretation-text").textContent = result.interpretation;
  el("ops-list").innerHTML = "<strong>Accepted:</strong> " +
    (result.ops_accepted.map((op) => `<span class="pill">${op.op}</span>`).join(" ") || "none");
  el("adjustments-list").innerHTML = result.adjustments.length
    ? "<strong>Adjustments:</strong> " + result.adjustments.map((a) => `${a.dimension}: ${a.requested.toFixed(2)} -&gt; ${a.applied.toFixed(2)}`).join(", ")
    : "";
  el("rejections-list").innerHTML = result.rejected.map((r) => {
    const cls = (r.reason === "policy_violation" || r.reason === "injection_suspected") ? "rejection-red" : "rejection-amber";
    const hint = r.closest_supported ? ` (closest supported: ${r.closest_supported})` : "";
    return `<div class="${cls}">${r.text} — ${r.reason}${hint}</div>`;
  }).join("");
}

function bandClass(band) {
  if (band === "strong") return "band-strong";
  if (band === "viable-with-gaps") return "band-viable";
  return "band-stretch";
}

function renderScoreTable(result) {
  el("filtered-out-line").textContent = `filtered out: ${result.filtered_out.length}`;
  const tbody = document.querySelector("#score-table tbody");
  tbody.innerHTML = result.ranked.map((e, i) => `
    <tr>
      <td><input type="checkbox" class="approve-cb" data-id="${e.candidate_id}"></td>
      <td>${i + 1}</td>
      <td>${e.candidate_id}</td>
      <td>${e.headline || ""}</td>
      <td>${e.score}</td>
      <td><span class="pill ${bandClass(e.band)}">${e.band}</span></td>
      <td>${e.flags.join(", ")}${(e.dup_members || []).length > 1 ? ' <span class="pill">dup</span>' : ""}</td>
    </tr>`).join("");
  document.querySelectorAll(".approve-cb").forEach((cb) => cb.addEventListener("change", (ev) => {
    if (ev.target.checked) state.approvedIds.add(ev.target.dataset.id);
    else state.approvedIds.delete(ev.target.dataset.id);
  }));
  if (result.insufficient_data.length) {
    el("insufficient-strip").classList.remove("hidden");
    el("insufficient-ids").textContent = result.insufficient_data.join(", ");
  }
}

async function onConfirmScore() {
  const result = await api("score", { role_id: state.roleId, rubric: state.rubric });
  state.scoreResult = result;
  renderScoreTable(result);
  el("score-section").classList.remove("hidden");
  await analyzeAll(result.ranked);
}

function highlightEvidence(text, evidence) {
  if (!text) return "";
  const idx = text.toLowerCase().indexOf(evidence.toLowerCase());
  if (idx === -1) return text;
  return text.slice(0, idx) + `<mark>${text.slice(idx, idx + evidence.length)}</mark>` + text.slice(idx + evidence.length);
}

function renderCard(entry, result) {
  const a = result.analysis;
  const cacheHit = result.meta.usage && result.meta.usage.cache_read_input_tokens > 0;
  const overlaps = a.overlaps.map((o) => `<li>${o.requirement}: "${highlightEvidence(o.evidence, o.evidence)}" (${o.source_field}, ${o.tier})</li>`).join("");
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
  replaceOrAppend(card);
}

function renderErrorCard(entry, err) {
  const card = document.createElement("div");
  card.className = "analyst-card";
  card.id = `card-${entry.candidate_id}`;
  card.innerHTML = `
    <h3>${entry.candidate_id} — ${entry.headline || ""}</h3>
    <p class="error-text">Analysis failed (${err.status || "error"}).</p>
    <button class="retry-btn">Retry</button>`;
  card.querySelector(".retry-btn").addEventListener("click", () => analyzeOne(entry));
  replaceOrAppend(card);
}

function replaceOrAppend(card) {
  const existing = document.getElementById(card.id);
  if (existing) existing.replaceWith(card);
  else el("analyst-cards").appendChild(card);
}

async function analyzeOne(entry) {
  try {
    const result = await api("analyze", { role_id: state.roleId, candidate_id: entry.candidate_id, rubric: state.rubric });
    state.analyses[entry.candidate_id] = result;
    renderCard(entry, result);
    return result;
  } catch (e) {
    renderErrorCard(entry, e);
    return null;
  }
}

async function analyzeAll(ranked) {
  el("cards-section").classList.remove("hidden");
  if (!ranked.length) return;
  await analyzeOne(ranked[0]);
  const rest = ranked.slice(1).map((entry) => () => analyzeOne(entry));
  await pool(rest, 4);
  await onRerank(ranked);
}

async function onRerank(ranked) {
  const result = await api("rerank", { role_id: state.roleId, top_ids: ranked.map((e) => e.candidate_id), rubric: state.rubric });
  state.rerankResult = result;
  el("rerank-section").classList.remove("hidden");
  el("rerank-disagreements").innerHTML = result.disagreements.length
    ? result.disagreements.map((d) => `<div class="pill rejection-amber">${d.candidate_id}: det #${d.det_rank} -&gt; llm #${d.llm_rank} — ${d.rationale}</div>`).join("")
    : "<p>Reranker agrees with the deterministic order.</p>";
  el("export-section").classList.remove("hidden");
}

function mdToHtml(md) {
  return md.split("\n").map((line) => {
    if (line.startsWith("# ")) return `<h1>${line.slice(2)}</h1>`;
    if (line.startsWith("## ")) return `<h2>${line.slice(3)}</h2>`;
    if (line.startsWith("| ")) return `<div class="md-row">${line}</div>`;
    return `<p>${line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</p>`;
  }).join("");
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function onExport() {
  state.approvedAt = new Date().toISOString();
  const body = {
    role_id: state.roleId, rubric: state.rubric, approved_ids: Array.from(state.approvedIds),
    analyses: state.analyses, rerank: state.rerankResult,
    session_meta: {
      guidance: state.guidance, rejected: state.rejected, adjustments: state.adjustments,
      decomposition: state.scoreResult.decomposition, compiled_at: state.compiledAt, approved_at: state.approvedAt,
    },
  };
  const result = await api("export", body);
  el("export-output").classList.remove("hidden");
  el("markdown-preview").innerHTML = mdToHtml(result.markdown);
  el("download-md-btn").onclick = () => download(`shortlist_${state.roleId}.md`, result.markdown, "text/markdown");
  el("download-audit-btn").onclick = () => download(`audit_${state.roleId}.json`, JSON.stringify(result.audit_json, null, 1), "application/json");
}

initAccessCode();
