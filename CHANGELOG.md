# Changelog

## 未发布

### 新增

- 设置 → 数据与备份 新增「更改数据目录」：可把数据库迁移到任意绝对路径，迁移后立即生效，原位置文件保留。
  桌面版支持直接选择文件夹；选择记录在程序目录的 `ledger.config.json`。

## 1.3.0 — 2026-11-05

### 新增

- 总览页恢复「最近活动」时间线：添加 Key、查看 Key、复制片段、更新余额都会留下记录。

### 变更

- Key 改为以明文保存在本机 SQLite（不再使用 Windows DPAPI）。旧加密库首次启动会自动迁移，并在同目录保留一份加密安全副本。
- 数据库与备份现在可以在电脑之间迁移；它们包含明文 Key，请自行限制数据目录的访问权限。
- 设置 → 数据与备份 新增「恢复数据库备份」；恢复前会自动备份当前库。
- 重新设计了总览、设置、搜索预览、更新弹窗、添加 Key 弹窗，以及背景与玻璃样式。

### 清理

- 删除前端三份从未被调用的遗留视图（约 523 行）与“快速导入”残留代码。
- 删除 6 个无调用方的 HTTP 接口：`/api/health`、`GET /api/keys/{id}`、`GET /api/keys/{id}/balance-history`、`GET /api/settings`、`PATCH /api/models/{id}`、`DELETE /api/models/{id}`。
- 删除无用文件：`docs/mockups/`（13 个设计稿）、`assets/app.png`、单文件打包链（`api_key_ledger_onefile.spec` / `build_onefile.bat` / `build_onefile.ps1`）。
- 清理 Python 死函数 5 处、死导入 3 处；合并两处重复的片段格式常量。
- 删除 105 条针对已下线界面的死 CSS 规则（`styles.css` 减少约 11%）。

### 测试

- 新增 HTTP 层测试 27 个（路由、CSRF/Host 校验、备份恢复、错误码），测试总数 28 → 55。
- CI 在打包之前强制执行测试，测试失败即中断发布。

### 兼容性

- 已发布的 v1.1.0 单文件版 exe 仍可正常启动并沿用原数据目录；本次只是移除了构建脚本，运行期判定逻辑保留。

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
