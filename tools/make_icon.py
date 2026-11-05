"""从 assets/app.svg 生成 assets/app.ico（多尺寸）。

只在需要改图标时手动运行，**不参与打包**。

依赖：
    - Pillow（渲染后缩放与写 ICO）
    - Chrome 或 Edge（把 SVG 栅格化；脚本里改 CHROME 路径即可）

用法：
    python tools/make_icon.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SIZES = [16, 24, 32, 48, 64, 128, 256]
BASE = 1024
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> str:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    raise SystemExit("没有找到 Chrome/Edge，无法把 SVG 栅格化。")


def render(svg: str, out: Path) -> Path:
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      html,body{{margin:0;padding:0;background:transparent;overflow:hidden}}
      svg{{display:block;width:{BASE}px;height:{BASE}px}}
    </style></head><body>{svg}</body></html>"""
    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    subprocess.run(
        [
            find_browser(),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--default-background-color=00000000",
            f"--window-size={BASE},{BASE}",
            f"--screenshot={out}",
            page.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    return out


def main() -> int:
    svg = (ROOT / "assets" / "app.svg").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        base = Image.open(render(svg, Path(tmp) / "icon.png")).convert("RGBA")
    if base.size != (BASE, BASE):
        print(f"渲染尺寸不对：{base.size}", file=sys.stderr)
        return 1
    # 圆角外侧本来就透明，检查四条边的中点确认背景铺满
    for point in [(BASE // 2, 8), (BASE // 2, BASE - 9), (8, BASE // 2), (BASE - 9, BASE // 2)]:
        if base.getpixel(point)[3] < 200:
            print(f"背景没铺满：{point}", file=sys.stderr)
            return 1

    target = ROOT / "assets" / "app.ico"
    base.save(target, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"{target.relative_to(ROOT)} -> {target.stat().st_size} bytes ({len(SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
