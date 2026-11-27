"""Ad and tracker blocking via Qt WebEngine request interception."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

from superwebby.paths import bundled_blocklist, bundled_core_blocklist
from superwebby.youtube import is_youtube_ad

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

    def __init__(self, parent: QObject | None = None, high_speed: bool = False) -> None:
        super().__init__(parent)
        self.enabled = True
        self._lock = threading.Lock()
        self._by_page: dict[str, PageBlockStats] = {}
        self.total_blocked = 0
        self.youtube_blocked = 0
        # Callable(host) -> bool: favorite sites set to "relaxed" use the core list only.
        self.relaxed_for = lambda _host: False
        self.core_domains, self.core_version = _read_list(bundled_core_blocklist())
        self.full_domains: set[str] = set()
        self.full_version = ""
        self.high_speed = False
        self.domains: set[str] = self.core_domains
        self.set_high_speed(high_speed)

    def set_high_speed(self, on: bool) -> None:
        """High Speed: core list only, no path rules. YouTube ad rules stay on."""
        self.high_speed = bool(on)
        if not self.high_speed and not self.full_domains:
            self.full_domains, self.full_version = _read_list(bundled_blocklist())
            self.full_domains |= self.core_domains
        self.domains = self.core_domains if self.high_speed else self.full_domains

    @property
    def list_version(self) -> str:
        return self.core_version if self.high_speed else (self.full_version or self.core_version)

    def host_is_blocked(self, host: str) -> bool:
        return _match(host, self.domains)

    def _domains_for(self, first_host: str) -> set[str]:
        if first_host and not self.high_speed:
            try:
                if self.relaxed_for(first_host):
                    return self.core_domains
            except Exception:
                pass
        return self.domains

    def would_block(self, url: str, main_frame: bool = False, first_party: str = "") -> bool:
        if not main_frame and is_youtube_ad(url):
            return True
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        domains = self._domains_for(urlparse(first_party).hostname or "")
        if host and _match(host, domains):
            return True
        if main_frame or self.high_speed:
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
        full_url = url.toString()
        first_host = info.firstPartyUrl().host().lower()
        if not is_main and is_youtube_ad(full_url):
            blocked = True
            with self._lock:
                self.youtube_blocked += 1
        elif host and _match(host, self._domains_for(first_host)):
            blocked = True
        elif not is_main and not self.high_speed and not self.relaxed_for(first_host):
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


def _match(host: str, domains: set[str]) -> bool:
    host = (host or "").lower().rstrip(".")
    while host:
        if host in domains:
            return True
        if "." not in host:
            break
        host = host.split(".", 1)[1]
    return False


def _read_list(path) -> tuple[set[str], str]:
    domains: set[str] = set()
    version = ""
    if not path.is_file():
        return domains, version
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if line.lower().startswith("# version:"):
                    version = line.split(":", 1)[1].strip()
                continue
            domains.add(line.lower())
    return domains, version
