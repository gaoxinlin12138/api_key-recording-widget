# Changelog

## 1.2.0 — 2026-11-02

- Switched the Windows installer to a folder-style deployment (exe + `_internal`).
- Faster startup and fewer antivirus false positives than the onefile installer.
- Installed builds keep the vault in `%LOCALAPPDATA%\ApiKeyLedger\data`.
- The portable ZIP keeps its data beside the exe.
- Existing 1.0.0 / 1.1.0 releases remain available; upgrade with the 1.2.0 setup.
- Future releases are published as setup + portable ZIP (no new onefile asset).

## 1.1.0 — 2026-11-02

- Added a startup update check against GitHub Releases.
- Shows the new version, release notes and a button to open the Release page.
- The check is metadata-only; the app never downloads or executes an update.
- Added a "Check for updates" button and a startup-check toggle in Settings.
- Added Windows file version metadata and a repeatable GitHub Release workflow.

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
