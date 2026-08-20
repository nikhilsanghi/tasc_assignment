/* Candidate-Role Match Intelligence — vanilla JS, renders JSON only. All behavior lives in /core. */
const MI = {};

MI.state = {
  accessCode: null, roles: [], roleId: null, rubric: null, scoreResult: null,
  analyses: {}, analysisErrors: {}, rerankResult: null, shortlistIds: new Set(),
  compiledAt: null, approvedAt: null, rejected: [], adjustments: [], guidance: "",
  view: "sourcing", drawerCandidateId: null, sessionId: null,
};

MI.el = function el(id) { return document.getElementById(id); };

MI.showTransientMessage = function showTransientMessage(text) {
  const line = MI.el("status-line");
  line.textContent = text;
  line.classList.remove("hidden");
  setTimeout(() => line.classList.add("hidden"), 4000);
};

MI.api = async function api(name, body, method = "POST", retried = false) {
  const headers = { "Content-Type": "application/json", "X-Access-Code": MI.state.accessCode };
  const opts = { method, headers };
  if (method !== "GET" && method !== "HEAD") opts.body = JSON.stringify(body || {});
  const res = await fetch(`/api/${name}`, opts);
  if (res.status === 429 && !retried) {
    const data = await res.json();
    const wait = data.retry_after || 5;
    MI.showTransientMessage(`rate limited, retrying in ${wait}s`);
    await new Promise((r) => setTimeout(r, wait * 1000));
    return MI.api(name, body, method, true);
  }
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.error || "request_failed");
    err.status = res.status;
    err.detail = data;
    throw err;
  }
  return data;
};

MI.pool = function pool(tasks, n = 4) {
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
};

/* ---------- auto-save (D-6x: client-side session persistence) ---------- */

MI.storage = { KEY: "mi_sessions_v1", CAP: 20 };

MI.storage.load = function load() {
  try {
    const raw = localStorage.getItem(MI.storage.KEY);
    return raw ? JSON.parse(raw) : { sessions: {}, order: [] };
  } catch (e) {
    return { sessions: {}, order: [] };
  }
};

MI.storage.save = function save(store, retried = false) {
  try {
    localStorage.setItem(MI.storage.KEY, JSON.stringify(store));
  } catch (e) {
    if (retried || !store.order.length) return;
    const evicted = store.order.pop();
    delete store.sessions[evicted];
    MI.drawer.showToast("History full — oldest search dropped");
    MI.storage.save(store, true);
  }
};

MI.storage.startSession = function startSession(roleId, roleTitle, guidance) {
  const store = MI.storage.load();
  const id = `sess_${Date.now()}`;
  const now = new Date().toISOString();
  const session = {
    id, created_at: now, updated_at: now, role_id: roleId, role_title: roleTitle, guidance,
    status: "compiled", rubric: null, compile: null, score: null, analyses: {},
    rerank: null, approved_ids: [], shortlist_ids: [], export: null,
  };
  store.sessions[id] = session;
  store.order.unshift(id);
  while (store.order.length > MI.storage.CAP) {
    const evicted = store.order.pop();
    delete store.sessions[evicted];
  }
  MI.storage.save(store);
  MI.state.sessionId = id;
  MI.storage.updateSearchesCount();
  return id;
};

MI.storage.updateSearchesCount = function updateSearchesCount() {
  MI.el("count-searches").textContent = MI.storage.load().order.length;
};

MI.storage.updateSessionById = function updateSessionById(id, patch) {
  if (!id) return;
  const store = MI.storage.load();
  const session = store.sessions[id];
  if (!session) return;
  Object.assign(session, patch, { updated_at: new Date().toISOString() });
  MI.storage.save(store);
};

MI.storage.updateSession = function updateSession(patch) {
  MI.storage.updateSessionById(MI.state.sessionId, patch);
};

MI.storage.listSessions = function listSessions() {
  const store = MI.storage.load();
  return store.order.map((id) => store.sessions[id]).filter(Boolean);
};

MI.storage.getSession = function getSession(id) {
  return MI.storage.load().sessions[id] || null;
};

MI.storage.deleteSession = function deleteSession(id) {
  const store = MI.storage.load();
  delete store.sessions[id];
  store.order = store.order.filter((sid) => sid !== id);
  MI.storage.save(store);
  MI.storage.updateSearchesCount();
};

const VIEWS = ["overview", "sourcing", "shortlist", "searches", "outreach", "reports"];

MI.router = {
  init() {
    window.addEventListener("hashchange", MI.router.route);
    MI.router.route();
  },
  route() {
    const hash = location.hash.replace(/^#\//, "");
    const view = VIEWS.includes(hash) ? hash : "sourcing";
    MI.router.show(view);
  },
  show(view) {
    MI.state.view = view;
    VIEWS.forEach((v) => MI.el(`view-${v}`).classList.toggle("hidden", v !== view));
    document.querySelectorAll(".nav-item").forEach((a) => {
      a.classList.toggle("active", a.dataset.view === view);
    });
    if (view === "searches") MI.extras.renderSearches();
    if (view === "reports") MI.extras.renderReports();
    if (view === "overview") MI.extras.renderOverview();
    if (view === "outreach") MI.extras.renderOutreach();
    if (view === "shortlist") MI.extras.enterShortlistView();
  },
};

function initAccessCode() {
  const stored = sessionStorage.getItem("access_code");
  if (stored) {
    MI.state.accessCode = stored;
    MI.el("access-overlay").classList.add("hidden");
    MI.el("app").classList.remove("hidden");
    boot();
    return;
  }
  MI.el("access-submit").addEventListener("click", async () => {
    const code = MI.el("access-input").value.trim();
    if (!code) return;
    MI.state.accessCode = code;
    try {
      await MI.api("health", {}, "POST");
      sessionStorage.setItem("access_code", code);
      MI.el("access-overlay").classList.add("hidden");
      MI.el("app").classList.remove("hidden");
      boot();
    } catch (e) {
      MI.el("access-error").textContent = "Invalid access code.";
      MI.state.accessCode = null;
    }
  });
}

function renderRoleSwitcher() {
  MI.el("role-menu").innerHTML = MI.state.roles.map((r) => `
    <button class="role-menu-item${r.role_id === MI.state.roleId ? " active" : ""}" data-role-id="${r.role_id}">
      <span>${r.title}</span>
      <span class="role-menu-id">${r.role_id}</span>
    </button>`).join("");
  const current = MI.state.roles.find((r) => r.role_id === MI.state.roleId);
  MI.el("role-switcher-title").textContent = current ? current.title : "Select role";
}

function selectRole(roleId, skipConfirm) {
  const role = MI.state.roles.find((r) => r.role_id === roleId);
  if (!skipConfirm && MI.state.sessionId && roleId !== MI.state.roleId) {
    if (!confirm(`Start a new search for ${role.title}? Your current search is already auto-saved.`)) {
      MI.el("role-menu").classList.add("hidden");
      return;
    }
    MI.views.resetSourcingUI();
  }
  MI.state.roleId = roleId;
  renderRoleSwitcher();
  MI.el("role-menu").classList.add("hidden");
}

function wireRoleSwitcher() {
  MI.el("role-switcher").addEventListener("click", () => MI.el("role-menu").classList.toggle("hidden"));
  MI.el("role-menu").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".role-menu-item");
    if (btn) selectRole(btn.dataset.roleId);
  });
  document.addEventListener("click", (ev) => {
    if (!ev.target.closest("#role-switcher") && !ev.target.closest("#role-menu")) {
      MI.el("role-menu").classList.add("hidden");
    }
  });
}

async function boot() {
  const health = await MI.api("health", {}, "GET");
  MI.state.roles = health.roles;
  if (health.roles.length) selectRole(health.roles[0].role_id, true);
  wireRoleSwitcher();
  MI.el("compile-btn").addEventListener("click", () => MI.views.onCompile());
  MI.el("confirm-score-btn").addEventListener("click", () => MI.views.onConfirmScore());
  MI.views.wireCriteriaBar();
  MI.views.wireApproveCheckboxes();
  MI.drawer.wire();
  MI.extras.wireSearches();
  MI.extras.wireReports();
  MI.extras.wireOutreach();
  MI.extras.wireShortlistRoleSwitcher();
  MI.storage.updateSearchesCount();
  MI.router.init();
}

initAccessCode();
