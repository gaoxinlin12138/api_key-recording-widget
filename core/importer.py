"""Parse keys and connection details pasted from provider consoles.

Supported inputs:
  * .env style assignments (the format in the user's screenshot)
  * JSON objects / arrays
  * curl commands
  * a bare API key

The parser is intentionally conservative.  It never sends the pasted text
anywhere and returns a small, editable draft for the UI.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from .catalog import provider_for_base_url, provider_for_env_prefix

_ENV_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
_KEY_RE = re.compile(
    r"^(?:sk-[A-Za-z0-9_\-\.]{12,}|AIza[0-9A-Za-z_\-]{20,}|[A-Za-z0-9_\-]{32,})$"
)
_SECRET_NAME_RE = re.compile(r"(?:^|_)(?:API_?KEY|KEY|TOKEN|SECRET)$", re.I)
_BASE_NAME_RE = re.compile(r"(?:BASE_URL|API_BASE|BASE|ENDPOINT|HOST)$", re.I)
_MODEL_NAME_RE = re.compile(r"MODEL", re.I)

_PATH_SUFFIXES = (
    "/chat/completions",
    "/completions",
    "/embeddings",
    "/images/generations",
    "/models",
    "/messages",
)


def parse_pasted(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return _failure("请先粘贴 Key、.env 或 curl 内容。")

    warnings: list[str] = []
    if text.startswith("{") or text.startswith("["):
        result = _parse_json(text)
        if result:
            result["warnings"] = warnings
            return _finish(result)

    env_result = _parse_env(text)
    if env_result:
        result, env_warnings = env_result
        warnings.extend(env_warnings)
        result["warnings"] = warnings
        return _finish(result)

    curl_result = _parse_curl(text)
    if curl_result:
        curl_result["warnings"] = warnings
        return _finish(curl_result)

    raw = _parse_raw(text)
    if raw:
        raw["warnings"] = warnings
        return _finish(raw)

    return _failure("没有识别到 API Key。可以手动填写，或检查粘贴内容是否完整。")


def _failure(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": message,
        "secret": "",
        "base_url": "",
        "model": "",
        "models": [],
        "env_prefix": "",
        "provider_id": None,
        "warnings": [],
    }


_PROVIDER_PREFIX = {
    "deepseek": "DEEPSEEK",
    "qwen": "QWEN",
    "openai": "OPENAI",
    "anthropic": "ANTHROPIC",
    "gemini": "GEMINI",
    "moonshot": "MOONSHOT",
    "zhipu": "ZHIPU",
    "custom": "CUSTOM",
}


def _finish(result: dict[str, Any]) -> dict[str, Any]:
    result.setdefault("models", [])
    result.setdefault("warnings", [])
    result.setdefault("secret", "")
    provider_id = result.get("provider_id")
    prefix = (result.get("env_prefix") or "").upper()
    if provider_id in _PROVIDER_PREFIX and prefix in {"", "API", "CUSTOM"}:
        result["env_prefix"] = _PROVIDER_PREFIX[provider_id]
        result["label"] = _label_from_prefix(result["env_prefix"], provider_id)
    if result.get("secret"):
        result["ok"] = True
    else:
        result["ok"] = False
        result.setdefault("error", "识别到了配置，但没有找到 API Key。")
    return result


def _clean_value(value: str) -> str:
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"', "`"}:
        value = value[1:-1]
    return value.strip()


def _normalize_base(value: str) -> str:
    value = _clean_value(value)
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        return value
    parsed = urlparse(value)
    path = parsed.path.rstrip("/")
    for suffix in _PATH_SUFFIXES:
        if path.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break

    host = (parsed.hostname or "").lower()
    # Anthropic and Gemini SDKs take the host (their version path is added by
    # the snippet), so a pasted /v1 or /v1beta should not be kept.
    if host in {"api.anthropic.com", "generativelanguage.googleapis.com"}:
        path = ""
    elif host == "api.openai.com" and not path:
        path = "/v1"
    elif host == "api.moonshot.cn" and not path:
        path = "/v1"
    elif host == "open.bigmodel.cn" and not path:
        path = "/api/paas/v4"
    elif host == "dashscope.aliyuncs.com" and not path:
        path = "/compatible-mode/v1"

    # Keep a meaningful version prefix (e.g. /v1, /compatible-mode/v1,
    # /api/paas/v4); drop only endpoint paths.
    return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")


def _guess_capability(variable: str) -> str:
    upper = variable.upper()
    if "EMBED" in upper:
        return "embedding"
    if "RERANK" in upper or "RANK" in upper:
        return "rerank"
    if "VISION" in upper or "MULTIMODAL" in upper or upper.endswith("_VL_MODEL"):
        return "vision"
    if "IMAGE" in upper or "IMG" in upper or "T2I" in upper:
        return "image"
    return "chat"


def _prefix_from_secret_var(name: str) -> str:
    upper = name.upper()
    for suffix in ("_API_KEY", "_APIKEY", "_KEY", "_TOKEN", "_SECRET"):
        if upper.endswith(suffix):
            prefix = upper[: -len(suffix)]
            return prefix.strip("_")
    return ""


def _prefix_from_base_var(name: str) -> str:
    upper = name.upper()
    for suffix in ("_API_BASE", "_BASE_URL", "_BASE", "_ENDPOINT", "_HOST"):
        if upper.endswith(suffix):
            return upper[: -len(suffix)].strip("_")
    return ""


def _model_candidates_from_assignments(assignments: dict[str, str]) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    seen: set[str] = set()
    for name, value in assignments.items():
        if not _MODEL_NAME_RE.search(name):
            continue
        value = _clean_value(value)
        if not value or value.startswith("${"):
            continue
        if value in seen:
            continue
        seen.add(value)
        models.append(
            {
                "var": name,
                "model_id": value,
                "capability": _guess_capability(name),
            }
        )
    return models


_TITLE_HINTS = (
    (("deepseek",), "deepseek"),
    (("百炼", "dashscope", "通义", "阿里云"), "qwen"),
    (("claude", "anthropic"), "anthropic"),
    (("gemini", "google ai studio", "generativelanguage"), "gemini"),
    (("kimi", "moonshot"), "moonshot"),
    (("智谱", "bigmodel", "glm"), "zhipu"),
    (("openai", "chatgpt"), "openai"),
)


def provider_from_title(title: str) -> str | None:
    """Infer a provider from the foreground window title at copy time."""
    lower = (title or "").lower()
    for needles, provider_id in _TITLE_HINTS:
        if any(needle in lower for needle in needles):
            return provider_id
    return None


def _guess_provider(
    secret: str, base_url: str, prefix: str, models: list[dict[str, str]]
) -> str | None:
    by_base = provider_for_base_url(base_url)
    if by_base:
        return by_base

    by_prefix = provider_for_env_prefix(prefix)
    if by_prefix:
        return by_prefix

    lower_secret = secret.lower()
    if lower_secret.startswith("sk-ant-"):
        return "anthropic"
    if secret.startswith("AIza"):
        return "gemini"
    if lower_secret.startswith("sk-proj-"):
        return "openai"

    for item in models:
        model = item.get("model_id", "").lower()
        if model.startswith("claude"):
            return "anthropic"
        if model.startswith("gemini"):
            return "gemini"
        if model.startswith(("qwen", "wanx", "gte-", "text-embedding-v")):
            return "qwen"
        if model.startswith(("glm", "embedding-3", "rerank")):
            return "zhipu"
        if model.startswith(("kimi", "moonshot")):
            return "moonshot"
        if model.startswith(("gpt", "o1", "o3", "o4", "text-embedding-3", "dall-e")):
            return "openai"
        if model.startswith("deepseek"):
            return "deepseek"
    return None


def _parse_env(text: str) -> tuple[dict[str, Any], list[str]] | None:
    assignments: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_RE.match(line)
        if not match:
            continue
        name, value = match.groups()
        assignments[name] = _clean_value(value)

    if not assignments:
        return None

    warnings: list[str] = []
    secret_name = ""
    secret = ""
    for name, value in assignments.items():
        if _SECRET_NAME_RE.search(name) and not name.upper().endswith(("_ID", "_NAME")):
            if value and not value.startswith("${") and len(value) >= 8:
                secret_name = name
                secret = value
                if "API_KEY" in name.upper() or "APIKEY" in name.upper():
                    break

    base_name = ""
    base_url = ""
    for name, value in assignments.items():
        if _BASE_NAME_RE.search(name) and value.startswith(("http://", "https://")):
            base_name = name
            base_url = value
            if "API_BASE" in name.upper() or "BASE_URL" in name.upper():
                break

    models = _model_candidates_from_assignments(assignments)
    prefix = _prefix_from_secret_var(secret_name) or _prefix_from_base_var(base_name)
    provider_id = _guess_provider(secret, base_url, prefix, models)

    if not secret:
        warnings.append("配置里没有找到常见的 API_KEY / _KEY / TOKEN 字段。")
    if not base_url:
        warnings.append("没有找到 Base URL，已使用平台默认地址。")
    if not models:
        warnings.append("没有找到模型字段，稍后可在模型库里勾选。")

    return (
        {
            "source": "env",
            "secret": secret,
            "base_url": _normalize_base(base_url),
            "model": next((m["model_id"] for m in models if m["capability"] == "chat"), ""),
            "models": models,
            "env_prefix": prefix,
            "provider_id": provider_id,
            "label": _label_from_prefix(prefix, provider_id),
            "raw_variables": sorted(assignments.keys()),
        },
        warnings,
    )


def _parse_json(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None

    flat: dict[str, Any] = {}

    def walk(value: Any, prefix: str = "", depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(child, (dict, list)):
                    walk(child, child_prefix, depth + 1)
                else:
                    flat[child_prefix] = child
        elif isinstance(value, list):
            for index, child in enumerate(value[:10]):
                walk(child, f"{prefix}[{index}]", depth + 1)

    walk(payload)

    def pick(*needles: str) -> tuple[str, str]:
        for name, value in flat.items():
            lower = name.lower()
            if any(lower.endswith(needle) or lower == needle for needle in needles):
                if isinstance(value, (str, int, float)) and str(value).strip():
                    return name, _clean_value(str(value))
        return "", ""

    secret_name, secret = pick("api_key", "apikey", "key", "token", "secret")
    base_name, base_url = pick("base_url", "baseurl", "base", "endpoint")
    model_name, model = pick("model", "model_id", "modelname")
    prefix = _prefix_from_secret_var(secret_name) or _prefix_from_base_var(base_name)
    models = (
        [{"var": model_name, "model_id": model, "capability": "chat"}]
        if model
        else []
    )
    provider_id = _guess_provider(secret, base_url, prefix, models)

    return {
        "source": "json",
        "secret": secret,
        "base_url": _normalize_base(base_url),
        "model": model,
        "models": models,
        "env_prefix": prefix,
        "provider_id": provider_id,
        "label": _label_from_prefix(prefix, provider_id),
    }


def _parse_curl(text: str) -> dict[str, Any] | None:
    if "curl" not in text.lower():
        return None

    url_match = re.search(r"https?://[^\s'\"\\]+", text)
    base_url = _normalize_base(url_match.group(0)) if url_match else ""

    secret = ""
    auth_match = re.search(
        r"(?:Authorization\s*:\s*Bearer\s+|x-api-key\s*:\s*|api-key\s*:\s*)([A-Za-z0-9_\-\.]{8,})",
        text,
        re.I,
    )
    if auth_match:
        secret = auth_match.group(1)

    model = ""
    for body in re.findall(r"(?:-d|--data(?:-raw|-binary)?)\s+(['\"])(.*?)\1", text, re.S):
        raw_body = body[1]
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            value = payload.get("model")
            if isinstance(value, str):
                model = value
                break

    if not secret and not model and not base_url:
        return None

    models = [{"var": "MODEL", "model_id": model, "capability": "chat"}] if model else []
    prefix = _prefix_from_base_url(base_url)
    provider_id = _guess_provider(secret, base_url, prefix, models)
    return {
        "source": "curl",
        "secret": secret,
        "base_url": base_url,
        "model": model,
        "models": models,
        "env_prefix": prefix,
        "provider_id": provider_id,
        "label": _label_from_prefix(prefix, provider_id),
    }


def _parse_raw(text: str) -> dict[str, Any] | None:
    candidate = _clean_value(text)
    if any(char.isspace() for char in candidate):
        return None
    if not _KEY_RE.match(candidate):
        return None
    provider_id = _guess_provider(candidate, "", "", [])
    return {
        "source": "raw",
        "secret": candidate,
        "base_url": "",
        "model": "",
        "models": [],
        "env_prefix": "",
        "provider_id": provider_id,
        "label": _label_from_prefix("", provider_id),
    }


def _prefix_from_base_url(base_url: str) -> str:
    host = urlparse(base_url).hostname or ""
    if "deepseek" in host:
        return "DEEPSEEK"
    if "dashscope" in host:
        return "QWEN"
    if "openai" in host:
        return "OPENAI"
    if "anthropic" in host:
        return "ANTHROPIC"
    if "googleapis" in host:
        return "GEMINI"
    if "moonshot" in host:
        return "MOONSHOT"
    if "bigmodel" in host:
        return "ZHIPU"
    return ""


def _label_from_prefix(prefix: str, provider_id: str | None) -> str:
    names = {
        "deepseek": "DeepSeek",
        "qwen": "通义千问",
        "openai": "OpenAI",
        "anthropic": "Claude",
        "gemini": "Gemini",
        "moonshot": "Kimi",
        "zhipu": "智谱",
        "custom": "自定义平台",
    }
    provider_name = names.get(provider_id or "", "API")
    if prefix and prefix.upper() not in {"API", "CUSTOM"}:
        acronyms = {"LLM", "API", "AI", "GPT", "GLM", "TTS", "ASR", "RAG", "OCR", "URL", "ID"}
        words = [
            part if part in acronyms else part.title()
            for part in prefix.split("_")
            if part
        ]
        pretty = " ".join(words).strip()
        return f"{pretty} Key"
    return f"{provider_name} Key"
