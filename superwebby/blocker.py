"""Ad and tracker blocking via Qt WebEngine request interception."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

from superwebby.paths import bundled_blocklist

# Conservative path signatures applied only to subresources, never the main frame.
PATH_RULES = (
    "/pagead/",
    "/pagead2/",
    "/pagead.js",
    "/ads/pixel",
    "/ads/beacon",
    "/ad-server/",
    "/adserver/",
    "/advertisement.",
    "/__utm.gif",
    "/google-analytics.com/",
    "/googlesyndication.com/",
    "/doubleclick.net/",
    "/amazon-adsystem.com/",
    "/adservice.google.",
    "/gtag/destination",
)


@dataclass
class PageBlockStats:
    hosts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    count: int = 0

    def record(self, host: str) -> None:
        self.hosts[host] += 1
        self.count += 1


class Blocker(QWebEngineUrlRequestInterceptor):
    """Thread-safe interceptor plus a UI-facing signal (queued)."""

    blocked = pyqtSignal(str, str)  # first-party url, blocked host
    tallied = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.enabled = True
        self.domains: set[str] = set()
        self._lock = threading.Lock()
        self._by_page: dict[str, PageBlockStats] = {}
        self.total_blocked = 0
        self._load_list()

    def _load_list(self) -> None:
        path = bundled_blocklist()
        if not path.is_file():
            return
        domains: set[str] = set()
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                domains.add(line.lower())
        self.domains = domains

    def host_is_blocked(self, host: str) -> bool:
        host = (host or "").lower().rstrip(".")
        while host:
            if host in self.domains:
                return True
            if "." not in host:
                break
            host = host.split(".", 1)[1]
        return False

    def would_block(self, url: str, main_frame: bool = False) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host and self.host_is_blocked(host):
            return True
        if main_frame:
            return False
        path = (parsed.path or "") + ("?" + parsed.query if parsed.query else "")
        lowered = (host + path).lower()
        return any(rule in lowered or rule in path.lower() for rule in PATH_RULES)

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        try:
            self._intercept(info)
        except Exception:
            # Never crash the WebEngine I/O thread.
            return

    def _intercept(self, info: QWebEngineUrlRequestInfo) -> None:
        if not self.enabled:
            return
        url = info.requestUrl()
        host = url.host().lower()
        first = info.firstPartyUrl().toString()
        try:
            rtype = info.resourceType()
        except Exception:
            rtype = None
        main_type = getattr(
            QWebEngineUrlRequestInfo.ResourceType, "ResourceTypeMainFrame", None
        )
        is_main = main_type is not None and rtype == main_type
        blocked = False
        if host and self.host_is_blocked(host):
            blocked = True
        elif not is_main:
            path = url.path()
            haystack = f"{host}{path}".lower()
            if any(rule in haystack for rule in PATH_RULES):
                blocked = True
        if not blocked:
            return
        info.block(True)
        origin = first or url.toString()
        with self._lock:
            stats = self._by_page.get(origin)
            if stats is None:
                stats = PageBlockStats()
                self._by_page[origin] = stats
            stats.record(host or url.toString())
            self.total_blocked += 1
        self.blocked.emit(origin, host or url.toString())

    def stats_for(self, page_url: str) -> PageBlockStats:
        with self._lock:
            stats = self._by_page.get(page_url)
            if stats is None:
                return PageBlockStats()
            return PageBlockStats(hosts=defaultdict(int, stats.hosts), count=stats.count)

    def reset_page(self, page_url: str) -> None:
        with self._lock:
            self._by_page.pop(page_url, None)
