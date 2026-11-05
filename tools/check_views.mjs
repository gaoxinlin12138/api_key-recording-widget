/**
 * 前端渲染回归测试（Node 运行，无浏览器依赖）。
 *
 * 覆盖：dashboard / keys / detail / settings 四个视图在有数据与空数据下的渲染。
 * 目的：node --check 只能发现语法错误，发现不了"变量写错导致运行时抛异常"，
 *       而这类错误在浏览器里同样表现为白屏或卡在启动画面。
 *
 * 用法：node tools/check_views.mjs
 * 退出码：0 通过，1 失败
 */
import { dashboardView, detailView, keysView, settingsView } from "../web/js/views.js";

const failures = [];
const MOJIBAKE = ["锛", "鍏", "鐢", "閽", "銆", "鍜", "浣", "鏄"];

const provider = {
  id: "deepseek",
  name: "DeepSeek",
  short_name: "DS",
  color: "#3867d6",
  key_count: 1,
  model_count: 2,
  description: "文本对话与推理",
};

const model = {
  id: "deepseek:deepseek-chat",
  model_id: "deepseek-chat",
  display_name: "DeepSeek Chat",
  capabilities: ["chat"],
  formats: ["env", "python", "curl", "js"],
  api_style: "openai_chat",
};

const key = {
  id: "key_abc",
  label: "主力 Key",
  hint: "sk-…abcd",
  env_prefix: "DEEPSEEK",
  project: "写作助手",
  environment: "开发",
  note: "备注",
  status: "active",
  created_at: "2026-11-01T10:00:00+00:00",
  last_copied_at: "2026-11-05T10:00:00+00:00",
  last_used_at: null,
  expires_at: null,
  provider,
  models: [model],
  balance: {
    amount: 88.5,
    currency: "CNY",
    source: "manual",
    checked_at: "2026-11-05T10:00:00+00:00",
    expires_at: null,
    note: "",
    quota_total: null,
    quota_used: null,
    quota_remaining: null,
    quota_unit: "",
  },
};

const settings = {
  clipboard_watch: "1",
  check_updates: "1",
  auto_refresh_balance: "1",
  low_balance_threshold: "20",
  low_balance_currency: "CNY",
  default_format: "env",
  include_comments: "0",
  direct_key: "0",
  background_style: "aurora",
  background_version: "1",
};

const app = {
  name: "API 钥匙簿",
  version: "1.3.2",
  data_path: "C:\\Users\\x\\AppData\\Local\\ApiKeyLedger\\data",
  data_dir_source: "default",
  data_dir_changeable: true,
  data_dir_warning: null,
  clipboard_available: true,
  clipboard_enabled: true,
  native: false,
  background_version: "1",
};

const full = {
  providers: [provider],
  keys: [key],
  models: [model],
  stats: {
    total_keys: 1,
    providers_with_keys: 1,
    month_new: 1,
    low_balance: 0,
    recent_usage: [
      {
        action: "copy_env",
        key_label: key.label,
        provider_name: provider.name,
        created_at: "2026-11-05T10:00:00+00:00",
      },
    ],
  },
  settings,
  app,
  settingsTab: "data",
};

const empty = {
  providers: [],
  keys: [],
  models: [],
  stats: { total_keys: 0, providers_with_keys: 0, month_new: 0, low_balance: 0, recent_usage: [] },
  settings,
  app: { ...app, data_path: "", data_dir_source: "default", data_dir_warning: null },
  settingsTab: "data",
};

const studio = {
  capability: "chat",
  format: "env",
  includeComments: false,
  directKey: false,
  includeAll: false,
  preview: "DEEPSEEK_API_KEY=sk-…abcd",
  previewLoading: false,
  previewError: "",
  selected: { chat: model.id },
};

function check(name, html, musts) {
  if (typeof html !== "string" || html.length < 50) {
    failures.push(`${name}: 渲染结果为空或过短`);
    return;
  }
  for (const marker of MOJIBAKE) {
    if (html.includes(marker)) failures.push(`${name}: 出现乱码字符 ${marker}`);
  }
  for (const bad of ["undefined", "NaN", "[object Object]"]) {
    if (html.includes(bad)) failures.push(`${name}: 输出里出现 ${bad}`);
  }
  for (const must of musts) {
    if (!html.includes(must)) failures.push(`${name}: 缺少关键内容「${must}」`);
  }
}

check("dashboard", dashboardView(full), ["平台", "最近活动", "Key 总数"]);
check("dashboard/empty", dashboardView(empty), ["没有使用记录"]);
check("keys", keysView(full, full.keys, ""), ["全部 Key", "主力 Key", "quick-copy", "delete-key"]);
check("keys/provider", keysView(full, full.keys, "deepseek"), ["DeepSeek"]);
check("keys/empty", keysView(empty, [], ""), ["这里还没有 Key"]);
check("detail", detailView(full, key, studio), ["片段工坊", "复制片段", "余额与额度", "主力 Key"]);
check("detail/missing", detailView(full, null, null), ["这个 Key 不存在"]);
check(
  "settings",
  settingsView(full),
  ["更改数据目录", "安全说明", "下载数据库备份", "恢复数据库备份"],
);
check(
  "settings/warning",
  settingsView({ ...full, app: { ...app, data_dir_warning: "Z:\\gone" } }),
  ["原数据目录不可用"],
);
check(
  "settings/unchangeable",
  settingsView({ ...full, app: { ...app, data_dir_changeable: false, data_dir_source: "cli" } }),
  ["--db"],
);

if (failures.length) {
  console.error("前端渲染检查失败：");
  for (const item of failures) console.error("  - " + item);
  process.exit(1);
}
console.log("前端渲染检查通过（10 个视图场景）");
