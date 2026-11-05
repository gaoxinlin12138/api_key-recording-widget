"""项目自检：死代码 / 重复定义 / CSS 冗余。

用法：
    python tools/check_project.py            # 只报告，退出码 0
    python tools/check_project.py --strict   # 有 error 时退出码 1（CI 用）

error（会让 --strict 失败）：
  - core/ 或 tests/ 里存在未使用的顶层 import
  - 两个以上前端文件重复定义同名顶层常量
  - web/js/*.js 存在语法错误（需本机有 node；没有则跳过）
  - 前端文件带 UTF-8 BOM 或含替换字符（U+FFFD）

warning（只提示）：
  - CSS 里定义了但 HTML/JS 从不使用的类
  - 同一选择器被重复定义 4 次以上
  - 前端 export 出去但没有任何文件引用的函数/常量
"""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
JS_FILES = sorted((WEB / "js").glob("*.js"))

errors: list[str] = []
warnings: list[str] = []


# ---------------------------------------------------------------- Python
def check_python_imports() -> None:
    for path in sorted((ROOT / "core").glob("*.py")) + sorted((ROOT / "tests").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported[(alias.asname or alias.name).split(".")[0]] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        imported[alias.asname or alias.name] = node.lineno
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for name, lineno in imported.items():
            if name == "annotations":
                continue
            if name not in used and source.count(name) <= 1:
                errors.append(f"{path.relative_to(ROOT)}:{lineno} 未使用的 import `{name}`")


# ---------------------------------------------------------------- JS
def read_js() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in JS_FILES}


def check_js_duplicate_consts(sources: dict[str, str]) -> None:
    owners: dict[str, list[str]] = {}
    for name, text in sources.items():
        for match in re.finditer(r"^(?:export )?const ([A-Z][A-Z0-9_]*)\s*=", text, re.M):
            owners.setdefault(match.group(1), []).append(name)
    for const, files in owners.items():
        if len(files) > 1:
            errors.append(f"顶层常量 `{const}` 重复定义于 {', '.join(files)}")


def check_js_unused_exports(sources: dict[str, str]) -> None:
    exports: list[tuple[str, str]] = []
    for name, text in sources.items():
        for match in re.finditer(
            r"^export (?:async )?(?:function|const) ([A-Za-z_$][\w$]*)", text, re.M
        ):
            exports.append((match.group(1), name))
    for symbol, owner in exports:
        refs = 0
        for name, text in sources.items():
            if name == owner:
                refs += len(re.findall(rf"\b{re.escape(symbol)}\b", text)) - 1
            else:
                refs += len(re.findall(rf"\b{re.escape(symbol)}\b", text))
        if refs <= 0:
            warnings.append(f"web/js/{owner} 导出的 `{symbol}` 没有任何引用")


# ---------------------------------------------------------------- CSS
def check_css(sources: dict[str, str]) -> None:
    css_path = WEB / "styles.css"
    css = css_path.read_text(encoding="utf-8")
    corpus = (WEB / "index.html").read_text(encoding="utf-8") + "\n" + "\n".join(sources.values())

    # data:image/svg+xml 里的 URL 片段会产生误报（如 xmlns 里的 org / w3），先剔除
    css_for_classes = re.sub(r"url\([^)]*\)", "", css)
    classes = sorted({c for c in re.findall(r"\.(-?[A-Za-z_][A-Za-z0-9_\-]*)", css_for_classes)})
    unused = [
        c for c in classes
        if not re.search(rf"(?<![\w-]){re.escape(c)}(?![\w-])", corpus)
    ]
    if unused:
        preview = ", ".join(unused[:12]) + (" …" if len(unused) > 12 else "")
        warnings.append(f"styles.css 有 {len(unused)} 个未使用类：{preview}")

    counters: Counter[str] = Counter()
    for match in re.finditer(r"(?m)^([.#][^{\r\n,]+?)\s*\{", css):
        counters[match.group(1).strip()] += 1
    noisy = [(sel, n) for sel, n in counters.most_common(6) if n > 3]
    for sel, count in noisy:
        warnings.append(f"选择器 `{sel}` 被重复定义 {count} 次")


def check_views_render() -> None:
    """跑 tools/check_views.mjs，验证四个视图在有/无数据下都能渲染。"""
    node = shutil.which("node")
    script = ROOT / "tools" / "check_views.mjs"
    if not node or not script.exists():
        warnings.append("未找到 node 或 check_views.mjs，跳过前端渲染检查")
        return
    result = subprocess.run(
        [node, str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        first = detail[0] if detail else "渲染失败"
        errors.append(f"前端渲染检查失败：{first}")


def check_js_syntax() -> None:
    """用 node --check 解析前端模块，并拦住 BOM / 替换字符 / 典型乱码。

    背景：2026-11-05 发 1.3.1 时，用 PowerShell 的 Get-Content/Set-Content
    对 views.js 做版本号替换，文件被按 GBK 读入再以 UTF-8 写出，中文变成乱码、
    JS 语法被破坏，导致安装后卡在启动画面。仅靠 Python 测试发现不了。
    """
    node = shutil.which("node")
    for path in JS_FILES:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            errors.append(f"web/js/{path.name} 带 UTF-8 BOM（应为无 BOM 的 UTF-8）")
        text = raw.decode("utf-8", errors="replace")
        if "\ufffd" in text:
            errors.append(f"web/js/{path.name} 含替换字符 U+FFFD（疑似编码损坏）")
        if looks_mojibake(text):
            errors.append(
                f"web/js/{path.name} 疑似编码损坏（GBK/UTF-8 混淆，中文已成乱码）"
            )
    if not node:
        warnings.append("未找到 node，跳过 JS 语法检查")
        return
    for path in JS_FILES:
        result = subprocess.run(
            [node, "--check", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            detail = next(
                (line.strip() for line in (result.stderr or "").splitlines() if line.strip()),
                "解析失败",
            )
            errors.append(f"web/js/{path.name} 语法错误：{detail}")


#: UTF-8 中文被当成 GBK 解码后，几乎必然出现的标志性汉字
MOJIBAKE_MARKERS = ("锛", "鍏", "鐢", "閽", "銆", "鍜", "浣", "鏄", "缁", "浠", "鏂")


def looks_mojibake(text: str) -> bool:
    hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    return hits >= 3


def check_text_files() -> None:
    """同一套乱码检测也覆盖 HTML/CSS/Markdown，避免同类事故从别的文件溜进来。"""
    extras = [WEB / "index.html", WEB / "styles.css", WEB / "favicon.svg"]
    extras += [ROOT / "README.md", ROOT / "CHANGELOG.md"]
    for path in extras:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if looks_mojibake(text):
            errors.append(f"{path.relative_to(ROOT)} 疑似编码损坏（中文已成乱码）")


# ---------------------------------------------------------------- main
def main() -> int:
    # Windows 上的 CI 控制台可能不是 UTF-8（cp1252/cp936），直接 print 中文会抛
    # UnicodeEncodeError 并把退出码变成 1。这里强制用 UTF-8，无法编码时降级替换。
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    check_python_imports()
    check_js_syntax()
    check_text_files()
    check_views_render()
    sources = read_js()
    check_js_duplicate_consts(sources)
    check_js_unused_exports(sources)
    check_css(sources)

    print("== 项目自检 ==")
    if errors:
        print(f"\n[ERROR] {len(errors)} 项")
        for item in errors:
            print("  - " + item)
    else:
        print("\n[ERROR] 0 项")
    if warnings:
        print(f"\n[WARN] {len(warnings)} 项（历史遗留，逐批收敛）")
        for item in warnings[:20]:
            print("  - " + item)
        if len(warnings) > 20:
            print(f"  … 另有 {len(warnings) - 20} 项")
    else:
        print("\n[WARN] 0 项")

    if "--strict" in sys.argv and errors:
        print("\n严格模式：存在 ERROR，退出码 1")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
