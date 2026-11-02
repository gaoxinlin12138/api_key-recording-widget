"""Windows DPAPI encryption for API keys.

The encryption is bound to the current Windows user on this computer.  It is
deliberately password-less: starting the tool does not ask for a master
password, but a copied database cannot be decrypted by another Windows user.
"""

from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes

_ENTROPY = b"ApiKeyLedger/v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1

if sys.platform == "win32":
    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptProtectData.restype = wintypes.BOOL

    _crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    _crypt32.CryptUnprotectData.restype = wintypes.BOOL

    _kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    _kernel32.LocalFree.restype = ctypes.c_void_p


def _make_blob(data: bytes) -> tuple["_DATA_BLOB", ctypes.Array]:
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB(
        cbData=len(data),
        pbData=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)),
    )
    return blob, buffer


def _read_and_free(blob: "_DATA_BLOB") -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        if blob.pbData:
            _kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))


def protect(secret: str) -> str:
    """Encrypt a secret and return a base64 string suitable for SQLite."""
    if sys.platform != "win32":
        raise RuntimeError("API Key 加密目前仅支持 Windows。")
    raw = (secret or "").encode("utf-8")
    if not raw:
        raise ValueError("API Key 不能为空。")

    data_in, data_buffer = _make_blob(raw)
    entropy_in, entropy_buffer = _make_blob(_ENTROPY)
    data_out = _DATA_BLOB()
    ok = _crypt32.CryptProtectData(
        ctypes.byref(data_in),
        "ApiKeyLedger",
        ctypes.byref(entropy_in),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(data_out),
    )
    # Keep the input buffers alive until the call has returned.
    _ = (data_buffer, entropy_buffer)
    if not ok:
        raise OSError(f"Windows 加密失败（错误码 {ctypes.get_last_error()}）。")
    return base64.b64encode(_read_and_free(data_out)).decode("ascii")


def unprotect(token: str) -> str:
    """Decrypt a value produced by :func:`protect`."""
    if sys.platform != "win32":
        raise RuntimeError("API Key 解密目前仅支持 Windows。")
    try:
        raw = base64.b64decode(token.encode("ascii"), validate=True)
    except Exception as exc:  # noqa: BLE001 - convert to a clear local error
        raise ValueError("API Key 密文格式不正确。") from exc

    data_in, data_buffer = _make_blob(raw)
    entropy_in, entropy_buffer = _make_blob(_ENTROPY)
    data_out = _DATA_BLOB()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(data_in),
        None,
        ctypes.byref(entropy_in),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(data_out),
    )
    _ = (data_buffer, entropy_buffer)
    if not ok:
        raise OSError(
            "无法解密这个 API Key。它可能是在另一台电脑或另一个 Windows 账户下保存的。"
        )
    return _read_and_free(data_out).decode("utf-8")
