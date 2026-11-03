from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.catalog import PROVIDERS
from core.importer import parse_pasted, provider_from_title
from core.providers import BalanceNotSupported, _request_json, fetch_balance, fetch_models
from core.security import protect, unprotect
from core.snippets import SnippetError, generate_snippet
from core.store import Store, StoreError
from core.updater import UpdateError, check_for_update, version_tuple


PROVIDER_MAP = {provider["id"]: provider for provider in PROVIDERS}


class ImporterTests(unittest.TestCase):
    def test_provider_from_window_title(self):
        self.assertEqual(
            provider_from_title("DeepSeek 开放平台 - Google Chrome"), "deepseek"
        )
        self.assertEqual(provider_from_title("阿里云百炼控制台"), "qwen")
        self.assertIsNone(provider_from_title("API 钥匙簿"))

    def test_env_screenshot_format(self):
        result = parse_pasted(
            "LLM_WIKI_API_BASE=https://api.deepseek.com\n"
            "LLM_WIKI_API_KEY=sk-test-1234567890abcdef\n"
            "LLM_WIKI_MODEL=deepseek-chat"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["secret"], "sk-test-1234567890abcdef")
        self.assertEqual(result["provider_id"], "deepseek")
        self.assertEqual(result["env_prefix"], "LLM_WIKI")
        self.assertEqual(result["model"], "deepseek-chat")
        self.assertEqual(result["source"], "env")

    def test_qwen_env_without_base(self):
        result = parse_pasted(
            "DASHSCOPE_API_KEY=sk-abcdefghijklmnop\n"
            "QWEN_MODEL=qwen-plus\n"
            "QWEN_EMBEDDING_MODEL=text-embedding-v4"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider_id"], "qwen")
        self.assertEqual(len(result["models"]), 2)
        self.assertEqual(result["models"][1]["capability"], "embedding")

    def test_curl_anthropic(self):
        result = parse_pasted(
            """curl https://api.anthropic.com/v1/messages \
            -H "x-api-key: sk-ant-abcdefghijklmnop" \
            -H "anthropic-version: 2023-06-01" \
            -d '{"model":"claude-sonnet-4-5","messages":[]}'"""
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider_id"], "anthropic")
        self.assertEqual(result["base_url"], "https://api.anthropic.com")
        self.assertEqual(result["model"], "claude-sonnet-4-5")

    def test_json_and_raw(self):
        result = parse_pasted(
            json.dumps(
                {
                    "api_key": "sk-abcdefghijklmnop",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4.1",
                }
            )
        )
        self.assertEqual(result["provider_id"], "openai")
        self.assertEqual(result["env_prefix"], "OPENAI")
        self.assertTrue(parse_pasted("sk-ant-abcdefghijklmnopqrstuvwxyz")["ok"])

    def test_rejects_empty(self):
        self.assertFalse(parse_pasted("")["ok"])


class SnippetTests(unittest.TestCase):
    def setUp(self):
        self.key = {
            "secret": "sk-test-1234567890",
            "hint": "sk-…7890",
            "env_prefix": "LLM_WIKI",
        }

    def model(self, provider_id, model_id, capability):
        provider = PROVIDER_MAP[provider_id]
        model = next(item for item in provider["models"] if item["model_id"] == model_id)
        item = dict(model)
        item["capability"] = capability
        return provider, item

    def test_deepseek_env(self):
        provider, model = self.model("deepseek", "deepseek-chat", "chat")
        text = generate_snippet(provider, self.key, [model], "env", include_secret=True)
        self.assertIn("LLM_WIKI_API_BASE=https://api.deepseek.com", text)
        self.assertIn("LLM_WIKI_API_KEY=sk-test-1234567890", text)
        self.assertIn("LLM_WIKI_MODEL=deepseek-chat", text)

    def test_deepseek_python(self):
        provider, model = self.model("deepseek", "deepseek-chat", "chat")
        text = generate_snippet(provider, self.key, [model], "python", include_comments=True)
        self.assertIn("from openai import OpenAI", text)
        self.assertIn("client.chat.completions.create", text)
        self.assertIn("LLM_WIKI_API_KEY", text)

    def test_qwen_embedding_uses_native_sdk(self):
        provider, model = self.model("qwen", "text-embedding-v4", "embedding")
        text = generate_snippet(provider, self.key, [model], "python")
        self.assertIn("from dashscope import TextEmbedding", text)
        self.assertIn("text-embedding-v4", text)

    def test_qwen_vision_env(self):
        provider, model = self.model("qwen", "qwen-vl-max", "vision")
        text = generate_snippet(provider, self.key, [model], "env", include_secret=False)
        self.assertIn("LLM_WIKI_VISION_MODEL=qwen-vl-max", text)
        self.assertIn("sk-…7890", text)

    def test_unsupported_format(self):
        provider = PROVIDER_MAP["custom"]
        model = {
            "model_id": "mystery",
            "display_name": "Mystery",
            "api_style": "unsupported",
            "capability": "chat",
        }
        self.assertTrue(generate_snippet(provider, self.key, [model], "env"))
        with self.assertRaises(SnippetError):
            generate_snippet(provider, self.key, [model], "python")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "ledger.db"
        self.store = Store(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_and_key_lifecycle(self):
        self.assertEqual(len(self.store.list_providers()), 8)
        self.assertGreaterEqual(len(self.store.list_models()), 30)
        models = self.store.list_models("deepseek")
        key = self.store.create_key(
            {
                "provider_id": "deepseek",
                "label": "测试 Key",
                "secret": "sk-test-1234567890abcdef",
                "env_prefix": "LLM_WIKI",
                "project": "测试项目",
                "note": "备注",
                "model_ids": [model["id"] for model in models],
            }
        )
        self.assertEqual(key["hint"], "sk-…cdef")
        self.assertNotIn("fingerprint", key)
        self.assertEqual(key["model_count"], 2)
        self.assertEqual(self.store.reveal_secret(key["id"]), "sk-test-1234567890abcdef")
        with self.assertRaises(StoreError):
            self.store.create_key(
                {
                    "provider_id": "deepseek",
                    "label": "重复",
                    "secret": "sk-test-1234567890abcdef",
                }
            )
        self.store.add_balance(key["id"], {"amount": 12.5, "currency": "CNY"})
        self.assertEqual(self.store.latest_balance(key["id"])["amount"], 12.5)
        self.assertEqual(len(self.store.balance_history(key["id"])), 1)
        self.assertGreater(len(self.store.backup_bytes()), 100)
        self.assertNotIn("sk-test", json.dumps(self.store.export_json(), ensure_ascii=False))
        self.store.delete_key(key["id"])
        self.assertEqual(len(self.store.list_keys()), 0)

    def test_custom_model(self):
        model = self.store.add_model(
            {
                "provider_id": "deepseek",
                "model_id": "my-model",
                "display_name": "My Model",
                "capabilities": ["chat"],
                "api_style": "openai_chat",
            }
        )
        self.assertEqual(model["model_id"], "my-model")
        key = self.store.create_key(
            {
                "provider_id": "deepseek",
                "label": "自定义模型 Key",
                "secret": "sk-custom-1234567890",
                "model_ids": [model["id"]],
            }
        )
        self.assertEqual(key["model_count"], 1)
        self.store.delete_model(model["id"])
        self.assertEqual(len(self.store.list_models("deepseek")), 2)

    def test_settings(self):
        settings = self.store.update_settings(
            {
                "clipboard_watch": "0",
                "low_balance_threshold": "5",
                "low_balance_currency": "usd",
            }
        )
        self.assertEqual(settings["clipboard_watch"], "0")
        self.assertEqual(settings["low_balance_threshold"], "5.0")
        self.assertEqual(settings["low_balance_currency"], "USD")

    def test_restore_backup(self):
        raw = self.store.backup_bytes()
        safety = self.store.restore_backup(raw)
        self.assertTrue(Path(safety).exists())
        with self.assertRaises(StoreError):
            self.store.restore_backup(b"not a sqlite database")

    def test_background_roundtrip(self):
        raw = b"\x89PNG\r\n\x1a\n" + b"test"
        version = self.store.save_background(raw, "image/png")
        background = self.store.get_background()
        self.assertIsNotNone(background)
        self.assertEqual(background[0], raw)
        self.assertEqual(background[1], "image/png")
        self.assertEqual(self.store.get_settings()["background_style"], "custom")
        self.assertEqual(self.store.get_settings()["background_version"], version)

    def test_low_balance_only_compares_same_currency(self):
        cny = self.store.create_key(
            {
                "provider_id": "deepseek",
                "label": "人民币",
                "secret": "sk-cny-1234567890",
                "model_ids": [],
            }
        )
        usd = self.store.create_key(
            {
                "provider_id": "deepseek",
                "label": "美元",
                "secret": "sk-usd-1234567890",
                "model_ids": [],
            }
        )
        self.store.add_balance(cny["id"], {"amount": 12, "currency": "CNY"})
        self.store.add_balance(usd["id"], {"amount": 5, "currency": "USD"})
        self.assertEqual(self.store.stats()["low_balance"], 1)
        self.store.update_settings({"low_balance_currency": "USD"})
        self.assertEqual(self.store.stats()["low_balance"], 1)
        self.store.update_settings({"low_balance_currency": "EUR"})
        self.assertEqual(self.store.stats()["low_balance"], 0)

    def test_upsert_fetched_models(self):
        added = self.store.upsert_fetched_models(
            "deepseek",
            [
                {
                    "model_id": "deepseek-new",
                    "display_name": "DeepSeek New",
                    "capabilities": ["chat"],
                }
            ],
        )
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["source"], "fetched")


class UpdateTests(unittest.TestCase):
    def test_version_tuple(self):
        self.assertEqual(version_tuple("v1.2.3"), (1, 2, 3))
        self.assertIsNone(version_tuple("1.2"))

    def test_newer_release(self):
        payload = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/x/y/releases/tag/v1.2.0",
            "body": "Changes",
        }
        with patch("core.updater._request_release", return_value=payload):
            result = check_for_update("1.1.0")
        self.assertTrue(result["update_available"])
        self.assertEqual(result["latest"], "1.2.0")

    def test_same_release(self):
        payload = {"tag_name": "v1.1.0", "html_url": "https://example.com"}
        with patch("core.updater._request_release", return_value=payload):
            result = check_for_update("1.1.0")
        self.assertFalse(result["update_available"])

    def test_invalid_release(self):
        with patch(
            "core.updater._request_release",
            return_value={"tag_name": "nightly"},
        ):
            with self.assertRaises(UpdateError):
                check_for_update("1.0.0")


class SecurityTests(unittest.TestCase):
    def test_roundtrip(self):
        token = protect("sk-secret-123456")
        self.assertEqual(unprotect(token), "sk-secret-123456")

    def test_empty(self):
        with self.assertRaises(ValueError):
            protect("")


class ProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.provider = PROVIDER_MAP["deepseek"]

    def test_request_client_does_not_pass_context_to_opener(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok": true}'
        with patch("core.providers._opener.open", return_value=response) as mocked:
            result = _request_json("https://example.com/test")
        self.assertEqual(result, {"ok": True})
        self.assertNotIn("context", mocked.call_args.kwargs)

    def test_fetch_models(self):
        fake = {
            "data": [
                {"id": "deepseek-chat"},
                {"id": "deepseek-embedding"},
            ]
        }
        with patch("core.providers._request_json", return_value=fake):
            models = fetch_models(self.provider, "sk-test")
        self.assertEqual(len(models), 2)
        self.assertEqual(models[1]["capabilities"], ["embedding"])

    def test_deepseek_balance(self):
        fake = {
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "88.50",
                    "granted_balance": "8.50",
                    "topped_up_balance": "80.00",
                }
            ]
        }
        with patch("core.providers._request_json", return_value=fake):
            balance = fetch_balance(self.provider, "sk-test")
        self.assertEqual(balance["amount"], 88.5)
        self.assertEqual(balance["currency"], "CNY")
        self.assertEqual(balance["source"], "auto")

    def test_no_balance_adapter(self):
        with self.assertRaises(BalanceNotSupported):
            fetch_balance(PROVIDER_MAP["openai"], "sk-test")


if __name__ == "__main__":
    unittest.main()
