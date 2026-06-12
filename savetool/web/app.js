const PY_FILES = [
  { path: "py/core.py", fs: "/home/pyodide/savetool/core.py" },
  { path: "py/js_api.py", fs: "/home/pyodide/savetool/js_api.py" },
  { path: "py/hxbit/init.py", fs: "/home/pyodide/savetool/hxbit/__init__.py" },
  { path: "py/hxbit/core.py", fs: "/home/pyodide/savetool/hxbit/core.py" },
  { path: "py/hxbit/debug.py", fs: "/home/pyodide/savetool/hxbit/debug.py" },
  { path: "py/hxbit/shims/init.py", fs: "/home/pyodide/savetool/hxbit/shims/__init__.py" },
  { path: "py/hxbit/shims/deadcells.py", fs: "/home/pyodide/savetool/hxbit/shims/deadcells.py" },
];

const state = {
  pyodide: null,
  api: null,
  loaded: false,
  fileName: null,
  checksumOk: false,
  chunks: [],
  featureFlagNames: {},
  dlcNames: {},
  header: null,
  activeTab: "header",
  selectedTreeNode: null,
};

const treeNodes = new Map();

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function setStatus(text, cls = "") {
  const bar = $("#status-bar");

  const debug = [];
  if (state.fileName) debug.push(state.fileName);
  if (state.loaded) {
    if (state.header) debug.push(`checksum:${state.checksumOk ? "ok" : "bad"}`);
    debug.push(`chunks:${state.chunks.length}`);
    debug.push(`tab:${state.activeTab}`);
  }
  const debugStr = debug.length ? ` [${debug.join(" | ")}]` : "";
  bar.textContent = text + debugStr;
  bar.className = cls ? cls : "";
}

async function initPyodide() {
  setStatus("loading pyodide…");
  const pyodide = await loadPyodide({ stdout: () => {}, stderr: () => {} });
  state.pyodide = pyodide;

  setStatus("installing python files…");
  pyodide.FS.mkdirTree("/home/pyodide/savetool/hxbit/shims");
  for (const { path, fs } of PY_FILES) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`Failed to fetch ${path}: ${res.status}`);
    const text = await res.text();
    pyodide.FS.writeFile(fs, text);
  }

  setStatus("importing modules…");
  await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/home/pyodide/savetool")
import js_api
  `);
  state.api = pyodide.pyimport("js_api");
  state.loaded = true;

  $("#file-input").disabled = false;
  $("#save-btn").disabled = false;
  setStatus("ready!");
}

async function openFile(file) {
  if (!state.loaded) return;
    setStatus(`loading ${file.name}…`);
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    const infoJson = state.api.load(bytes);
    const info = JSON.parse(infoJson);

    state.fileName = file.name;
    state.checksumOk = info.checksum_ok;
    state.chunks = info.chunks;
    state.featureFlagNames = info.feature_flag_names;
    state.dlcNames = info.dlc_names;
    state.header = {
      ...info.header,
      stored_checksum: info.stored_checksum,
      calculated_checksum: info.calculated_checksum,
    };
    treeNodes.clear();

    $("#app").hidden = false;
    $("#drop-hint").classList.add("hidden");

    renderTabs();
    activateTab("header");

    const cls = info.checksum_ok ? "ok" : "warn";
    const msg = info.checksum_ok ? "chk ok" : "chk INVALID";
    setStatus(`loaded ${file.name}. ${msg}.`, cls);
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message || err}`, "error");
  }
}

function renderTabs() {
  const tabs = $("#tabs");
  tabs.innerHTML = "";

  const headerBtn = document.createElement("button");
  headerBtn.className = "tab active";
  headerBtn.dataset.tab = "header";
  headerBtn.textContent = "Header";
  headerBtn.addEventListener("click", () => activateTab("header"));
  tabs.appendChild(headerBtn);

  for (const chunk of state.chunks) {
    const btn = document.createElement("button");
    btn.className = "tab";
    btn.dataset.tab = `chunk-${chunk.bit}`;
    btn.textContent = chunk.name;
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = chunk.type;
    btn.appendChild(badge);
    if (chunk.parse_error) {
      btn.title = `Parse warning: ${chunk.parse_error}`;
      badge.style.background = "var(--warning)";
      badge.style.color = "#000";
    } else if (chunk.error) {
      btn.title = `Error: ${chunk.error}`;
      badge.style.background = "var(--danger)";
    }
    btn.addEventListener("click", () => activateTab(`chunk-${chunk.bit}`));
    tabs.appendChild(btn);
  }
}

function activateTab(id) {
  state.activeTab = id;
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === id));

  let panel = $(`.tab-panel[data-tab="${id}"]`);
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "tab-panel";
    panel.dataset.tab = id;
    $("#tab-content").appendChild(panel);
  }
  if (!panel.dataset.rendered) {
    if (id === "header") {
      renderHeaderTab(panel);
    } else {
      const bit = Number(id.split("-")[1]);
      const chunk = state.chunks.find((c) => c.bit === bit);
      if (chunk) renderChunkPanel(panel, chunk);
    }
    panel.dataset.rendered = "true";
  }

  $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.tab === id));
}

function renderHeaderTab(panel) {
  panel.innerHTML = "";
  panel.className = "tab-panel form-pane";
  panel.dataset.tab = "header";

  const checksum = document.createElement("div");
  checksum.className = "checksum-line";
  const statusClass = state.checksumOk ? "ok" : "bad";
  const statusText = state.checksumOk ? "ok" : "bad";
  checksum.innerHTML = `
    <span class="${statusClass}">Checksum: ${statusText}</span>
    <span>Stored: ${state.header?.stored_checksum ?? ""}</span>
    <span>Calculated: ${state.header?.calculated_checksum ?? ""}</span>
  `;
  panel.appendChild(checksum);

  const form = document.createElement("div");
  form.className = "form-grid";
  form.innerHTML = `
    <label for="hdr-version">Format version</label>
    <input type="number" id="hdr-version" value="${state.header.version}">

    <label for="hdr-githash">Git commit hash</label>
    <input type="text" id="hdr-githash" value="${state.header.git_hash}" maxlength="40" pattern="[0-9a-fA-F]{40}">

    <label for="hdr-builddate">Build date</label>
    <input type="text" id="hdr-builddate" value="${state.header.build_date}">

    <label>Feature flags</label>
    <div id="hdr-flags" class="checkbox-grid"></div>
  `;
  panel.appendChild(form);

  const flagsDiv = $("#hdr-flags", panel);
  for (const [bit, name] of Object.entries(state.featureFlagNames)) {
    const enabled = state.header.feature_flags[bit];
    const row = document.createElement("label");
    row.className = "checkbox-row";
    row.innerHTML = `
      <input type="checkbox" data-bit="${bit}" ${enabled ? "checked" : ""}>
      <span>${name} (bit ${bit})</span>
    `;
    flagsDiv.appendChild(row);
  }

  const actions = document.createElement("div");
  actions.className = "form-actions";
  const applyBtn = document.createElement("button");
  applyBtn.id = "hdr-apply";
  applyBtn.textContent = "make it so!";
  actions.appendChild(applyBtn);
  panel.appendChild(actions);

  $("#hdr-apply", panel).addEventListener("click", () => {
    try {
      const version = $("#hdr-version", panel).value;
      const gitHash = $("#hdr-githash", panel).value;
      const buildDate = $("#hdr-builddate", panel).value;
      const flags = {};
      $$("#hdr-flags input[type=checkbox]", panel).forEach((cb) => {
        flags[cb.dataset.bit] = cb.checked;
      });
      state.api.set_header(version, gitHash, buildDate, JSON.stringify(flags));
      setStatus("Header changes applied.", "ok");
    } catch (err) {
      setStatus(`Header error: ${err.message || err}`, "error");
    }
  });
}

function renderChunkPanel(panel, chunk) {
  panel.innerHTML = "";

  if (chunk.type === "hxbit" || chunk.type === "hxbit_error") {
    renderHxbitPanel(panel, chunk);
  } else if (chunk.type === "date") {
    renderDatePanel(panel, chunk);
  } else if (chunk.type === "version") {
    renderVersionPanel(panel, chunk);
  } else if (chunk.type === "dlc") {
    renderDlcPanel(panel, chunk);
  } else {
    renderHexPanel(panel, chunk);
  }
}

function renderDatePanel(panel, chunk) {
  panel.className = "tab-panel form-pane";
  panel.dataset.tab = `chunk-${chunk.bit}`;
  panel.innerHTML = `
    <h3>${chunk.name}</h3>
    <div class="form-row">
      <label for="date-${chunk.bit}">Save date (YYYY-MM-DD HH:MM:SS, local time)</label>
      <input type="text" id="date-${chunk.bit}" value="${chunk.value}">
    </div>
    <div class="form-actions">
      <button id="date-apply-${chunk.bit}">make it so!</button>
    </div>
  `;
  $(`#date-apply-${chunk.bit}`, panel).addEventListener("click", () => {
    try {
      state.api.set_date(chunk.bit, $(`#date-${chunk.bit}`, panel).value);
      setStatus("time traveled!", "ok");
    } catch (err) {
      setStatus(`Date error: ${err.message || err}`, "error");
    }
  });
}

function renderVersionPanel(panel, chunk) {
  panel.className = "tab-panel form-pane";
  panel.dataset.tab = `chunk-${chunk.bit}`;
  panel.innerHTML = `
    <h3>${chunk.name}</h3>
    <div class="form-row">
      <label for="ver-${chunk.bit}">Game version number</label>
      <input type="text" id="ver-${chunk.bit}" value="${chunk.value}">
    </div>
    <div class="form-actions">
      <button id="ver-apply-${chunk.bit}">make it so!</button>
    </div>
  `;
  $(`#ver-apply-${chunk.bit}`, panel).addEventListener("click", () => {
    try {
      state.api.set_version(chunk.bit, $(`#ver-${chunk.bit}`, panel).value);
      setStatus("Version updated.", "ok");
    } catch (err) {
      setStatus(`Version error: ${err.message || err}`, "error");
    }
  });
}

function renderDlcPanel(panel, chunk) {
  panel.className = "tab-panel form-pane";
  panel.dataset.tab = `chunk-${chunk.bit}`;
  panel.innerHTML = `<h3>${chunk.name}</h3><div id="dlc-list-${chunk.bit}"></div><div class="form-actions"><button id="dlc-apply-${chunk.bit}">make it so!</button></div>`;
  const list = $(`#dlc-list-${chunk.bit}`, panel);
  for (const [bit, name] of Object.entries(state.dlcNames)) {
    const owned = chunk.owned[bit];
    const row = document.createElement("label");
    row.className = "checkbox-row";
    row.innerHTML = `
      <input type="checkbox" data-bit="${bit}" ${owned ? "checked" : ""}>
      <span>${name}</span>
    `;
    list.appendChild(row);
  }
  $(`#dlc-apply-${chunk.bit}`, panel).addEventListener("click", () => {
    const owned = {};
    $$(`#dlc-list-${chunk.bit} input[type=checkbox]`, panel).forEach((cb) => {
      owned[cb.dataset.bit] = cb.checked;
    });
    try {
      state.api.set_dlc(chunk.bit, JSON.stringify(owned));
      setStatus("DLC ownership updated.", "ok");
    } catch (err) {
      setStatus(`DLC error: ${err.message || err}`, "error");
    }
  });
}

function renderHexPanel(panel, chunk) {
  panel.className = "tab-panel hex-pane";
  panel.dataset.tab = `chunk-${chunk.bit}`;
  panel.innerHTML = `<pre>${escapeHtml(chunk.preview || "(no preview)")}</pre>`;
}

function renderHxbitPanel(panel, chunk) {
  panel.className = "tab-panel";
  panel.dataset.tab = `chunk-${chunk.bit}`;

  const split = document.createElement("div");
  split.className = "panel-split";

  const treePane = document.createElement("div");
  treePane.className = "tree-pane";
  treePane.innerHTML = `<ul class="tree" id="tree-${chunk.bit}"></ul>`;

  const detailPane = document.createElement("div");
  detailPane.className = "detail-pane";
  detailPane.id = `detail-${chunk.bit}`;
  detailPane.innerHTML = `<p class="help-text">Select a node to view or edit its value.</p>`;

  split.appendChild(treePane);
  split.appendChild(detailPane);
  panel.appendChild(split);

  if (chunk.error) {
    detailPane.innerHTML = `<p class="error-text">${escapeHtml(chunk.error)}</p>`;
    return;
  }

  const root = $(`#tree-${chunk.bit}`, panel);
  const rootItem = document.createElement("li");
  const rootNode = makeTreeNode(chunk.bit, [], "Root", "list", `${chunk.root_count} roots`, true);
  rootItem.appendChild(rootNode);
  root.appendChild(rootItem);
  toggleNode(rootNode, chunk.bit, []);
}

function makeTreeNode(bit, path, label, kind, summary, expandable, isCycle = false) {
  const node = document.createElement("div");
  node.className = "tree-node";
  node.dataset.bit = bit;
  node.dataset.path = JSON.stringify(path);
  treeNodes.set(`${bit}:${JSON.stringify(path)}`, node);

  const toggle = document.createElement("span");
  toggle.className = expandable ? "tree-toggle" : "tree-toggle placeholder";
  toggle.textContent = expandable ? "▶" : "";

  const icon = document.createElement("span");
  icon.className = "node-icon";
  icon.textContent = expandable ? "{}" : "•";

  const lbl = document.createElement("span");
  lbl.className = "node-label";
  lbl.textContent = label;

  const sum = document.createElement("span");
  sum.className = "node-summary";
  sum.textContent = summary;

  const k = document.createElement("span");
  k.className = "node-kind";
  k.textContent = kind;

  node.appendChild(toggle);
  node.appendChild(icon);
  node.appendChild(lbl);
  node.appendChild(sum);
  node.appendChild(k);

  if (expandable) {
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleNode(node, bit, path);
    });
    node.addEventListener("click", () => {
      selectNode(node, bit, path);
    });
  } else {
    node.addEventListener("click", () => {
      selectNode(node, bit, path);
    });
  }

  return node;
}

async function toggleNode(nodeEl, bit, path) {
  const toggle = $(".tree-toggle", nodeEl);
  const expanded = toggle.textContent === "▼";
  const li = nodeEl.closest("li");

  if (expanded) {
    toggle.textContent = "▶";
    const ul = li.querySelector(":scope > ul");
    if (ul) ul.remove();
    return;
  }

  toggle.textContent = "▼";
  await loadChildren(bit, path, li);
}

async function loadChildren(bit, path, parentLi, offset = 0, replace = false) {
  let ul = parentLi.querySelector(":scope > ul");
  if (!ul) {
    ul = document.createElement("ul");
    parentLi.appendChild(ul);
  }
  if (replace) ul.innerHTML = "";

  try {
    const res = state.api.tree_children(bit, JSON.stringify(path), offset);
    const data = JSON.parse(res);

    for (const child of data.children) {
      const li = document.createElement("li");
      li.appendChild(makeTreeNode(bit, child.path, child.label, child.kind, child.summary, child.expandable, child.is_cycle));
      ul.appendChild(li);
    }

    if (data.next_offset !== null) {
      const moreLi = document.createElement("li");
      const more = document.createElement("div");
      more.className = "tree-more";
      more.textContent = `more nodes! (${data.total - data.next_offset} left)`;
      more.addEventListener("click", () => {
        more.remove();
        loadChildren(bit, path, parentLi, data.next_offset);
      });
      moreLi.appendChild(more);
      ul.appendChild(moreLi);
    }
  } catch (err) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="error-text">${escapeHtml(err.message || err)}</span>`;
    ul.appendChild(li);
  }
}

async function selectNode(nodeEl, bit, path) {
  $$(".tree-node.selected").forEach((n) => n.classList.remove("selected"));
  nodeEl.classList.add("selected");
  state.selectedTreeNode = { bit, path };

  const detail = $(`#detail-${bit}`);
  detail.innerHTML = "<p class=\"help-text\">Loading…</p>";

  try {
    const res = state.api.tree_node(bit, JSON.stringify(path));
    const info = JSON.parse(res);
    renderNodeDetail(detail, bit, path, info);
  } catch (err) {
    detail.innerHTML = `<p class="error-text">${escapeHtml(err.message || err)}</p>`;
  }
}

function renderNodeDetail(container, bit, path, info) {
  container.innerHTML = "";

  const pathBar = document.createElement("div");
  pathBar.className = "path-bar";
  pathBar.textContent = info.path_str || "Root";
  container.appendChild(pathBar);

  const meta = document.createElement("div");
  meta.style.marginBottom = "12px";
  meta.innerHTML = `<span class="node-kind">${info.kind}</span> <span class="node-summary">${escapeHtml(info.summary)}</span>`;
  container.appendChild(meta);

  if (info.is_cycle) {
    container.innerHTML += `<p class="help-text">Circular reference — expand the original node to inspect.</p>`;
    return;
  }

  if (info.detail !== undefined) {
    const detail = document.createElement("div");
    detail.className = "detail-body";
    detail.textContent = info.detail;
    container.appendChild(detail);
  }

  if (info.editable) {
    const form = document.createElement("div");
    form.className = "form-row";
    form.style.marginTop = "16px";
    form.innerHTML = `
      <label for="edit-val">Value (${info.scalar_type})</label>
      <input type="text" id="edit-val" value="${escapeHtml(String(info.value ?? ""))}">
      <select id="edit-type">
        <option value="None" ${info.scalar_type === "None" ? "selected" : ""}>None</option>
        <option value="bool" ${info.scalar_type === "bool" ? "selected" : ""}>bool</option>
        <option value="int" ${info.scalar_type === "int" ? "selected" : ""}>int</option>
        <option value="float" ${info.scalar_type === "float" ? "selected" : ""}>float</option>
        <option value="str" ${info.scalar_type === "str" ? "selected" : ""}>str</option>
      </select>
      <div class="form-actions">
        <button id="edit-save">make it so!</button>
      </div>
      <p class="help-text">For ints you may use decimal (42) or hex (0x2a). Booleans accept true/false/1/0.</p>
      <p id="edit-error" class="error-text"></p>
    `;
    container.appendChild(form);

    $("#edit-save", form).addEventListener("click", async () => {
      const raw = $("#edit-val", form).value;
      const typeName = $("#edit-type", form).value;
      try {
        const updated = state.api.set_value(bit, JSON.stringify(path), typeName, raw);
        const updatedInfo = JSON.parse(updated);
        renderNodeDetail(container, bit, path, updatedInfo);
        refreshTreeLabels(bit, path);
        setStatus("Value updated.", "ok");
      } catch (err) {
        $("#edit-error", form).textContent = err.message || err;
      }
    });
  }

  if (info.kind !== "None" && info.kind !== "bool" && info.kind !== "int" && info.kind !== "float" && info.kind !== "str") {
    const schemasBtn = document.createElement("button");
    schemasBtn.textContent = "Show schemas";
    schemasBtn.style.marginTop = "12px";
    schemasBtn.addEventListener("click", async () => {
      try {
        const text = state.api.schemas_text(bit);
        showModal("Schemas", `<pre class="schemas-pane">${escapeHtml(text)}</pre>`);
      } catch (err) {
        setStatus(`Schemas error: ${err.message || err}`, "error");
      }
    });
    container.appendChild(schemasBtn);
  }
}

async function refreshTreeLabels(bit, path) {
  const node = treeNodes.get(`${bit}:${JSON.stringify(path)}`);
  if (!node) return;
  try {
    const res = state.api.tree_node(bit, JSON.stringify(path));
    const info = JSON.parse(res);
    const summary = $(".node-summary", node);
    if (summary) summary.textContent = info.summary;
  } catch (err) {}
}

function showModal(title, html) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const box = document.createElement("div");
  box.className = "modal-box";
  box.innerHTML = `
    <div class="modal-header">
      <strong>${escapeHtml(title)}</strong>
      <button id="modal-close" class="modal-close">×</button>
    </div>
    <div class="modal-body">${html}</div>
  `;
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  $("#modal-close", box).addEventListener("click", () => overlay.remove());
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function downloadSave() {
  if (!state.loaded) return;
  try {
    setStatus("packing save…");
    const bytes = state.api.serialise();
    const blob = new Blob([bytes], { type: "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = state.fileName ? `edited_${state.fileName}` : "edited_save.dat";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setStatus("Save downloaded.", "ok");
  } catch (err) {
    console.error(err);
    setStatus(`Download error: ${err.message || err}`, "error");
  }
}

function setupEvents() {
  $("#file-input").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) openFile(file);
  });

  $("#save-btn").addEventListener("click", downloadSave);

  document.addEventListener("dragover", (e) => {
    e.preventDefault();
    document.body.classList.add("drag-over");
  });

  document.addEventListener("dragleave", () => {
    document.body.classList.remove("drag-over");
  });

  document.addEventListener("drop", (e) => {
    e.preventDefault();
    document.body.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) openFile(file);
  });
}

initPyodide().catch((err) => {
  console.error(err);
  setStatus(`pyodide error: ${err.message || err}`, "error");
});

setupEvents();
