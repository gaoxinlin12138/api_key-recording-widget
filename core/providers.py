"""Provider network adapters: model discovery and balance lookup.

Only official, documented endpoints are used.  If a provider does not expose
balance information to a normal API key, the UI falls back to a manual entry
instead of inventing a number.
"""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

from .utils import as_float, normalize_base_url

MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = "ApiKeyLedger/1.0 (+local)"


class ProviderError(RuntimeError):
    pass


class BalanceNotSupported(ProviderError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


_opener = build_opener(
    _NoRedirect(),
    HTTPSHandler(context=ssl.create_default_context()),
)


def _request_json(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> Any:
    body = None
    final_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        final_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        final_headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=final_headers, method=method)
    try:
        with _opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read(600).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
        message = _extract_error_message(detail) or f"HTTP {exc.code}"
        raise ProviderError(f"平台返回错误：{message}") from exc
    except URLError as exc:
        raise ProviderError(f"连接不上平台接口：{exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError("平台接口响应超时，请稍后再试。") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("平台返回内容过大，已停止读取。")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("平台返回的不是有效 JSON。") from exc


def _extract_error_message(text: str) -> str:
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text[:240]
    if isinstance(data, dict):
        for key in ("error", "message", "msg", "detail"):
            value = data.get(key)
            if isinstance(value, str):
                return value[:300]
            if isinstance(value, dict):
                nested = value.get("message")
                if isinstance(nested, str):
                    return nested[:300]
    return text[:240]


def _bearer(secret: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {secret}"}


def _base(provider: dict[str, Any], override: str = "") -> str:
    return normalize_base_url(override or provider.get("default_base_url") or "")


def _models_url(provider: dict[str, Any], override: str = "") -> str:
    explicit = (provider.get("models_url") or "").strip()
    if explicit and not override:
        return explicit
    base = _base(provider, override)
    if not base:
        raise ProviderError("这个平台还没有填写 Base URL。")
    return f"{base.rstrip('/')}/models"


def guess_capabilities(model_id: str, methods: list[str] | None = None) -> list[str]:
    lower = model_id.lower()
    methods = [str(item).lower() for item in (methods or [])]
    if any(word in lower for word in ("embedding", "embed", "bge-", "gte-", "text-embedding")):
        return ["embedding"]
    if "rerank" in lower:
        return ["rerank"]
    if any(word in lower for word in ("dall-e", "imagen", "image", "wanx", "flux", "stable-diffusion")):
        return ["image"]
    if any(word in lower for word in ("whisper", "tts", "audio", "speech")):
        return ["audio"]
    if any(word in lower for word in ("vl", "vision", "multimodal", "omni")):
        return ["chat", "vision"]
    if "embedcontent" in methods:
        return ["embedding"]
    return ["chat"]


def fetch_models(
    provider: dict[str, Any], secret: str, base_url_override: str = ""
) -> list[dict[str, Any]]:
    adapter = (provider.get("model_fetch") or "openai").lower()
    if adapter == "anthropic":
        data = _request_json(
            "https://api.anthropic.com/v1/models?limit=100",
            {
                "x-api-key": secret,
                "anthropic-version": "2023-06-01",
            },
        )
        items = data.get("data", []) if isinstance(data, dict) else []
        result = []
        for item in items[:200]:
            model_id = item.get("id", "")
            if not model_id:
                continue
            result.append(
                {
                    "model_id": model_id,
                    "display_name": item.get("display_name") or model_id,
                    "capabilities": ["chat", "vision"],
                    "base_url": "",
                }
            )
        if not result:
            raise ProviderError("平台没有返回可用模型。")
        return result

    if adapter == "gemini":
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models?"
            + urlencode({"key": secret, "pageSize": 1000})
        )
        data = _request_json(url)
        items = data.get("models", []) if isinstance(data, dict) else []
        result = []
        for item in items[:200]:
            name = item.get("name", "")
            model_id = name.split("/")[-1] if name else ""
            if not model_id:
                continue
            methods = item.get("supportedGenerationMethods") or []
            capabilities = guess_capabilities(model_id, methods)
            if "generateContent" not in methods and "embedContent" not in methods:
                continue
            result.append(
                {
                    "model_id": model_id,
                    "display_name": item.get("displayName") or model_id,
                    "capabilities": capabilities,
                    "base_url": "",
                }
            )
        if not result:
            raise ProviderError("平台没有返回可用模型。")
        return result

    # OpenAI-compatible providers.
    url = _models_url(provider, base_url_override)
    data = _request_json(url, _bearer(secret))
    items = data.get("data", []) if isinstance(data, dict) else []
    result = []
    for item in items[:200]:
        model_id = item.get("id", "")
        if not model_id:
            continue
        result.append(
            {
                "model_id": model_id,
                "display_name": item.get("name") or model_id,
                "capabilities": guess_capabilities(model_id),
                "base_url": _base(provider, base_url_override),
            }
        )
    if not result:
        raise ProviderError("平台没有返回可用模型。")
    return result


def fetch_balance(provider: dict[str, Any], secret: str) -> dict[str, Any]:
    adapter = (provider.get("balance_adapter") or "").lower()
    if not adapter:
        raise BalanceNotSupported(
            "这个平台没有向普通 API Key 开放余额查询，请手动记录余额或额度。"
        )

    if adapter == "deepseek":
        data = _request_json("https://api.deepseek.com/user/balance", _bearer(secret))
        infos = data.get("balance_infos", []) if isinstance(data, dict) else []
        info = infos[0] if infos else {}
        amount = as_float(info.get("total_balance"))
        if amount is None:
            raise ProviderError("余额接口返回的格式无法识别。")
        note_parts = []
        if info.get("topped_up_balance") is not None:
            note_parts.append(f"充值余额 {info.get('topped_up_balance')}")
        if info.get("granted_balance") is not None:
            note_parts.append(f"赠送余额 {info.get('granted_balance')}")
        return {
            "amount": amount,
            "currency": (info.get("currency") or "CNY").upper(),
            "source": "auto",
            "note": "，".join(note_parts),
            "raw": json.dumps(data, ensure_ascii=False)[:2000],
        }

    if adapter == "moonshot":
        data = _request_json(
            "https://api.moonshot.cn/v1/users/me/balance", _bearer(secret)
        )
        payload = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
        if not isinstance(payload, dict):
            raise ProviderError("余额接口返回的格式无法识别。")
        amount = as_float(payload.get("available_balance"))
        if amount is None:
            raise ProviderError("余额接口返回的格式无法识别。")
        note_parts = []
        if payload.get("cash_balance") is not None:
            note_parts.append(f"现金余额 {payload.get('cash_balance')}")
        if payload.get("voucher_balance") is not None:
            note_parts.append(f"代金券 {payload.get('voucher_balance')}")
        return {
            "amount": amount,
            "currency": "CNY",
            "source": "auto",
            "note": "，".join(note_parts),
            "raw": json.dumps(data, ensure_ascii=False)[:2000],
        }

    raise BalanceNotSupported("这个平台的余额适配器还没有实现。")
