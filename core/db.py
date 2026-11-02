"""SQLite schema and bootstrap helpers."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .catalog import PROVIDERS
from .utils import utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '#64748b',
    docs_url TEXT NOT NULL DEFAULT '',
    default_base_url TEXT NOT NULL DEFAULT '',
    auth_style TEXT NOT NULL DEFAULT 'bearer',
    balance_adapter TEXT NOT NULL DEFAULT '',
    model_fetch TEXT NOT NULL DEFAULT 'openai',
    models_url TEXT NOT NULL DEFAULT '',
    env_prefix TEXT NOT NULL DEFAULT 'API',
    description TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_custom INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES providers(id),
    label TEXT NOT NULL,
    secret_enc TEXT NOT NULL,
    secret_hint TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    env_prefix TEXT NOT NULL,
    project TEXT NOT NULL DEFAULT '',
    environment TEXT NOT NULL DEFAULT '开发',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_copied_at TEXT,
    last_used_at TEXT,
    base_url_override TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_fingerprint
    ON api_keys(fingerprint);

CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    capabilities TEXT NOT NULL DEFAULT '["chat"]',
    api_style TEXT NOT NULL DEFAULT 'openai_chat',
    base_url TEXT NOT NULL DEFAULT '',
    context_window INTEGER,
    pricing TEXT NOT NULL DEFAULT '{}',
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'catalog',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(provider_id, model_id)
);

CREATE TABLE IF NOT EXISTS key_models (
    key_id TEXT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (key_id, model_id)
);

CREATE TABLE IF NOT EXISTS balance_snapshots (
    id TEXT PRIMARY KEY,
    key_id TEXT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    amount REAL,
    currency TEXT NOT NULL DEFAULT 'CNY',
    quota_total REAL,
    quota_used REAL,
    quota_remaining REAL,
    quota_unit TEXT NOT NULL DEFAULT '',
    expires_at TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    note TEXT NOT NULL DEFAULT '',
    raw TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_balance_key_time
    ON balance_snapshots(key_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    key_id TEXT REFERENCES api_keys(id) ON DELETE CASCADE,
    model_id TEXT,
    capability TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_time
    ON usage_events(created_at DESC);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_SETTINGS = {
    "clipboard_watch": "1",
    "low_balance_threshold": "20",
    "low_balance_currency": "CNY",
    "default_format": "env",
    "include_comments": "0",
    "direct_key": "0",
}


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: Path) -> None:
    now = utc_now()
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '1')"
        )
        for provider in PROVIDERS:
            conn.execute(
                """
                INSERT OR IGNORE INTO providers (
                    id, name, short_name, color, docs_url, default_base_url,
                    auth_style, balance_adapter, model_fetch, models_url,
                    env_prefix, description, sort_order, is_custom
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider["id"],
                    provider["name"],
                    provider.get("short_name", ""),
                    provider.get("color", "#64748b"),
                    provider.get("docs_url", ""),
                    provider.get("default_base_url", ""),
                    provider.get("auth_style", "bearer"),
                    provider.get("balance_adapter", ""),
                    provider.get("model_fetch", "openai"),
                    provider.get("models_url", ""),
                    provider.get("env_prefix", "API"),
                    provider.get("description", ""),
                    provider.get("sort_order", 0),
                    provider.get("is_custom", 0),
                ),
            )
            for model in provider.get("models", []):
                model_db_id = f"{provider['id']}:{model['model_id']}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO models (
                        id, provider_id, model_id, display_name, capabilities,
                        api_style, base_url, context_window, pricing, notes,
                        source, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'catalog', 1, ?, ?)
                    """,
                    (
                        model_db_id,
                        provider["id"],
                        model["model_id"],
                        model.get("display_name", model["model_id"]),
                        json.dumps(model.get("capabilities", ["chat"]), ensure_ascii=False),
                        model.get("api_style", "openai_chat"),
                        model.get("base_url", ""),
                        model.get("context_window"),
                        json.dumps(model.get("pricing", {}), ensure_ascii=False),
                        model.get("notes", ""),
                        now,
                        now,
                    ),
                )

        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, value),
            )
        conn.commit()


def month_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")
