/* Candidate-Role Match Intelligence — vanilla JS, renders JSON only. All behavior lives in /core. */
const MI = {};

MI.state = {
  accessCode: null, roles: [], roleId: null, rubric: null, scoreResult: null,
  analyses: {}, rerankResult: null, approvedIds: new Set(),
  compiledAt: null, approvedAt: null, rejected: [], adjustments: [], guidance: "",
  view: "sourcing",
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

function selectRole(roleId) {
  MI.state.roleId = roleId;
  renderRoleSwitcher();
  MI.el("role-menu").classList.add("hidden");
  MI.el("sourcing-role-title").textContent = MI.state.roles.find((r) => r.role_id === roleId).title;
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
  if (health.roles.length) selectRole(health.roles[0].role_id);
  wireRoleSwitcher();
  MI.el("compile-btn").addEventListener("click", () => MI.views.onCompile());
  MI.el("confirm-score-btn").addEventListener("click", () => MI.views.onConfirmScore());
  MI.el("export-btn").addEventListener("click", () => MI.drawer.onExport());
  MI.router.init();
}

initAccessCode();
