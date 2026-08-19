/* Drawer, shortlist flow, toasts, modal, Shortlist view, export rendering. */
MI.drawer = {};

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
  MI.el("export-output").classList.remove("hidden");
  MI.el("markdown-preview").innerHTML = MI.drawer.mdToHtml(result.markdown);
  MI.el("download-md-btn").onclick = () => MI.drawer.download(`shortlist_${MI.state.roleId}.md`, result.markdown, "text/markdown");
  MI.el("download-audit-btn").onclick = () => MI.drawer.download(`audit_${MI.state.roleId}.json`, JSON.stringify(result.audit_json, null, 1), "application/json");
};
