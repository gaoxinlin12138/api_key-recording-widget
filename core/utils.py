"""Small shared helpers that do not touch the database or the network."""

from __future__ import annotations

import hashlib
import math
import re
import secrets
from datetime import datetime, timezone
from typing import Any


def new_id(prefix: str = "") -> str:
    return f"{prefix}{secrets.token_hex(8)}"


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp that sorts correctly as text."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def mask_secret(secret: str) -> str:
    secret = (secret or "").strip()
    if not secret:
        return "未填写"
    if len(secret) <= 8:
        return "•" * len(secret)
    if secret.startswith("sk-"):
        head = secret[:3]
    elif secret.startswith("AIza"):
        head = secret[:4]
    else:
        head = secret[:2]
    return f"{head}…{secret[-4:]}"


def sanitize_env_prefix(value: str, fallback: str = "API") -> str:
    prefix = re.sub(r"[^A-Za-z0-9_]+", "_", (value or "").strip()).strip("_").upper()
    if not prefix:
        prefix = fallback
    if prefix[0].isdigit():
        prefix = f"API_{prefix}"
    return prefix[:48]


def normalize_base_url(value: str | None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value.rstrip("/")


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def truncate(value: str, limit: int = 120) -> str:
    value = (value or "").strip()
    return value if len(value) <= limit else f"{value[:limit - 1]}…"
