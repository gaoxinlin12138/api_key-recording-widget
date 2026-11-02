"""Start the local API Key Ledger.

Source mode:
    python app.py                 # default browser
    python app.py --native        # desktop window (requires pywebview)
    python app.py --no-browser    # server only

Frozen mode:
    API钥匙簿.exe                 # desktop window by default
    API钥匙簿.exe --browser       # open the default browser instead
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _app_dir() -> Path:
    """Directory containing the exe/source entry point."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _resource_dir() -> Path:
    """Directory containing bundled web assets."""
    if _is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _is_onefile() -> bool:
    """True for a PyInstaller onefile build (it runs from a temp folder)."""
    if not _is_frozen():
        return False
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return False
    return Path(meipass).resolve().parent != Path(sys.executable).resolve().parent


def _data_dir() -> Path:
    override = os.environ.get("API_KEY_LEDGER_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if _is_frozen():
        if _is_onefile():
            # A onefile exe can be moved on its own; keep the vault outside it.
            local = os.environ.get("LOCALAPPDATA")
            root = Path(local) if local else Path.home() / "AppData" / "Local"
            return root / "ApiKeyLedger" / "data"
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parent / "data"


def _setup_logging(data_dir: Path) -> None:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(data_dir / "app.log"),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            encoding="utf-8",
        )
    except OSError:
        # A read-only folder should not prevent the app from starting.
        pass


def main() -> None:
    app_dir = _app_dir()
    resource_dir = _resource_dir()
    data_dir = _data_dir()
    _setup_logging(data_dir)

    from core.version import __version__

    parser = argparse.ArgumentParser(description="API 钥匙簿 · 本地 API Key 台账")
    parser.add_argument(
        "--version", action="version", version=f"API 钥匙簿 {__version__}"
    )
    parser.add_argument("--port", type=int, default=8765, help="起始端口，默认 8765")
    parser.add_argument(
        "--no-browser", action="store_true", help="启动后不自动打开浏览器"
    )
    parser.add_argument(
        "--browser", action="store_true", help="强制使用默认浏览器界面"
    )
    parser.add_argument(
        "--native", action="store_true", help="强制使用独立桌面窗口"
    )
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite 数据库路径",
    )
    args = parser.parse_args()

    port = max(1024, min(args.port, 65535))
    db_path = Path(args.db) if args.db else data_dir / "ledger.db"
    web_dir = resource_dir / "web"
    native = args.native or (_is_frozen() and not args.browser)
    if args.browser:
        native = False

    try:
        if native:
            from core.desktop import run_desktop

            run_desktop(
                base_dir=app_dir,
                db_path=db_path,
                web_dir=web_dir,
                port=port,
            )
        else:
            from core.server import run_server

            run_server(
                base_dir=app_dir,
                db_path=db_path,
                web_dir=web_dir,
                port=port,
                open_browser=not args.no_browser,
            )
    except Exception:
        logging.exception("Application failed to start")
        if _is_frozen():
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"API 钥匙簿启动失败。\n\n详细错误已写入：\n{data_dir / 'app.log'}",
                    "API 钥匙簿",
                    0x10,
                )
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
