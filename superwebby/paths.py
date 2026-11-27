"""Filesystem locations for config, profile, and bundled data."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    return app_root() / "data"


def bundled_blocklist() -> Path:
    return data_dir() / "blocklist.txt"


def bundled_core_blocklist() -> Path:
    return data_dir() / "blocklist-core.txt"


def bundled_cookie_js() -> Path:
    return data_dir() / "cookie_banner.js"


IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

APP_DIR_NAME = "Superwebby"


def xdg_home(env_name: str, default: str) -> Path:
    raw = os.environ.get(env_name)
    if raw:
        return Path(raw).expanduser()
    return Path.home() / default


def _override(env_name: str) -> Path | None:
    """XDG_* variables win on every platform when set explicitly (used by --self-test)."""
    raw = os.environ.get(env_name)
    return Path(raw).expanduser() if raw else None


def _win_env_dir(env_name: str, fallback: str) -> Path:
    raw = os.environ.get(env_name)
    return Path(raw) if raw else Path.home() / fallback


def config_dir() -> Path:
    o = _override("XDG_CONFIG_HOME")
    if o is not None:
        return o / "superwebby"
    if IS_WINDOWS:
        return _win_env_dir("APPDATA", "AppData/Roaming") / APP_DIR_NAME
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME / "config"
    return xdg_home("XDG_CONFIG_HOME", ".config") / "superwebby"


def data_home() -> Path:
    o = _override("XDG_DATA_HOME")
    if o is not None:
        return o / "superwebby"
    if IS_WINDOWS:
        return _win_env_dir("LOCALAPPDATA", "AppData/Local") / APP_DIR_NAME
    if IS_MACOS:
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    return xdg_home("XDG_DATA_HOME", ".local/share") / "superwebby"


def cache_home() -> Path:
    o = _override("XDG_CACHE_HOME")
    if o is not None:
        return o / "superwebby"
    if IS_WINDOWS:
        return _win_env_dir("LOCALAPPDATA", "AppData/Local") / APP_DIR_NAME / "Cache"
    if IS_MACOS:
        return Path.home() / "Library" / "Caches" / APP_DIR_NAME
    return xdg_home("XDG_CACHE_HOME", ".cache") / "superwebby"


def _windows_downloads() -> Path | None:
    """Ask Windows for the real Downloads folder (it can be moved to another drive)."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
        fid = GUID(0x374DE290, 0x123F, 0x4565,
                   (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
        out = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        if shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) != 0:
            return None
        try:
            return Path(out.value) if out.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - any failure falls back to ~/Downloads
        return None


def downloads_dir() -> Path:
    raw = os.environ.get("XDG_DOWNLOAD_DIR")
    if raw:
        return Path(raw).expanduser()
    if IS_WINDOWS:
        return _windows_downloads() or Path.home() / "Downloads"
    if IS_MACOS:
        return Path.home() / "Downloads"
    # Honor user-dirs if present, otherwise ~/Downloads.
    user_dirs = xdg_home("XDG_CONFIG_HOME", ".config") / "user-dirs.dirs"
    if user_dirs.is_file():
        for line in user_dirs.read_text(errors="ignore").splitlines():
            if line.startswith("XDG_DOWNLOAD_DIR="):
                value = line.split("=", 1)[1].strip().strip('"')
                value = value.replace("$HOME", str(Path.home()))
                return Path(value)
    return Path.home() / "Downloads"


def profile_dir(incognito: bool = False) -> Path:
    if incognito:
        return cache_home() / "incognito-tmp"
    return data_home() / "profile"


def platform_label() -> str:
    """Human-readable build/platform line for the about page."""
    import platform

    machine = platform.machine() or "?"
    if IS_WINDOWS:
        name = f"Windows {platform.release()}"
    elif IS_MACOS:
        name = f"macOS {platform.mac_ver()[0] or '?'}"
    elif os.environ.get("FLATPAK_ID") or Path("/.flatpak-info").exists():
        name = "Linux (Flatpak)"
    else:
        name = "Linux"
    kind = "prebuilt binary" if getattr(sys, "frozen", False) else "from source"
    return f"{name}, {machine}, {kind}. Builds: Linux (AUR, Flatpak, tarball), Windows (installer, portable zip), macOS (.dmg, Apple Silicon and Intel)."
