const ICON_PATHS = {
  key: '<circle cx="7.5" cy="15.5" r="3.5"/><path d="M10.2 13.1 18 5.3M14.5 5.3l3.2 3.2M12.6 7.2l3.2 3.2"/>',
  grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.2.6.77 1 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1Z"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/>',
  eye: '<path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.6"/>',
  "eye-off": '<path d="m3 3 18 18M10.6 6.2A10.6 10.6 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-3.2 3.8M6.1 6.6C3.8 8.2 2.5 12 2.5 12s3.5 6 9.5 6c1.4 0 2.6-.3 3.7-.8M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14.9-3M4 5v4h4M4 13a8 8 0 0 0 14.9 3M20 19v-4h-4"/>',
  trash: '<path d="M4 7h16M9 7V4.5h6V7M6 7l.8 13h10.4L18 7M10 11v5M14 11v5"/>',
  edit: '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="m14.5 7.5 3 3"/>',
  "arrow-left": '<path d="M19 12H5M11 18l-6-6 6-6"/>',
  "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  "chevron-right": '<path d="m9 6 6 6-6 6"/>',
  check: '<path d="m4.5 12.5 5 5 10-11"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  alert: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.2v.1"/>',
  wallet: '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H19v14H6.5A2.5 2.5 0 0 1 4 16.5v-9Z"/><path d="M4 8h13M16 12h4M16 12a1.5 1.5 0 0 0 0 3h4"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  sparkles: '<path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3ZM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15ZM5 14l.7 1.8L7.5 16l-1.8.7L5 18.5l-.7-1.8L2.5 16l1.8-.2L5 14Z"/>',
  clipboard: '<rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5V3h6v1.5M9 10h6M9 14h6M9 18h4"/>',
  download: '<path d="M12 3v12M7 11l5 5 5-5M4 20h16"/>',
  folder: '<path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h4l2 2h8a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5v-10Z"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M19 14v4.5A1.5 1.5 0 0 1 17.5 20h-13A1.5 1.5 0 0 1 3 18.5v-13A1.5 1.5 0 0 1 4.5 4H9"/>',
  database: '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  shield: '<path d="M12 3 4.5 6v5.2c0 4.5 3.2 8 7.5 9.8 4.3-1.8 7.5-5.3 7.5-9.8V6L12 3Z"/><path d="m9 12 2 2 4-4"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  server: '<rect x="3.5" y="4" width="17" height="7" rx="2"/><rect x="3.5" y="13" width="17" height="7" rx="2"/><path d="M7 7.5h.1M7 16.5h.1M11 7.5h6M11 16.5h6"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
  filter: '<path d="M3 5h18l-7 8v5l-4 2v-7L3 5Z"/>',
  "more-horizontal": '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  "lock": '<rect x="4.5" y="10" width="15" height="10" rx="2"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10M12 14v3"/>',
  "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.1"/>',
  "grip": '<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>',
  "image": '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="m5 17 4.5-4.5 3 3L15 13l4 4"/>',
  "upload": '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
  "minimize": '<path d="M5 12h14"/>',
  "maximize": '<rect x="5" y="5" width="14" height="14" rx="1.5"/>',
};

export function icon(name, size = 18, className = "") {
  const paths = ICON_PATHS[name] || ICON_PATHS.key;
  return `<svg class="${className}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

export function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function attr(value) {
  return esc(value);
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function debounce(fn, wait = 160) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

export function formatDate(value, { year = true, time = true } = {}) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const options = { month: "2-digit", day: "2-digit" };
  if (year) options.year = "numeric";
  if (time) {
    options.hour = "2-digit";
    options.minute = "2-digit";
    options.hour12 = false;
  }
  return new Intl.DateTimeFormat("zh-CN", options).format(date);
}

export function timeAgo(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 45) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  if (seconds < 86400 * 30) return `${Math.floor(seconds / 86400)} 天前`;
  return formatDate(value, { year: true, time: false });
}

export function formatMoney(amount, currency = "CNY") {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return "—";
  const value = Number(amount);
  try {
    return new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: currency || "CNY",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${currency || "¥"} ${value.toFixed(2)}`;
  }
}

export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(Number(value));
}

export const BACKGROUND_PRESETS = [
  {
    id: "aurora",
    name: "DODIN",
    hint: "天空 · 奶油",
    colors: ["#C8EBFE", "#DCEEFF", "#FDF6E6"],
  },
  {
    id: "ocean",
    name: "海面",
    hint: "湖蓝 · 薄荷",
    colors: ["#d5f2f2", "#d9ebff", "#e4f6ed"],
  },
  {
    id: "sunset",
    name: "日落",
    hint: "杏粉 · 雾紫",
    colors: ["#ffead7", "#ffdfe8", "#e9defa"],
  },
  {
    id: "forest",
    name: "森林",
    hint: "苔绿 · 米白",
    colors: ["#e2f0dc", "#d9eee6", "#f4efdf"],
  },
  {
    id: "paper",
    name: "纸白",
    hint: "暖白 · 灰米",
    colors: ["#f7f1e4", "#eee7d8", "#faf7ef"],
  },
];

export const CAPABILITY_LABELS = {
  chat: "文本",
  vision: "视觉",
  embedding: "向量",
  rerank: "重排",
  image: "图像",
  audio: "语音",
};

export function capabilityChips(capabilities = []) {
  return capabilities
    .filter((item) => CAPABILITY_LABELS[item])
    .map(
      (item) =>
        `<span class="chip ${esc(item)}">${esc(CAPABILITY_LABELS[item])}</span>`
    )
    .join("");
}

export function providerAvatar(provider) {
  const initials = provider?.short_name || (provider?.name || "API").slice(0, 2);
  return `<span class="platform-avatar" style="--pc:${attr(
    provider?.color || "#64748b"
  )}">${esc(initials)}</span>`;
}

export function providerBadge(provider) {
  return `<span class="badge badge-provider" style="--pc:${attr(
    provider?.color || "#64748b"
  )}"><span class="dot"></span>${esc(provider?.name || "平台")}</span>`;
}

export function statusBadge(status, expiresAt) {
  if (expiresAt && new Date(expiresAt).getTime() < Date.now()) {
    return `<span class="badge badge-danger"><span class="dot"></span>已过期</span>`;
  }
  if (status === "disabled") {
    return `<span class="badge badge-quiet">已停用</span>`;
  }
  return `<span class="badge badge-ok"><span class="dot"></span>使用中</span>`;
}

export function emptyState({ iconName = "key", title, text, action = "" }) {
  return `<div class="empty">
    <div class="empty-icon">${icon(iconName, 24)}</div>
    <div class="empty-title">${esc(title)}</div>
    <div class="empty-text">${esc(text)}</div>
    ${action}
  </div>`;
}

export function actionLabel(action) {
  return (
    {
      created: "添加 Key",
      copy_env: "复制 .env",
      copy_python: "复制 Python",
      copy_curl: "复制 cURL",
      copy_js: "复制 JavaScript",
      reveal: "查看 Key",
      balance: "更新余额",
    }[action] || "更新记录"
  );
}

export function actionIcon(action) {
  if (String(action).startsWith("copy_")) return "copy";
  if (action === "created") return "plus";
  if (action === "reveal") return "eye";
  if (action === "balance") return "wallet";
  return "sparkles";
}
