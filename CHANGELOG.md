# Changelog

## 1.0.0 — 2026-11-02

First desktop release.

- Local encrypted API-key ledger for DeepSeek, Qwen, OpenAI, Claude, Gemini,
  Kimi, Zhipu and custom OpenAI-compatible providers.
- Paste import from `.env`, JSON, curl and bare keys.
- Per-key model selection with chat, vision, embedding, rerank and image
  capabilities.
- Snippet studio for `.env`, Python, cURL and JavaScript, including
  provider-native DashScope, Anthropic and Gemini templates.
- Manual balance/quota history; automatic balance for DeepSeek and Kimi.
- Live model discovery where the provider exposes a models endpoint.
- Windows DPAPI encryption at rest.
- Clipboard watcher for newly copied keys.
- Portable folder build and single-file desktop build.
- Per-user Inno Setup installer; user data stays in
  `%LOCALAPPDATA%\ApiKeyLedger\data`.
