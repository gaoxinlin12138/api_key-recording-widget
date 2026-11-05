import {
  BACKGROUND_PRESETS,
  CAPABILITY_LABELS,
  FORMAT_LABELS,
  FORMAT_ORDER,
  actionIcon,
  actionLabel,
  capabilityChips,
  emptyState,
  esc,
  formatDate,
  formatMoney,
  formatNumber,
  icon,
  providerAvatar,
  providerBadge,
  statusBadge,
  timeAgo,
} from "./ui.js";

export function availableCapabilities(key) {
  const order = ["chat", "vision", "embedding", "rerank", "image", "audio"];
  const present = new Set();
  for (const model of key.models || []) {
    for (const capability of model.capabilities || []) {
      if (CAPABILITY_LABELS[capability]) present.add(capability);
    }
  }
  return order.filter((item) => present.has(item));
}

export function modelsForCapability(key, capability) {
  return (key.models || []).filter(
    (model) => (model.capabilities || []).includes(capability)
  );
}

export function selectedModelFor(key, studio) {
  const models = modelsForCapability(key, studio.capability);
  const selectedId = studio.selected?.[studio.capability];
  return models.find((model) => model.id === selectedId) || models[0] || null;
}

function providerFilterChips(state, activeId) {
  const active = activeId || "";
  const chips = [
    `<button class="filter-chip ${active ? "" : "active"}" data-action="filter-provider" data-id="">全部 <span class="count">${state.keys.length}</span></button>`,
  ];
  for (const provider of state.providers.filter((item) => item.key_count > 0)) {
    chips.push(
      `<button class="filter-chip ${active === provider.id ? "active" : ""}" data-action="filter-provider" data-id="${esc(
        provider.id
      )}"><span class="platform-dot" style="background:${esc(provider.color)}"></span>${esc(
        provider.name
      )} <span class="count">${provider.key_count}</span></button>`
    );
  }
  return `<div class="filter-row">${chips.join("")}</div>`;
}

function lowBalanceKeys(state) {
  const threshold = Number(state.settings?.low_balance_threshold ?? 20);
  const currency = state.settings?.low_balance_currency || "CNY";
  return (state.keys || []).filter(
    (key) =>
      key.balance &&
      key.balance.amount !== null &&
      key.balance.amount !== undefined &&
      (key.balance.currency || "CNY") === currency &&
      Number(key.balance.amount) < threshold
  );
}

export function keysView(state, filteredKeys, activeProviderId) {
  const provider = activeProviderId
    ? state.providers.find((item) => item.id === activeProviderId)
    : null;
  const title = provider ? provider.name : "全部 Key";
  const sub = provider
    ? `${provider.key_count} 个 Key · ${provider.description || ""}`
    : `${state.keys.length} 个 Key，分布在 ${state.stats?.providers_with_keys || 0} 个平台`;

  const rows = filteredKeys
    .map((key) => {
      const models = key.models || [];
      const modelHtml = models.length
        ? models
            .slice(0, 2)
            .map((model) => `<span class="model-mini" title="${esc(model.model_id)}">${esc(model.model_id)}</span>`)
            .join("") +
          (models.length > 2 ? `<span class="model-mini more">+${models.length - 2}</span>` : "")
        : `<span class="faint" style="font-size:11px">尚未选模型</span>`;
      const balance = key.balance;
      const lowCurrency = state.settings?.low_balance_currency || "CNY";
      const isLow =
        balance &&
        (balance.currency || "CNY") === lowCurrency &&
        balance.amount !== null &&
        Number(balance.amount) < Number(state.settings?.low_balance_threshold ?? 20);
      const balanceHtml = balance
        ? `<strong class="${isLow ? "balance-low" : ""}">${formatMoney(
            balance.amount,
            balance.currency
          )}</strong><span class="sub">${balance.source === "auto" ? "自动查询" : "手动记录"} · ${esc(
            timeAgo(balance.checked_at)
          )}</span>`
        : `<span class="faint" style="font-size:11px">未记录</span>`;
      return `<tr data-action="open-key" data-id="${esc(key.id)}" tabindex="0">
        <td>
          <div class="key-cell">
            ${providerAvatar(key.provider)}
            <div style="min-width:0">
              <div class="key-name">${esc(key.label)}</div>
              <div class="key-sub">${esc(key.provider.name)} · <span class="mono">${esc(
        key.hint
      )}</span></div>
            </div>
          </div>
        </td>
        <td><div class="project-cell ${key.project ? "" : "empty"}" title="${esc(
        key.project || ""
      )}">${esc(key.project || "未填写用途")}</div></td>
        <td><div class="model-mini-list">${modelHtml}</div></td>
        <td class="balance-cell">${balanceHtml}</td>
        <td class="date-cell">${key.last_copied_at ? esc(timeAgo(key.last_copied_at)) : "—"}</td>
        <td class="actions-cell">
          <div class="row-actions">
            <button class="btn btn-secondary btn-sm" data-action="quick-copy" data-id="${esc(
              key.id
            )}" title="复制这个 Key 的 .env">${icon("copy", 13)} .env</button>
            <button class="btn btn-danger btn-sm btn-icon" data-action="delete-key" data-id="${esc(
              key.id
            )}" title="删除这个 Key" aria-label="删除这个 Key">${icon("trash", 13)}</button>
          </div>
        </td>
      </tr>`;
    })
    .join("");

  const table = filteredKeys.length
    ? `<div class="table-wrap">
        <table class="key-table">
          <thead><tr>
            <th>Key</th><th>用途</th><th>可用模型</th><th class="num">余额</th><th>最近复制</th><th class="actions-col"></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`
    : emptyState({
        iconName: "search",
        title: state.search ? "没有匹配的 Key" : "这里还没有 Key",
        text: state.search
          ? `没有找到包含“${state.search}”的记录，换个关键词或清空搜索。`
          : "从仪表盘的快速导入开始，或者手动添加第一个 Key。",
        action: state.search
          ? `<button class="btn btn-secondary" data-action="clear-search">清空搜索</button>`
          : `<button class="btn btn-primary" data-action="add-key">${icon("plus", 15)} 添加第一个 Key</button>`,
      });

  return `
    <div class="page-head">
      <div class="page-title-wrap">
        <div class="eyebrow">KEYS</div>
        <h1 class="page-title">${esc(title)}</h1>
        <p class="page-sub">${esc(sub)}</p>
      </div>
    </div>
    ${providerFilterChips(state, activeProviderId)}
    ${table}
  `;
}

function infoItem(label, value, extraClass = "") {
  return `<div class="info-item">
    <div class="info-label">${esc(label)}</div>
    <div class="info-value ${extraClass}">${value}</div>
  </div>`;
}

function balanceBars(balance) {
  if (!balance) return "";
  const rows = [];
  const total = Number(balance.quota_total);
  if (balance.quota_total !== null && balance.quota_total !== undefined && !Number.isNaN(total) && total > 0) {
    const used = Number(balance.quota_used || 0);
    const remaining = Number(balance.quota_remaining ?? Math.max(total - used, 0));
    const pct = Math.max(0, Math.min(100, (remaining / total) * 100));
    rows.push(
      `<div class="bar-row"><span>剩余额度</span><span class="bar-track"><span class="bar-fill ${
        pct < 20 ? "warn" : ""
      }" style="width:${pct}%"></span></span><span class="bar-value">${formatNumber(
        remaining
      )} / ${formatNumber(total)}${esc(balance.quota_unit || "")}</span></div>`
    );
  } else if (balance.quota_remaining !== null && balance.quota_remaining !== undefined) {
    rows.push(
      `<div class="bar-row"><span>剩余额度</span><span class="bar-track"><span class="bar-fill" style="width:100%"></span></span><span class="bar-value">${formatNumber(
        balance.quota_remaining
      )}${esc(balance.quota_unit || "")}</span></div>`
    );
  }
  return rows.length ? `<div class="balance-bars">${rows.join("")}</div>` : "";
}

function snippetCard(key, studio) {
  if (!key.models || !key.models.length) {
    return `<section class="card snippet-card">
      <div class="card-head">
        <div><div class="card-title">片段工坊</div><div class="card-sub">选好模型，就能生成可直接复制的配置。</div></div>
      </div>
      <div class="card-body">${emptyState({
        iconName: "layers",
        title: "还没有可用模型",
        text: "先为这个 Key 勾选模型，片段工坊才知道该生成哪套调用方式。",
        action: `<button class="btn btn-secondary" data-action="manage-models" data-id="${esc(
          key.id
        )}">管理模型</button>`,
      })}</div>
    </section>`;
  }

  const capabilities = availableCapabilities(key);
  const capability = capabilities.includes(studio.capability)
    ? studio.capability
    : capabilities[0];
  const models = modelsForCapability(key, capability);
  const selected =
    models.find((model) => model.id === studio.selected?.[capability]) || models[0] || null;
  const formats = selected?.formats?.length ? selected.formats : ["env"];
  const format = formats.includes(studio.format)
    ? studio.format
    : formats.includes("env")
    ? "env"
    : formats[0];

  const capabilityTabs = capabilities
    .map(
      (item) => `<button class="seg-btn ${item === capability ? "active" : ""}" data-action="set-capability" data-id="${esc(
        item
      )}">${esc(CAPABILITY_LABELS[item] || item)}</button>`
    )
    .join("");

  const formatTabs = FORMAT_ORDER.map((item) => {
    const enabled = formats.includes(item);
    return `<button class="seg-btn ${item === format ? "active" : ""}" data-action="set-format" data-id="${esc(
      item
    )}" ${enabled ? "" : "disabled"} title="${enabled ? "" : "这个模型暂不支持该格式"}">${esc(
      FORMAT_LABELS[item]
    )}</button>`;
  }).join("");

  const modelOptions = models
    .map(
      (model) =>
        `<option value="${esc(model.id)}" ${model.id === selected?.id ? "selected" : ""}>${esc(
          model.display_name
        )} · ${esc(model.model_id)}</option>`
    )
    .join("");

  const preview = studio.previewLoading
    ? "正在生成预览…"
    : studio.previewError
    ? ""
    : studio.preview || "选择模型后，这里会显示可直接复制的片段。";

  const errorHtml = studio.previewError
    ? `<div class="code-error">${esc(studio.previewError)}</div>`
    : "";

  const options = [
    `<label class="check-inline"><input type="checkbox" data-studio-option="includeComments" ${
      studio.includeComments ? "checked" : ""
    }> 生成注释</label>`,
    format !== "env"
      ? `<label class="check-inline"><input type="checkbox" data-studio-option="directKey" ${
          studio.directKey ? "checked" : ""
        }> 代码里直接写入 Key</label>`
      : "",
    format === "env"
      ? `<label class="check-inline"><input type="checkbox" data-studio-option="includeAll" ${
          studio.includeAll ? "checked" : ""
        }> 合并其他已选能力</label>`
      : "",
  ]
    .filter(Boolean)
    .join("");

  return `<section class="card snippet-card">
    <div class="card-head">
      <div>
        <div class="card-title">片段工坊</div>
        <div class="card-sub">${esc(selected?.display_name || "选择一个模型")} · ${esc(
    FORMAT_LABELS[format] || format
  )}</div>
      </div>
      <span class="badge badge-brand">${icon("sparkles", 12)} 一键复制</span>
    </div>
    <div class="studio-controls">
      <div class="segmented" role="tablist" aria-label="模型能力">${capabilityTabs}</div>
      <div class="studio-row">
        <label for="studio-model">模型</label>
        <select id="studio-model" class="select" data-studio-model>${modelOptions}</select>
      </div>
      <div class="segmented" role="tablist" aria-label="输出格式">${formatTabs}</div>
      <div class="studio-options">${options}</div>
    </div>
    <div class="code-shell">
      <div class="code-top">
        <div class="code-label"><span class="dot"></span>${esc(FORMAT_LABELS[format] || format)} PREVIEW</div>
        <div class="code-status">${studio.previewLoading ? "生成中…" : "Key 已隐藏"}</div>
      </div>
      <pre class="code-pre" id="snippet-preview" aria-live="polite">${esc(preview)}</pre>
    </div>
    ${errorHtml}
    <div style="padding:0 20px 16px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      <button class="btn btn-primary" data-action="copy-snippet" data-id="${esc(
        key.id
      )}" ${studio.previewLoading || studio.previewError ? "disabled" : ""}>${icon(
    "copy",
    15
  )} 复制片段</button>
      <span class="faint" style="font-size:10.5px">${format === "env" ? "复制时才写入真实 Key" : "默认使用环境变量，不把 Key 写进代码"}</span>
    </div>
    <div class="code-note">${icon("info", 12)} 预览里只会显示打码后的 Key；点“复制片段”才会读取真实 Key，并记入使用时间。</div>
  </section>`;
}

function balanceCard(key, state) {
  const balance = key.balance;
  const provider = key.provider;
  const canAuto = Boolean(
    state.providers.find((item) => item.id === provider.id)?.balance_adapter
  );
  const threshold = Number(state.settings?.low_balance_threshold ?? 20);
  const thresholdCurrency = state.settings?.low_balance_currency || "CNY";
  const isLow =
    balance &&
    (balance.currency || "CNY") === thresholdCurrency &&
    balance.amount !== null &&
    Number(balance.amount) < threshold;

  const content = balance
    ? `<div class="balance-hero">
        <div>
          <div class="balance-value">${formatMoney(balance.amount, balance.currency)}<small>${esc(
      balance.currency || "CNY"
    )}</small></div>
          <div class="balance-source ${balance.source === "auto" ? "auto" : "manual"}">
            ${balance.source === "auto" ? icon("refresh", 11) : icon("edit", 11)}
            ${balance.source === "auto" ? "自动查询" : "手动记录"} · ${esc(timeAgo(balance.checked_at))}
          </div>
        </div>
        <div class="balance-meta">
          ${balance.expires_at ? `有效期至 ${esc(formatDate(balance.expires_at, { time: false }))}` : "未设置有效期"}
          ${isLow ? `<div class="badge badge-warn" style="margin-top:5px">低于提醒线</div>` : ""}
        </div>
      </div>
      ${balanceBars(balance)}
      ${balance.note ? `<div class="note-block" style="font-size:11px;padding:8px 10px">${esc(balance.note)}</div>` : ""}`
    : emptyState({
        iconName: "wallet",
        title: "还没有余额记录",
        text: "这个平台不一定开放余额查询；可以先手动记一笔，之后每次更新都会保留历史。",
      });

  return `<section class="card">
    <div class="card-head">
      <div><div class="card-title">余额与额度</div><div class="card-sub">余额、配额和到期时间都按时间点保存。</div></div>
      <div class="card-actions">
        <button class="btn btn-ghost btn-sm" data-action="manual-balance" data-id="${esc(
          key.id
        )}">${icon("edit", 13)} 手动记录</button>
        ${
          canAuto
            ? `<button class="btn btn-secondary btn-sm" data-action="refresh-balance" data-id="${esc(
                key.id
              )}">${icon("refresh", 13)} 自动查询</button>`
            : ""
        }
      </div>
    </div>
    <div class="card-body">${content}</div>
  </section>`;
}

export function detailView(state, key, studio) {
  if (!key) {
    return `<div class="page-head"><div><div class="eyebrow">KEYS</div><h1 class="page-title">这个 Key 不存在</h1><p class="page-sub">它可能已经被删除。</p></div></div>
      <button class="btn btn-secondary" data-action="back-to-keys">${icon("arrow-left", 14)} 返回 Key 列表</button>`;
  }

  const models = key.models || [];
  const modelHtml = models.length
    ? `<div class="model-list">${models
        .map(
          (model) => `<div class="model-row">
            <div class="model-row-main">
              <div class="model-row-name">${esc(model.display_name)}</div>
              <div class="model-row-id">${esc(model.model_id)}</div>
            </div>
            <div class="model-tags">${capabilityChips(model.capabilities)}</div>
          </div>`
        )
        .join("")}</div>`
    : emptyState({
        iconName: "layers",
        title: "还没有勾选模型",
        text: "把该 Key 能调用的模型勾上，片段工坊才能生成对应的代码。",
        action: `<button class="btn btn-secondary" data-action="manage-models" data-id="${esc(
          key.id
        )}">选择模型</button>`,
      });

  return `
    <button class="back-link" data-action="back-to-keys">${icon("arrow-left", 14)} 返回 Key 列表</button>
    <div class="detail-head">
      <div style="min-width:0">
        <div class="detail-title-row">
          <h1 class="detail-title">${esc(key.label)}</h1>
          ${statusBadge(key.status, key.expires_at)}
          ${providerBadge(key.provider)}
        </div>
        <div class="detail-sub">
          <span class="mono">${esc(key.hint)}</span>
          <span>·</span>
          <span>${key.models.length} 个可用模型</span>
          <span>·</span>
          <span>添加于 ${esc(formatDate(key.created_at, { time: false }))}</span>
        </div>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary" data-action="edit-key" data-id="${esc(
          key.id
        )}">${icon("edit", 14)} 编辑</button>
        <button class="btn btn-secondary" data-action="reveal-key" data-id="${esc(
          key.id
        )}">${icon("eye", 14)} 查看 Key</button>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-main">
        <section class="card">
          <div class="card-head">
            <div><div class="card-title">Key 信息</div><div class="card-sub">用途、环境和时间都记在这里。</div></div>
          </div>
          <div class="card-body">
            <div class="info-grid">
              ${infoItem(
                "平台",
                `<span style="display:inline-flex;align-items:center;gap:7px">${providerAvatar(
                  key.provider
                )}<span style="font-weight:600">${esc(key.provider.name)}</span></span>`
              )}
              ${infoItem("环境变量前缀", `<span class="code-inline">${esc(key.env_prefix)}</span>`)}
              ${infoItem("项目 / 用途", esc(key.project || "未填写"))}
              ${infoItem("环境", esc(key.environment || "开发"))}
              ${infoItem("创建时间", esc(formatDate(key.created_at)))}
              ${infoItem("最后复制", key.last_copied_at ? esc(formatDate(key.last_copied_at)) : "—")}
              ${infoItem("最后使用", key.last_used_at ? esc(formatDate(key.last_used_at)) : "—")}
            </div>
            <div class="card-divider"></div>
            <div class="info-label">备注</div>
            <div class="note-block">${esc(key.note || "还没有备注。")}</div>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div><div class="card-title">可用模型</div><div class="card-sub">不同能力可能对应不同的模型和调用方式。</div></div>
            <button class="btn btn-secondary btn-sm" data-action="manage-models" data-id="${esc(
              key.id
            )}">${icon("layers", 13)} 管理模型</button>
          </div>
          <div class="card-body">${modelHtml}</div>
        </section>

        ${balanceCard(key, state)}
      </div>

      <div class="detail-side">
        ${snippetCard(key, studio)}
      </div>
    </div>
  `;
}

export function settingsView(state) {
  const settings = state.settings || {};
  const app = state.app || {};
  const active = state.settingsTab || "preferences";
  const clipboardOn = settings.clipboard_watch === "1";
  const clipboardAvailable = Boolean(app.clipboard_available);
  const checkUpdatesOn = settings.check_updates !== "0";
  const autoRefreshOn = settings.auto_refresh_balance !== "0";
  const format = settings.default_format || "env";
  const navItems = [
    ["preferences", "settings", "偏好设置", "监听、刷新与片段默认值"],
    ["appearance", "image", "外观背景", "背景与液态玻璃"],
    ["data", "database", "数据与备份", "备份、导出与打开目录"],
    ["security", "shield", "安全说明", "本地存储与安全边界"],
    ["about", "info", "关于", "版本、更新与退出"],
  ];

  return `
    <div class="page-head">
      <div class="page-title-wrap">
        <div class="eyebrow">SETTINGS</div>
        <h1 class="page-title">设置</h1>
        <p class="page-sub">调整本地行为、备份数据，或查看这个工具的安全边界。</p>
      </div>
    </div>

    <div class="settings-layout">
      <aside class="settings-nav card">
        <div class="settings-nav-title">偏好与数据</div>
        <div class="settings-nav-list">
          ${navItems
            .map(
              ([id, iconName, title, desc]) => `<button class="settings-nav-item ${
                active === id ? "active" : ""
              }" data-action="settings-tab" data-id="${id}" data-settings-tab="${id}">
                <span class="settings-nav-icon">${icon(iconName, 16)}</span>
                <span class="settings-nav-copy"><strong>${title}</strong><small>${desc}</small></span>
              </button>`
            )
            .join("")}
        </div>
        <div class="settings-nav-foot">${icon("shield", 13)} 数据只保存在本机</div>
      </aside>

      <section class="settings-panel card">
        <div class="settings-panel-section ${active === "preferences" ? "active" : ""}" data-settings-panel="preferences">
          <div class="settings-section-head">
            <div><h2>偏好设置</h2><p>这些选项只影响本机行为，不会上传。</p></div>
          </div>
          <form id="settings-form">
            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">剪贴板监听</div>
                <div class="setting-desc">复制到像 API Key 的文本时，弹窗询问是否入库。只识别 Key 或 .env，不保存其他剪贴板内容。${clipboardAvailable ? "" : "当前系统不支持。"}</div>
              </div>
              <div class="setting-control">
                <label class="switch" title="剪贴板监听">
                  <input type="checkbox" name="clipboard_watch" ${clipboardOn ? "checked" : ""} ${clipboardAvailable ? "" : "disabled"}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">启动时检查更新</div>
                <div class="setting-desc">每天启动时查询一次 GitHub Releases；只提示新版本，不自动下载或安装。</div>
              </div>
              <div class="setting-control">
                <label class="switch" title="启动时检查更新">
                  <input type="checkbox" name="check_updates" ${checkUpdatesOn ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">自动刷新余额</div>
                <div class="setting-desc">支持自动查询的平台（DeepSeek、Kimi）每 15 分钟刷新一次；其他平台仍用手动记录。</div>
              </div>
              <div class="setting-control">
                <label class="switch" title="自动刷新余额">
                  <input type="checkbox" name="auto_refresh_balance" ${autoRefreshOn ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">低余额提醒线</div>
                <div class="setting-desc">余额低于这个数字时，仪表盘会提醒。只对已经记录过余额的 Key 生效。</div>
              </div>
              <div class="setting-control setting-inline">
                <select class="select" name="low_balance_currency" style="width:86px" aria-label="提醒币种">
                  ${["CNY", "USD", "EUR"]
                    .map(
                      (item) =>
                        `<option value="${item}" ${
                          (settings.low_balance_currency || "CNY") === item ? "selected" : ""
                        }>${item}</option>`
                    )
                    .join("")}
                </select>
                <input class="input" type="number" min="0" step="1" name="low_balance_threshold" style="width:104px" value="${esc(
                  settings.low_balance_threshold || "20"
                )}">
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">默认片段格式</div>
                <div class="setting-desc">打开 Key 详情时优先展示的格式。</div>
              </div>
              <div class="setting-control" style="width:132px">
                <select class="select" name="default_format">
                  ${FORMAT_ORDER.map(
                    (item) =>
                      `<option value="${item}" ${format === item ? "selected" : ""}>${
                        FORMAT_LABELS[item]
                      }</option>`
                  ).join("")}
                </select>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">代码片段默认带注释</div>
                <div class="setting-desc">生成 Python / cURL / JavaScript 时附带安装提示和模型说明。</div>
              </div>
              <div class="setting-control">
                <label class="switch" title="默认带注释">
                  <input type="checkbox" name="include_comments" ${settings.include_comments === "1" ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">代码里直接写入 Key</div>
                <div class="setting-desc">默认关闭，代码使用环境变量读取 Key。开启后复制代码会把真实 Key 写进代码，适合一次性脚本。</div>
              </div>
              <div class="setting-control">
                <label class="switch" title="代码里直接写入 Key">
                  <input type="checkbox" name="direct_key" ${settings.direct_key === "1" ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="settings-actions">
              <button class="btn btn-primary" type="submit" data-action="save-settings">${icon("check", 15)} 保存设置</button>
              <span class="faint">保存后立即生效</span>
            </div>
          </form>
        </div>

        <div class="settings-panel-section ${active === "appearance" ? "active" : ""}" data-settings-panel="appearance">
          <div class="settings-section-head">
            <div><h2>外观背景</h2><p>背景只影响界面观感，不会改变你的 Key 和余额数据。</p></div>
          </div>
          <div class="appearance-block">
            <div class="appearance-label">背景预设</div>
            <div class="background-grid">
              ${BACKGROUND_PRESETS.map(
                (preset) => `<button class="background-card ${
                  (settings.background_style || "aurora") === preset.id ? "active" : ""
                }" data-action="set-background" data-id="${preset.id}">
                  <span class="background-swatch" style="background:linear-gradient(135deg, ${preset.colors.join(
                    ", "
                  )})"></span>
                  <span class="background-card-copy"><strong>${preset.name}</strong><small>${preset.hint}</small></span>
                  ${icon("check", 14, "background-check")}
                </button>`
              ).join("")}
              <button class="background-card ${
                settings.background_style === "custom" ? "active" : ""
              }" data-action="set-background" data-id="custom">
                <span class="background-swatch background-swatch-custom" ${
                  settings.background_style === "custom"
                    ? `style="background-image:url('/api/background/image?v=${esc(
                        app.background_version || "0"
                      )}')"`
                    : ""
                }>${settings.background_style === "custom" ? "" : icon("image", 20)}</span>
                <span class="background-card-copy"><strong>自定义图片</strong><small>PNG · JPEG · WebP</small></span>
                ${icon("check", 14, "background-check")}
              </button>
            </div>

            <div class="appearance-upload">
              <label class="btn btn-secondary btn-sm">
                ${icon("upload", 14)} 上传背景图片
                <input id="background-file" type="file" accept="image/png,image/jpeg,image/webp" hidden>
              </label>
              <button class="btn btn-ghost btn-sm" data-action="reset-background">${icon(
                "refresh",
                14
              )} 恢复默认</button>
              <span class="faint">图片会保存在本机数据目录，不超过 6 MB。</span>
            </div>
          </div>
        </div>

        <div class="settings-panel-section ${active === "data" ? "active" : ""}" data-settings-panel="data">
          <div class="settings-section-head">
            <div><h2>数据与备份</h2><p>建议定期下载一份数据库备份。</p></div>
          </div>
          <div class="banner banner-warn">${icon("alert", 15)}<div><strong>当前为明文保存模式。</strong>数据库和备份中的 Key 不再加密，任何能访问这些文件的人都可以读取。</div></div>
          <div class="settings-block">
            <div class="info-label">数据目录</div>
            ${
              app.data_dir_warning
                ? `<div class="banner banner-error">${icon("alert", 15)}<div><strong>原数据目录不可用，已临时改用默认目录。</strong><br>${esc(
                    app.data_dir_warning
                  )}<br>插回原来的盘或选择一个新的数据目录即可恢复。</div></div>`
                : ""
            }
            <div class="data-path">${icon("database", 14)} ${esc(app.data_path || "data")}</div>
            <div class="btn-row" style="margin:10px 0 4px">
              <button class="btn btn-secondary btn-sm" data-action="change-data-dir" ${
                app.data_dir_changeable === false ? "disabled" : ""
              }>${icon("folder", 14)} 更改数据目录</button>
              ${
                app.data_dir_changeable !== false && app.data_dir_source !== "default"
                  ? `<button class="btn btn-ghost btn-sm" data-action="reset-data-dir">恢复默认目录</button>`
                  : ""
              }
              <span class="faint" style="font-size:11px">${
                app.data_dir_changeable === false
                  ? "当前用 --db 参数启动，只能在命令行指定。"
                  : app.data_dir_source === "env"
                  ? "当前由环境变量 API_KEY_LEDGER_DATA_DIR 指定。"
                  : app.data_dir_source === "config"
                  ? "当前为自定义目录。"
                  : "当前为默认目录。"
              }</span>
            </div>
            <div class="settings-action-grid" style="margin-top:14px">
              <button class="btn btn-secondary" data-action="backup">${icon("download", 15)} 下载数据库备份</button>
              <button class="btn btn-secondary" data-action="export">${icon("external", 15)} 导出 JSON（不含 Key）</button>
              <label class="btn btn-secondary file-btn">${icon("upload", 15)} 恢复数据库备份
                <input id="restore-file" type="file" accept=".db,application/octet-stream,application/x-sqlite3" hidden>
              </label>
              <button class="btn btn-ghost" data-action="open-data-dir">${icon("folder", 15)} 打开数据文件夹</button>
            </div>
            <p class="field-hint">恢复会覆盖当前数据库，并先自动备份当前库。备份包含明文 Key，请妥善保管。</p>
            <p class="field-hint">更改数据目录会把当前数据库<strong>复制</strong>到新位置并立即切换；原位置的文件保留不删，确认无误后可自行删除。</p>
          </div>
        </div>

        <div class="settings-panel-section ${active === "security" ? "active" : ""}" data-settings-panel="security">
          <div class="settings-section-head">
            <div><h2>安全说明</h2><p>这是一个本机工具，不是云服务。</p></div>
          </div>
          <ul class="security-list">
            <li>${icon("shield", 15)} Key 以明文保存在本机，不再绑定系统账户；请限制数据目录访问权限。</li>
            <li>${icon("server", 15)} 服务只监听 127.0.0.1，不对外网开放。</li>
            <li>${icon("database", 15)} 数据保存在本机 SQLite，不会上传；备份包含明文 Key，请妥善保管。</li>
            <li>${icon("eye-off", 15)} 列表和预览只显示打码后的 Key，复制或查看时才读取。</li>
          </ul>
        </div>

        <div class="settings-panel-section ${active === "about" ? "active" : ""}" data-settings-panel="about">
          <div class="settings-section-head">
            <div><h2>关于</h2><p>${esc(app.name || "API 钥匙簿")}</p></div>
          </div>
          <div class="info-grid settings-info">
            ${infoItem("版本", esc(app.version || "1.3.3"))}
            ${infoItem("数据目录", `<span class="mono" style="font-size:11px">${esc(app.data_path || "")}</span>`)}
            ${infoItem("剪贴板监听", clipboardOn ? "已开启" : "已关闭")}
            ${infoItem("界面", app.native ? "桌面窗口" : "浏览器")}
          </div>
          <div class="settings-actions">
            <button class="btn btn-secondary" data-action="check-updates">${icon("refresh", 15)} 检查更新</button>
            ${
              app.native
                ? `<button class="btn btn-secondary" data-action="exit-app">退出程序</button>`
                : ""
            }
          </div>
        </div>
      </section>
    </div>
  `;
}

export function dashboardView(state) {
  const stats = state.stats || {};
  const providers = state.providers || [];
  const lowKeys = lowBalanceKeys(state);
  const threshold = Number(state.settings?.low_balance_threshold ?? 20);
  const thresholdCurrency = state.settings?.low_balance_currency || "CNY";

  const metrics = [
    ["Key 总数", stats.total_keys ?? 0, "明文保存在本机", "key"],
    ["使用中的平台", stats.providers_with_keys ?? 0, `共 ${providers.length} 个平台模板`, "server"],
    ["本月新增", stats.month_new ?? 0, "按本地时间统计", "sparkles"],
    ["待关注余额", stats.low_balance ?? 0, `低于 ${formatMoney(threshold, thresholdCurrency)}`, "wallet", stats.low_balance ? "warn" : ""],
  ];

  const metricHtml = metrics
    .map(
      ([label, value, foot, iconName, tone]) => `<div class="overview-metric ${tone || ""}">
        <div class="overview-metric-top"><span>${esc(label)}</span>${icon(iconName, 15)}</div>
        <strong>${formatNumber(value)}</strong>
        <small>${esc(foot)}</small>
      </div>`
    )
    .join("");

  const alertHtml = lowKeys.length
    ? `<div class="attention-line">
        ${icon("alert", 15)}
        <span><strong>${lowKeys.length} 个 Key</strong> 余额低于提醒线：${esc(
          lowKeys.slice(0, 3).map((key) => key.label).join("、")
        )}${lowKeys.length > 3 ? " 等" : ""}</span>
      </div>`
    : "";

  const platformTiles = providers
    .map(
      (provider) => `<button class="platform-tile" data-action="go-platform" data-id="${esc(
        provider.id
      )}">
        <div class="platform-tile-top">
          ${providerAvatar(provider)}
          <strong>${esc(provider.name)}</strong>
          <span class="platform-count">${provider.key_count} Key</span>
        </div>
        <div class="platform-tile-desc">${esc(provider.description || "")}</div>
        <div class="platform-tile-meta">${provider.model_count} 个模型${icon("chevron-right", 13)}</div>
      </button>`
    )
    .join("");

  const recent = (stats.recent_usage || []).slice(0, 7);
  const recentHtml = recent.length
    ? recent
        .map(
          (item) => `<div class="recent-row">
            <div class="recent-dot">${icon(actionIcon(item.action), 14)}</div>
            <div class="recent-main">
              <div class="recent-title">${esc(actionLabel(item.action))} · ${esc(
            item.key_label || "已删除的 Key"
          )}</div>
              <div class="recent-meta">${esc(item.provider_name || "本地记录")}</div>
            </div>
            <div class="recent-time">${esc(timeAgo(item.created_at))}</div>
          </div>`
        )
        .join("")
    : emptyState({
        iconName: "clock",
        title: "还没有使用记录",
        text: "复制一次片段、更新一次余额或查看一次 Key，这里就会出现时间线。",
      });

  return `
    <div class="page-head compact">
      <div class="page-title-wrap">
        <div class="eyebrow">API LEDGER</div>
        <h1 class="page-title">把散落的 Key，收进一个地方。</h1>
        <p class="page-sub">记录平台、用途和模型能力；需要调用时，直接复制对应平台、对应模型的代码片段。</p>
      </div>
    </div>

    ${alertHtml}
    <section class="overview-strip">${metricHtml}</section>

    <section class="card platform-panel">
      <div class="card-head">
        <div><div class="card-title">平台</div><div class="card-sub">点一个平台，查看它下面的 Key。</div></div>
        <span class="badge badge-quiet">${providers.length} 个</span>
      </div>
      <div class="card-body">
        <div class="platform-grid">${platformTiles}</div>
      </div>
    </section>

    <section class="card recent-panel">
      <div class="card-head">
        <div><div class="card-title">最近活动</div><div class="card-sub">复制片段、更新余额、查看 Key 都会留下记录。</div></div>
        <span class="badge badge-quiet">最近 ${recent.length} 条</span>
      </div>
      <div class="card-body"><div class="recent-list">${recentHtml}</div></div>
    </section>
  `;
}
