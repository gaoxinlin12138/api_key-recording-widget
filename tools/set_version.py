"""Set the application version from a release tag."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tools/set_version.py 1.2.3")
    version = sys.argv[1].strip().lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("version must look like 1.2.3")
    path = ROOT / "core" / "version.py"
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{version}"',
        text,
        count=1,
    )
    path.write_text(text, encoding="utf-8")
    print(f"version -> {version}")


if __name__ == "__main__":
    main()
