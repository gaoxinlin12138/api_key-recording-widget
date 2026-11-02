"""Optional native desktop window powered by pywebview.

The browser UI is still served by the local HTTP server.  pywebview only wraps
it in a WebView2 window so the packaged app does not need to open a browser.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import webview

from .server import APP_NAME, start_server

logger = logging.getLogger(__name__)


class DesktopApi:
    def __init__(self) -> None:
        # Keep these private.  pywebview exposes public attributes of js_api,
        # and a Window/HTTPServer reference must never be introspected.
        self._window: Any = None
        self._running: Any = None

    def close_app(self) -> bool:
        """Called from the settings page via window.pywebview.api."""
        if self._window is not None:
            self._window.destroy()
        return True

    def save_backup(self) -> str:
        """Save the encrypted SQLite backup through a native save dialog."""
        if self._running is None:
            return ""
        return self._save(
            "api-key-ledger-backup.db",
            self._running.app.store.backup_bytes(),
        )

    def save_export(self) -> str:
        """Save a JSON export without secrets through a native save dialog."""
        if self._running is None:
            return ""
        payload = json.dumps(
            self._running.app.store.export_json(),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        return self._save("api-key-ledger-export.json", payload)

    def _save(self, filename: str, payload: bytes) -> str:
        if self._window is None:
            return ""
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=filename,
        )
        if not result:
            return ""
        target = result[0] if isinstance(result, (list, tuple)) else result
        Path(target).write_bytes(payload)
        return str(target)


def run_desktop(
    base_dir: Path,
    db_path: Path,
    web_dir: Path,
    port: int = 8765,
) -> None:
    running = start_server(
        base_dir=base_dir,
        db_path=db_path,
        web_dir=web_dir,
        port=port,
        native=True,
    )
    api = DesktopApi()
    api._running = running
    window = webview.create_window(
        APP_NAME,
        running.url,
        width=1280,
        height=860,
        min_size=(1000, 680),
        background_color="#f3f1ea",
        js_api=api,
        text_select=True,
    )
    api._window = window
    try:
        webview.start()
    finally:
        running.stop()
        logger.info("Desktop window closed; server stopped")
