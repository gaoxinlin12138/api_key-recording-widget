"""Optional Windows clipboard watcher.

It only wakes up when the clipboard sequence number changes, ignores text
larger than a small limit, and hands the text to a callback.  The callback is
responsible for recognising keys and for never persisting unrelated text.
"""

from __future__ import annotations

import ctypes
import hashlib
import sys
import threading
import time
from ctypes import wintypes
from typing import Callable

CF_UNICODETEXT = 13
MAX_CLIPBOARD_CHARS = 16_000

if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.argtypes = []
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.GetClipboardData.argtypes = [wintypes.UINT]
    _user32.GetClipboardData.restype = wintypes.HANDLE
    _user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    _user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    _user32.GetClipboardSequenceNumber.argtypes = []
    _user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalLock.restype = wintypes.LPVOID
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalUnlock.restype = wintypes.BOOL


def _read_clipboard() -> str | None:
    if sys.platform != "win32":
        return None
    if not _user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    if not _user32.OpenClipboard(None):
        return None
    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            # Read until the NUL terminator.  Passing a fixed size would read
            # past the string and append unrelated heap contents.
            text = ctypes.wstring_at(pointer)
            return text.split("\x00", 1)[0][:MAX_CLIPBOARD_CHARS]
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()


class ClipboardWatcher:
    def __init__(self, callback: Callable[[str], None]):
        self._callback = callback
        self._enabled = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_hash = ""
        self._last_sequence = 0
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return sys.platform == "win32"

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)
        if enabled:
            self.start()

    def start(self) -> None:
        if not self.available:
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="clipboard-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self.enabled:
                self._stop.wait(0.8)
                continue
            try:
                sequence = _user32.GetClipboardSequenceNumber()
                if sequence == self._last_sequence:
                    self._stop.wait(0.7)
                    continue
                self._last_sequence = sequence
                text = _read_clipboard()
                if not text:
                    self._stop.wait(0.7)
                    continue
                digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
                if digest == self._last_hash:
                    self._stop.wait(0.7)
                    continue
                self._last_hash = digest
                self._callback(text)
            except Exception:  # noqa: BLE001 - a clipboard read must never kill the app
                pass
            self._stop.wait(0.7)
