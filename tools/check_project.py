"""项目自检：死代码 / 重复定义 / CSS 冗余。

用法：
    python tools/check_project.py            # 只报告，退出码 0
    python tools/check_project.py --strict   # 有 error 时退出码 1（CI 用）

error（会让 --strict 失败）：
  - core/ 或 tests/ 里存在未使用的顶层 import
  - 两个以上前端文件重复定义同名顶层常量

warning（只提示）：
  - CSS 里定义了但 HTML/JS 从不使用的类
  - 同一选择器被重复定义 4 次以上
  - 前端 export 出去但没有任何文件引用的函数/常量
"""

from __future__ import annotations

import ast
import re
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

    classes = sorted({c for c in re.findall(r"\.(-?[A-Za-z_][A-Za-z0-9_\-]*)", css)})
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


# ---------------------------------------------------------------- main
def main() -> int:
    check_python_imports()
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
