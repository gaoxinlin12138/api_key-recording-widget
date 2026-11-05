# 项目规范（防反弹）

> 这份文档是 2026-11 那次清理的产物。清理前仓库里有 523 行从未被调用的视图、105 条死 CSS
> 规则、16 次重复定义的同一选择器、6 个没人调用的接口。下面的规则就是为了让这些东西不再长回来。
>
> 适用范围：本仓库所有代码（`core/`、`web/`、`tests/`、`tools/`、打包脚本）。
> 新规则与本文冲突时，先改本文再改代码，不允许"这次特殊"。

---

## 1. 模块职责与边界

### 1.1 每个模块负责什么

| 模块 | 唯一职责 | 明确不负责 |
|---|---|---|
| [app.py](../app.py) | 解析命令行、定位数据目录、选择桌面/浏览器模式 | 任何业务逻辑、任何 SQL |
| [core/server.py](../core/server.py) | HTTP 服务、路由分发、鉴权、静态文件 | 直接写 SQL、直接拼装业务规则 |
| [core/store.py](../core/store.py) | 业务规则 + 持久化（唯一允许写 SQL 的地方） | 发 HTTP 请求、渲染 HTML |
| [core/db.py](../core/db.py) | 表结构、初始数据播种 | 业务校验 |
| [core/catalog.py](../core/catalog.py) | 内置平台与模型的初始目录（纯数据） | 任何逻辑 |
| [core/providers.py](../core/providers.py) | 调用外部平台接口（取模型、查余额） | 读写本地数据库 |
| [core/importer.py](../core/importer.py) | 把粘贴文本解析成草稿 | 落库 |
| [core/snippets.py](../core/snippets.py) | 生成代码片段文本 | 读数据库、发请求 |
| [core/clipboard.py](../core/clipboard.py) | Win32 剪贴板监听 | 判断"要不要入库"（由 server 决定） |
| [core/desktop.py](../core/desktop.py) | pywebview 窗口与原生保存对话框 | 业务逻辑 |
| [core/updater.py](../core/updater.py) | 查询 GitHub Release 元数据 | 下载或执行更新（永不） |
| [core/security.py](../core/security.py) | 旧版 DPAPI 解密（仅迁移用） | 加密新数据（1.3.0 起明文存储） |
| [core/utils.py](../core/utils.py) | 无副作用的纯函数 | 访问数据库、网络、文件 |
| [web/js/api.js](../web/js/api.js) | 前端唯一出口：fetch + CSRF + 错误包装 | 业务判断 |
| [web/js/views.js](../web/js/views.js) | 纯渲染函数：state → HTML 字符串 | 发请求、改 state |
| [web/js/ui.js](../web/js/ui.js) | 图标、格式化、通用组件、共享常量 | 业务规则 |
| [web/js/app.js](../web/js/app.js) | 状态、路由、事件分发、弹窗编排 | 直接拼长 HTML（交给 views） |

### 1.2 边界硬规则

1. **只有 `core/store.py` 写 SQL。** 其他文件出现 `SELECT/INSERT/UPDATE/DELETE` 即为违规。
2. **`views.js` 里禁止出现 `fetch(` / `api(`。** 渲染函数只接收数据、返回字符串。
3. **`ui.js` 里禁止出现业务概念**（平台、余额、Key、片段）。它只认识"数字、日期、图标、标签"。
4. **`core/*` 不得 import `web/*`；`web/*` 不得 import `core/*`。** 两侧只通过 HTTP JSON 通信。
5. **路由层不得内联业务规则。** `server.py` 只做：取参数 → 调 store/provider/snippet → 返回 JSON。
6. **`providers.py` 不得读写本地库。** 它拿到的 provider 字典由调用方传入。
7. **前端共享常量只允许定义一次**（当前在 `ui.js`：`FORMAT_LABELS`、`FORMAT_ORDER`、`CAPABILITY_LABELS`、`BACKGROUND_PRESETS`）。
8. **删除功能时，同时删除它的路由、store 方法、前端入口、CSS 与测试。** 不允许"先留着以后可能用"。

> 违反边界时，自检脚本或 code review 必须拦住；拦不住的按 bug 处理。

---

## 2. 新增依赖流程

当前状态：**运行时零第三方依赖**（纯标准库），`requirements-build.txt` 只有 `pywebview`、`pyinstaller`。这是一个刻意维持的优势——它决定了安装包体积、启动速度和杀软误报率。

新增任何依赖前，按顺序回答 7 个问题，全部通过才允许引入：

1. **标准库能替代吗？** 能就不用。
2. **是运行时依赖还是构建期依赖？** 运行时依赖要写进 README 的"环境要求"，构建期只进 `requirements-build.txt`。
3. **它会不会进打包产物？** 会的话估算体积增量，超过 5 MB 必须说明理由。
4. **有已知 CVE 吗？** 查一下最近 12 个月的漏洞记录。
5. **许可证兼容吗？** 不能是 AGPL 这类会传染的。
6. **离线可用吗？** 本工具的核心承诺是"不联网也能用"，依赖不得在启动时联网。
7. **会不会触发杀软？** pyinstaller 打包后，加密/注入类库极易误报。

通过后：钉死版本（`>=x.y,<z`）→ 更新 `requirements-build.txt` → 更新 README → 跑一遍"干净机器打包"验证。

> 反例：不要因为"顺手"引入 `requests`、`pydantic`、`date-fns` 这类可被标准库/十几行代码替代的东西。

---

## 3. 变更强制要求

1. **任何代码修改必须附带测试。** 没有测试的 PR 不合并。
2. **测试放在 `tests/`**：
   - 纯逻辑（解析、片段、存储、工具）→ `tests/test_core.py`
   - HTTP 行为（路由、鉴权、状态码、备份恢复）→ `tests/test_server.py`
3. **测试必须断言行为，不是断言实现。** 例如断言"重复 Key 返回 400 且提示已录入"，而不是断言内部函数被调用。
4. **禁止为了过测试而改断言。** 测试红了先查代码；确认是测试写错才改，并在提交信息里说明"为什么原断言是错的"。
5. **前端改动没有自动化测试，必须做人工验收**，并在提交信息里写清"手工验证了哪几页、点了什么"。
6. **涉及数据格式、接口签名、默认值的改动，必须同步更新 `CHANGELOG.md`。**
7. **删功能要留证据。** 提交信息里写清"全项目检索结果：0 引用"，或附上验收步骤。

---

## 4. 流水线规范

### 4.1 本地提交流程（每次）

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v   # 功能测试
.venv\Scripts\python.exe tools\check_project.py --strict     # 代码自检
```

两者都通过才允许提交。

### 4.2 CI 门禁（[release.yml](../.github/workflows/release.yml)）

打包前依次执行，任一步失败即中断，**不会产出 Release**：

1. `Run tests` —— 全部单元 + HTTP 测试
2. `Project self-check --strict` —— 死 import、重复常量
3. 构建文件夹版 → 便携 ZIP → 安装包 → SHA256 → 发布

### 4.3 自检脚本查什么

| 级别 | 检查项 | 当前门槛 |
|---|---|---|
| ERROR（阻断） | Python 未使用 import | 必须为 0 |
| ERROR（阻断） | 前端顶层常量跨文件重复定义 | 必须为 0 |
| WARN（记录） | CSS 未使用类 | 允许存在，逐批收敛 |
| WARN（记录） | 选择器重复定义 > 3 次 | 允许存在，逐批收敛 |
| WARN（记录） | 前端 export 无引用 | 允许存在，逐批收敛 |

### 4.4 分支与提交

- 功能/清理一律开分支：`cleanup/<主题>`、`feat/<主题>`、`fix/<主题>`。**不直接往 `main` 提交。**
- 提交信息格式：`type(scope): 中文摘要`，正文写"改了什么 / 为什么 / 怎么验证"。
- 一批只做一类事。清理时禁止"顺手重构"。
- 合并前必须：测试全绿 + 自检无 ERROR + 人工验收记录。

### 4.5 发布

见 README「发布新版本」。版本号唯一来源是 [core/version.py](../core/version.py)，改完必须重新生成 `version_info.txt`。

---

## 5. 小颗粒开发规范

**硬规定：一次任务只能是一个可独立验收的小块。** 不接受"做个完整用户系统""优化一下性能"这类需求。

### 5.1 任务立项模板（缺一项不许开工）

```text
任务名：
输入：      （用户给什么 / 系统已有什么）
输出：      （页面上能看到什么 / 接口返回什么）
验收标准：   （可勾选、可复现、别人能照着验）
不做的事：   （明确划出边界，防止膨胀）
影响面：    （涉及哪些文件、哪些验收条目）
```

### 5.2 拆分示例（本项目的真实粒度）

❌ 一次性做"Key 管理模块"
✅ 拆成 4 个任务：
1. 手动添加 Key（表单 + 落库 + 列表展示）
2. 从剪贴板识别并预填（解析 + 弹窗预填）
3. 编辑与删除 Key（含二次确认）
4. 查看明文 Key（含使用记录）

❌ 一次性做"模型管理"
✅ 拆成：勾选模型 → 从平台拉取 → 添加自定义模型 → 按能力生成片段

每个小任务都必须单独跑测试、单独给验收步骤。

### 5.3 需求模糊时

先写"我理解的输入/输出/验收"，让对方确认，**不要靠猜直接写代码**。猜测产生的功能，80% 会成为下一次清理的对象。

---

## 6. 反模式清单（都在这仓库真实发生过）

| 反模式 | 曾经的样子 | 现在的对策 |
|---|---|---|
| 保留旧版视图"以防万一" | `dashboardViewLegacy`、`settingsViewLegacy`、`dashboardViewLegacy2` 共 523 行，0 引用 | 删功能时连视图一起删；自检脚本查无引用 export |
| 同一选择器反复覆盖 | `.nav-item.active::after` 定义 16 次，`display:none !important` 与 `display:block !important` 互相打架 | 样式改一次就删旧规则；自检脚本报重复次数 |
| 常量复制两份 | `FORMAT_LABELS` 在 `app.js` 与 `views.js` 各一份 | 共享常量只放 `ui.js`；自检脚本阻断重复 |
| 接口先留着 | 6 个接口无任何调用方（health、keys/{id}、balance-history、settings GET、models PATCH/DELETE） | 删接口要连测试夹具一起改；提交信息写清"0 调用方" |
| 为过测试改断言 | — | 明确禁止；改了必须在提交信息里论证 |
| 构建脚本与产物线脱节 | 单文件打包链 CI 根本不用 | 删掉过期脚本；README 同步 |
| 只测"好路径" | 备份恢复此前没有任何测试 | 每个接口至少覆盖一个失败分支 |

---

## 7. 已知取舍与例外

1. **明文存储（1.3.0 起的既定选择）。** Key 以明文保存在本机 SQLite，数据库与备份含明文 Key。这是为了"数据可迁移"而接受的取舍，已在 CHANGELOG、设置页、README 三处明写。**任何安全相关改动（加密、令牌、权限）必须单独立项，不得混在功能提交里。**
2. **CSRF 令牌是唯一鉴权。** 服务只监听 `127.0.0.1`，Host/Origin 校验挡浏览器跨站，但不挡本机其它进程。这是本机工具的边界，不是缺陷——除非有人要求"防本机恶意软件"，那属于新需求。
3. **`store.delete_model` / `store.balance_history` 目前仅测试可达。** 保留是因为它们验证了级联删除与历史查询规则；若后续仍无界面接入，再决定是否删除。
4. **CSS 里仍有 36 个未使用类与 6 个高频重复选择器。** 收敛它们需要视觉回归，单独排期，见 [BACKLOG.md](BACKLOG.md) 的 P2。

---

## 8. 常用命令

```powershell
.venv\Scripts\python.exe app.py                      # 浏览器模式
.venv\Scripts\python.exe app.py --native             # 桌面窗口
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe tools\check_project.py --strict
.venv\Scripts\python.exe tools\check_project.py      # 只看 WARN
```

```bash
git checkout -b feat/<主题>
git commit -m "feat(scope): 摘要"
```
