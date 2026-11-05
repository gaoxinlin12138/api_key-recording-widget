"""HTTP 层测试：路由、鉴权、备份恢复、错误码。

这些用例覆盖验收清单里此前完全没有自动化守卫的部分：
AC-02（首屏 state）、AC-18/19（备份与恢复）、AC-24（安全边界），
以及批次4 删除的 6 个接口必须保持 404。
"""

from __future__ import annotations

import base64
import json
import re
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from core.server import start_server

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


class ServerTestCase(unittest.TestCase):
    """起一个真实 HTTP 服务，用 urllib 走完整请求链路。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.tmp.name) / "ledger.db"
        cls.running = start_server(
            base_dir=ROOT,
            db_path=cls.db_path,
            port=0,
            web_dir=WEB_DIR,
        )
        cls.base = cls.running.url.rstrip("/")
        with urllib.request.urlopen(f"{cls.base}/", timeout=10) as response:
            html = response.read().decode("utf-8")
        match = re.search(r'name="csrf-token" content="([^"]+)"', html)
        if not match:
            raise RuntimeError("首页没有注入 CSRF 令牌")
        cls.token = match.group(1)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.running.stop()
        cls.tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        *,
        token: str | None = "auto",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, object]:
        url = f"{self.base}{path}"
        data = None
        hdrs = dict(headers or {})
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        if token == "auto":
            hdrs["X-CSRF-Token"] = self.token
        elif token:
            hdrs["X-CSRF-Token"] = token
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                status = response.status
                ctype = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
            ctype = exc.headers.get("Content-Type", "")
        if "application/json" in ctype:
            return status, json.loads(raw.decode("utf-8") or "{}")
        return status, raw

    def create_key(self, label: str = "测试 Key", secret: str = "sk-test-1234567890") -> dict:
        status, payload = self.request(
            "POST",
            "/api/keys",
            {
                "provider_id": "deepseek",
                "label": label,
                "secret": secret,
                "model_ids": [],
            },
        )
        self.assertEqual(status, 201, payload)
        return payload["key"]


class RoutingTests(ServerTestCase):
    def test_state_has_full_payload(self) -> None:
        status, payload = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        for field in ("providers", "keys", "models", "stats", "settings", "app"):
            self.assertIn(field, payload)
        self.assertGreaterEqual(len(payload["providers"]), 8)
        self.assertGreaterEqual(len(payload["models"]), 30)
        self.assertIn("version", payload["app"])

    def test_removed_endpoints_stay_gone(self) -> None:
        key = self.create_key("待删接口", "sk-removed-0001")
        removed = [
            ("GET", "/api/health", None),
            ("GET", f"/api/keys/{key['id']}", None),
            ("GET", f"/api/keys/{key['id']}/balance-history", None),
            ("GET", "/api/settings", None),
            ("PATCH", f"/api/models/deepseek:deepseek-chat", {"notes": "x"}),
            ("DELETE", "/api/models/deepseek:deepseek-chat", None),
        ]
        for method, path, body in removed:
            status, _ = self.request(method, path, body)
            self.assertEqual(status, 404, f"{method} {path} 应为 404")

    def test_unknown_api_returns_404(self) -> None:
        status, payload = self.request("GET", "/api/does-not-exist")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_unknown_static_returns_404(self) -> None:
        status, _ = self.request("GET", "/assets/js/nope.js", token=None)
        self.assertEqual(status, 404)


class AuthTests(ServerTestCase):
    def test_missing_token_is_rejected(self) -> None:
        status, payload = self.request("GET", "/api/state", token=None)
        self.assertEqual(status, 403)
        self.assertIn("error", payload)

    def test_wrong_token_is_rejected(self) -> None:
        status, _ = self.request("GET", "/api/state", token="not-the-token")
        self.assertEqual(status, 403)

    def test_foreign_origin_is_rejected(self) -> None:
        status, _ = self.request(
            "GET", "/api/state", headers={"Origin": "https://evil.example.com"}
        )
        self.assertEqual(status, 403)

    def test_local_origin_is_accepted(self) -> None:
        status, _ = self.request(
            "GET", "/api/state", headers={"Origin": "http://127.0.0.1:1"}
        )
        self.assertEqual(status, 200)

    def test_foreign_host_is_rejected(self) -> None:
        status, _ = self.request("GET", "/api/state", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 403)

    def test_background_image_bypasses_token_but_not_host(self) -> None:
        status, payload = self.request("GET", "/api/background/image", token=None)
        self.assertEqual(status, 404)
        self.assertIn("error", payload)


class KeyLifecycleTests(ServerTestCase):
    def test_create_reveal_update_delete(self) -> None:
        key = self.create_key("生命周期", "sk-lifecycle-1234567890")
        self.assertEqual(key["hint"], "sk-…7890")
        self.assertNotIn("secret", key)

        status, payload = self.request("POST", f"/api/keys/{key['id']}/reveal")
        self.assertEqual(status, 200)
        self.assertEqual(payload["secret"], "sk-lifecycle-1234567890")

        status, payload = self.request(
            "PATCH", f"/api/keys/{key['id']}", {"label": "改名后"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["key"]["label"], "改名后")

        status, _ = self.request("DELETE", f"/api/keys/{key['id']}")
        self.assertEqual(status, 200)
        status, payload = self.request("GET", "/api/keys")
        self.assertNotIn(key["id"], [item["id"] for item in payload["keys"]])

    def test_duplicate_key_is_rejected(self) -> None:
        self.create_key("重复一", "sk-duplicate-0001")
        status, payload = self.request(
            "POST",
            "/api/keys",
            {
                "provider_id": "deepseek",
                "label": "重复二",
                "secret": "sk-duplicate-0001",
                "model_ids": [],
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("已经录入过", payload["error"])

    def test_invalid_key_payload_is_rejected(self) -> None:
        status, _ = self.request(
            "POST", "/api/keys", {"provider_id": "deepseek", "label": "空", "secret": ""}
        )
        self.assertEqual(status, 400)

    def test_copied_marks_usage(self) -> None:
        key = self.create_key("复制记录", "sk-copied-0001")
        status, _ = self.request(
            "POST",
            f"/api/keys/{key['id']}/copied",
            {"model_ids": [], "capability": "chat", "format": "env"},
        )
        self.assertEqual(status, 200)
        status, payload = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        labels = [item["key_label"] for item in payload["stats"]["recent_usage"]]
        self.assertIn("复制记录", labels)


class SnippetTests(ServerTestCase):
    def test_snippet_for_every_format(self) -> None:
        status, payload = self.request("GET", "/api/state")
        model = next(
            item
            for item in payload["models"]
            if item["provider_id"] == "deepseek" and "chat" in item["capabilities"]
        )
        key = self.create_key("片段", "sk-snippet-0001")
        self.request(
            "POST",
            f"/api/keys/{key['id']}/models",
            {"model_ids": [model["id"]]},
        )
        for fmt in ("env", "python", "curl", "js"):
            status, body = self.request(
                "POST",
                "/api/snippets",
                {
                    "key_id": key["id"],
                    "models": [{"id": model["id"], "capability": "chat"}],
                    "format": fmt,
                },
            )
            self.assertEqual(status, 200, f"{fmt}: {body}")
            self.assertTrue(body["text"], fmt)
            self.assertTrue(body["masked"], fmt)
            self.assertNotIn("sk-snippet-0001", body["text"], fmt)

    def test_snippet_without_key_is_rejected(self) -> None:
        status, _ = self.request("POST", "/api/snippets", {"models": []})
        self.assertEqual(status, 400)


class SettingsTests(ServerTestCase):
    def test_patch_settings_validates(self) -> None:
        status, payload = self.request(
            "PATCH", "/api/settings", {"low_balance_threshold": "5", "low_balance_currency": "usd"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["settings"]["low_balance_currency"], "USD")
        self.assertEqual(payload["settings"]["low_balance_threshold"], "5.0")

        status, _ = self.request("PATCH", "/api/settings", {"low_balance_currency": "RMB1"})
        self.assertEqual(status, 400)

        status, _ = self.request("PATCH", "/api/settings", {"low_balance_threshold": "-1"})
        self.assertEqual(status, 400)

        status, _ = self.request("PATCH", "/api/settings", {"background_style": "nope"})
        self.assertEqual(status, 400)

    def test_unknown_setting_is_ignored(self) -> None:
        status, payload = self.request("PATCH", "/api/settings", {"whatever": "1"})
        self.assertEqual(status, 200)
        self.assertNotIn("whatever", payload["settings"])


class BackupTests(ServerTestCase):
    def test_backup_download_and_export(self) -> None:
        self.create_key("备份", "sk-backup-0001")
        status, raw = self.request("GET", "/api/backup")
        self.assertEqual(status, 200)
        self.assertTrue(bytes(raw).startswith(b"SQLite format 3\x00"))

        status, exported = self.request("GET", "/api/export")
        self.assertEqual(status, 200)
        serialized = json.dumps(exported, ensure_ascii=False)
        self.assertNotIn("sk-backup-0001", serialized)

    def test_restore_roundtrip(self) -> None:
        self.create_key("恢复前", "sk-restore-0001")
        _, raw = self.request("GET", "/api/backup")
        data_url = "data:application/octet-stream;base64," + base64.b64encode(
            bytes(raw)
        ).decode("ascii")
        status, payload = self.request(
            "POST", "/api/backup/restore", {"data_url": data_url}
        )
        self.assertEqual(status, 200)
        self.assertTrue(Path(payload["backup_path"]).exists())

    def test_restore_rejects_garbage(self) -> None:
        data_url = "data:application/octet-stream;base64," + base64.b64encode(
            b"definitely not a database"
        ).decode("ascii")
        status, payload = self.request(
            "POST", "/api/backup/restore", {"data_url": data_url}
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_restore_rejects_bad_payload(self) -> None:
        status, _ = self.request("POST", "/api/backup/restore", {"data_url": "hello"})
        self.assertEqual(status, 400)


class BackgroundTests(ServerTestCase):
    def test_rejects_non_image_payload(self) -> None:
        data_url = "data:image/png;base64," + base64.b64encode(b"not a png").decode("ascii")
        status, payload = self.request(
            "POST", "/api/background/upload", {"data_url": data_url}
        )
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_rejects_unsupported_mime(self) -> None:
        data_url = "data:image/gif;base64," + base64.b64encode(b"GIF89a").decode("ascii")
        status, payload = self.request(
            "POST", "/api/background/upload", {"data_url": data_url}
        )
        self.assertEqual(status, 400)


class ClipboardTests(ServerTestCase):
    def test_pending_list_and_invalid_accept(self) -> None:
        status, payload = self.request("GET", "/api/clipboard/pending")
        self.assertEqual(status, 200)
        self.assertEqual(payload["pending"], [])

        status, _ = self.request("POST", "/api/clipboard/clip_nope/accept")
        self.assertEqual(status, 404)


class ImportTests(ServerTestCase):
    def test_parse_env_text(self) -> None:
        status, payload = self.request(
            "POST",
            "/api/import/parse",
            {"text": "OPENAI_API_KEY=sk-abcdefghijklmnop\nOPENAI_MODEL=gpt-4.1"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider_id"], "openai")

    def test_parse_empty_is_not_ok(self) -> None:
        status, payload = self.request("POST", "/api/import/parse", {"text": ""})
        self.assertEqual(status, 200)
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
