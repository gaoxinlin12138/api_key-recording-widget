"""Check GitHub Releases for a newer desktop build.

No account, token or backend is required for a public repository.  The app
only checks metadata; it never downloads or executes a release automatically.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .version import __version__

GITHUB_REPO = "gaoxinlin12138/api_key-recording-widget"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
LATEST_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
USER_AGENT = "ApiKeyLedger-Updater/1.0"


class UpdateError(RuntimeError):
    pass


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (value or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _request_release(timeout: int = 12) -> dict[str, Any]:
    request = urllib.request.Request(
        LATEST_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_000_000)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub 返回 HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"连接 GitHub 失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise UpdateError("检查更新超时。") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("GitHub 返回的内容不是有效 JSON。") from exc
    if not isinstance(data, dict):
        raise UpdateError("GitHub 返回格式不正确。")
    return data


def check_for_update(
    current: str = __version__,
    *,
    timeout: int = 12,
) -> dict[str, Any]:
    data = _request_release(timeout=timeout)
    latest_tag = str(data.get("tag_name") or "")
    latest = latest_tag.lstrip("v")
    current_tuple = version_tuple(current)
    latest_tuple = version_tuple(latest)
    if current_tuple is None or latest_tuple is None:
        raise UpdateError("版本号格式无法比较。")

    notes = str(data.get("body") or "").strip()
    return {
        "ok": True,
        "current": current,
        "latest": latest,
        "latest_tag": latest_tag,
        "update_available": latest_tuple > current_tuple,
        "url": str(data.get("html_url") or RELEASES_URL),
        "notes": notes[:8000],
        "published_at": data.get("published_at"),
        "name": data.get("name"),
    }
