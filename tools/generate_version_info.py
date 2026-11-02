"""Generate PyInstaller's Windows version resource from core/version.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.version import __version__  # noqa: E402


def main() -> None:
    parts = [int(part) for part in __version__.split(".")]
    parts = (parts + [0, 0, 0, 0])[:4]
    tuple_text = ", ".join(str(part) for part in parts)
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({tuple_text}),
    prodvers=({tuple_text}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'080404B0',
          [StringStruct(u'CompanyName', u'API Key Ledger'),
           StringStruct(u'FileDescription', u'API Key Ledger desktop application'),
           StringStruct(u'FileVersion', u'{__version__}'),
           StringStruct(u'InternalName', u'APIKeyLedger'),
           StringStruct(u'LegalCopyright', u''),
           StringStruct(u'OriginalFilename', u'APIKeyLedger.exe'),
           StringStruct(u'ProductName', u'API Key Ledger'),
           StringStruct(u'ProductVersion', u'{__version__}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
"""
    (ROOT / "version_info.txt").write_text(content, encoding="utf-8")
    print(f"version_info.txt -> {__version__}")


if __name__ == "__main__":
    main()
