"""Per-program configuration file (currently only the data directory).

The app needs to know where the database lives *before* it opens the database,
so this setting cannot live inside the database.  The file sits next to the
program:

- installed build -> ``%LOCALAPPDATA%\\Programs\\ApiKeyLedger\\ledger.config.json``
- portable build  -> ``<exe folder>\\ledger.config.json``
- source checkout -> ``<repo>\\ledger.config.json`` (git-ignored)

Resolution order for the data directory:
    1. ``API_KEY_LEDGER_DATA_DIR`` environment variable
    2. ``data_dir`` in the config file
    3. the normal default (LOCALAPPDATA for installed, ``./data`` otherwise)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "ledger.config.json"
ENV_VAR = "API_KEY_LEDGER_DATA_DIR"


def config_file(app_dir: Path) -> Path:
    return Path(app_dir) / CONFIG_FILENAME


def _read(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_data_dir(app_dir: Path) -> Path | None:
    """Return the configured data directory, or None when not configured."""
    value = _read(config_file(app_dir)).get("data_dir")
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser()


def write_data_dir(app_dir: Path, data_dir: Path) -> None:
    path = config_file(app_dir)
    data = _read(path)
    data["data_dir"] = str(Path(data_dir))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def clear_data_dir(app_dir: Path) -> None:
    path = config_file(app_dir)
    if not path.exists():
        return
    data = _read(path)
    data.pop("data_dir", None)
    if data:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    else:
        path.unlink(missing_ok=True)


def resolve_data_dir(
    app_dir: Path,
    default_dir: Path,
    env: dict[str, str] | None = None,
) -> tuple[Path, str]:
    """Return (data_dir, source) where source is 'env' | 'config' | 'default'."""
    environ = os.environ if env is None else env
    override = environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser(), "env"
    configured = read_data_dir(app_dir)
    if configured is not None:
        return configured, "config"
    return Path(default_dir), "default"


def is_usable_dir(path: Path) -> bool:
    """True when the directory exists (or can be created) and is writable."""
    target = Path(path)
    anchor = target.anchor
    if anchor:
        # 盘符/UNC 根不存在时，mkdir 也会失败；先给出更快的判断
        if not Path(anchor).exists():
            return False
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-probe"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError:
        return False
    return True


def resolve_data_dir_safe(
    app_dir: Path,
    default_dir: Path,
    env: dict[str, str] | None = None,
) -> tuple[Path, str, str | None]:
    """Like resolve_data_dir, but never returns an unusable directory.

    Returns ``(data_dir, source, fallback_from)``.  When the configured or
    environment directory cannot be used (removed USB drive, deleted folder,
    disconnected network share), it falls back to the default directory and
    reports the rejected path in ``fallback_from`` so the UI can explain it.
    """
    resolved, source = resolve_data_dir(app_dir, default_dir, env)
    if source == "default":
        return resolved, source, None
    if is_usable_dir(resolved):
        return resolved, source, None
    return Path(default_dir), "default", str(resolved)
