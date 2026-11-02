import { ApiError, api, copyText, downloadFile } from "./api.js";
import {
  CAPABILITY_LABELS,
  capabilityChips,
  debounce,
  esc,
  formatDate,
  formatMoney,
  icon,
  providerAvatar,
  timeAgo,
} from "./ui.js";
import {
  availableCapabilities,
  dashboardView,
  detailView,
  keysView,
  modelsForCapability,
  selectedModelFor,
  settingsView,
} from "./views.js";

const FORMAT_LABELS = { env: ".env", python: "Python", curl: "cURL", js: "JavaScript" };
const FORMAT_ORDER = ["env", "python", "curl", "js"];

const state = {
  loading: true,
  error: "",
  providers: [],
  keys: [],
  models: [],
  stats: {},
  settings: {},
  app: {},
  clipboardPending: [],
  search: "",
  route: null,
  studio: null,
  sidebarOpen: false,
};

let modalState = null;
let clipboardTimer = null;
let captureEl = null;

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

// ---------------------------------------------------------------------------
// boot and routing
// ---------------------------------------------------------------------------
async function boot() {
  try {
    await loadState();
    state.loading = false;
    renderShell();
    state.route = parseHash();
    renderRoute({ scrollTop: true });
    startClipboardPolling();
    setTimeout(() => maybeCheckUpdates(false), 1200);
    window.addEventListener("hashchange", () => {
      if (modalState) closeModal(true);
      closeSidebar();
      state.route = parseHash();
      renderRoute({ scrollTop: true });
    });
  } catch (error) {
    renderFatal(error);
  }
}

async function loadState() {
  const data = await api("/api/state");
  state.providers = data.providers || [];
  state.keys = data.keys || [];
  state.models = data.models || [];
  state.stats = data.stats || {};
  state.settings = data.settings || {};
  state.app = data.app || {};
  state.clipboardPending = data.clipboard_pending || [];
  state.error = "";
}

function parseHash() {
  const raw = (location.hash || "").replace(/^#/, "") || "/dashboard";
  const parts = raw.split("/").filter(Boolean);
  if (parts[0] === "key" && parts[1]) return { name: "key", keyId: parts[1] };
  if (parts[0] === "platform" && parts[1]) return { name: "keys", providerId: parts[1] };
  if (parts[0] === "keys") return { name: "keys", providerId: "" };
  if (parts[0] === "settings") return { name: "settings" };
  return { name: "dashboard" };
}

function navigate(hash) {
  if (location.hash === hash) {
    state.route = parseHash();
    renderRoute({ preserveScroll: false });
    return;
  }
  location.hash = hash;
}

function renderFatal(error) {
  const message = error instanceof Error ? error.message : String(error);
  $("#app").innerHTML = `<div class="boot" style="max-width:520px;margin:0 auto;padding:24px;text-align:center">
    <div class="empty-icon">${icon("alert", 24)}</div>
    <h1 style="font-size:22px">打不开钥匙簿</h1>
    <p class="muted" style="font-size:13px;line-height:1.7">${esc(message)}</p>
    <button class="btn btn-primary" data-action="retry">重新连接</button>
  </div>`;
}

// ---------------------------------------------------------------------------
// shell
// ---------------------------------------------------------------------------
function renderShell() {
  $("#app").innerHTML = `<div class="app-shell">
    <aside class="sidebar" id="sidebar"></aside>
    <div class="sidebar-scrim" id="sidebar-scrim" hidden></div>
    <div class="main-col">
      <header class="topbar">
        <div class="topbar-left">
          <button class="btn btn-ghost btn-icon mobile-menu" data-action="sidebar-toggle" aria-label="打开菜单">${icon("menu", 18)}</button>
          <div class="searchbox">
            ${icon("search", 16)}
            <input id="search-input" autocomplete="off" placeholder="搜索 Key、项目、备注或模型…" aria-label="搜索" value="${esc(
              state.search
            )}">
            <kbd>Ctrl K</kbd>
          </div>
        </div>
        <div class="topbar-actions">
          <button class="btn btn-secondary" data-action="add-key">${icon("plus", 15)}<span class="btn-label">添加 Key</span></button>
        </div>
      </header>
      <main id="view" class="content" aria-live="polite"></main>
    </div>
  </div>`;
  renderSidebar();
}

function renderSidebar() {
  const sidebar = $("#sidebar");
  if (!sidebar) return;
  const route = state.route || parseHash();
  const allKeysActive = route.name === "keys" && !route.providerId;
  const dashboardActive = route.name === "dashboard";
  const settingsActive = route.name === "settings";
  const clipboardOn = state.settings.clipboard_watch === "1";
  const providers = state.providers.filter((provider) => provider.key_count > 0);

  sidebar.innerHTML = `
    <div class="brand">
      <div class="brand-mark">${icon("key", 20)}</div>
      <div class="brand-text">
        <div class="brand-name">API 钥匙簿</div>
        <div class="brand-sub">LOCAL KEY LEDGER</div>
      </div>
    </div>
    <div class="sidebar-scroll">
      <div class="nav-section">
        <button class="nav-item ${dashboardActive ? "active" : ""}" data-action="go-dashboard">
          ${icon("grid", 17, "nav-icon")} 总览
        </button>
        <button class="nav-item ${allKeysActive || route.name === "key" ? "active" : ""}" data-action="go-keys">
          ${icon("key", 17, "nav-icon")} 全部 Key
          <span class="nav-count">${state.keys.length}</span>
        </button>
      </div>
      <div class="nav-section">
        <div class="nav-label">平台</div>
        ${
          providers.length
            ? providers
                .map(
                  (provider) => `<button class="nav-item ${
                    route.name === "keys" && route.providerId === provider.id ? "active" : ""
                  }" data-action="go-platform" data-id="${esc(provider.id)}">
                    <span class="platform-dot" style="background:${esc(provider.color)}"></span>
                    <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(
                      provider.name
                    )}</span>
                    <span class="nav-count">${provider.key_count}</span>
                  </button>`
                )
                .join("")
            : `<div class="field-hint" style="padding:4px 10px 8px">还没有录入 Key</div>`
        }
      </div>
    </div>
    <div class="sidebar-foot">
      <div class="clip-status ${clipboardOn ? "on" : ""}">
        <span class="pulse"></span>
        ${clipboardOn ? "剪贴板监听中" : "剪贴板监听已关"}
      </div>
      <button class="nav-item ${settingsActive ? "active" : ""}" data-action="go-settings">
        ${icon("settings", 17, "nav-icon")} 设置
      </button>
    </div>`;
}

function renderRoute({ scrollTop = false, preserveScroll = false } = {}) {
  const view = $("#view");
  if (!view) return;
  const route = state.route || parseHash();
  state.route = route;
  let html = "";
  let key = null;

  if (route.name === "dashboard") {
    html = dashboardView(state);
    document.title = "总览 · API 钥匙簿";
  } else if (route.name === "keys") {
    html = keysView(state, filteredKeys(route.providerId), route.providerId || "");
    document.title = "全部 Key · API 钥匙簿";
  } else if (route.name === "key") {
    key = state.keys.find((item) => item.id === route.keyId) || null;
    if (key) {
      reconcileStudio(key);
      html = detailView(state, key, state.studio);
      document.title = `${key.label} · API 钥匙簿`;
    } else {
      html = detailView(state, null, null);
      document.title = "Key 不存在 · API 钥匙簿";
    }
  } else if (route.name === "settings") {
    html = settingsView(state);
    document.title = "设置 · API 钥匙簿";
  }

  const y = window.scrollY;
  view.innerHTML = html;
  renderSidebar();
  if (scrollTop) {
    window.scrollTo(0, 0);
  } else if (preserveScroll) {
    requestAnimationFrame(() => window.scrollTo(0, y));
  }

  if (key && state.studio) {
    updatePreviewDom();
    if (!state.studio.preview && !state.studio.previewLoading && !state.studio.previewError) {
      refreshPreview();
    }
  }
}

function filteredKeys(providerId = "") {
  const query = state.search.trim().toLowerCase();
  return state.keys.filter((key) => {
    if (providerId && key.provider.id !== providerId) return false;
    if (!query) return true;
    const haystack = [
      key.label,
      key.project,
      key.note,
      key.environment,
      key.provider.name,
      key.hint,
      key.env_prefix,
      ...(key.models || []).flatMap((model) => [
        model.model_id,
        model.display_name,
        ...(model.capabilities || []),
      ]),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

// ---------------------------------------------------------------------------
// studio
// ---------------------------------------------------------------------------
function preferredFormat(key, capability) {
  const model = modelsForCapability(key, capability)[0];
  const formats = model?.formats?.length ? model.formats : ["env"];
  const configured = state.settings.default_format || "env";
  if (formats.includes(configured)) return configured;
  return formats.includes("env") ? "env" : formats[0];
}

function makeStudio(key) {
  const capabilities = availableCapabilities(key);
  const capability = capabilities.includes("chat") ? "chat" : capabilities[0] || "chat";
  const selected = {};
  for (const item of capabilities) {
    const model = modelsForCapability(key, item)[0];
    if (model) selected[item] = model.id;
  }
  return {
    keyId: key.id,
    capability,
    format: preferredFormat(key, capability),
    selected,
    preview: "",
    previewLoading: false,
    previewError: "",
    includeComments: state.settings.include_comments === "1",
    directKey: state.settings.direct_key === "1",
    includeAll: false,
    requestSeq: 0,
  };
}

function reconcileStudio(key) {
  if (!state.studio || state.studio.keyId !== key.id) {
    state.studio = makeStudio(key);
    return;
  }
  const studio = state.studio;
  const capabilities = availableCapabilities(key);
  if (!capabilities.includes(studio.capability)) {
    studio.capability = capabilities.includes("chat") ? "chat" : capabilities[0] || "chat";
  }
  for (const capability of capabilities) {
    const models = modelsForCapability(key, capability);
    if (!models.some((model) => model.id === studio.selected[capability])) {
      if (models[0]) studio.selected[capability] = models[0].id;
      else delete studio.selected[capability];
    }
  }
  const current = selectedModelFor(key, studio);
  const formats = current?.formats?.length ? current.formats : ["env"];
  if (!formats.includes(studio.format)) {
    studio.format = formats.includes("env") ? "env" : formats[0];
  }
}

function studioSelections(key, studio) {
  const model = selectedModelFor(key, studio);
  if (!model) return [];
  const selections = [{ id: model.id, capability: studio.capability }];
  if (studio.format === "env" && studio.includeAll) {
    for (const [capability, modelId] of Object.entries(studio.selected)) {
      if (capability === studio.capability) continue;
      const other = key.models.find(
        (item) => item.id === modelId && (item.capabilities || []).includes(capability)
      );
      if (other) selections.push({ id: other.id, capability });
    }
  }
  return selections;
}

function currentStudioKey() {
  const route = state.route;
  if (!route || route.name !== "key") return null;
  return state.keys.find((item) => item.id === route.keyId) || null;
}

async function refreshPreview() {
  const key = currentStudioKey();
  const studio = state.studio;
  if (!key || !studio) return;
  const selections = studioSelections(key, studio);
  if (!selections.length) {
    studio.preview = "这个能力下还没有选中模型。";
    studio.previewError = "";
    updatePreviewDom();
    return;
  }
  const seq = ++studio.requestSeq;
  studio.previewLoading = true;
  studio.previewError = "";
  updatePreviewDom();
  try {
    const data = await api("/api/snippets", {
      method: "POST",
      body: {
        key_id: key.id,
        models: selections,
        format: studio.format,
        include_secret: false,
        direct_key: false,
        include_comments: studio.includeComments,
      },
    });
    if (seq !== studio.requestSeq) return;
    studio.preview = data.text || "";
  } catch (error) {
    if (seq !== studio.requestSeq) return;
    studio.preview = "";
    studio.previewError = error.message || "生成失败。";
    toast(studio.previewError, "err");
  } finally {
    if (seq === studio.requestSeq) {
      studio.previewLoading = false;
      updatePreviewDom();
    }
  }
}

function updatePreviewDom() {
  const studio = state.studio;
  if (!studio) return;
  const pre = $("#snippet-preview");
  const status = $(".code-status");
  const copyBtn = $('[data-action="copy-snippet"]');
  if (pre) {
    if (studio.previewLoading) pre.textContent = "正在生成预览…";
    else if (studio.previewError) pre.textContent = `// 生成失败\n// ${studio.previewError}`;
    else pre.textContent = studio.preview || "选择模型后，这里会显示可直接复制的片段。";
  }
  if (status) status.textContent = studio.previewLoading ? "生成中…" : "Key 已隐藏";
  if (copyBtn) copyBtn.disabled = studio.previewLoading || Boolean(studio.previewError);
}

// ---------------------------------------------------------------------------
// modals
// ---------------------------------------------------------------------------
function openModal({ title, subtitle = "", body, footer = "", width = "", onMount, onClose }) {
  closeModal(true);
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-backdrop" data-modal-backdrop>
    <div class="modal ${width}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-head">
        <div>
          <div class="modal-title" id="modal-title">${esc(title)}</div>
          ${subtitle ? `<div class="modal-sub">${esc(subtitle)}</div>` : ""}
        </div>
        <button class="modal-close" data-action="close-modal" aria-label="关闭">${icon("x", 17)}</button>
      </div>
      <div class="modal-body" id="modal-body">${body}</div>
      ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
    </div>
  </div>`;

  const backdrop = $("[data-modal-backdrop]");
  const dialog = $(".modal", backdrop);
  modalState = {
    root,
    backdrop,
    dialog,
    dirty: false,
    onClose: onClose || null,
    lastFocus: document.activeElement,
  };

  backdrop.addEventListener("mousedown", (event) => {
    if (event.target === backdrop) requestCloseModal();
  });
  dialog.addEventListener("input", () => {
    if (modalState) modalState.dirty = true;
  });
  dialog.addEventListener("change", () => {
    if (modalState) modalState.dirty = true;
  });
  dialog.addEventListener("keydown", handleModalKeydown);
  if (onMount) onMount(dialog);
  hideCaptureCard();
  const focusTarget =
    dialog.querySelector("[autofocus]") ||
    dialog.querySelector("input:not([type=hidden]), select, textarea, button");
  if (focusTarget) {
    requestAnimationFrame(() => focusTarget.focus());
  }
  return modalState;
}

function handleModalKeydown(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    requestCloseModal();
    return;
  }
  if (event.key !== "Tab") return;
  const focusables = $$(
    'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    modalState.dialog
  ).filter((element) => element.offsetParent !== null);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function requestCloseModal() {
  if (!modalState) return;
  if (modalState.dirty) {
    const discard = window.confirm("有未保存的修改，确定要放弃吗？");
    if (!discard) return;
  }
  closeModal(true);
}

function closeModal(force = false) {
  if (!modalState) return;
  if (!force && modalState.dirty) {
    const discard = window.confirm("有未保存的修改，确定要放弃吗？");
    if (!discard) return;
  }
  const { onClose, lastFocus } = modalState;
  modalState = null;
  $("#modal-root").innerHTML = "";
  if (lastFocus && typeof lastFocus.focus === "function") {
    requestAnimationFrame(() => lastFocus.focus());
  }
  if (onClose) onClose();
  setTimeout(pollClipboard, 400);
}

function setModalError(message) {
  const body = $("#modal-body");
  if (!body) return;
  let box = $("#modal-error");
  if (!box) {
    box = document.createElement("div");
    box.id = "modal-error";
    box.className = "banner banner-error";
    body.prepend(box);
  }
  if (!message) {
    box.remove();
    return;
  }
  box.innerHTML = `${icon("alert", 15)}<div>${esc(message)}</div>`;
}

function confirmDialog({ title, message, confirmText = "确认", danger = true }) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      closeModal(true);
      resolve(value);
    };
    openModal({
      title,
      body: `<div class="banner ${danger ? "banner-error" : "banner-info"}">${icon(
        danger ? "alert" : "info",
        16
      )}<div>${esc(message)}</div></div>`,
      footer: `<div class="foot-left">这个操作会立即生效</div>
        <div class="foot-actions">
          <button class="btn btn-secondary" data-action="confirm-cancel">取消</button>
          <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-action="confirm-ok">${esc(
        confirmText
      )}</button>
        </div>`,
      width: "narrow",
      onMount(dialog) {
        $('[data-action="confirm-cancel"]', dialog).addEventListener("click", () => finish(false));
        $('[data-action="confirm-ok"]', dialog).addEventListener("click", () => finish(true));
      },
      onClose() {
        if (!settled) {
          settled = true;
          resolve(false);
        }
      },
    });
  });
}

// ---------------------------------------------------------------------------
// add / edit key
// ---------------------------------------------------------------------------
function providerModels(providerId) {
  return state.models
    .filter((model) => model.provider_id === providerId)
    .sort((a, b) => {
      const capA = (a.capabilities || [])[0] || "";
      const capB = (b.capabilities || [])[0] || "";
      return capA.localeCompare(capB) || a.model_id.localeCompare(b.model_id);
    });
}

function renderModelPicker(providerId, selectedIds) {
  const models = providerModels(providerId);
  if (!models.length) {
    return `<div class="banner banner-info">${icon("info", 15)}<div>这个平台还没有模型。可以先保存 Key，再到“管理模型”里添加自定义模型。</div></div>`;
  }
  const selected = selectedIds === undefined ? new Set(models.map((model) => model.id)) : new Set(selectedIds);
  return `<div class="check-tools">
      <span class="check-tools-note">已选 ${models.filter((model) => selected.has(model.id)).length} / ${models.length}</span>
      <div class="btn-row">
        <button class="btn btn-ghost btn-sm" type="button" data-action="select-all-models">全选</button>
        <button class="btn btn-ghost btn-sm" type="button" data-action="clear-models">清空</button>
      </div>
    </div>
    <div class="check-grid" style="margin-top:8px">
      ${models
        .map(
          (model) => `<label class="check-card">
            <input type="checkbox" name="model_ids" value="${esc(model.id)}" ${
            selected.has(model.id) ? "checked" : ""
          }>
            <div class="check-card-main">
              <div class="check-card-name">${esc(model.display_name)}</div>
              <div class="check-card-id">${esc(model.model_id)}</div>
              <div class="check-card-tags">${capabilityChips(model.capabilities)}</div>
            </div>
          </label>`
        )
        .join("")}
    </div>`;
}

function openAddKeyModal(draft = null, keyToEdit = null) {
  const isEdit = Boolean(keyToEdit);
  const providerId = draft?.provider_id || keyToEdit?.provider?.id || state.providers[0]?.id || "";
  const provider = state.providers.find((item) => item.id === providerId) || state.providers[0];
  let selectedIds;
  if (isEdit) {
    selectedIds = (keyToEdit.models || []).map((model) => model.id);
  } else if (draft?.models?.length) {
    const hints = new Set(draft.models.map((model) => model.model_id));
    selectedIds = providerModels(providerId)
      .filter((model) => hints.has(model.model_id))
      .map((model) => model.id);
  } else {
    selectedIds = providerModels(providerId).map((model) => model.id);
  }

  const title = isEdit ? "编辑 Key" : "添加 API Key";
  const subtitle = isEdit
    ? "修改用途、备注或模型勾选；API Key 留空表示不修改。"
    : "粘贴一次，平台、地址和模型会自动带入。保存前可以改。";

  const body = `
    ${
      isEdit
        ? ""
        : `<div class="form-section">
            <div class="form-section-title">${icon("clipboard", 13)} 从文本识别</div>
            <textarea class="textarea mono" id="import-text" spellcheck="false" placeholder="粘贴 .env、JSON、curl 或单独的 API Key…"></textarea>
            <div class="btn-row">
              <button class="btn btn-secondary btn-sm" type="button" data-action="parse-paste">${icon(
                "sparkles",
                14
              )} 识别粘贴内容</button>
              <span class="field-hint" id="parse-result">识别后会自动填入下面的字段</span>
            </div>
          </div>`
    }
    <form id="key-form" class="form-section" autocomplete="off">
      <div class="form-grid">
        <div class="field">
          <label class="field-label" for="key-provider">平台</label>
          <select class="select" id="key-provider" name="provider_id" data-provider-select ${
            isEdit ? "disabled" : ""
          }>
            ${state.providers
              .map(
                (item) =>
                  `<option value="${esc(item.id)}" ${item.id === providerId ? "selected" : ""}>${esc(
                    item.name
                  )}</option>`
              )
              .join("")}
          </select>
          ${isEdit ? `<input type="hidden" name="provider_id" value="${esc(providerId)}">` : ""}
        </div>
        <div class="field">
          <label class="field-label" for="key-label">名称</label>
          <input class="input" id="key-label" name="label" maxlength="80" required value="${esc(
            keyToEdit?.label || draft?.label || ""
          )}" placeholder="例如：LLM Wiki 主 Key">
        </div>

        <div class="field span-2">
          <label class="field-label" for="key-secret">API Key <span class="optional">${
            isEdit ? "留空不修改" : "必填"
          }</span></label>
          <div class="input-with-action">
            <input class="input mono" id="key-secret" name="secret" type="password" autocomplete="off" spellcheck="false" ${
              isEdit ? "" : "required"
            } value="${esc(draft?.secret || "")}" placeholder="${isEdit ? "不修改就留空" : "sk-…"}">
            <button class="btn btn-ghost btn-sm" type="button" data-action="toggle-secret" aria-label="显示或隐藏 Key">${icon(
              "eye",
              14
            )}</button>
          </div>
        </div>

        <div class="field">
          <label class="field-label" for="key-base">Base URL <span class="optional">可选</span></label>
          <input class="input mono" id="key-base" name="base_url_override" value="${esc(
            draft?.base_url || keyToEdit?.base_url_override || ""
          )}" placeholder="${esc(provider?.default_base_url || "https://…")}">
          <div class="field-hint">留空使用平台默认地址；自定义平台建议填写。</div>
        </div>
        <div class="field">
          <label class="field-label" for="key-prefix">环境变量前缀</label>
          <input class="input mono" id="key-prefix" name="env_prefix" maxlength="48" value="${esc(
            keyToEdit?.env_prefix || draft?.env_prefix || provider?.env_prefix || "API"
          )}" placeholder="LLM_WIKI" data-prefix-input>
          <div class="field-hint">生成的变量会变成 <span class="code-inline" id="prefix-preview">${
            keyToEdit?.env_prefix || draft?.env_prefix || provider?.env_prefix || "API"
          }_API_KEY</span>。</div>
        </div>

        <div class="field">
          <label class="field-label" for="key-project">项目 / 用途</label>
          <input class="input" id="key-project" name="project" maxlength="120" value="${esc(
            keyToEdit?.project || ""
          )}" placeholder="例如：LLM Wiki 文档站">
        </div>
        <div class="field">
          <label class="field-label" for="key-env">环境</label>
          <select class="select" id="key-env" name="environment">
            ${["开发", "测试", "生产", "个人"]
              .map(
                (item) =>
                  `<option value="${item}" ${
                    (keyToEdit?.environment || "开发") === item ? "selected" : ""
                  }>${item}</option>`
              )
              .join("")}
          </select>
        </div>

        <div class="field">
          <label class="field-label" for="key-expires">过期时间 <span class="optional">可选</span></label>
          <input class="input" id="key-expires" name="expires_at" type="date" value="${esc(
            keyToEdit?.expires_at || ""
          )}">
        </div>
        <div class="field span-2">
          <label class="field-label" for="key-note">备注</label>
          <textarea class="textarea" id="key-note" name="note" maxlength="2000" placeholder="例如：只给内部知识库用，额度每月 20 元。">${esc(
            keyToEdit?.note || ""
          )}</textarea>
        </div>
      </div>

      <div class="form-section">
        <div class="form-section-title">${icon("layers", 13)} 可用模型</div>
        <div id="model-picker">${renderModelPicker(providerId, selectedIds)}</div>
      </div>
    </form>
  `;

  const footer = `<div class="foot-left">Key 会在保存时加密，列表只显示尾部。</div>
    <div class="foot-actions">
      <button class="btn btn-secondary" type="button" data-action="close-modal">取消</button>
      <button class="btn btn-primary" type="submit" form="key-form" data-action="save-key">${icon(
        "check",
        15
      )} ${isEdit ? "保存修改" : "保存 Key"}</button>
    </div>`;

  openModal({
    title,
    subtitle,
    body,
    footer,
    width: "wide",
    onMount(dialog) {
      const form = $("#key-form", dialog);
      const providerSelect = $("#key-provider", dialog);
      const prefixInput = $("#key-prefix", dialog);
      const baseInput = $("#key-base", dialog);

      const updatePrefixHint = () => {
        const preview = $("#prefix-preview", dialog);
        if (!preview) return;
        const prefix = (prefixInput.value || "API")
          .replace(/[^A-Za-z0-9_]/g, "_")
          .replace(/^_+|_+$/g, "")
          .toUpperCase();
        preview.textContent = `${prefix || "API"}_API_KEY`;
      };

      prefixInput.addEventListener("input", () => {
        prefixInput.dataset.touched = "1";
        updatePrefixHint();
      });

      providerSelect?.addEventListener("change", () => {
        const nextProvider = state.providers.find((item) => item.id === providerSelect.value);
        if (!nextProvider) return;
        if (!prefixInput.dataset.touched) prefixInput.value = nextProvider.env_prefix || "API";
        updatePrefixHint();
        baseInput.placeholder = nextProvider.default_base_url || "https://…";
        const ids = providerModels(nextProvider.id).map((model) => model.id);
        $("#model-picker", dialog).innerHTML = renderModelPicker(nextProvider.id, ids);
      });

      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await saveKeyForm(form, isEdit, keyToEdit, dialog);
      });

      dialog.addEventListener("click", async (event) => {
        const actionEl = event.target.closest("[data-action]");
        if (!actionEl) return;
        const action = actionEl.dataset.action;
        if (action === "parse-paste") {
          event.preventDefault();
          const textarea = $("#import-text", dialog);
          const text = textarea?.value || "";
          if (!text.trim()) {
            setModalError("先粘贴一段内容，再点识别。");
            return;
          }
          await withBusy(actionEl, "识别中…", async () => {
            try {
              const parsed = await api("/api/import/parse", {
                method: "POST",
                body: { text },
              });
              if (!parsed.ok) {
                setModalError(parsed.error || "没有识别到 API Key。");
                return;
              }
              applyDraftToForm(parsed, dialog);
              setModalError("");
            } catch (error) {
              setModalError(error.message);
            }
          });
        } else if (action === "toggle-secret") {
          event.preventDefault();
          const secret = $("#key-secret", dialog);
          if (!secret) return;
          const showing = secret.type === "text";
          secret.type = showing ? "password" : "text";
          actionEl.innerHTML = icon(showing ? "eye" : "eye-off", 14);
        } else if (action === "select-all-models") {
          event.preventDefault();
          $$('input[name="model_ids"]', dialog).forEach((input) => {
            input.checked = true;
          });
          modalState.dirty = true;
        } else if (action === "clear-models") {
          event.preventDefault();
          $$('input[name="model_ids"]', dialog).forEach((input) => {
            input.checked = false;
          });
          modalState.dirty = true;
        }
      });

      if (draft) {
        applyDraftToForm(draft, dialog, false);
      }
    },
  });
}

function applyDraftToForm(draft, dialog, markDirty = true) {
  const providerSelect = $("#key-provider", dialog);
  if (draft.provider_id && state.providers.some((item) => item.id === draft.provider_id)) {
    providerSelect.value = draft.provider_id;
  }
  const providerId = providerSelect.value;
  const provider = state.providers.find((item) => item.id === providerId);
  const baseInput = $("#key-base", dialog);
  const prefixInput = $("#key-prefix", dialog);
  const labelInput = $("#key-label", dialog);
  const secretInput = $("#key-secret", dialog);

  if (draft.base_url) baseInput.value = draft.base_url;
  if (draft.env_prefix) prefixInput.value = draft.env_prefix;
  if (draft.label) labelInput.value = draft.label;
  if (draft.secret) secretInput.value = draft.secret;
  if (provider) baseInput.placeholder = provider.default_base_url || "https://…";

  const hints = new Set((draft.models || []).map((item) => item.model_id));
  let selectedIds = providerModels(providerId)
    .filter((model) => hints.has(model.model_id))
    .map((model) => model.id);
  if (!selectedIds.length) selectedIds = providerModels(providerId).map((model) => model.id);
  $("#model-picker", dialog).innerHTML = renderModelPicker(providerId, selectedIds);
  const prefixPreview = $("#prefix-preview", dialog);
  if (prefixPreview) {
    const cleanPrefix = (prefixInput.value || "API")
      .replace(/[^A-Za-z0-9_]/g, "_")
      .replace(/^_+|_+$/g, "")
      .toUpperCase();
    prefixPreview.textContent = `${cleanPrefix || "API"}_API_KEY`;
  }

  const result = $("#parse-result", dialog);
  if (result) {
    const bits = [draft.source === "env" ? ".env" : draft.source === "curl" ? "curl" : draft.source === "json" ? "JSON" : "Key"];
    if (draft.provider_id) bits.push(provider?.name || draft.provider_id);
    if (draft.models?.length) bits.push(`${draft.models.length} 个模型`);
    result.textContent = `已识别：${bits.join(" · ")}，确认后保存。`;
  }
  if (markDirty && modalState) modalState.dirty = true;
}

async function saveKeyForm(form, isEdit, keyToEdit, dialog) {
  setModalError("");
  const formData = new FormData(form);
  const providerId = formData.get("provider_id")?.toString() || "";
  const label = (formData.get("label")?.toString() || "").trim();
  const secret = (formData.get("secret")?.toString() || "").trim();
  const modelIds = formData.getAll("model_ids").map(String);
  const baseUrl = (formData.get("base_url_override")?.toString() || "").trim();
  const envPrefix = (formData.get("env_prefix")?.toString() || "")
    .replace(/[^A-Za-z0-9_]/g, "_")
    .replace(/^_+|_+$/g, "")
    .toUpperCase();
  const provider = state.providers.find((item) => item.id === providerId);

  if (!providerId) return setModalError("请选择平台。");
  if (!label) return setModalError("请填写一个名称，方便之后辨认。");
  if (!isEdit && !secret) return setModalError("请填写 API Key。");
  if (!isEdit && provider?.is_custom && !baseUrl) {
    return setModalError("自定义平台需要填写 Base URL。");
  }
  if (!envPrefix) return setModalError("环境变量前缀不能为空。");

  const payload = {
    provider_id: providerId,
    label,
    base_url_override: baseUrl,
    env_prefix: envPrefix,
    project: formData.get("project")?.toString() || "",
    environment: formData.get("environment")?.toString() || "开发",
    note: formData.get("note")?.toString() || "",
    expires_at: formData.get("expires_at")?.toString() || "",
    model_ids: modelIds,
  };
  if (!isEdit || secret) payload.secret = secret;

  const submit = $('[data-action="save-key"]', dialog);
  await withBusy(submit, isEdit ? "保存中…" : "创建中…", async () => {
    try {
      const data = await api(isEdit ? `/api/keys/${keyToEdit.id}` : "/api/keys", {
        method: isEdit ? "PATCH" : "POST",
        body: payload,
      });
      const saved = data.key;
      await loadState();
      closeModal(true);
      renderSidebar();
      toast(isEdit ? "Key 已更新" : "Key 已保存", "ok");
      if (saved?.id) {
        navigate(`#/key/${saved.id}`);
        if (state.route?.keyId === saved.id) renderRoute({ preserveScroll: false });
      }
    } catch (error) {
      setModalError(error.message);
      toast(error.message, "err");
    }
  });
}

// ---------------------------------------------------------------------------
// model manager
// ---------------------------------------------------------------------------
async function openModelManager(keyId) {
  const key = state.keys.find((item) => item.id === keyId);
  if (!key) return;
  const models = providerModels(key.provider.id);
  const selected = new Set((key.models || []).map((model) => model.id));
  const apiStyles = [
    ["openai_chat", "OpenAI 兼容 · 对话"],
    ["openai_embedding", "OpenAI 兼容 · Embedding"],
    ["openai_image", "OpenAI 兼容 · 图像"],
    ["anthropic_messages", "Anthropic Messages"],
    ["gemini_generate", "Gemini generateContent"],
    ["gemini_embedding", "Gemini Embedding"],
    ["dashscope_multimodal", "DashScope 多模态"],
    ["dashscope_embedding", "DashScope Embedding"],
    ["dashscope_rerank", "DashScope Rerank"],
    ["dashscope_image", "DashScope 图像"],
    ["zhipu_rerank", "智谱 Rerank"],
  ];

  const body = `
    <div class="flex items-center justify-between gap-8 mb-12" style="flex-wrap:wrap">
      <div class="field-hint">勾选这个 Key 实际能调用的模型。不同能力分开选。</div>
      <div class="btn-row">
        <button class="btn btn-secondary btn-sm" type="button" data-action="fetch-models" data-id="${esc(
          key.id
        )}">${icon("refresh", 13)} 从平台拉取</button>
      </div>
    </div>
    <form id="model-manager-form">
      <div class="check-tools">
        <span class="check-tools-note">${models.length} 个平台模型 · 已选 ${models.filter((model) => selected.has(model.id)).length}</span>
        <div class="btn-row">
          <button class="btn btn-ghost btn-sm" type="button" data-action="manager-select-all">全选</button>
          <button class="btn btn-ghost btn-sm" type="button" data-action="manager-clear">清空</button>
        </div>
      </div>
      <div class="check-grid" style="margin-top:10px">
        ${
          models.length
            ? models
                .map(
                  (model) => `<label class="check-card">
                    <input type="checkbox" name="model_ids" value="${esc(model.id)}" ${
                    selected.has(model.id) ? "checked" : ""
                  }>
                    <div class="check-card-main">
                      <div class="check-card-name">${esc(model.display_name)}</div>
                      <div class="check-card-id">${esc(model.model_id)}</div>
                      <div class="check-card-tags">${capabilityChips(model.capabilities)}</div>
                    </div>
                  </label>`
                )
                .join("")
            : `<div class="field-hint">这个平台还没有模型，用下面的表单添加一个。</div>`
        }
      </div>

      <div class="form-section" style="margin-top:16px">
        <details>
          <summary style="cursor:pointer;font-size:12px;font-weight:650;color:var(--brand-strong)">${icon(
            "plus",
            13
          )} 添加自定义模型</summary>
          <div class="form-grid" style="margin-top:12px">
            <div class="field">
              <label class="field-label">模型 ID</label>
              <input class="input mono" name="model_id" placeholder="例如 qwen-plus">
            </div>
            <div class="field">
              <label class="field-label">显示名称</label>
              <input class="input" name="display_name" placeholder="例如 Qwen Plus">
            </div>
            <div class="field">
              <label class="field-label">能力</label>
              <select class="select" name="capability">
                ${Object.entries(CAPABILITY_LABELS)
                  .map(([value, label]) => `<option value="${value}">${label}</option>`)
                  .join("")}
              </select>
            </div>
            <div class="field">
              <label class="field-label">调用方式</label>
              <select class="select" name="api_style">
                ${apiStyles
                  .map(([value, label]) => `<option value="${value}">${label}</option>`)
                  .join("")}
              </select>
            </div>
            <div class="field span-2">
              <label class="field-label">Base URL <span class="optional">可选</span></label>
              <input class="input mono" name="base_url" placeholder="${esc(
                key.provider.default_base_url || "https://…"
              )}">
            </div>
          </div>
          <div class="btn-row" style="margin-top:10px">
            <button class="btn btn-secondary btn-sm" type="submit" data-action="add-model">${icon(
              "plus",
              13
            )} 添加模型</button>
            <span class="field-hint">添加后会尝试自动勾选。</span>
          </div>
        </details>
      </div>
    </form>
  `;

  openModal({
    title: `管理模型 · ${key.label}`,
    subtitle: `${key.provider.name} · ${key.models.length} 个已选模型`,
    body,
    width: "wide",
    footer: `<div class="foot-left">模型会决定片段工坊里的调用方式。</div>
      <div class="foot-actions">
        <button class="btn btn-secondary" type="button" data-action="close-modal">取消</button>
        <button class="btn btn-primary" type="submit" form="model-manager-form" data-action="save-models">${icon(
          "check",
          15
        )} 保存选择</button>
      </div>`,
    onMount(dialog) {
      const form = $("#model-manager-form", dialog);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitter = event.submitter;
        if (submitter?.dataset.action === "add-model") {
          await addCustomModel(form, key, submitter, dialog);
          return;
        }
        await saveModelSelection(form, key, submitter);
      });

      dialog.addEventListener("click", async (event) => {
        const actionEl = event.target.closest("[data-action]");
        if (!actionEl) return;
        const action = actionEl.dataset.action;
        if (action === "manager-select-all") {
          event.preventDefault();
          $$('input[name="model_ids"]', dialog).forEach((input) => {
            input.checked = true;
          });
          modalState.dirty = true;
        } else if (action === "manager-clear") {
          event.preventDefault();
          $$('input[name="model_ids"]', dialog).forEach((input) => {
            input.checked = false;
          });
          modalState.dirty = true;
        } else if (action === "fetch-models") {
          event.preventDefault();
          await withBusy(actionEl, "拉取中…", async () => {
            try {
              const result = await api(`/api/keys/${key.id}/fetch-models`, {
                method: "POST",
                body: { auto_enable: true },
              });
              await loadState();
              closeModal(true);
              toast(
                result.count ? `已新增 ${result.count} 个模型` : "没有发现新模型",
                result.count ? "ok" : "warn"
              );
              openModelManager(key.id);
            } catch (error) {
              toast(error.message, "err");
            }
          });
        }
      });
    },
  });
}

async function saveModelSelection(form, key, submitter) {
  const modelIds = new FormData(form).getAll("model_ids").map(String);
  await withBusy(submitter, "保存中…", async () => {
    try {
      await api(`/api/keys/${key.id}/models`, {
        method: "POST",
        body: { model_ids: modelIds },
      });
      await loadState();
      if (state.studio?.keyId === key.id) state.studio = null;
      closeModal(true);
      renderRoute({ preserveScroll: true });
      toast("模型选择已保存", "ok");
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

async function addCustomModel(form, key, submitter, dialog) {
  const data = new FormData(form);
  const modelId = (data.get("model_id")?.toString() || "").trim();
  if (!modelId) {
    toast("先填写模型 ID。", "warn");
    return;
  }
  const capability = data.get("capability")?.toString() || "chat";
  const payload = {
    provider_id: key.provider.id,
    model_id: modelId,
    display_name: (data.get("display_name")?.toString() || modelId).trim(),
    capabilities: [capability],
    api_style: data.get("api_style")?.toString() || "openai_chat",
    base_url: data.get("base_url")?.toString() || "",
  };
  await withBusy(submitter, "添加中…", async () => {
    try {
      const result = await api(`/api/providers/${key.provider.id}/models`, {
        method: "POST",
        body: payload,
      });
      const currentIds = [...new Set((key.models || []).map((model) => model.id))];
      await api(`/api/keys/${key.id}/models`, {
        method: "POST",
        body: { model_ids: [...currentIds, result.model.id] },
      });
      await loadState();
      if (state.studio?.keyId === key.id) state.studio = null;
      closeModal(true);
      toast("模型已添加并勾选", "ok");
      openModelManager(key.id);
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

// ---------------------------------------------------------------------------
// balance
// ---------------------------------------------------------------------------
function openBalanceModal(key) {
  const balance = key.balance || {};
  const currencies = ["CNY", "USD", "EUR"];
  if (balance.currency && !currencies.includes(balance.currency)) currencies.push(balance.currency);
  const body = `<form id="balance-form" class="form-section">
    <div class="form-grid">
      <div class="field">
        <label class="field-label">余额金额</label>
        <input class="input" type="number" step="0.01" name="amount" value="${esc(
          balance.amount ?? ""
        )}" placeholder="例如 20.00">
      </div>
      <div class="field">
        <label class="field-label">币种</label>
        <select class="select" name="currency">
          ${currencies
            .map(
              (item) =>
                `<option value="${item}" ${(balance.currency || "CNY") === item ? "selected" : ""}>${item}</option>`
            )
            .join("")}
        </select>
      </div>
      <div class="field">
        <label class="field-label">配额总量 <span class="optional">可选</span></label>
        <input class="input" type="number" step="0.01" name="quota_total" value="${esc(
          balance.quota_total ?? ""
        )}">
      </div>
      <div class="field">
        <label class="field-label">已用配额 <span class="optional">可选</span></label>
        <input class="input" type="number" step="0.01" name="quota_used" value="${esc(
          balance.quota_used ?? ""
        )}">
      </div>
      <div class="field">
        <label class="field-label">剩余额度 <span class="optional">可选</span></label>
        <input class="input" type="number" step="0.01" name="quota_remaining" value="${esc(
          balance.quota_remaining ?? ""
        )}">
      </div>
      <div class="field">
        <label class="field-label">额度单位</label>
        <input class="input" name="quota_unit" value="${esc(
          balance.quota_unit || ""
        )}" placeholder="tokens / 次 / 元">
      </div>
      <div class="field">
        <label class="field-label">到期时间 <span class="optional">可选</span></label>
        <input class="input" type="date" name="expires_at" value="${esc(
          balance.expires_at || ""
        )}">
      </div>
      <div class="field span-2">
        <label class="field-label">备注</label>
        <input class="input" name="note" value="${esc(
          balance.note || ""
        )}" placeholder="例如：赠送额度，月底到期">
      </div>
    </div>
    <p class="field-hint">至少填写余额或一个额度字段。每次保存都会保留一条历史记录。</p>
  </form>`;

  openModal({
    title: `记录余额 · ${key.label}`,
    subtitle: "手动记录一个时间点，之后可以在详情里回看历史。",
    body,
    width: "narrow",
    footer: `<div class="foot-left">来源会标记为“手动记录”。</div>
      <div class="foot-actions">
        <button class="btn btn-secondary" type="button" data-action="close-modal">取消</button>
        <button class="btn btn-primary" type="submit" form="balance-form" data-action="save-balance">${icon(
          "check",
          15
        )} 保存记录</button>
      </div>`,
    onMount(dialog) {
      const form = $("#balance-form", dialog);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitter = event.submitter;
        const data = new FormData(form);
        const payload = {};
        for (const keyName of [
          "amount",
          "quota_total",
          "quota_used",
          "quota_remaining",
        ]) {
          const value = data.get(keyName)?.toString().trim();
          const number = value === "" ? null : Number(value);
          if (number !== null && !Number.isFinite(number)) {
            toast("余额和额度需要填写有效数字。", "warn");
            return;
          }
          payload[keyName] = number;
        }
        if (
          [payload.amount, payload.quota_total, payload.quota_used, payload.quota_remaining].every(
            (value) => value === null || Number.isNaN(value)
          )
        ) {
          toast("至少填写余额或一个额度字段。", "warn");
          return;
        }
        payload.currency = data.get("currency")?.toString() || "CNY";
        payload.quota_unit = data.get("quota_unit")?.toString() || "";
        payload.expires_at = data.get("expires_at")?.toString() || "";
        payload.note = data.get("note")?.toString() || "";
        await withBusy(submitter, "保存中…", async () => {
          try {
            await api(`/api/keys/${key.id}/balance`, { method: "POST", body: payload });
            await loadState();
            closeModal(true);
            renderRoute({ preserveScroll: true });
            toast("余额记录已保存", "ok");
          } catch (error) {
            toast(error.message, "err");
          }
        });
      });
    },
  });
}

async function refreshBalance(keyId, button) {
  const key = state.keys.find((item) => item.id === keyId);
  if (!key) return;
  await withBusy(button, "查询中…", async () => {
    try {
      const result = await api(`/api/keys/${keyId}/fetch-balance`, { method: "POST" });
      await loadState();
      renderRoute({ preserveScroll: true });
      toast(
        result.balance ? `余额已更新：${formatMoney(result.balance.amount, result.balance.currency)}` : "余额已更新",
        "ok"
      );
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

// ---------------------------------------------------------------------------
// reveal
// ---------------------------------------------------------------------------
async function openRevealModal(key) {
  try {
    const data = await api(`/api/keys/${key.id}/reveal`, { method: "POST" });
    openModal({
      title: `查看 Key · ${key.label}`,
      subtitle: "完整 Key 只会在这次弹窗里显示，关闭后请重新解密。",
      body: `<div class="banner banner-warn">${icon(
        "shield",
        16
      )}<div>不要在录屏、共享屏幕或公开聊天窗口里展示这一页。</div></div>
        <div class="key-reveal-box">
          <code id="revealed-key">${esc(data.secret)}</code>
          <button class="btn btn-secondary btn-sm" data-action="copy-revealed">${icon(
            "copy",
            13
          )} 复制</button>
        </div>`,
      width: "narrow",
      onMount(dialog) {
        $('[data-action="copy-revealed"]', dialog).addEventListener("click", async (event) => {
          await withBusy(event.currentTarget, "复制中…", async () => {
            try {
              await copyText(data.secret);
              toast("Key 已复制", "ok");
            } catch {
              toast("复制失败，请手动选中。", "err");
            }
          });
        });
      },
    });
  } catch (error) {
    toast(error.message, "err");
  }
}

// ---------------------------------------------------------------------------
// snippet copy
// ---------------------------------------------------------------------------
async function copySnippet(button) {
  const key = currentStudioKey();
  const studio = state.studio;
  if (!key || !studio) return;
  const selections = studioSelections(key, studio);
  if (!selections.length) {
    toast("先选择一个模型。", "warn");
    return;
  }
  await withBusy(button, "复制中…", async () => {
    try {
      const data = await api("/api/snippets", {
        method: "POST",
        body: {
          key_id: key.id,
          models: selections,
          format: studio.format,
          include_secret: true,
          direct_key: studio.directKey,
          include_comments: studio.includeComments,
        },
      });
      await copyText(data.text);
      await api(`/api/keys/${key.id}/copied`, {
        method: "POST",
        body: {
          model_ids: selections.map((item) => item.id),
          capability: studio.capability,
          format: studio.format,
        },
      });
      const now = new Date().toISOString();
      key.last_copied_at = now;
      key.last_used_at = now;
      const label = FORMAT_LABELS[studio.format] || studio.format;
      const realKey = studio.format === "env" || studio.directKey;
      toast(`已复制 ${label}${realKey ? "，包含真实 Key" : ""}`, "ok");
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

async function quickCopy(keyId, button) {
  const key = state.keys.find((item) => item.id === keyId);
  if (!key) return;
  if (!key.models?.length) {
    toast("这个 Key 还没有勾选模型。", "warn");
    return;
  }
  const model =
    key.models.find((item) => (item.capabilities || []).includes("chat")) || key.models[0];
  const capability = (model.capabilities || [])[0] || "chat";
  await withBusy(button, "复制中…", async () => {
    try {
      const data = await api("/api/snippets", {
        method: "POST",
        body: {
          key_id: key.id,
          models: [{ id: model.id, capability }],
          format: "env",
          include_secret: true,
          direct_key: false,
          include_comments: false,
        },
      });
      await copyText(data.text);
      await api(`/api/keys/${key.id}/copied`, {
        method: "POST",
        body: { model_ids: [model.id], capability, format: "env" },
      });
      const now = new Date().toISOString();
      key.last_copied_at = now;
      key.last_used_at = now;
      toast(".env 已复制，包含真实 Key", "ok");
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

// ---------------------------------------------------------------------------
// settings and data
// ---------------------------------------------------------------------------
async function saveSettings(form, button) {
  const data = new FormData(form);
  const payload = {
    clipboard_watch: data.get("clipboard_watch") ? "1" : "0",
    check_updates: data.get("check_updates") ? "1" : "0",
    low_balance_threshold: data.get("low_balance_threshold")?.toString() || "20",
    low_balance_currency: data.get("low_balance_currency")?.toString() || "CNY",
    default_format: data.get("default_format")?.toString() || "env",
    include_comments: data.get("include_comments") ? "1" : "0",
    direct_key: data.get("direct_key") ? "1" : "0",
  };
  await withBusy(button, "保存中…", async () => {
    try {
      const result = await api("/api/settings", { method: "PATCH", body: payload });
      state.settings = result.settings;
      await loadState();
      renderSidebar();
      startClipboardPolling();
      toast("设置已保存", "ok");
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

// ---------------------------------------------------------------------------
// update check
// ---------------------------------------------------------------------------
async function maybeCheckUpdates(force = false, button = null) {
  if (!force && state.settings.check_updates === "0") return;
  const task = async () => {
    try {
      const data = await api("/api/update/check", {
        method: "POST",
        body: { force },
      });
      state.update = data;
      if (data.ok && data.update_available) {
        showUpdateDialog(data);
      } else if (force) {
        toast(
          data.ok ? "已经是最新版本。" : data.error || "检查更新失败。",
          data.ok ? "ok" : "warn"
        );
      }
    } catch (error) {
      if (force) toast(error.message, "err");
    }
  };
  if (button) await withBusy(button, "检查中…", task);
  else await task();
}

function showUpdateDialog(data) {
  if (modalState) {
    toast(`发现新版本 ${data.latest}，可在设置页查看。`, "warn");
    return;
  }
  const notes = (data.notes || "").trim();
  openModal({
    title: `发现新版本 ${data.latest}`,
    subtitle: `当前 ${data.current} · 最新 ${data.latest}`,
    body: `<div class="banner banner-info">${icon(
      "sparkles",
      16
    )}<div>新版本已经发布到 GitHub Releases。更新不会自动下载或安装。</div></div>
      ${
        notes
          ? `<div class="note-block" style="max-height:260px;overflow:auto">${esc(notes)}</div>`
          : `<p class="muted" style="font-size:12px">打开 Release 页面查看更新内容。</p>`
      }`,
    footer: `<div class="foot-left">升级安装不会删除你的 Key 数据。</div>
      <div class="foot-actions">
        <button class="btn btn-secondary" data-action="close-modal">稍后</button>
        <button class="btn btn-primary" data-action="open-update">${icon(
          "external",
          15
        )} 查看更新</button>
      </div>`,
    width: "narrow",
  });
}

async function openUpdatePage() {
  const url = state.update?.url;
  if (!url) {
    toast("没有可用的更新地址。", "warn");
    return;
  }
  await api("/api/open-url", { method: "POST", body: { url } });
  closeModal(true);
}

async function backupData(button) {
  await withBusy(button, "准备中…", async () => {
    try {
      const native = window.pywebview?.api;
      if (state.app.native && native?.save_backup) {
        const path = await native.save_backup();
        toast(path ? `备份已保存：${path}` : "已取消备份", path ? "ok" : "warn");
        return;
      }
      await downloadFile("/api/backup", "api-key-ledger-backup.db");
      toast("数据库备份已下载", "ok");
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

async function exportData(button) {
  await withBusy(button, "导出中…", async () => {
    try {
      const native = window.pywebview?.api;
      if (state.app.native && native?.save_export) {
        const path = await native.save_export();
        toast(path ? `JSON 已保存：${path}` : "已取消导出", path ? "ok" : "warn");
        return;
      }
      await downloadFile("/api/export", "api-key-ledger-export.json");
      toast("JSON 已导出（不含 Key）", "ok");
    } catch (error) {
      toast(error.message, "err");
    }
  });
}

// ---------------------------------------------------------------------------
// clipboard
// ---------------------------------------------------------------------------
function startClipboardPolling() {
  if (clipboardTimer) clearInterval(clipboardTimer);
  if (state.settings.clipboard_watch !== "1" || !state.app.clipboard_available) {
    hideCaptureCard();
    return;
  }
  clipboardTimer = setInterval(pollClipboard, 2800);
  pollClipboard();
}

async function pollClipboard() {
  if (state.settings.clipboard_watch !== "1" || !state.app.clipboard_available) return;
  try {
    const data = await api("/api/clipboard/pending");
    state.clipboardPending = data.pending || [];
    renderCaptureCard();
  } catch {
    /* clipboard polling is best-effort */
  }
}

function renderCaptureCard() {
  if (!state.clipboardPending.length || modalState) {
    hideCaptureCard();
    return;
  }
  const item = state.clipboardPending[0];
  const draft = item.draft || {};
  const provider = state.providers.find((candidate) => candidate.id === draft.provider_id);
  const hint = draft.secret ? `…${String(draft.secret).slice(-4)}` : "";
  if (!captureEl) {
    captureEl = document.createElement("div");
    captureEl.className = "capture-card";
    captureEl.id = "capture-card";
    document.body.appendChild(captureEl);
  }
  captureEl.innerHTML = `<div class="capture-kicker">${icon(
    "clipboard",
    12
  )} CLIPBOARD CAPTURE</div>
    <div class="capture-title">检测到一个新的 API Key</div>
    <div class="capture-sub">${esc(provider?.name || "待选择平台")} · ${esc(
    draft.label || "未命名"
  )} · ${esc(hint)}</div>
    <div class="capture-actions">
      <button class="btn btn-primary btn-sm" data-action="clipboard-accept" data-id="${esc(
        item.id
      )}">查看并添加</button>
      <button class="btn btn-secondary btn-sm" data-action="clipboard-dismiss" data-id="${esc(
        item.id
      )}">忽略</button>
    </div>`;
}

function hideCaptureCard() {
  if (captureEl) {
    captureEl.remove();
    captureEl = null;
  }
}

async function acceptClipboard(pendingId) {
  try {
    const data = await api(`/api/clipboard/${pendingId}/accept`, { method: "POST" });
    state.clipboardPending = state.clipboardPending.filter((item) => item.id !== pendingId);
    hideCaptureCard();
    openAddKeyModal(data.draft);
  } catch (error) {
    toast(error.message, "err");
  }
}

async function dismissClipboard(pendingId) {
  try {
    await api(`/api/clipboard/${pendingId}/dismiss`, { method: "POST" });
  } catch {
    /* ignore */
  }
  state.clipboardPending = state.clipboardPending.filter((item) => item.id !== pendingId);
  hideCaptureCard();
  pollClipboard();
}

// ---------------------------------------------------------------------------
// quick parse
// ---------------------------------------------------------------------------
async function quickParse(button) {
  const textarea = $("#quick-paste");
  const errorBox = $("#quick-error");
  const text = textarea?.value || "";
  if (!text.trim()) {
    if (errorBox) {
      errorBox.textContent = "先粘贴一段内容，再点识别。";
      errorBox.classList.add("show");
    }
    return;
  }
  await withBusy(button, "识别中…", async () => {
    try {
      const parsed = await api("/api/import/parse", { method: "POST", body: { text } });
      if (!parsed.ok) {
        if (errorBox) {
          errorBox.textContent = parsed.error || "没有识别到 API Key。";
          errorBox.classList.add("show");
        }
        return;
      }
      if (errorBox) errorBox.classList.remove("show");
      openAddKeyModal(parsed);
    } catch (error) {
      if (errorBox) {
        errorBox.textContent = error.message;
        errorBox.classList.add("show");
      }
    }
  });
}

// ---------------------------------------------------------------------------
// utilities
// ---------------------------------------------------------------------------
function toast(message, type = "ok") {
  const root = $("#toast-root");
  if (!root) return;
  const element = document.createElement("div");
  element.className = `toast ${type}`;
  element.innerHTML = `${icon(type === "ok" ? "check-circle" : "alert", 15)}<div>${esc(
    message
  )}</div>`;
  root.appendChild(element);
  while (root.children.length > 3) root.firstElementChild.remove();
  setTimeout(() => {
    element.classList.add("leaving");
    setTimeout(() => element.remove(), 220);
  }, 3400);
}

async function withBusy(button, label, task) {
  if (!button) {
    await task();
    return;
  }
  const original = button.innerHTML;
  const width = button.offsetWidth;
  button.disabled = true;
  if (width) button.style.minWidth = `${width}px`;
  button.innerHTML = `<span class="spin"></span>${esc(label)}`;
  try {
    await task();
  } finally {
    button.disabled = false;
    button.innerHTML = original;
    button.style.minWidth = "";
  }
}

function openSidebar() {
  state.sidebarOpen = true;
  $("#sidebar")?.classList.add("open");
  const scrim = $("#sidebar-scrim");
  if (scrim) scrim.hidden = false;
}

function closeSidebar() {
  state.sidebarOpen = false;
  $("#sidebar")?.classList.remove("open");
  const scrim = $("#sidebar-scrim");
  if (scrim) scrim.hidden = true;
}

// ---------------------------------------------------------------------------
// event wiring
// ---------------------------------------------------------------------------
document.addEventListener("click", async (event) => {
  const actionEl = event.target.closest("[data-action]");
  if (!actionEl) return;
  const action = actionEl.dataset.action;
  const id = actionEl.dataset.id || "";

  if (action === "retry") {
    location.reload();
    return;
  }
  if (
    [
      "add-key",
      "quick-parse",
      "go-dashboard",
      "go-keys",
      "go-platform",
      "go-settings",
      "filter-provider",
      "open-key",
      "back-to-keys",
      "edit-key",
      "delete-key",
      "reveal-key",
      "manage-models",
      "manual-balance",
      "refresh-balance",
      "quick-copy",
      "copy-snippet",
      "set-capability",
      "set-format",
      "close-modal",
      "backup",
      "export",
      "open-data-dir",
      "clear-search",
      "sidebar-toggle",
      "clipboard-accept",
      "clipboard-dismiss",
      "exit-app",
      "check-updates",
      "open-update",
    ].includes(action)
  ) {
    event.preventDefault();
  }

  try {
    if (action === "add-key") {
      openAddKeyModal();
    } else if (action === "quick-parse") {
      await quickParse(actionEl);
    } else if (action === "go-dashboard") {
      navigate("#/dashboard");
    } else if (action === "go-keys") {
      navigate("#/keys");
    } else if (action === "go-platform") {
      navigate(`#/platform/${id}`);
    } else if (action === "go-settings") {
      navigate("#/settings");
    } else if (action === "filter-provider") {
      navigate(id ? `#/platform/${id}` : "#/keys");
    } else if (action === "open-key") {
      navigate(`#/key/${id}`);
    } else if (action === "back-to-keys") {
      navigate("#/keys");
    } else if (action === "edit-key") {
      const key = state.keys.find((item) => item.id === id);
      if (key) openAddKeyModal(null, key);
    } else if (action === "delete-key") {
      const key = state.keys.find((item) => item.id === id);
      if (!key) return;
      const confirmed = await confirmDialog({
        title: "删除这个 Key？",
        message: `确定删除「${key.label}」？它的余额记录、模型关联和使用时间线也会一起删除，无法恢复。`,
        confirmText: "删除 Key",
        danger: true,
      });
      if (!confirmed) return;
      await withBusy(actionEl, "删除中…", async () => {
        try {
          await api(`/api/keys/${key.id}`, { method: "DELETE" });
          await loadState();
          navigate("#/keys");
          renderSidebar();
          toast("Key 已删除", "ok");
        } catch (error) {
          toast(error.message, "err");
        }
      });
    } else if (action === "reveal-key") {
      const key = state.keys.find((item) => item.id === id);
      if (key) await withBusy(actionEl, "解密中…", () => openRevealModal(key));
    } else if (action === "manage-models") {
      await openModelManager(id);
    } else if (action === "manual-balance") {
      const key = state.keys.find((item) => item.id === id);
      if (key) openBalanceModal(key);
    } else if (action === "refresh-balance") {
      await refreshBalance(id, actionEl);
    } else if (action === "quick-copy") {
      await quickCopy(id, actionEl);
    } else if (action === "copy-snippet") {
      await copySnippet(actionEl);
    } else if (action === "set-capability") {
      const studio = state.studio;
      if (!studio) return;
      studio.capability = id;
      const key = currentStudioKey();
      if (key) {
        const model = modelsForCapability(key, id)[0];
        if (model) studio.selected[id] = model.id;
        const formats = model?.formats?.length ? model.formats : ["env"];
        if (!formats.includes(studio.format)) studio.format = formats[0];
      }
      studio.preview = "";
      studio.previewError = "";
      renderRoute({ preserveScroll: true });
    } else if (action === "set-format") {
      const studio = state.studio;
      if (!studio) return;
      studio.format = id;
      studio.preview = "";
      studio.previewError = "";
      renderRoute({ preserveScroll: true });
    } else if (action === "close-modal") {
      requestCloseModal();
    } else if (action === "backup") {
      await backupData(actionEl);
    } else if (action === "export") {
      await exportData(actionEl);
    } else if (action === "open-data-dir") {
      await api("/api/open-data-dir", { method: "POST" });
      toast("已打开数据文件夹", "ok");
    } else if (action === "clear-search") {
      state.search = "";
      const input = $("#search-input");
      if (input) input.value = "";
      renderRoute({ preserveScroll: true });
    } else if (action === "sidebar-toggle") {
      if (state.sidebarOpen) closeSidebar();
      else openSidebar();
    } else if (action === "clipboard-accept") {
      await acceptClipboard(id);
    } else if (action === "clipboard-dismiss") {
      await dismissClipboard(id);
    } else if (action === "exit-app") {
      const api = window.pywebview?.api;
      if (api?.close_app) {
        await api.close_app();
      } else {
        toast("请直接关闭窗口。", "warn");
      }
    } else if (action === "check-updates") {
      await maybeCheckUpdates(true, actionEl);
    } else if (action === "open-update") {
      await withBusy(actionEl, "打开中…", openUpdatePage);
    }
  } catch (error) {
    toast(error.message || String(error), "err");
  }
});

document.addEventListener("change", async (event) => {
  const target = event.target;
  if (target.matches("[data-studio-model]")) {
    const studio = state.studio;
    if (!studio) return;
    studio.selected[studio.capability] = target.value;
    const key = currentStudioKey();
    if (key) {
      const model = selectedModelFor(key, studio);
      const formats = model?.formats?.length ? model.formats : ["env"];
      if (!formats.includes(studio.format)) studio.format = formats[0];
    }
    studio.preview = "";
    studio.previewError = "";
    renderRoute({ preserveScroll: true });
  } else if (target.matches("[data-studio-option]")) {
    const studio = state.studio;
    if (!studio) return;
    studio[target.dataset.studioOption] = target.checked;
    if (target.dataset.studioOption === "directKey") {
      renderRoute({ preserveScroll: true });
      return;
    }
    studio.preview = "";
    studio.previewError = "";
    refreshPreview();
  }
});

const onSearch = debounce(() => {
  state.search = $("#search-input")?.value || "";
  if (state.route?.name !== "keys") {
    navigate("#/keys");
  } else {
    renderRoute({ preserveScroll: true });
  }
}, 160);

document.addEventListener("input", (event) => {
  if (event.target.id === "search-input") {
    onSearch();
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "settings-form") {
    event.preventDefault();
    const submitter = event.submitter;
    await saveSettings(event.target, submitter);
  }
});

document.addEventListener("keydown", (event) => {
  const target = event.target;
  const isTyping =
    target instanceof HTMLElement &&
    (target.matches("input, textarea, select") || target.isContentEditable);

  if (event.key === "Escape") {
    if (modalState) {
      event.preventDefault();
      requestCloseModal();
      return;
    }
    if (state.sidebarOpen) {
      event.preventDefault();
      closeSidebar();
    }
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    $("#search-input")?.focus();
    return;
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "n") {
    event.preventDefault();
    openAddKeyModal();
    return;
  }
  if (event.key === "/" && !isTyping) {
    event.preventDefault();
    $("#search-input")?.focus();
    return;
  }
  if (event.key === "Enter" && target instanceof HTMLElement && target.matches('tr[data-action="open-key"]')) {
    event.preventDefault();
    target.click();
  }
});

window.addEventListener("beforeunload", (event) => {
  if (modalState?.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

boot();
