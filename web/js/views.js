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
    `<button class="filter-chip ${active ? "" : "active"}" data-action="filter-provider" data-id="">鍏ㄩ儴 <span class="count">${state.keys.length}</span></button>`,
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
  const title = provider ? provider.name : "鍏ㄩ儴 Key";
  const sub = provider
    ? `${provider.key_count} 涓?Key 路 ${provider.description || ""}`
    : `${state.keys.length} 涓?Key锛屽垎甯冨湪 ${state.stats?.providers_with_keys || 0} 涓钩鍙癭;

  const rows = filteredKeys
    .map((key) => {
      const models = key.models || [];
      const modelHtml = models.length
        ? models
            .slice(0, 2)
            .map((model) => `<span class="model-mini" title="${esc(model.model_id)}">${esc(model.model_id)}</span>`)
            .join("") +
          (models.length > 2 ? `<span class="model-mini more">+${models.length - 2}</span>` : "")
        : `<span class="faint" style="font-size:11px">灏氭湭閫夋ā鍨?/span>`;
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
          )}</strong><span class="sub">${balance.source === "auto" ? "鑷姩鏌ヨ" : "鎵嬪姩璁板綍"} 路 ${esc(
            timeAgo(balance.checked_at)
          )}</span>`
        : `<span class="faint" style="font-size:11px">鏈褰?/span>`;
      return `<tr data-action="open-key" data-id="${esc(key.id)}" tabindex="0">
        <td>
          <div class="key-cell">
            ${providerAvatar(key.provider)}
            <div style="min-width:0">
              <div class="key-name">${esc(key.label)}</div>
              <div class="key-sub">${esc(key.provider.name)} 路 <span class="mono">${esc(
        key.hint
      )}</span></div>
            </div>
          </div>
        </td>
        <td><div class="project-cell ${key.project ? "" : "empty"}" title="${esc(
        key.project || ""
      )}">${esc(key.project || "鏈～鍐欑敤閫?)}</div></td>
        <td><div class="model-mini-list">${modelHtml}</div></td>
        <td class="balance-cell">${balanceHtml}</td>
        <td class="date-cell">${key.last_copied_at ? esc(timeAgo(key.last_copied_at)) : "鈥?}</td>
        <td class="actions-cell">
          <div class="row-actions">
            <button class="btn btn-secondary btn-sm" data-action="quick-copy" data-id="${esc(
              key.id
            )}" title="澶嶅埗杩欎釜 Key 鐨?.env">${icon("copy", 13)} .env</button>
            <button class="btn btn-danger btn-sm btn-icon" data-action="delete-key" data-id="${esc(
              key.id
            )}" title="鍒犻櫎杩欎釜 Key" aria-label="鍒犻櫎杩欎釜 Key">${icon("trash", 13)}</button>
          </div>
        </td>
      </tr>`;
    })
    .join("");

  const table = filteredKeys.length
    ? `<div class="table-wrap">
        <table class="key-table">
          <thead><tr>
            <th>Key</th><th>鐢ㄩ€?/th><th>鍙敤妯″瀷</th><th class="num">浣欓</th><th>鏈€杩戝鍒?/th><th class="actions-col"></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`
    : emptyState({
        iconName: "search",
        title: state.search ? "娌℃湁鍖归厤鐨?Key" : "杩欓噷杩樻病鏈?Key",
        text: state.search
          ? `娌℃湁鎵惧埌鍖呭惈鈥?{state.search}鈥濈殑璁板綍锛屾崲涓叧閿瘝鎴栨竻绌烘悳绱€俙
          : "浠庝华琛ㄧ洏鐨勫揩閫熷鍏ュ紑濮嬶紝鎴栬€呮墜鍔ㄦ坊鍔犵涓€涓?Key銆?,
        action: state.search
          ? `<button class="btn btn-secondary" data-action="clear-search">娓呯┖鎼滅储</button>`
          : `<button class="btn btn-primary" data-action="add-key">${icon("plus", 15)} 娣诲姞绗竴涓?Key</button>`,
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
      `<div class="bar-row"><span>鍓╀綑棰濆害</span><span class="bar-track"><span class="bar-fill ${
        pct < 20 ? "warn" : ""
      }" style="width:${pct}%"></span></span><span class="bar-value">${formatNumber(
        remaining
      )} / ${formatNumber(total)}${esc(balance.quota_unit || "")}</span></div>`
    );
  } else if (balance.quota_remaining !== null && balance.quota_remaining !== undefined) {
    rows.push(
      `<div class="bar-row"><span>鍓╀綑棰濆害</span><span class="bar-track"><span class="bar-fill" style="width:100%"></span></span><span class="bar-value">${formatNumber(
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
        <div><div class="card-title">鐗囨宸ュ潑</div><div class="card-sub">閫夊ソ妯″瀷锛屽氨鑳界敓鎴愬彲鐩存帴澶嶅埗鐨勯厤缃€?/div></div>
      </div>
      <div class="card-body">${emptyState({
        iconName: "layers",
        title: "杩樻病鏈夊彲鐢ㄦā鍨?,
        text: "鍏堜负杩欎釜 Key 鍕鹃€夋ā鍨嬶紝鐗囨宸ュ潑鎵嶇煡閬撹鐢熸垚鍝璋冪敤鏂瑰紡銆?,
        action: `<button class="btn btn-secondary" data-action="manage-models" data-id="${esc(
          key.id
        )}">绠＄悊妯″瀷</button>`,
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
    )}" ${enabled ? "" : "disabled"} title="${enabled ? "" : "杩欎釜妯″瀷鏆備笉鏀寔璇ユ牸寮?}">${esc(
      FORMAT_LABELS[item]
    )}</button>`;
  }).join("");

  const modelOptions = models
    .map(
      (model) =>
        `<option value="${esc(model.id)}" ${model.id === selected?.id ? "selected" : ""}>${esc(
          model.display_name
        )} 路 ${esc(model.model_id)}</option>`
    )
    .join("");

  const preview = studio.previewLoading
    ? "姝ｅ湪鐢熸垚棰勮鈥?
    : studio.previewError
    ? ""
    : studio.preview || "閫夋嫨妯″瀷鍚庯紝杩欓噷浼氭樉绀哄彲鐩存帴澶嶅埗鐨勭墖娈点€?;

  const errorHtml = studio.previewError
    ? `<div class="code-error">${esc(studio.previewError)}</div>`
    : "";

  const options = [
    `<label class="check-inline"><input type="checkbox" data-studio-option="includeComments" ${
      studio.includeComments ? "checked" : ""
    }> 鐢熸垚娉ㄩ噴</label>`,
    format !== "env"
      ? `<label class="check-inline"><input type="checkbox" data-studio-option="directKey" ${
          studio.directKey ? "checked" : ""
        }> 浠ｇ爜閲岀洿鎺ュ啓鍏?Key</label>`
      : "",
    format === "env"
      ? `<label class="check-inline"><input type="checkbox" data-studio-option="includeAll" ${
          studio.includeAll ? "checked" : ""
        }> 鍚堝苟鍏朵粬宸查€夎兘鍔?/label>`
      : "",
  ]
    .filter(Boolean)
    .join("");

  return `<section class="card snippet-card">
    <div class="card-head">
      <div>
        <div class="card-title">鐗囨宸ュ潑</div>
        <div class="card-sub">${esc(selected?.display_name || "閫夋嫨涓€涓ā鍨?)} 路 ${esc(
    FORMAT_LABELS[format] || format
  )}</div>
      </div>
      <span class="badge badge-brand">${icon("sparkles", 12)} 涓€閿鍒?/span>
    </div>
    <div class="studio-controls">
      <div class="segmented" role="tablist" aria-label="妯″瀷鑳藉姏">${capabilityTabs}</div>
      <div class="studio-row">
        <label for="studio-model">妯″瀷</label>
        <select id="studio-model" class="select" data-studio-model>${modelOptions}</select>
      </div>
      <div class="segmented" role="tablist" aria-label="杈撳嚭鏍煎紡">${formatTabs}</div>
      <div class="studio-options">${options}</div>
    </div>
    <div class="code-shell">
      <div class="code-top">
        <div class="code-label"><span class="dot"></span>${esc(FORMAT_LABELS[format] || format)} PREVIEW</div>
        <div class="code-status">${studio.previewLoading ? "鐢熸垚涓€? : "Key 宸查殣钘?}</div>
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
  )} 澶嶅埗鐗囨</button>
      <span class="faint" style="font-size:10.5px">${format === "env" ? "澶嶅埗鏃舵墠鍐欏叆鐪熷疄 Key" : "榛樿浣跨敤鐜鍙橀噺锛屼笉鎶?Key 鍐欒繘浠ｇ爜"}</span>
    </div>
    <div class="code-note">${icon("info", 12)} 棰勮閲屽彧浼氭樉绀烘墦鐮佸悗鐨?Key锛涚偣鈥滃鍒剁墖娈碘€濇墠浼氳鍙栫湡瀹?Key锛屽苟璁板叆浣跨敤鏃堕棿銆?/div>
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
            ${balance.source === "auto" ? "鑷姩鏌ヨ" : "鎵嬪姩璁板綍"} 路 ${esc(timeAgo(balance.checked_at))}
          </div>
        </div>
        <div class="balance-meta">
          ${balance.expires_at ? `鏈夋晥鏈熻嚦 ${esc(formatDate(balance.expires_at, { time: false }))}` : "鏈缃湁鏁堟湡"}
          ${isLow ? `<div class="badge badge-warn" style="margin-top:5px">浣庝簬鎻愰啋绾?/div>` : ""}
        </div>
      </div>
      ${balanceBars(balance)}
      ${balance.note ? `<div class="note-block" style="font-size:11px;padding:8px 10px">${esc(balance.note)}</div>` : ""}`
    : emptyState({
        iconName: "wallet",
        title: "杩樻病鏈変綑棰濊褰?,
        text: "杩欎釜骞冲彴涓嶄竴瀹氬紑鏀句綑棰濇煡璇紱鍙互鍏堟墜鍔ㄨ涓€绗旓紝涔嬪悗姣忔鏇存柊閮戒細淇濈暀鍘嗗彶銆?,
      });

  return `<section class="card">
    <div class="card-head">
      <div><div class="card-title">浣欓涓庨搴?/div><div class="card-sub">浣欓銆侀厤棰濆拰鍒版湡鏃堕棿閮芥寜鏃堕棿鐐逛繚瀛樸€?/div></div>
      <div class="card-actions">
        <button class="btn btn-ghost btn-sm" data-action="manual-balance" data-id="${esc(
          key.id
        )}">${icon("edit", 13)} 鎵嬪姩璁板綍</button>
        ${
          canAuto
            ? `<button class="btn btn-secondary btn-sm" data-action="refresh-balance" data-id="${esc(
                key.id
              )}">${icon("refresh", 13)} 鑷姩鏌ヨ</button>`
            : ""
        }
      </div>
    </div>
    <div class="card-body">${content}</div>
  </section>`;
}

export function detailView(state, key, studio) {
  if (!key) {
    return `<div class="page-head"><div><div class="eyebrow">KEYS</div><h1 class="page-title">杩欎釜 Key 涓嶅瓨鍦?/h1><p class="page-sub">瀹冨彲鑳藉凡缁忚鍒犻櫎銆?/p></div></div>
      <button class="btn btn-secondary" data-action="back-to-keys">${icon("arrow-left", 14)} 杩斿洖 Key 鍒楄〃</button>`;
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
        title: "杩樻病鏈夊嬀閫夋ā鍨?,
        text: "鎶婅 Key 鑳借皟鐢ㄧ殑妯″瀷鍕句笂锛岀墖娈靛伐鍧婃墠鑳界敓鎴愬搴旂殑浠ｇ爜銆?,
        action: `<button class="btn btn-secondary" data-action="manage-models" data-id="${esc(
          key.id
        )}">閫夋嫨妯″瀷</button>`,
      });

  return `
    <button class="back-link" data-action="back-to-keys">${icon("arrow-left", 14)} 杩斿洖 Key 鍒楄〃</button>
    <div class="detail-head">
      <div style="min-width:0">
        <div class="detail-title-row">
          <h1 class="detail-title">${esc(key.label)}</h1>
          ${statusBadge(key.status, key.expires_at)}
          ${providerBadge(key.provider)}
        </div>
        <div class="detail-sub">
          <span class="mono">${esc(key.hint)}</span>
          <span>路</span>
          <span>${key.models.length} 涓彲鐢ㄦā鍨?/span>
          <span>路</span>
          <span>娣诲姞浜?${esc(formatDate(key.created_at, { time: false }))}</span>
        </div>
      </div>
      <div class="page-actions">
        <button class="btn btn-secondary" data-action="edit-key" data-id="${esc(
          key.id
        )}">${icon("edit", 14)} 缂栬緫</button>
        <button class="btn btn-secondary" data-action="reveal-key" data-id="${esc(
          key.id
        )}">${icon("eye", 14)} 鏌ョ湅 Key</button>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-main">
        <section class="card">
          <div class="card-head">
            <div><div class="card-title">Key 淇℃伅</div><div class="card-sub">鐢ㄩ€斻€佺幆澧冨拰鏃堕棿閮借鍦ㄨ繖閲屻€?/div></div>
          </div>
          <div class="card-body">
            <div class="info-grid">
              ${infoItem(
                "骞冲彴",
                `<span style="display:inline-flex;align-items:center;gap:7px">${providerAvatar(
                  key.provider
                )}<span style="font-weight:600">${esc(key.provider.name)}</span></span>`
              )}
              ${infoItem("鐜鍙橀噺鍓嶇紑", `<span class="code-inline">${esc(key.env_prefix)}</span>`)}
              ${infoItem("椤圭洰 / 鐢ㄩ€?, esc(key.project || "鏈～鍐?))}
              ${infoItem("鐜", esc(key.environment || "寮€鍙?))}
              ${infoItem("鍒涘缓鏃堕棿", esc(formatDate(key.created_at)))}
              ${infoItem("鏈€鍚庡鍒?, key.last_copied_at ? esc(formatDate(key.last_copied_at)) : "鈥?)}
              ${infoItem("鏈€鍚庝娇鐢?, key.last_used_at ? esc(formatDate(key.last_used_at)) : "鈥?)}
            </div>
            <div class="card-divider"></div>
            <div class="info-label">澶囨敞</div>
            <div class="note-block">${esc(key.note || "杩樻病鏈夊娉ㄣ€?)}</div>
          </div>
        </section>

        <section class="card">
          <div class="card-head">
            <div><div class="card-title">鍙敤妯″瀷</div><div class="card-sub">涓嶅悓鑳藉姏鍙兘瀵瑰簲涓嶅悓鐨勬ā鍨嬪拰璋冪敤鏂瑰紡銆?/div></div>
            <button class="btn btn-secondary btn-sm" data-action="manage-models" data-id="${esc(
              key.id
            )}">${icon("layers", 13)} 绠＄悊妯″瀷</button>
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
    ["preferences", "settings", "鍋忓ソ璁剧疆", "鐩戝惉銆佸埛鏂颁笌鐗囨榛樿鍊?],
    ["appearance", "image", "澶栬鑳屾櫙", "鑳屾櫙涓庢恫鎬佺幓鐠?],
    ["data", "database", "鏁版嵁涓庡浠?, "澶囦唤銆佸鍑轰笌鎵撳紑鐩綍"],
    ["security", "shield", "瀹夊叏璇存槑", "鏈湴瀛樺偍涓庡畨鍏ㄨ竟鐣?],
    ["about", "info", "鍏充簬", "鐗堟湰銆佹洿鏂颁笌閫€鍑?],
  ];

  return `
    <div class="page-head">
      <div class="page-title-wrap">
        <div class="eyebrow">SETTINGS</div>
        <h1 class="page-title">璁剧疆</h1>
        <p class="page-sub">璋冩暣鏈湴琛屼负銆佸浠芥暟鎹紝鎴栨煡鐪嬭繖涓伐鍏风殑瀹夊叏杈圭晫銆?/p>
      </div>
    </div>

    <div class="settings-layout">
      <aside class="settings-nav card">
        <div class="settings-nav-title">鍋忓ソ涓庢暟鎹?/div>
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
        <div class="settings-nav-foot">${icon("shield", 13)} 鏁版嵁鍙繚瀛樺湪鏈満</div>
      </aside>

      <section class="settings-panel card">
        <div class="settings-panel-section ${active === "preferences" ? "active" : ""}" data-settings-panel="preferences">
          <div class="settings-section-head">
            <div><h2>鍋忓ソ璁剧疆</h2><p>杩欎簺閫夐」鍙奖鍝嶆湰鏈鸿涓猴紝涓嶄細涓婁紶銆?/p></div>
          </div>
          <form id="settings-form">
            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">鍓创鏉跨洃鍚?/div>
                <div class="setting-desc">澶嶅埗鍒板儚 API Key 鐨勬枃鏈椂锛屽脊绐楄闂槸鍚﹀叆搴撱€傚彧璇嗗埆 Key 鎴?.env锛屼笉淇濆瓨鍏朵粬鍓创鏉垮唴瀹广€?{clipboardAvailable ? "" : "褰撳墠绯荤粺涓嶆敮鎸併€?}</div>
              </div>
              <div class="setting-control">
                <label class="switch" title="鍓创鏉跨洃鍚?>
                  <input type="checkbox" name="clipboard_watch" ${clipboardOn ? "checked" : ""} ${clipboardAvailable ? "" : "disabled"}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">鍚姩鏃舵鏌ユ洿鏂?/div>
                <div class="setting-desc">姣忓ぉ鍚姩鏃舵煡璇竴娆?GitHub Releases锛涘彧鎻愮ず鏂扮増鏈紝涓嶈嚜鍔ㄤ笅杞芥垨瀹夎銆?/div>
              </div>
              <div class="setting-control">
                <label class="switch" title="鍚姩鏃舵鏌ユ洿鏂?>
                  <input type="checkbox" name="check_updates" ${checkUpdatesOn ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">鑷姩鍒锋柊浣欓</div>
                <div class="setting-desc">鏀寔鑷姩鏌ヨ鐨勫钩鍙帮紙DeepSeek銆並imi锛夋瘡 15 鍒嗛挓鍒锋柊涓€娆★紱鍏朵粬骞冲彴浠嶇敤鎵嬪姩璁板綍銆?/div>
              </div>
              <div class="setting-control">
                <label class="switch" title="鑷姩鍒锋柊浣欓">
                  <input type="checkbox" name="auto_refresh_balance" ${autoRefreshOn ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">浣庝綑棰濇彁閱掔嚎</div>
                <div class="setting-desc">浣欓浣庝簬杩欎釜鏁板瓧鏃讹紝浠〃鐩樹細鎻愰啋銆傚彧瀵瑰凡缁忚褰曡繃浣欓鐨?Key 鐢熸晥銆?/div>
              </div>
              <div class="setting-control setting-inline">
                <select class="select" name="low_balance_currency" style="width:86px" aria-label="鎻愰啋甯佺">
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
                <div class="setting-title">榛樿鐗囨鏍煎紡</div>
                <div class="setting-desc">鎵撳紑 Key 璇︽儏鏃朵紭鍏堝睍绀虹殑鏍煎紡銆?/div>
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
                <div class="setting-title">浠ｇ爜鐗囨榛樿甯︽敞閲?/div>
                <div class="setting-desc">鐢熸垚 Python / cURL / JavaScript 鏃堕檮甯﹀畨瑁呮彁绀哄拰妯″瀷璇存槑銆?/div>
              </div>
              <div class="setting-control">
                <label class="switch" title="榛樿甯︽敞閲?>
                  <input type="checkbox" name="include_comments" ${settings.include_comments === "1" ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="setting-row">
              <div class="setting-main">
                <div class="setting-title">浠ｇ爜閲岀洿鎺ュ啓鍏?Key</div>
                <div class="setting-desc">榛樿鍏抽棴锛屼唬鐮佷娇鐢ㄧ幆澧冨彉閲忚鍙?Key銆傚紑鍚悗澶嶅埗浠ｇ爜浼氭妸鐪熷疄 Key 鍐欒繘浠ｇ爜锛岄€傚悎涓€娆℃€ц剼鏈€?/div>
              </div>
              <div class="setting-control">
                <label class="switch" title="浠ｇ爜閲岀洿鎺ュ啓鍏?Key">
                  <input type="checkbox" name="direct_key" ${settings.direct_key === "1" ? "checked" : ""}>
                  <span class="switch-track"></span>
                </label>
              </div>
            </div>

            <div class="settings-actions">
              <button class="btn btn-primary" type="submit" data-action="save-settings">${icon("check", 15)} 淇濆瓨璁剧疆</button>
              <span class="faint">淇濆瓨鍚庣珛鍗崇敓鏁?/span>
            </div>
          </form>
        </div>

        <div class="settings-panel-section ${active === "appearance" ? "active" : ""}" data-settings-panel="appearance">
          <div class="settings-section-head">
            <div><h2>澶栬鑳屾櫙</h2><p>鑳屾櫙鍙奖鍝嶇晫闈㈣鎰燂紝涓嶄細鏀瑰彉浣犵殑 Key 鍜屼綑棰濇暟鎹€?/p></div>
          </div>
          <div class="appearance-block">
            <div class="appearance-label">鑳屾櫙棰勮</div>
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
                <span class="background-card-copy"><strong>鑷畾涔夊浘鐗?/strong><small>PNG 路 JPEG 路 WebP</small></span>
                ${icon("check", 14, "background-check")}
              </button>
            </div>

            <div class="appearance-upload">
              <label class="btn btn-secondary btn-sm">
                ${icon("upload", 14)} 涓婁紶鑳屾櫙鍥剧墖
                <input id="background-file" type="file" accept="image/png,image/jpeg,image/webp" hidden>
              </label>
              <button class="btn btn-ghost btn-sm" data-action="reset-background">${icon(
                "refresh",
                14
              )} 鎭㈠榛樿</button>
              <span class="faint">鍥剧墖浼氫繚瀛樺湪鏈満鏁版嵁鐩綍锛屼笉瓒呰繃 6 MB銆?/span>
            </div>
          </div>
        </div>

        <div class="settings-panel-section ${active === "data" ? "active" : ""}" data-settings-panel="data">
          <div class="settings-section-head">
            <div><h2>鏁版嵁涓庡浠?/h2><p>寤鸿瀹氭湡涓嬭浇涓€浠芥暟鎹簱澶囦唤銆?/p></div>
          </div>
          <div class="banner banner-warn">${icon("alert", 15)}<div><strong>褰撳墠涓烘槑鏂囦繚瀛樻ā寮忋€?/strong>鏁版嵁搴撳拰澶囦唤涓殑 Key 涓嶅啀鍔犲瘑锛屼换浣曡兘璁块棶杩欎簺鏂囦欢鐨勪汉閮藉彲浠ヨ鍙栥€?/div></div>
          <div class="settings-block">
            <div class="info-label">鏁版嵁鐩綍</div>
            <div class="data-path">${icon("database", 14)} ${esc(app.data_path || "data")}</div>
            <div class="btn-row" style="margin:10px 0 4px">
              <button class="btn btn-secondary btn-sm" data-action="change-data-dir" ${
                app.data_dir_changeable === false ? "disabled" : ""
              }>${icon("folder", 14)} 鏇存敼鏁版嵁鐩綍</button>
              <span class="faint" style="font-size:11px">${
                app.data_dir_changeable === false
                  ? "褰撳墠鐢?--db 鍙傛暟鍚姩锛屽彧鑳藉湪鍛戒护琛屾寚瀹氥€?
                  : app.data_dir_source === "env"
                  ? "褰撳墠鐢辩幆澧冨彉閲?API_KEY_LEDGER_DATA_DIR 鎸囧畾銆?
                  : app.data_dir_source === "config"
                  ? "褰撳墠涓鸿嚜瀹氫箟鐩綍銆?
                  : "褰撳墠涓洪粯璁ょ洰褰曘€?
              }</span>
            </div>
            <div class="settings-action-grid" style="margin-top:14px">
              <button class="btn btn-secondary" data-action="backup">${icon("download", 15)} 涓嬭浇鏁版嵁搴撳浠?/button>
              <button class="btn btn-secondary" data-action="export">${icon("external", 15)} 瀵煎嚭 JSON锛堜笉鍚?Key锛?/button>
              <label class="btn btn-secondary file-btn">${icon("upload", 15)} 鎭㈠鏁版嵁搴撳浠?
                <input id="restore-file" type="file" accept=".db,application/octet-stream,application/x-sqlite3" hidden>
              </label>
              <button class="btn btn-ghost" data-action="open-data-dir">${icon("folder", 15)} 鎵撳紑鏁版嵁鏂囦欢澶?/button>
            </div>
            <p class="field-hint">鎭㈠浼氳鐩栧綋鍓嶆暟鎹簱锛屽苟鍏堣嚜鍔ㄥ浠藉綋鍓嶅簱銆傚浠藉寘鍚槑鏂?Key锛岃濡ュ杽淇濈銆?/p>
            <p class="field-hint">鏇存敼鏁版嵁鐩綍浼氭妸褰撳墠鏁版嵁搴?strong>澶嶅埗</strong>鍒版柊浣嶇疆骞剁珛鍗冲垏鎹紱鍘熶綅缃殑鏂囦欢淇濈暀涓嶅垹锛岀‘璁ゆ棤璇悗鍙嚜琛屽垹闄ゃ€?/p>
          </div>
        </div>

        <div class="settings-panel-section ${active === "security" ? "active" : ""}" data-settings-panel="security">
          <div class="settings-section-head">
            <div><h2>瀹夊叏璇存槑</h2><p>杩欐槸涓€涓湰鏈哄伐鍏凤紝涓嶆槸浜戞湇鍔°€?/p></div>
          </div>
          <ul class="security-list">
            <li>${icon("shield", 15)} Key 浠ユ槑鏂囦繚瀛樺湪鏈満锛屼笉鍐嶇粦瀹氱郴缁熻处鎴凤紱璇烽檺鍒舵暟鎹洰褰曡闂潈闄愩€?/li>
            <li>${icon("server", 15)} 鏈嶅姟鍙洃鍚?127.0.0.1锛屼笉瀵瑰缃戝紑鏀俱€?/li>
            <li>${icon("database", 15)} 鏁版嵁淇濆瓨鍦ㄦ湰鏈?SQLite锛屼笉浼氫笂浼狅紱澶囦唤鍖呭惈鏄庢枃 Key锛岃濡ュ杽淇濈銆?/li>
            <li>${icon("eye-off", 15)} 鍒楄〃鍜岄瑙堝彧鏄剧ず鎵撶爜鍚庣殑 Key锛屽鍒舵垨鏌ョ湅鏃舵墠璇诲彇銆?/li>
          </ul>
        </div>

        <div class="settings-panel-section ${active === "about" ? "active" : ""}" data-settings-panel="about">
          <div class="settings-section-head">
            <div><h2>鍏充簬</h2><p>${esc(app.name || "API 閽ュ寵绨?)}</p></div>
          </div>
          <div class="info-grid settings-info">
            ${infoItem("鐗堟湰", esc(app.version || "1.3.1"))}
            ${infoItem("鏁版嵁鐩綍", `<span class="mono" style="font-size:11px">${esc(app.data_path || "")}</span>`)}
            ${infoItem("鍓创鏉跨洃鍚?, clipboardOn ? "宸插紑鍚? : "宸插叧闂?)}
            ${infoItem("鐣岄潰", app.native ? "妗岄潰绐楀彛" : "娴忚鍣?)}
          </div>
          <div class="settings-actions">
            <button class="btn btn-secondary" data-action="check-updates">${icon("refresh", 15)} 妫€鏌ユ洿鏂?/button>
            ${
              app.native
                ? `<button class="btn btn-secondary" data-action="exit-app">閫€鍑虹▼搴?/button>`
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
    ["Key 鎬绘暟", stats.total_keys ?? 0, "鏄庢枃淇濆瓨鍦ㄦ湰鏈?, "key"],
    ["浣跨敤涓殑骞冲彴", stats.providers_with_keys ?? 0, `鍏?${providers.length} 涓钩鍙版ā鏉縛, "server"],
    ["鏈湀鏂板", stats.month_new ?? 0, "鎸夋湰鍦版椂闂寸粺璁?, "sparkles"],
    ["寰呭叧娉ㄤ綑棰?, stats.low_balance ?? 0, `浣庝簬 ${formatMoney(threshold, thresholdCurrency)}`, "wallet", stats.low_balance ? "warn" : ""],
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
        <span><strong>${lowKeys.length} 涓?Key</strong> 浣欓浣庝簬鎻愰啋绾匡細${esc(
          lowKeys.slice(0, 3).map((key) => key.label).join("銆?)
        )}${lowKeys.length > 3 ? " 绛? : ""}</span>
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
        <div class="platform-tile-meta">${provider.model_count} 涓ā鍨?{icon("chevron-right", 13)}</div>
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
              <div class="recent-title">${esc(actionLabel(item.action))} 路 ${esc(
            item.key_label || "宸插垹闄ょ殑 Key"
          )}</div>
              <div class="recent-meta">${esc(item.provider_name || "鏈湴璁板綍")}</div>
            </div>
            <div class="recent-time">${esc(timeAgo(item.created_at))}</div>
          </div>`
        )
        .join("")
    : emptyState({
        iconName: "clock",
        title: "杩樻病鏈変娇鐢ㄨ褰?,
        text: "澶嶅埗涓€娆＄墖娈点€佹洿鏂颁竴娆′綑棰濇垨鏌ョ湅涓€娆?Key锛岃繖閲屽氨浼氬嚭鐜版椂闂寸嚎銆?,
      });

  return `
    <div class="page-head compact">
      <div class="page-title-wrap">
        <div class="eyebrow">API LEDGER</div>
        <h1 class="page-title">鎶婃暎钀界殑 Key锛屾敹杩涗竴涓湴鏂广€?/h1>
        <p class="page-sub">璁板綍骞冲彴銆佺敤閫斿拰妯″瀷鑳藉姏锛涢渶瑕佽皟鐢ㄦ椂锛岀洿鎺ュ鍒跺搴斿钩鍙般€佸搴旀ā鍨嬬殑浠ｇ爜鐗囨銆?/p>
      </div>
    </div>

    ${alertHtml}
    <section class="overview-strip">${metricHtml}</section>

    <section class="card platform-panel">
      <div class="card-head">
        <div><div class="card-title">骞冲彴</div><div class="card-sub">鐐逛竴涓钩鍙帮紝鏌ョ湅瀹冧笅闈㈢殑 Key銆?/div></div>
        <span class="badge badge-quiet">${providers.length} 涓?/span>
      </div>
      <div class="card-body">
        <div class="platform-grid">${platformTiles}</div>
      </div>
    </section>

    <section class="card recent-panel">
      <div class="card-head">
        <div><div class="card-title">鏈€杩戞椿鍔?/div><div class="card-sub">澶嶅埗鐗囨銆佹洿鏂颁綑棰濄€佹煡鐪?Key 閮戒細鐣欎笅璁板綍銆?/div></div>
        <span class="badge badge-quiet">鏈€杩?${recent.length} 鏉?/span>
      </div>
      <div class="card-body"><div class="recent-list">${recentHtml}</div></div>
    </section>
  `;
}
