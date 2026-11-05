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


def _local_vault_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    root = Path(local) if local else Path.home() / "AppData" / "Local"
    return root / "ApiKeyLedger" / "data"


def _default_data_dir() -> Path:
    if _is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        # Installed builds (including folder installs) keep data outside the
        # program folder so upgrades/uninstalls cannot remove it.
        if _is_onefile() or (exe_dir / "installed.marker").exists():
            return _local_vault_dir()
        return exe_dir / "data"
    return Path(__file__).resolve().parent / "data"


def _data_dir(app_dir: Path) -> tuple[Path, str]:
    """Resolve the data directory: env var -> config file -> default."""
    from core.config import resolve_data_dir

    return resolve_data_dir(app_dir, _default_data_dir())


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
    data_dir, data_source = _data_dir(app_dir)

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
    _setup_logging(db_path.parent)
    # --db pins the database explicitly, so the in-app data-dir setting must
    # stay disabled to avoid a setting that silently has no effect.
    from core.config import config_file as _config_file

    config_path = None if args.db else _config_file(app_dir)
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
                config_file=config_path,
                data_dir_source=data_source,
            )
        else:
            from core.server import run_server

            run_server(
                base_dir=app_dir,
                db_path=db_path,
                web_dir=web_dir,
                port=port,
                open_browser=not args.no_browser,
                config_file=config_path,
                data_dir_source=data_source,
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
