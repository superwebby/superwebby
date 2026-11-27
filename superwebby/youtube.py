"""YouTube / YouTube Music ad blocking. Always on, including High Speed mode."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from superwebby.paths import data_dir

YOUTUBE_HOSTS = ("youtube.com", "music.youtube.com", "m.youtube.com", "youtube-nocookie.com")

# Hosts that serve only ads/ad measurement for YouTube.
AD_HOSTS = (
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "google-analytics.com",
    "googletagservices.com",
    "imasdk.googleapis.com",
    "pagead2.googlesyndication.com",
    "ad.youtube.com",
    "ads.youtube.com",
    "s.youtube.com",
)

# Path fragments on youtube.com / music.youtube.com / googlevideo.com.
AD_PATHS = (
    "/api/stats/ads",
    "/api/stats/atr",
    "/api/stats/qoe?adformat",
    "/pagead/",
    "/ptracking",
    "/get_midroll_",
    "/youtubei/v1/player/ad_break",
    "/youtubei/v1/log_event?alt=json&key=",  # ad impression logging
    "/generate_204?ad",
    "/pcs/activeview",
    "/csi_204",
    "/error_204?ad",
    "/ad_data_204",
)


def _host_match(host: str, suffixes: tuple[str, ...]) -> bool:
    host = (host or "").lower()
    return any(host == s or host.endswith("." + s) for s in suffixes)


def is_youtube_ad(url: str) -> bool:
    """True if the request is a YouTube ad or ad-telemetry request."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if _host_match(host, AD_HOSTS):
        return True
    path = parsed.path or ""
    query = parsed.query or ""
    full = path + ("?" + query if query else "")
    if _host_match(host, YOUTUBE_HOSTS) or host.endswith("googlevideo.com"):
        if any(frag in full for frag in AD_PATHS):
            return True
    if host.endswith("googlevideo.com") and query:
        params = parse_qs(query)
        # Ad video streams carry &oad= or ctier=L (and ad-specific "adformat").
        if "oad" in params or "adformat" in params:
            return True
        if params.get("ctier", [""])[0] == "L":
            return True
    return False


def userscript_source() -> str:
    path = data_dir() / "youtube_adblock.js"
    return path.read_text(encoding="utf-8") if path.is_file() else ""
