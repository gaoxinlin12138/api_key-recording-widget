"""Optional native desktop window powered by pywebview.

The browser UI is still served by the local HTTP server.  pywebview only wraps
it in a WebView2 window so the packaged app does not need to open a browser.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
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
        self._maximized = False

    def close_app(self) -> bool:
        """Called from the settings page via window.pywebview.api."""
        if self._window is not None:
            self._window.destroy()
        return True

    def minimize_window(self) -> bool:
        if self._window is not None:
            self._window.minimize()
        return True

    def toggle_maximize(self) -> bool:
        if self._window is not None:
            if self._maximized:
                self._window.restore()
                self._maximized = False
            else:
                self._window.maximize()
                self._maximized = True
        return True

    def focus_window(self) -> bool:
        """Bring the running desktop window to the foreground."""
        if self._window is None:
            return False
        try:
            self._window.show()
            self._window.restore()
            self._window.on_top = True
            threading.Timer(1.2, self._release_top).start()
        except Exception:  # noqa: BLE001
            logger.exception("Could not raise the desktop window")
            return False
        if sys.platform == "win32":
            try:
                import ctypes

                native = getattr(self._window, "native", None)
                if native is not None and hasattr(native, "Handle"):
                    hwnd = int(native.Handle.ToInt32())
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:  # noqa: BLE001
                logger.debug("SetForegroundWindow failed", exc_info=True)
        return True

    def _release_top(self) -> None:
        try:
            if self._window is not None:
                self._window.on_top = False
        except Exception:  # noqa: BLE001
            pass

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

    def pick_folder(self) -> str:
        """Let the user choose a folder (used by the data-directory setting)."""
        if self._window is None:
            return ""
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return ""
        return str(result[0] if isinstance(result, (list, tuple)) else result)


def run_desktop(
    base_dir: Path,
    db_path: Path,
    web_dir: Path,
    port: int = 8765,
    config_file: Path | None = None,
    data_dir_source: str = "default",
) -> None:
    running = start_server(
        base_dir=base_dir,
        db_path=db_path,
        web_dir=web_dir,
        port=port,
        native=True,
        config_file=config_file,
        data_dir_source=data_dir_source,
    )
    api = DesktopApi()
    api._running = running
    window = webview.create_window(
        APP_NAME,
        running.url,
        width=1060,
        height=700,
        min_size=(940, 620),
        background_color="#e9f3ee",
        js_api=api,
        text_select=True,
        frameless=True,
        easy_drag=False,
    )
    api._window = window
    try:
        webview.start()
    finally:
        running.stop()
        logger.info("Desktop window closed; server stopped")
