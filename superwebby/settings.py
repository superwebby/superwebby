"""User settings: favorite sites, per-site tweaks, and High Speed mode.

Stored as JSON in ~/.config/superwebby/settings.json. There is no wizard:
everything here is edited from superwebby://settings or the command line
(``superwebby --add-favorite example.com``).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from superwebby.paths import config_dir, data_dir

# Built-in per-site fixes, applied whenever the site is a favorite (and the
# dark-mode ones always). Keys are registrable hosts; subdomains match.
#   no_dark     forced dark mode breaks colors/canvases on this site
#   no_janitor  the cookie-banner janitor clicks something it should not
#   relaxed     use only the core ad/tracker list on this site (logins, players)
BUILTIN_SITE_FIXES: dict[str, dict[str, bool]] = {
    "docs.google.com": {"no_dark": True},
    "sheets.google.com": {"no_dark": True},
    "drive.google.com": {"no_dark": True},
    "figma.com": {"no_dark": True},
    "canva.com": {"no_dark": True},
    "photopea.com": {"no_dark": True},
    "maps.google.com": {"no_dark": True},
    "openstreetmap.org": {"no_dark": True},
    "excalidraw.com": {"no_dark": True},
    "accounts.google.com": {"no_janitor": True, "relaxed": True},
    "login.microsoftonline.com": {"no_janitor": True, "relaxed": True},
    "paypal.com": {"no_janitor": True, "relaxed": True},
    "stripe.com": {"no_janitor": True, "relaxed": True},
    "bankofamerica.com": {"no_janitor": True, "relaxed": True},
    "chase.com": {"no_janitor": True, "relaxed": True},
    "twitch.tv": {"relaxed": True},
    "spotify.com": {"relaxed": True},
    "netflix.com": {"relaxed": True},
}


@dataclass
class FavoriteSite:
    host: str
    title: str = ""
    pinned: bool = True
    no_dark: bool = False
    no_janitor: bool = False
    relaxed: bool = False


@dataclass
class Settings:
    favorites: list[FavoriteSite] = field(default_factory=list)
    high_speed: bool = False

    # ---- persistence -------------------------------------------------
    @staticmethod
    def path() -> Path:
        return config_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        data: dict = {}
        path = cls.path()
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
        else:
            data = _baked_defaults()
        favorites = []
        for raw in data.get("favorites", []) or []:
            if isinstance(raw, str):
                raw = {"host": raw}
            host = normalize_host(str(raw.get("host", "")))
            if not host:
                continue
            fav = FavoriteSite(host=host)
            for key in ("title", "pinned", "no_dark", "no_janitor", "relaxed"):
                if key in raw:
                    setattr(fav, key, raw[key])
            favorites.append(fav)
        settings = cls(favorites=favorites, high_speed=bool(data.get("high_speed", False)))
        if os.environ.get("SUPERWEBBY_HIGH_SPEED") == "1":
            settings.high_speed = True
        return settings

    def save(self) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "favorites": [asdict(f) for f in self.favorites],
            "high_speed": self.high_speed,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    # ---- favorites ---------------------------------------------------
    def add_favorite(self, text: str) -> FavoriteSite | None:
        host = normalize_host(text)
        if not host:
            return None
        for fav in self.favorites:
            if fav.host == host:
                return fav
        fav = FavoriteSite(host=host)
        # Pre-apply any known fixes so a new favorite works out of the box.
        for key, value in _builtin_for(host).items():
            setattr(fav, key, value)
        self.favorites.append(fav)
        return fav

    def remove_favorite(self, host: str) -> None:
        host = normalize_host(host)
        self.favorites = [f for f in self.favorites if f.host != host]

    def favorite_for(self, host: str) -> FavoriteSite | None:
        host = normalize_host(host)
        for fav in self.favorites:
            if host == fav.host or host.endswith("." + fav.host):
                return fav
        return None

    # ---- effective per-site policy -----------------------------------
    def tweaks_for(self, host: str) -> dict[str, bool]:
        host = normalize_host(host)
        result = {"no_dark": False, "no_janitor": False, "relaxed": False}
        builtin = _builtin_for(host)
        if builtin.get("no_dark"):
            result["no_dark"] = True
        fav = self.favorite_for(host)
        if fav is not None:
            result["no_dark"] = result["no_dark"] or fav.no_dark
            result["no_janitor"] = fav.no_janitor or bool(builtin.get("no_janitor"))
            result["relaxed"] = fav.relaxed
        elif builtin.get("no_janitor"):
            result["no_janitor"] = True
        return result

    def hosts_with(self, key: str) -> list[str]:
        hosts = set()
        for host, fixes in BUILTIN_SITE_FIXES.items():
            if fixes.get(key) and key != "relaxed":
                hosts.add(host)
        for fav in self.favorites:
            if getattr(fav, key, False):
                hosts.add(fav.host)
        return sorted(hosts)


def _builtin_for(host: str) -> dict[str, bool]:
    host = normalize_host(host)
    while host:
        if host in BUILTIN_SITE_FIXES:
            return BUILTIN_SITE_FIXES[host]
        if "." not in host:
            break
        host = host.split(".", 1)[1]
    return {}


def normalize_host(text: str) -> str:
    raw = (text or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    host = (urlparse(raw).hostname or "").rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if "." not in host and host != "localhost":
        return ""
    return host


def _baked_defaults() -> dict:
    """Favorites baked into a personalized build (data/favorites.json)."""
    baked = data_dir() / "favorites.json"
    if baked.is_file():
        try:
            data = json.loads(baked.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {}
