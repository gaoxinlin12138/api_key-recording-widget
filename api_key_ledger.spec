# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the portable, windowed API Key Ledger build."""

from PyInstaller.utils.hooks import collect_data_files

datas = [
    ("web", "web"),
    ("assets/app.ico", "assets"),
]
datas += collect_data_files("webview")
datas += collect_data_files("pythonnet")
datas += collect_data_files("clr_loader")

hiddenimports = [
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.mshtml",
    "pythonnet",
    "clr_loader",
    "clr_loader.util",
    "clr_loader.util.find",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="API钥匙簿",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/app.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="APIKeyLedger",
)
