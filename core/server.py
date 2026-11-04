"""Local HTTP server and JSON API for the API Key Ledger."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import sys
import threading
import time
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .clipboard import ClipboardWatcher
from .importer import parse_pasted, provider_from_title
from .providers import (
    BalanceNotSupported,
    ProviderError,
    fetch_balance,
    fetch_models,
)
from .snippets import SnippetError, generate_snippet
from .store import Store, StoreError
from .updater import GITHUB_REPO, check_for_update
from .utils import fingerprint, new_id, utc_now
from .version import __app_name__, __version__

APP_NAME = __app_name__
APP_VERSION = __version__
MAX_BODY = 12_000_000
MAX_BACKGROUND_BYTES = 6_000_000
BACKGROUND_DATA_URL = re.compile(
    r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$", re.S
)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class Application:
    def __init__(
        self,
        base_dir: Path,
        db_path: Path,
        web_dir: Path | None = None,
        native: bool = False,
    ):
        self.base_dir = Path(base_dir)
        self.web_dir = Path(web_dir) if web_dir else self.base_dir / "web"
        self.native = native
        self.data_dir = db_path.parent
        self.store = Store(db_path)
        self.csrf_token = secrets.token_urlsafe(32)
        self.port = 0
        self._pending: dict[str, dict[str, Any]] = {}
        self._pending_lock = threading.Lock()
        self._update_cache: dict[str, Any] | None = None
        self._update_cache_at = 0.0
        self._balance_refresh_lock = threading.Lock()
        self.clipboard = ClipboardWatcher(self._on_clipboard)
        self.settings = self.store.get_settings()
        if self.settings.get("clipboard_watch") == "1":
            self.clipboard.set_enabled(True)

    def stop(self) -> None:
        self.clipboard.stop()

    # ------------------------------------------------------------------
    # clipboard capture
    # ------------------------------------------------------------------
    def _on_clipboard(self, text: str, source_title: str = "") -> None:
        draft = parse_pasted(text)
        if draft.get("ok") and not draft.get("provider_id") and source_title:
            provider_id = provider_from_title(source_title)
            if provider_id:
                provider = self.store.get_provider(provider_id)
                draft["provider_id"] = provider_id
                draft["provider_source"] = "window"
                if (draft.get("env_prefix") or "").upper() in {"", "API", "CUSTOM"}:
                    draft["env_prefix"] = provider.get("env_prefix") or "API"
        secret = (draft.get("secret") or "").strip()
        if not draft.get("ok") or not secret:
            return
        if self.store.has_fingerprint(secret):
            return
        fp = fingerprint(secret)
        now = time.time()
        with self._pending_lock:
            self._cleanup_pending(now)
            for item in self._pending.values():
                if item["fingerprint"] == fp:
                    return
            pending_id = new_id("clip_")
            self._pending[pending_id] = {
                "id": pending_id,
                "fingerprint": fp,
                "draft": draft,
                "created_at": utc_now(),
                "ts": now,
            }
            if len(self._pending) > 5:
                oldest = min(self._pending.values(), key=lambda item: item["ts"])
                self._pending.pop(oldest["id"], None)

    def _cleanup_pending(self, now: float | None = None) -> None:
        now = now or time.time()
        expired = [
            key
            for key, item in self._pending.items()
            if now - item["ts"] > 600
        ]
        for key in expired:
            self._pending.pop(key, None)

    def pending_list(self) -> list[dict[str, Any]]:
        now = time.time()
        with self._pending_lock:
            self._cleanup_pending(now)
            return [
                {
                    "id": item["id"],
                    "draft": item["draft"],
                    "hint": item["draft"].get("secret", "")[-4:],
                    "created_at": item["created_at"],
                }
                for item in sorted(
                    self._pending.values(), key=lambda value: value["ts"], reverse=True
                )
            ]

    def accept_pending(self, pending_id: str) -> dict[str, Any]:
        with self._pending_lock:
            item = self._pending.pop(pending_id, None)
        if not item:
            raise ApiError("这条剪贴板记录已经失效，请重新复制。", 404)
        return item["draft"]

    def dismiss_pending(self, pending_id: str) -> None:
        with self._pending_lock:
            self._pending.pop(pending_id, None)

    # ------------------------------------------------------------------
    # state / snippets
    # ------------------------------------------------------------------
    def state(self) -> dict[str, Any]:
        data = self.store.state()
        data["app"] = {
            "name": APP_NAME,
            "version": APP_VERSION,
            "data_path": str(self.data_dir),
            "clipboard_available": self.clipboard.available,
            "clipboard_enabled": self.clipboard.enabled,
            "native": self.native,
            "background_version": self.store.get_settings().get("background_version", "0"),
            "server_time": utc_now(),
        }
        data["clipboard_pending"] = self.pending_list()
        return data

    def build_snippet(self, body: dict[str, Any]) -> dict[str, Any]:
        key_id = (body.get("key_id") or "").strip()
        if not key_id:
            raise ApiError("缺少 key_id。")
        raw_key = self.store.get_key_raw(key_id)
        provider = self.store.get_provider(raw_key["provider_id"])
        selections = body.get("models")
        if not isinstance(selections, list) or not selections:
            raise ApiError("请至少选择一个模型。")

        key_public = self.store.get_key_public(key_id)
        available = {model["id"]: model for model in key_public["models"]}
        models: list[dict[str, Any]] = []
        for selection in selections:
            if isinstance(selection, str):
                selection = {"id": selection}
            if not isinstance(selection, dict):
                continue
            model_id = selection.get("id") or selection.get("model_id")
            model = available.get(model_id)
            if not model:
                raise ApiError("所选模型不在此 Key 的可用模型里。")
            capability = (selection.get("capability") or "").strip()
            if capability and capability not in model.get("capabilities", []):
                raise ApiError(
                    f"{model['display_name']} 不支持 {capability} 能力。"
                )
            if not capability:
                capability = (model.get("capabilities") or ["chat"])[0]
            item = dict(model)
            item["capability"] = capability
            models.append(item)

        fmt = (body.get("format") or "env").strip()
        include_secret = bool(body.get("include_secret"))
        direct_key = bool(body.get("direct_key"))
        include_comments = bool(body.get("include_comments"))
        snippet_key = {
            "secret": self.store.reveal_secret_for_snippet(key_id)
            if include_secret
            else "",
            "hint": raw_key["secret_hint"],
            "env_prefix": raw_key["env_prefix"],
            "_now": utc_now(),
        }
        try:
            text = generate_snippet(
                provider,
                snippet_key,
                models,
                fmt,
                include_secret=include_secret,
                direct_key=direct_key,
                include_comments=include_comments,
            )
        except SnippetError as exc:
            raise ApiError(str(exc), 400) from exc
        return {
            "text": text,
            "format": fmt,
            "masked": not include_secret,
            "capabilities": [model["capability"] for model in models],
        }

    # ------------------------------------------------------------------
    # settings
    # ------------------------------------------------------------------
    def update_settings(self, data: dict[str, Any]) -> dict[str, str]:
        settings = self.store.update_settings(data)
        self.settings = settings
        self.clipboard.set_enabled(settings.get("clipboard_watch") == "1")
        return settings

    def reload_settings(self) -> dict[str, str]:
        settings = self.store.get_settings()
        self.settings = settings
        self.clipboard.set_enabled(settings.get("clipboard_watch") == "1")
        return settings

    def refresh_balances(self) -> dict[str, Any]:
        """Refresh balances for providers that expose an official endpoint."""
        with self._balance_refresh_lock:
            refreshed = 0
            failed: list[dict[str, str]] = []
            for key in self.store.list_keys():
                provider = self.store.get_provider(key["provider"]["id"])
                if not provider.get("balance_adapter"):
                    continue
                try:
                    secret = self.store.reveal_secret_for_snippet(key["id"])
                    balance = fetch_balance(provider, secret)
                    self.store.add_balance(
                        key["id"], balance, record_event=False
                    )
                    refreshed += 1
                except Exception as exc:  # noqa: BLE001
                    failed.append(
                        {
                            "key_id": key["id"],
                            "label": key["label"],
                            "error": str(exc)[:300],
                        }
                    )
            return {"refreshed": refreshed, "failed": failed}

    def check_updates(self, force: bool = False) -> dict[str, Any]:
        now = time.time()
        if (
            not force
            and self._update_cache is not None
            and now - self._update_cache_at < 6 * 3600
        ):
            return self._update_cache
        try:
            result = check_for_update(APP_VERSION)
        except Exception as exc:  # noqa: BLE001
            result = {
                "ok": False,
                "current": APP_VERSION,
                "error": str(exc),
            }
        self._update_cache = result
        self._update_cache_at = now
        return result


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    app: Application

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # Keep the console quiet.  Never log request bodies or query strings.
        return

    def _check_host(self) -> None:
        host = (self.headers.get("Host") or "").split(":")[0].strip("[]").lower()
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ApiError("只允许从本机访问。", 403)

    def _check_api_auth(self) -> None:
        token = self.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(token, self.app.csrf_token):
            raise ApiError("页面会话已失效，请刷新页面后重试。", 403)
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlparse(origin)
            if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise ApiError("不允许跨站请求。", 403)

    def _read_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ApiError("请求长度不正确。") from exc
        if length > MAX_BODY:
            raise ApiError("请求内容过大。", 413)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("请求内容不是有效 JSON。") from exc
        if not isinstance(data, dict):
            raise ApiError("请求内容必须是 JSON 对象。")
        return data

    def _send_json(self, status: int, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def _send_bytes(
        self,
        status: int,
        payload: bytes,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _security_headers(self) -> None:
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )

    # ------------------------------------------------------------------
    # routing
    # ------------------------------------------------------------------
    def do_OPTIONS(self) -> None:  # noqa: N802
        # No CORS headers on purpose: a cross-origin preflight fails.
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            self._check_host()
            if path == "/api/background/image" and method == "GET":
                self._serve_background()
            elif path.startswith("/api/"):
                self._check_api_auth()
                self._handle_api(method, path)
            elif method == "GET":
                self._serve_static(path)
            else:
                raise ApiError("接口不存在。", 404)
        except ApiError as exc:
            self._send_error_json(exc.status, exc.message)
        except (StoreError, SnippetError, BalanceNotSupported, ProviderError) as exc:
            self._send_error_json(400, str(exc))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send_error_json(500, f"本地服务出错了：{exc}")

    # ------------------------------------------------------------------
    # static files
    # ------------------------------------------------------------------
    def _serve_static(self, path: str) -> None:
        if path in {"/", "/index.html"}:
            index_path = self.app.web_dir / "index.html"
            if not index_path.exists():
                raise ApiError("界面文件缺失：web/index.html", 500)
            html = index_path.read_text(encoding="utf-8").replace(
                "__CSRF_TOKEN__", self.app.csrf_token
            )
            payload = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self._security_headers()
            self.end_headers()
            self.wfile.write(payload)
            return

        if path == "/favicon.ico":
            favicon = self.app.web_dir / "favicon.svg"
            if favicon.exists():
                self._serve_file(favicon, "image/svg+xml")
                return
            raise ApiError("文件不存在。", 404)

        if path.startswith("/assets/"):
            relative = path[len("/assets/") :]
            candidate = (self.app.web_dir / relative).resolve()
            web_root = self.app.web_dir.resolve()
            if web_root not in candidate.parents and candidate != web_root:
                raise ApiError("文件不存在。", 404)
            if not candidate.is_file():
                raise ApiError("文件不存在。", 404)
            self._serve_file(candidate)
            return

        raise ApiError("文件不存在。", 404)

    def _serve_background(self) -> None:
        background = self.app.store.get_background()
        if background is None:
            raise ApiError("还没有自定义背景。", 404)
        data, mime = background
        self._send_bytes(200, data, mime)

    def _serve_file(self, path: Path, content_type: str | None = None) -> None:
        mime = content_type or {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".woff2": "font/woff2",
        }.get(path.suffix.lower(), "application/octet-stream")
        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    def _handle_api(self, method: str, path: str) -> None:
        app = self.app

        if method == "GET" and path == "/api/state":
            self._send_json(200, app.state())
            return

        if method == "GET" and path == "/api/health":
            self._send_json(200, {"ok": True, "version": APP_VERSION})
            return

        if method == "POST" and path == "/api/import/parse":
            body = self._read_body()
            self._send_json(200, parse_pasted(body.get("text", "")))
            return

        if method == "POST" and path == "/api/keys":
            body = self._read_body()
            key = app.store.create_key(body)
            self._send_json(201, {"key": key})
            return

        if method == "GET" and path == "/api/keys":
            self._send_json(200, {"keys": app.store.list_keys()})
            return

        match = re.fullmatch(
            r"/api/providers/([A-Za-z0-9_\-]+)/preview-models", path
        )
        if match and method == "POST":
            body = self._read_body()
            provider_id = match.group(1)
            secret = str(body.get("secret") or "").strip()
            if not secret:
                raise ApiError("请先填写 API Key，再从平台刷新模型。")
            provider = app.store.get_provider(provider_id)
            fetched = fetch_models(
                provider, secret, str(body.get("base_url") or "").strip()
            )
            added = app.store.upsert_fetched_models(provider_id, fetched)
            self._send_json(
                200,
                {
                    "models": app.store.list_models(provider_id),
                    "added": len(added),
                },
            )
            return

        match = re.fullmatch(r"/api/providers/([A-Za-z0-9_\-]+)/models", path)
        if match and method == "POST":
            body = self._read_body()
            body["provider_id"] = match.group(1)
            model = app.store.add_model(body)
            self._send_json(201, {"model": model})
            return

        match = re.fullmatch(r"/api/models/([A-Za-z0-9_:\-]+)", path)
        if match:
            if method == "PATCH":
                body = self._read_body()
                model = app.store.update_model(match.group(1), body)
                self._send_json(200, {"model": model})
                return
            if method == "DELETE":
                result = app.store.delete_model(match.group(1))
                self._send_json(200, result)
                return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)", path)
        if match:
            key_id = match.group(1)
            if method == "GET":
                self._send_json(200, {"key": app.store.get_key_public(key_id)})
                return
            if method == "PATCH":
                body = self._read_body()
                key = app.store.update_key(key_id, body)
                self._send_json(200, {"key": key})
                return
            if method == "DELETE":
                result = app.store.delete_key(key_id)
                self._send_json(200, result)
                return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/reveal", path)
        if match and method == "POST":
            key_id = match.group(1)
            secret = app.store.reveal_secret(key_id)
            self._send_json(200, {"secret": secret})
            return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/models", path)
        if match and method == "POST":
            key_id = match.group(1)
            body = self._read_body()
            key = app.store.set_key_models(key_id, body.get("model_ids") or [])
            self._send_json(200, {"key": key})
            return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/fetch-models", path)
        if match and method == "POST":
            key_id = match.group(1)
            raw = app.store.get_key_raw(key_id)
            provider = app.store.get_provider(raw["provider_id"])
            secret = app.store.reveal_secret_for_snippet(key_id)
            fetched = fetch_models(
                provider, secret, raw.get("base_url_override", "")
            )
            added = app.store.upsert_fetched_models(raw["provider_id"], fetched)
            body = self._read_body()
            if body.get("auto_enable", True) and added:
                key_public = app.store.get_key_public(key_id)
                existing = [model["id"] for model in key_public["models"]]
                merged = existing + [model["id"] for model in added if model["id"] not in existing]
                app.store.set_key_models(key_id, merged)
            self._send_json(
                200,
                {
                    "added": added,
                    "count": len(added),
                    "fetched": len(fetched),
                    "key": app.store.get_key_public(key_id),
                },
            )
            return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/fetch-balance", path)
        if match and method == "POST":
            key_id = match.group(1)
            raw = app.store.get_key_raw(key_id)
            provider = app.store.get_provider(raw["provider_id"])
            secret = app.store.reveal_secret_for_snippet(key_id)
            balance = fetch_balance(provider, secret)
            saved = app.store.add_balance(key_id, balance)
            self._send_json(
                200,
                {
                    "balance": saved,
                    "key": app.store.get_key_public(key_id),
                },
            )
            return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/balance", path)
        if match and method == "POST":
            key_id = match.group(1)
            body = self._read_body()
            body["source"] = "manual"
            balance = app.store.add_balance(key_id, body)
            self._send_json(200, {"balance": balance})
            return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/balance-history", path)
        if match and method == "GET":
            key_id = match.group(1)
            self._send_json(
                200, {"history": app.store.balance_history(key_id, limit=50)}
            )
            return

        match = re.fullmatch(r"/api/keys/([A-Za-z0-9_\-]+)/copied", path)
        if match and method == "POST":
            key_id = match.group(1)
            body = self._read_body()
            app.store.mark_copied(
                key_id,
                body.get("model_ids") or [],
                (body.get("capability") or "").strip(),
                (body.get("format") or "env").strip(),
            )
            self._send_json(200, {"ok": True})
            return

        if method == "POST" and path == "/api/snippets":
            body = self._read_body()
            self._send_json(200, app.build_snippet(body))
            return

        if method == "GET" and path == "/api/settings":
            self._send_json(200, {"settings": app.store.get_settings()})
            return

        if method == "PATCH" and path == "/api/settings":
            body = self._read_body()
            settings = app.update_settings(body)
            self._send_json(200, {"settings": settings})
            return

        if method == "GET" and path == "/api/clipboard/pending":
            self._send_json(200, {"pending": app.pending_list()})
            return

        match = re.fullmatch(r"/api/clipboard/([A-Za-z0-9_\-]+)/accept", path)
        if match and method == "POST":
            draft = app.accept_pending(match.group(1))
            self._send_json(200, {"draft": draft})
            return

        match = re.fullmatch(r"/api/clipboard/([A-Za-z0-9_\-]+)/dismiss", path)
        if match and method == "POST":
            app.dismiss_pending(match.group(1))
            self._send_json(200, {"ok": True})
            return

        if method == "POST" and path == "/api/backup/restore":
            body = self._read_body()
            data_url = str(body.get("data_url") or "")
            match = re.match(
                r"^data:[^,]*;base64,([A-Za-z0-9+/=\s]+)$", data_url, re.S
            )
            if not match:
                raise ApiError("请选择有效的数据库备份文件。")
            try:
                raw = base64.b64decode(
                    re.sub(r"\s+", "", match.group(1)), validate=True
                )
            except (binascii.Error, ValueError) as exc:
                raise ApiError("备份文件损坏，无法读取。") from exc
            safety_path = app.store.restore_backup(raw)
            app.reload_settings()
            self._send_json(
                200,
                {
                    "ok": True,
                    "backup_path": safety_path,
                },
            )
            return

        if method == "GET" and path == "/api/backup":
            payload = app.store.backup_bytes()
            self._send_bytes(
                200,
                payload,
                "application/octet-stream",
                {
                    "Content-Disposition": 'attachment; filename="api-key-ledger-backup.db"'
                },
            )
            return

        if method == "GET" and path == "/api/export":
            self._send_json(200, app.store.export_json())
            return

        if method == "POST" and path == "/api/background/upload":
            body = self._read_body()
            data_url = str(body.get("data_url") or "").strip()
            match = BACKGROUND_DATA_URL.fullmatch(data_url)
            if not match:
                raise ApiError("只支持 PNG、JPEG 或 WebP 图片。")
            mime = match.group(1)
            try:
                raw = base64.b64decode(
                    re.sub(r"\s+", "", match.group(2)), validate=True
                )
            except (binascii.Error, ValueError) as exc:
                raise ApiError("图片数据损坏，请重新选择。") from exc
            if len(raw) > MAX_BACKGROUND_BYTES:
                raise ApiError("背景图片不能超过 6 MB。", 413)
            expected = {
                "image/png": b"\x89PNG\r\n\x1a\n",
                "image/jpeg": b"\xff\xd8\xff",
                "image/webp": b"RIFF",
            }[mime]
            if not raw.startswith(expected):
                raise ApiError("图片格式与内容不匹配。")
            version = app.store.save_background(raw, mime)
            self._send_json(
                200,
                {"ok": True, "style": "custom", "version": version},
            )
            return

        if method == "POST" and path == "/api/balances/refresh":
            self._send_json(200, app.refresh_balances())
            return

        if method == "POST" and path == "/api/update/check":
            body = self._read_body()
            self._send_json(200, app.check_updates(force=bool(body.get("force"))))
            return

        if method == "POST" and path == "/api/open-url":
            body = self._read_body()
            target = str(body.get("url") or "").strip()
            parsed = urlparse(target)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "github.com"
                or not parsed.path.startswith(f"/{GITHUB_REPO}/releases")
            ):
                raise ApiError("只允许打开本项目的 GitHub Release 页面。")
            webbrowser.open(target)
            self._send_json(200, {"ok": True})
            return

        if method == "POST" and path == "/api/open-data-dir":
            if sys.platform == "win32":
                os.startfile(str(app.data_dir))  # noqa: S606 - user-triggered local action
                self._send_json(200, {"ok": True})
            else:
                raise ApiError("当前系统不支持直接打开文件夹。", 400)
            return

        raise ApiError("接口不存在。", 404)


def _build_handler(app: Application) -> type[Handler]:
    class BoundHandler(Handler):
        pass

    BoundHandler.app = app
    return BoundHandler


def _find_server(host: str, start_port: int, handler: type[Handler]) -> ThreadingHTTPServer:
    last_error: Exception | None = None
    for port in range(start_port, start_port + 20):
        try:
            server = ThreadingHTTPServer((host, port), handler)
            server.daemon_threads = True
            server.allow_reuse_address = True
            return server
        except OSError as exc:
            last_error = exc
            continue
    raise RuntimeError(f"找不到可用端口（从 {start_port} 开始尝试）。") from last_error


class RunningServer:
    def __init__(
        self,
        app: Application,
        server: ThreadingHTTPServer,
        thread: threading.Thread,
        url: str,
        db_path: Path,
    ):
        self.app = app
        self.server = server
        self.thread = thread
        self.url = url
        self.db_path = db_path
        self._stopped = False

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            self.app.stop()
        finally:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)


def start_server(
    base_dir: Path,
    db_path: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    web_dir: Path | None = None,
    native: bool = False,
) -> RunningServer:
    """Start the local server in a background thread and return a handle."""
    app = Application(base_dir, db_path, web_dir=web_dir, native=native)
    handler = _build_handler(app)
    server = _find_server(host, port, handler)
    actual_port = server.server_address[1]
    app.port = actual_port
    url = f"http://{host}:{actual_port}/"
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.5},
        name="api-key-ledger-http",
        daemon=True,
    )
    thread.start()
    return RunningServer(app, server, thread, url, Path(db_path))


def run_server(
    base_dir: Path,
    db_path: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    web_dir: Path | None = None,
) -> None:
    running = start_server(
        base_dir=base_dir,
        db_path=db_path,
        host=host,
        port=port,
        web_dir=web_dir,
    )
    print(f"\n{APP_NAME} 已启动：{running.url}")
    print(f"数据文件：{db_path}")
    print(f"剪贴板监听：{'开启' if running.app.clipboard.enabled else '关闭'}")
    print("按 Ctrl+C 停止。\n")

    if open_browser:
        threading.Timer(0.7, lambda: webbrowser.open(running.url)).start()

    try:
        running.thread.join()
    except KeyboardInterrupt:
        print("\n正在停止…")
    finally:
        running.stop()
