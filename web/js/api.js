const CSRF =
  document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function api(path, { method = "GET", body, signal } = {}) {
  const headers = { "X-CSRF-Token": CSRF };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("连不上本地服务，请确认启动窗口还在运行。", 0);
  }

  const type = response.headers.get("content-type") || "";
  let payload;
  if (type.includes("application/json")) {
    payload = await response.json().catch(() => ({}));
  } else {
    payload = await response.text();
  }

  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && payload.error) ||
      (typeof payload === "string" && payload) ||
      `请求失败（HTTP ${response.status}）`;
    throw new ApiError(message, response.status);
  }
  return payload;
}

export async function downloadFile(path, filename) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "X-CSRF-Token": CSRF },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("连不上本地服务，请确认启动窗口还在运行。", 0);
  }
  if (!response.ok) {
    let message = `下载失败（HTTP ${response.status}）`;
    try {
      const data = await response.json();
      if (data?.error) message = data.error;
    } catch {
      /* ignore */
    }
    throw new ApiError(message, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  area.style.pointerEvents = "none";
  document.body.appendChild(area);
  area.focus();
  area.select();
  document.execCommand("copy");
  area.remove();
}
