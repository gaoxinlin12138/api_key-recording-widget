"""Persistence and business rules for keys, models, balances and usage."""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from .db import connect, init_db, month_prefix
from .security import unprotect
from .snippets import SUPPORTED_FORMATS, supported_formats
from .utils import (
    as_float,
    fingerprint,
    mask_secret,
    new_id,
    normalize_base_url,
    sanitize_env_prefix,
    utc_now,
)

ALLOWED_FORMATS = {"env", "python", "curl", "js"}
ALLOWED_CAPABILITIES = {"chat", "vision", "embedding", "rerank", "image", "audio"}
ALLOWED_STYLES = set(SUPPORTED_FORMATS)


class StoreError(ValueError):
    pass


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._write_lock = threading.RLock()
        init_db(self.db_path)
        self._migrate_plaintext()

    def _migrate_plaintext(self) -> None:
        """Convert a legacy DPAPI database to portable plaintext storage."""
        with self._write_lock, connect(self.db_path) as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()
            }
            if "secret_enc" not in columns:
                return
            if "secret" in columns:
                return
            stamp = time.strftime("%Y%m%d-%H%M%S")
            safety = self.db_path.with_name(f"ledger.before-plaintext-{stamp}.db")
            safety.write_bytes(self.backup_bytes())
            try:
                conn.execute("ALTER TABLE api_keys RENAME COLUMN secret_enc TO secret")
                rows = conn.execute("SELECT id, secret FROM api_keys").fetchall()
                for row in rows:
                    plaintext = unprotect(row["secret"])
                    conn.execute(
                        "UPDATE api_keys SET secret=? WHERE id=?",
                        (plaintext, row["id"]),
                    )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                raise StoreError(
                    f"无法迁移旧加密数据。原库已备份到：{safety}"
                ) from exc

    # ------------------------------------------------------------------
    # providers and models
    # ------------------------------------------------------------------
    def list_providers(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM providers ORDER BY sort_order, name"
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["key_count"] = conn.execute(
                    "SELECT COUNT(*) FROM api_keys WHERE provider_id=?", (row["id"],)
                ).fetchone()[0]
                item["model_count"] = conn.execute(
                    "SELECT COUNT(*) FROM models WHERE provider_id=? AND enabled=1",
                    (row["id"],),
                ).fetchone()[0]
                result.append(item)
            return result

    def get_provider(self, provider_id: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM providers WHERE id=?", (provider_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"平台不存在：{provider_id}")
            return dict(row)

    def list_models(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM models WHERE enabled=1"
        params: list[Any] = []
        if provider_id:
            query += " AND provider_id=?"
            params.append(provider_id)
        query += " ORDER BY provider_id, api_style, model_id"
        with connect(self.db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._public_model(row) for row in rows]

    def get_model(self, model_id: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
            if row is None:
                raise StoreError(f"模型不存在：{model_id}")
            return self._public_model(row)

    def add_model(self, data: dict[str, Any]) -> dict[str, Any]:
        provider_id = (data.get("provider_id") or "").strip()
        self.get_provider(provider_id)
        model_id = (data.get("model_id") or "").strip()
        if not model_id:
            raise StoreError("模型 ID 不能为空。")
        capabilities = self._clean_capabilities(data.get("capabilities"))
        style = (data.get("api_style") or "openai_chat").strip()
        if style not in ALLOWED_STYLES:
            raise StoreError(f"不支持的调用方式：{style}")
        display_name = (data.get("display_name") or model_id).strip()
        base_url = normalize_base_url(data.get("base_url"))
        now = utc_now()
        db_id = f"{provider_id}:{model_id}"
        with self._write_lock, connect(self.db_path) as conn:
            existing = conn.execute("SELECT id FROM models WHERE id=?", (db_id,)).fetchone()
            if existing:
                raise StoreError(f"模型 {model_id} 已存在，可以直接编辑它。")
            conn.execute(
                """
                INSERT INTO models (
                    id, provider_id, model_id, display_name, capabilities,
                    api_style, base_url, context_window, pricing, notes,
                    source, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, 'manual', 1, ?, ?)
                """,
                (
                    db_id,
                    provider_id,
                    model_id,
                    display_name,
                    json.dumps(capabilities, ensure_ascii=False),
                    style,
                    base_url,
                    data.get("context_window") or None,
                    (data.get("notes") or "").strip(),
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM models WHERE id=?", (db_id,)).fetchone()
            return self._public_model(row)

    def update_model(self, model_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._write_lock, connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
            if row is None:
                raise StoreError(f"模型不存在：{model_id}")
            fields: dict[str, Any] = {}
            if "display_name" in data:
                fields["display_name"] = (data.get("display_name") or "").strip() or row["model_id"]
            if "capabilities" in data:
                fields["capabilities"] = json.dumps(
                    self._clean_capabilities(data.get("capabilities")), ensure_ascii=False
                )
            if "api_style" in data:
                style = (data.get("api_style") or "").strip()
                if style not in ALLOWED_STYLES:
                    raise StoreError(f"不支持的调用方式：{style}")
                fields["api_style"] = style
            if "base_url" in data:
                fields["base_url"] = normalize_base_url(data.get("base_url"))
            if "context_window" in data:
                value = data.get("context_window")
                fields["context_window"] = int(value) if value not in (None, "") else None
            if "notes" in data:
                fields["notes"] = (data.get("notes") or "").strip()
            if "enabled" in data:
                fields["enabled"] = 1 if data.get("enabled") else 0
            if not fields:
                return self._public_model(row)
            fields["updated_at"] = utc_now()
            assignments = ", ".join(f"{key}=?" for key in fields)
            conn.execute(
                f"UPDATE models SET {assignments} WHERE id=?",
                [*fields.values(), model_id],
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
            return self._public_model(updated)

    def delete_model(self, model_id: str) -> dict[str, Any]:
        with self._write_lock, connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
            if row is None:
                raise StoreError(f"模型不存在：{model_id}")
            if row["source"] == "catalog":
                # Keep the catalogue row but hide it.  This survives restarts
                # because database seeding never overwrites existing rows.
                conn.execute(
                    "UPDATE models SET enabled=0, updated_at=? WHERE id=?",
                    (utc_now(), model_id),
                )
                conn.commit()
                return {"disabled": True, "id": model_id}
            conn.execute("DELETE FROM models WHERE id=?", (model_id,))
            conn.commit()
            return {"deleted": True, "id": model_id}

    def upsert_fetched_models(
        self, provider_id: str, fetched: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        provider = self.get_provider(provider_id)
        now = utc_now()
        added: list[dict[str, Any]] = []
        with self._write_lock, connect(self.db_path) as conn:
            for item in fetched:
                model_id = (item.get("model_id") or "").strip()
                if not model_id:
                    continue
                db_id = f"{provider_id}:{model_id}"
                existing = conn.execute(
                    "SELECT * FROM models WHERE id=?", (db_id,)
                ).fetchone()
                if existing:
                    continue
                capabilities = self._clean_capabilities(item.get("capabilities"))
                style = self._guess_style(provider_id, model_id, capabilities)
                display_name = (item.get("display_name") or model_id).strip()
                conn.execute(
                    """
                    INSERT INTO models (
                        id, provider_id, model_id, display_name, capabilities,
                        api_style, base_url, context_window, pricing, notes,
                        source, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, 'fetched', 1, ?, ?)
                    """,
                    (
                        db_id,
                        provider_id,
                        model_id,
                        display_name,
                        json.dumps(capabilities, ensure_ascii=False),
                        style,
                        normalize_base_url(item.get("base_url") or ""),
                        item.get("context_window"),
                        "从平台接口自动拉取，请确认调用方式与能力。",
                        now,
                        now,
                    ),
                )
                added.append(
                    self._public_model(
                        conn.execute("SELECT * FROM models WHERE id=?", (db_id,)).fetchone()
                    )
                )
            conn.commit()
        return added

    # ------------------------------------------------------------------
    # keys
    # ------------------------------------------------------------------
    def list_keys(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT k.*, p.name AS provider_name, p.short_name AS provider_short,
                       p.color AS provider_color, p.docs_url AS provider_docs,
                       p.default_base_url AS provider_base, p.is_custom AS provider_custom
                FROM api_keys k
                JOIN providers p ON p.id = k.provider_id
                ORDER BY k.created_at DESC
                """
            ).fetchall()
            return [self._hydrate_key(conn, row) for row in rows]

    def get_key_public(self, key_id: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT k.*, p.name AS provider_name, p.short_name AS provider_short,
                       p.color AS provider_color, p.docs_url AS provider_docs,
                       p.default_base_url AS provider_base, p.is_custom AS provider_custom
                FROM api_keys k
                JOIN providers p ON p.id = k.provider_id
                WHERE k.id=?
                """,
                (key_id,),
            ).fetchone()
            if row is None:
                raise StoreError("这个 Key 不存在，可能已经被删除。")
            return self._hydrate_key(conn, row)

    def has_fingerprint(self, value: str) -> bool:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM api_keys WHERE fingerprint=? LIMIT 1",
                (fingerprint(value),),
            ).fetchone()
            return row is not None

    def get_key_raw(self, key_id: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT k.*, p.name AS provider_name, p.short_name AS provider_short,
                       p.color AS provider_color, p.docs_url AS provider_docs,
                       p.default_base_url AS provider_base, p.is_custom AS provider_custom
                FROM api_keys k
                JOIN providers p ON p.id = k.provider_id
                WHERE k.id=?
                """,
                (key_id,),
            ).fetchone()
            if row is None:
                raise StoreError("这个 Key 不存在，可能已经被删除。")
            return dict(row)

    def create_key(self, data: dict[str, Any]) -> dict[str, Any]:
        provider_id = (data.get("provider_id") or "").strip()
        provider = self.get_provider(provider_id)
        secret = (data.get("secret") or "").strip()
        if not secret:
            raise StoreError("API Key 不能为空。")
        label = (data.get("label") or "").strip() or f"{provider['name']} Key"
        env_prefix = sanitize_env_prefix(
            data.get("env_prefix") or provider.get("env_prefix", "API"),
            fallback=provider.get("env_prefix", "API"),
        )
        fp = fingerprint(secret)
        now = utc_now()
        key_id = new_id("key_")
        base_override = normalize_base_url(data.get("base_url_override"))
        with self._write_lock, connect(self.db_path) as conn:
            duplicate = conn.execute(
                "SELECT id, label FROM api_keys WHERE fingerprint=?", (fp,)
            ).fetchone()
            if duplicate:
                raise StoreError(f"这个 Key 已经录入过了：{duplicate['label']}。")
            conn.execute(
                """
                INSERT INTO api_keys (
                    id, provider_id, label, secret, secret_hint, fingerprint,
                    env_prefix, project, environment, note, status, expires_at,
                    created_at, updated_at, base_url_override
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    key_id,
                    provider_id,
                    label,
                    secret,
                    mask_secret(secret),
                    fp,
                    env_prefix,
                    (data.get("project") or "").strip(),
                    (data.get("environment") or "开发").strip(),
                    (data.get("note") or "").strip(),
                    (data.get("expires_at") or "").strip() or None,
                    now,
                    now,
                    base_override,
                ),
            )
            if "model_ids" in data:
                self._set_key_models(conn, key_id, provider_id, data.get("model_ids") or [])
            else:
                # A new key gets all of the provider's catalogue models by
                # default; the user can uncheck them in the model manager.
                rows = conn.execute(
                    "SELECT id FROM models WHERE provider_id=? AND enabled=1",
                    (provider_id,),
                ).fetchall()
                self._set_key_models(conn, key_id, provider_id, [r["id"] for r in rows])
            self._add_usage(conn, key_id, None, "", "created", "录入 Key")
            conn.commit()
            return self.get_key_public(key_id)

    def update_key(self, key_id: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._write_lock, connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM api_keys WHERE id=?", (key_id,)).fetchone()
            if row is None:
                raise StoreError("这个 Key 不存在，可能已经被删除。")
            fields: dict[str, Any] = {}
            for field in ("label", "project", "environment", "note", "status", "expires_at"):
                if field in data:
                    value = data.get(field)
                    if field == "label":
                        value = (value or "").strip()
                        if not value:
                            raise StoreError("名称不能为空。")
                    elif field == "expires_at":
                        value = (value or "").strip() or None
                    else:
                        value = (value or "").strip()
                    fields[field] = value
            if "env_prefix" in data:
                fields["env_prefix"] = sanitize_env_prefix(
                    data.get("env_prefix"), fallback=row["env_prefix"]
                )
            if "base_url_override" in data:
                fields["base_url_override"] = normalize_base_url(
                    data.get("base_url_override")
                )
            if data.get("secret"):
                secret = data["secret"].strip()
                fp = fingerprint(secret)
                duplicate = conn.execute(
                    "SELECT id, label FROM api_keys WHERE fingerprint=? AND id<>?",
                    (fp, key_id),
                ).fetchone()
                if duplicate:
                    raise StoreError(f"这个 Key 已经录入过了：{duplicate['label']}。")
                fields["secret"] = secret
                fields["secret_hint"] = mask_secret(secret)
                fields["fingerprint"] = fp
            if fields:
                fields["updated_at"] = utc_now()
                assignments = ", ".join(f"{key}=?" for key in fields)
                conn.execute(
                    f"UPDATE api_keys SET {assignments} WHERE id=?",
                    [*fields.values(), key_id],
                )
            if "model_ids" in data:
                self._set_key_models(
                    conn, key_id, row["provider_id"], data.get("model_ids") or []
                )
            conn.commit()
            return self.get_key_public(key_id)

    def delete_key(self, key_id: str) -> dict[str, Any]:
        with self._write_lock, connect(self.db_path) as conn:
            row = conn.execute("SELECT label FROM api_keys WHERE id=?", (key_id,)).fetchone()
            if row is None:
                raise StoreError("这个 Key 不存在，可能已经被删除。")
            conn.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
            conn.commit()
            return {"deleted": True, "label": row["label"]}

    def reveal_secret(self, key_id: str) -> str:
        row = self.get_key_raw(key_id)
        secret = row["secret"]
        with self._write_lock, connect(self.db_path) as conn:
            self._add_usage(conn, key_id, None, "", "reveal", "查看 Key")
            conn.commit()
        return secret

    def reveal_secret_for_snippet(self, key_id: str) -> str:
        """Read the plaintext secret without writing a reveal audit row."""
        return self.get_key_raw(key_id)["secret"]

    def set_key_models(self, key_id: str, model_ids: list[str]) -> dict[str, Any]:
        with self._write_lock, connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT provider_id FROM api_keys WHERE id=?", (key_id,)
            ).fetchone()
            if row is None:
                raise StoreError("这个 Key 不存在，可能已经被删除。")
            self._set_key_models(conn, key_id, row["provider_id"], model_ids)
            conn.execute(
                "UPDATE api_keys SET updated_at=? WHERE id=?", (utc_now(), key_id)
            )
            conn.commit()
        return self.get_key_public(key_id)

    # ------------------------------------------------------------------
    # balance and usage
    # ------------------------------------------------------------------
    def add_balance(
        self, key_id: str, data: dict[str, Any], *, record_event: bool = True
    ) -> dict[str, Any]:
        if self.get_key_raw(key_id) is None:
            raise StoreError("这个 Key 不存在，可能已经被删除。")
        amount = as_float(data.get("amount"))
        quota_total = as_float(data.get("quota_total"))
        quota_used = as_float(data.get("quota_used"))
        quota_remaining = as_float(data.get("quota_remaining"))
        if all(value is None for value in (amount, quota_total, quota_used, quota_remaining)):
            raise StoreError("至少填写余额或一个额度字段。")
        checked_at = utc_now()
        with self._write_lock, connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO balance_snapshots (
                    id, key_id, amount, currency, quota_total, quota_used,
                    quota_remaining, quota_unit, expires_at, source, note,
                    raw, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("bal_"),
                    key_id,
                    amount,
                    (data.get("currency") or "CNY").strip().upper(),
                    quota_total,
                    quota_used,
                    quota_remaining,
                    (data.get("quota_unit") or "").strip(),
                    (data.get("expires_at") or "").strip() or None,
                    data.get("source") or "manual",
                    (data.get("note") or "").strip(),
                    data.get("raw") or "",
                    checked_at,
                ),
            )
            conn.execute(
                "UPDATE api_keys SET updated_at=? WHERE id=?", (checked_at, key_id)
            )
            if record_event:
                self._add_usage(conn, key_id, None, "", "balance", "更新余额")
            conn.commit()
            return {
                "amount": amount,
                "currency": (data.get("currency") or "CNY").strip().upper(),
                "quota_total": quota_total,
                "quota_used": quota_used,
                "quota_remaining": quota_remaining,
                "quota_unit": (data.get("quota_unit") or "").strip(),
                "expires_at": (data.get("expires_at") or "").strip() or None,
                "source": data.get("source") or "manual",
                "note": (data.get("note") or "").strip(),
                "checked_at": checked_at,
            }

    def latest_balance(self, key_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM balance_snapshots WHERE key_id=? ORDER BY checked_at DESC LIMIT 1",
                (key_id,),
            ).fetchone()
            return self._public_balance(row)

    def balance_history(self, key_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM balance_snapshots WHERE key_id=? ORDER BY checked_at DESC LIMIT ?",
                (key_id, max(1, min(limit, 200))),
            ).fetchall()
            return [self._public_balance(row) for row in rows if row is not None]

    def add_usage(
        self,
        key_id: str | None,
        model_id: str | None,
        capability: str,
        action: str,
        note: str = "",
    ) -> None:
        with self._write_lock, connect(self.db_path) as conn:
            self._add_usage(conn, key_id, model_id, capability, action, note)
            conn.commit()

    def mark_copied(
        self,
        key_id: str,
        model_ids: list[str],
        capability: str,
        fmt: str,
    ) -> None:
        now = utc_now()
        with self._write_lock, connect(self.db_path) as conn:
            conn.execute(
                "UPDATE api_keys SET last_copied_at=?, last_used_at=?, updated_at=? WHERE id=?",
                (now, now, now, key_id),
            )
            self._add_usage(
                conn,
                key_id,
                ",".join(model_ids),
                capability,
                f"copy_{fmt}",
                f"复制 {fmt} 片段",
            )
            conn.commit()

    def list_usage(self, limit: int = 30) -> list[dict[str, Any]]:
        query = """
            SELECT u.*, k.label AS key_label, p.name AS provider_name, p.color AS provider_color
            FROM usage_events u
            LEFT JOIN api_keys k ON k.id = u.key_id
            LEFT JOIN providers p ON p.id = k.provider_id
            ORDER BY u.created_at DESC
            LIMIT ?
        """
        with connect(self.db_path) as conn:
            rows = conn.execute(query, (max(1, min(limit, 200)),)).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # settings and dashboard
    # ------------------------------------------------------------------
    def save_background(self, data: bytes, mime: str) -> str:
        """Persist a custom background image and select it."""
        target = self.db_path.parent / "background.bin"
        target.write_bytes(data)
        version = str(int(time.time()))
        with self._write_lock, connect(self.db_path) as conn:
            for key, value in {
                "background_style": "custom",
                "background_mime": mime,
                "background_version": version,
            }.items():
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            conn.commit()
        return version

    def get_background(self) -> tuple[bytes, str] | None:
        target = self.db_path.parent / "background.bin"
        if not target.exists():
            return None
        mime = self.get_settings().get("background_mime") or "image/png"
        return target.read_bytes(), mime

    def get_settings(self) -> dict[str, str]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            result = {row["key"]: row["value"] for row in rows}
            for key, value in {
                "clipboard_watch": "1",
                "check_updates": "1",
                "auto_refresh_balance": "1",
                "background_style": "aurora",
                "background_version": "0",
                "low_balance_threshold": "20",
                "low_balance_currency": "CNY",
            }.items():
                result.setdefault(key, value)
            return result

    def update_settings(self, data: dict[str, Any]) -> dict[str, str]:
        allowed = {
            "clipboard_watch",
            "check_updates",
            "auto_refresh_balance",
            "background_style",
            "low_balance_threshold",
            "low_balance_currency",
            "default_format",
            "include_comments",
            "direct_key",
        }
        with self._write_lock, connect(self.db_path) as conn:
            for key, value in data.items():
                if key not in allowed:
                    continue
                if key in {
                    "clipboard_watch",
                    "check_updates",
                    "auto_refresh_balance",
                    "include_comments",
                    "direct_key",
                }:
                    value = "1" if str(value).lower() in {"1", "true", "on", "yes"} else "0"
                elif key == "default_format":
                    value = str(value)
                    if value not in ALLOWED_FORMATS:
                        raise StoreError("默认格式不正确。")
                elif key == "low_balance_threshold":
                    number = as_float(value)
                    if number is None or number < 0:
                        raise StoreError("低余额阈值必须是非负数字。")
                    value = str(number)
                elif key == "low_balance_currency":
                    value = str(value).strip().upper()
                    if not re.fullmatch(r"[A-Z]{3}", value):
                        raise StoreError("提醒币种必须是三位货币代码，例如 CNY、USD。")
                elif key == "background_style":
                    value = str(value).strip()
                    if value not in {
                        "aurora",
                        "sunset",
                        "ocean",
                        "forest",
                        "paper",
                        "custom",
                    }:
                        raise StoreError("不支持的背景样式。")
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(value)),
                )
            conn.commit()
        return self.get_settings()

    def stats(self) -> dict[str, Any]:
        settings = self.get_settings()
        threshold = as_float(settings.get("low_balance_threshold")) or 0
        low_currency = (settings.get("low_balance_currency") or "CNY").upper()
        with connect(self.db_path) as conn:
            total_keys = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
            providers_with_keys = conn.execute(
                "SELECT COUNT(DISTINCT provider_id) FROM api_keys"
            ).fetchone()[0]
            total_models = conn.execute(
                "SELECT COUNT(*) FROM models WHERE enabled=1"
            ).fetchone()[0]
            month_new = conn.execute(
                "SELECT COUNT(*) FROM api_keys WHERE created_at LIKE ?",
                (f"{month_prefix()}%",),
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT k.id FROM api_keys k
                WHERE EXISTS (SELECT 1 FROM balance_snapshots b WHERE b.key_id=k.id)
                """
            ).fetchall()
            low_balance = 0
            for row in rows:
                latest = conn.execute(
                    "SELECT amount, currency FROM balance_snapshots "
                    "WHERE key_id=? ORDER BY checked_at DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                if (
                    latest
                    and latest["amount"] is not None
                    and (latest["currency"] or "").upper() == low_currency
                    and latest["amount"] < threshold
                ):
                    low_balance += 1
        return {
            "total_keys": total_keys,
            "providers_with_keys": providers_with_keys,
            "total_models": total_models,
            "month_new": month_new,
            "low_balance": low_balance,
            "recent_usage": self.list_usage(limit=10),
        }

    def state(self) -> dict[str, Any]:
        return {
            "providers": self.list_providers(),
            "keys": self.list_keys(),
            "models": self.list_models(),
            "stats": self.stats(),
            "settings": self.get_settings(),
        }

    # ------------------------------------------------------------------
    # backup / export
    # ------------------------------------------------------------------
    def backup_bytes(self) -> bytes:
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="api-key-ledger-", suffix=".db", delete=False
            ) as handle:
                tmp_path = Path(handle.name)
            with connect(self.db_path) as source:
                dest = sqlite3.connect(str(tmp_path))
                try:
                    source.backup(dest)
                finally:
                    dest.close()
            return tmp_path.read_bytes()
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def restore_backup(self, data: bytes) -> str:
        """Validate a ledger backup and restore it into this store.

        The current database is copied to a timestamped safety file first.
        """
        if len(data) < 100 or not data.startswith(b"SQLite format 3\x00"):
            raise StoreError("这不是有效的 SQLite 备份文件。")
        if len(data) > 12_000_000:
            raise StoreError("备份文件不能超过 12 MB。")

        stamp = time.strftime("%Y%m%d-%H%M%S")
        safety = self.db_path.with_name(f"ledger.before-restore-{stamp}.db")
        temp = self.db_path.with_name(f".ledger-restore-{stamp}.tmp")
        temp.write_bytes(data)
        source = None
        target = None
        try:
            source = sqlite3.connect(str(temp))
            check = source.execute("PRAGMA integrity_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise StoreError("备份数据库校验失败，文件可能已损坏。")
            tables = {
                row[0]
                for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            required = {"api_keys", "models", "key_models", "settings"}
            if not required.issubset(tables):
                raise StoreError("备份缺少钥匙簿数据表，不能恢复。")

            with self._write_lock:
                safety.write_bytes(self.backup_bytes())
                target = sqlite3.connect(str(self.db_path))
                source.backup(target)
                target.close()
                target = None
            self._migrate_plaintext()
            return str(safety)
        finally:
            if source is not None:
                source.close()
            if target is not None:
                target.close()
            temp.unlink(missing_ok=True)

    def export_json(self) -> dict[str, Any]:
        state = self.state()
        # Remove internal fields that are not useful in a portable export.
        for key in state["keys"]:
            key.pop("secret", None)
        return {
            "app": "api-key-ledger",
            "version": 1,
            "exported_at": utc_now(),
            "providers": state["providers"],
            "keys": state["keys"],
            "models": state["models"],
            "settings": state["settings"],
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_capabilities(value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return ["chat"]
        result = []
        for item in value:
            item = str(item).strip().lower()
            if item in ALLOWED_CAPABILITIES and item not in result:
                result.append(item)
        return result or ["chat"]

    def _set_key_models(
        self,
        conn: sqlite3.Connection,
        key_id: str,
        provider_id: str,
        model_ids: list[str],
    ) -> None:
        valid_rows = conn.execute(
            "SELECT id FROM models WHERE provider_id=? AND enabled=1", (provider_id,)
        ).fetchall()
        valid = {row["id"] for row in valid_rows}
        chosen = []
        for model_id in model_ids or []:
            if model_id in valid and model_id not in chosen:
                chosen.append(model_id)
        conn.execute("DELETE FROM key_models WHERE key_id=?", (key_id,))
        for model_id in chosen:
            conn.execute(
                "INSERT OR IGNORE INTO key_models(key_id, model_id, enabled) VALUES(?, ?, 1)",
                (key_id, model_id),
            )

    @staticmethod
    def _add_usage(
        conn: sqlite3.Connection,
        key_id: str | None,
        model_id: str | None,
        capability: str,
        action: str,
        note: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO usage_events(id, key_id, model_id, capability, action, note, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("use_"),
                key_id,
                model_id,
                capability or "",
                action,
                note or "",
                utc_now(),
            ),
        )

    @staticmethod
    def _public_model(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["capabilities"] = _json_load(item.get("capabilities"), ["chat"])
        item["pricing"] = _json_load(item.get("pricing"), {})
        item["formats"] = supported_formats(item.get("api_style", "openai_chat"))
        item["enabled"] = bool(item.get("enabled"))
        item.pop("created_at", None)
        item.pop("updated_at", None)
        return item

    @staticmethod
    def _public_balance(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        item = dict(row)
        item.pop("key_id", None)
        return item

    def _hydrate_key(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> dict[str, Any]:
        item = dict(row)
        item.pop("secret", None)
        models = conn.execute(
            """
            SELECT m.* FROM models m
            JOIN key_models km ON km.model_id = m.id
            WHERE km.key_id=? AND km.enabled=1 AND m.enabled=1
            ORDER BY m.provider_id, m.api_style, m.model_id
            """,
            (item["id"],),
        ).fetchall()
        item["models"] = [self._public_model(model) for model in models]
        item["model_count"] = len(item["models"])
        item.pop("fingerprint", None)
        balance = conn.execute(
            "SELECT * FROM balance_snapshots WHERE key_id=? ORDER BY checked_at DESC LIMIT 1",
            (item["id"],),
        ).fetchone()
        item["balance"] = self._public_balance(balance)
        item["provider"] = {
            "id": item.pop("provider_id"),
            "name": item.pop("provider_name"),
            "short_name": item.pop("provider_short", ""),
            "color": item.pop("provider_color", "#64748b"),
            "docs_url": item.pop("provider_docs", ""),
            "default_base_url": item.pop("provider_base", ""),
            "is_custom": bool(item.pop("provider_custom", 0)),
        }
        item["hint"] = item.pop("secret_hint", "")
        item["has_secret"] = True
        return item

    @staticmethod
    def _guess_style(provider_id: str, model_id: str, capabilities: list[str]) -> str:
        lower = model_id.lower()
        if provider_id == "anthropic":
            return "anthropic_messages"
        if provider_id == "gemini":
            return "gemini_embedding" if "embedding" in capabilities else "gemini_generate"
        if provider_id == "qwen":
            if "embedding" in capabilities:
                return "dashscope_embedding"
            if "rerank" in capabilities:
                return "dashscope_rerank"
            if "image" in capabilities:
                return "dashscope_image"
            if "vision" in capabilities or "vl" in lower:
                return "dashscope_multimodal"
            return "openai_chat"
        if provider_id == "zhipu":
            if "embedding" in capabilities:
                return "openai_embedding"
            if "rerank" in capabilities:
                return "zhipu_rerank"
            return "openai_chat"
        if "embedding" in capabilities:
            return "openai_embedding"
        if capabilities == ["chat"] or "chat" in capabilities:
            return "openai_chat"
        return "unsupported"
