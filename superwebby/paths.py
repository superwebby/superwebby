"""Filesystem locations for config, profile, and bundled data."""

from __future__ import annotations

import os
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


def xdg_home(env_name: str, default: str) -> Path:
    raw = os.environ.get(env_name)
    if raw:
        return Path(raw).expanduser()
    return Path.home() / default


def config_dir() -> Path:
    return xdg_home("XDG_CONFIG_HOME", ".config") / "superwebby"


def data_home() -> Path:
    return xdg_home("XDG_DATA_HOME", ".local/share") / "superwebby"


def cache_home() -> Path:
    return xdg_home("XDG_CACHE_HOME", ".cache") / "superwebby"


def downloads_dir() -> Path:
    raw = os.environ.get("XDG_DOWNLOAD_DIR")
    if raw:
        return Path(raw).expanduser()
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
