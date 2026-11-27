"""Web profile, page, and view setup — no telemetry, no permission nags."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
    QWebEngineSettings,
    QWebEngineUrlScheme,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QMenu

from superwebby import __version__
from superwebby.paths import bundled_cookie_js, cache_home, downloads_dir, profile_dir


SCHEME_NAME = b"superwebby"


def register_scheme() -> None:
    """Must run before QApplication / any WebEngine object is created."""
    already = False
    try:
        # scheme() lookup may throw if unregistered depending on Qt version
        existing = QWebEngineUrlScheme.schemeByName(SCHEME_NAME)
        already = bytes(existing.name()) == SCHEME_NAME
    except Exception:
        already = False
    if already:
        return
    scheme = QWebEngineUrlScheme(SCHEME_NAME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Path)
    scheme.setDefaultPort(-1)
    flags = (
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.CorsEnabled
        | QWebEngineUrlScheme.Flag.FetchApiAllowed
        | QWebEngineUrlScheme.Flag.ViewSourceAllowed
    )
    scheme.setFlags(flags)
    QWebEngineUrlScheme.registerScheme(scheme)


SCRIPT_NAMES = ("superwebby-cookie-janitor", "superwebby-color-scheme", "superwebby-youtube-adblock")


def _host_guard(hosts: list[str]) -> str:
    """JS prelude that returns early on the given hosts (and their subdomains)."""
    import json

    return (
        "var __swSkip = %s; var __swH = location.hostname.replace(/^www\\./, '');"
        "for (var __i = 0; __i < __swSkip.length; __i++) {"
        "  var __d = __swSkip[__i];"
        "  if (__swH === __d || __swH.slice(-(__d.length + 1)) === '.' + __d) return;"
        "}" % json.dumps(hosts)
    )


def _script(name: str, source: str, point, subframes: bool = True) -> QWebEngineScript:
    script = QWebEngineScript()
    script.setName(name)
    script.setSourceCode(source)
    script.setInjectionPoint(point)
    script.setRunsOnSubFrames(subframes)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    return script


def refresh_scripts(profile: QWebEngineProfile, settings=None) -> None:
    """(Re)install injected scripts. Safe to call whenever settings change."""
    collection = profile.scripts()
    for name in SCRIPT_NAMES:
        for existing in collection.find(name):
            collection.remove(existing)
    high_speed = bool(settings and settings.high_speed)
    no_janitor = settings.hosts_with("no_janitor") if settings else []
    no_dark = settings.hosts_with("no_dark") if settings else []
    # YouTube / YouTube Music ad removal: every build, every mode.
    from superwebby.youtube import userscript_source

    yt = userscript_source()
    if yt:
        collection.insert(
            _script("superwebby-youtube-adblock", yt, QWebEngineScript.InjectionPoint.DocumentCreation, False)
        )
    # Cookie-banner janitor: off in High Speed mode, skipped on exempt sites.
    if not high_speed:
        js_path = bundled_cookie_js()
        if js_path.is_file():
            body = js_path.read_text(encoding="utf-8")
            source = "(function(){" + _host_guard(no_janitor) + "\n" + body + "\n})();"
            collection.insert(
                _script("superwebby-cookie-janitor", source, QWebEngineScript.InjectionPoint.DocumentReady)
            )
    css = (
        "(function () {" + _host_guard(no_dark) +
        " try { document.documentElement.style.colorScheme = 'dark'; } catch (e) {} })();"
    )
    collection.insert(
        _script("superwebby-color-scheme", css, QWebEngineScript.InjectionPoint.DocumentCreation)
    )


def apply_settings(settings: QWebEngineSettings, high_speed: bool = False) -> None:
    attr = QWebEngineSettings.WebAttribute
    settings.setAttribute(attr.JavascriptEnabled, True)
    settings.setAttribute(attr.JavascriptCanOpenWindows, True)
    settings.setAttribute(attr.LocalStorageEnabled, True)
    settings.setAttribute(attr.ErrorPageEnabled, True)
    settings.setAttribute(attr.FullScreenSupportEnabled, True)
    settings.setAttribute(attr.PluginsEnabled, False)
    # High Speed mode turns DNS prefetch on; normal mode keeps it off for privacy.
    settings.setAttribute(attr.DnsPrefetchEnabled, bool(high_speed))
    settings.setAttribute(attr.HyperlinkAuditingEnabled, False)
    settings.setAttribute(attr.XSSAuditingEnabled, True)
    settings.setAttribute(attr.FocusOnNavigationEnabled, False)
    settings.setAttribute(attr.PdfViewerEnabled, True)
    settings.setAttribute(attr.PlaybackRequiresUserGesture, True)
    settings.setAttribute(attr.WebRTCPublicInterfacesOnly, True)
    settings.setAttribute(attr.ScreenCaptureEnabled, False)
    if hasattr(attr, "ForceDarkMode"):
        settings.setAttribute(attr.ForceDarkMode, True)
    if hasattr(attr, "AllowGeolocationOnInsecureOrigins"):
        settings.setAttribute(attr.AllowGeolocationOnInsecureOrigins, False)


def create_profile(blocker, incognito: bool = False, settings=None) -> QWebEngineProfile:
    if incognito:
        profile = QWebEngineProfile(None)
    else:
        storage = str(profile_dir(False))
        profile = QWebEngineProfile("superwebby", None)
        profile.setPersistentStoragePath(storage)
        profile.setCachePath(str(cache_home() / "web"))
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    try:
        profile.setPushServiceEnabled(False)
    except Exception:
        pass
    try:
        profile.setSpellCheckEnabled(False)
    except Exception:
        pass
    try:
        policy = QWebEngineProfile.PersistentPermissionsPolicy.StoreInMemory
        profile.setPersistentPermissionsPolicy(policy)
    except Exception:
        pass
    downloads_dir().mkdir(parents=True, exist_ok=True)
    try:
        profile.setDownloadPath(str(downloads_dir()))
    except Exception:
        pass
    profile._superwebby_settings = settings
    _install_cookie_filter(profile, settings)
    apply_settings(profile.settings(), high_speed=bool(settings and settings.high_speed))
    profile.setUrlRequestInterceptor(blocker)
    refresh_scripts(profile, settings)
    # Keep a normal Chromium-family UA so sites work, but don't spoof Brave/Chrome brands.
    ua = profile.httpUserAgent()
    if "Superwebby" not in ua:
        profile.setHttpUserAgent(ua.replace("QtWebEngine", "Superwebby") + " Superwebby/" + __version__)
    return profile


def _install_cookie_filter(profile: QWebEngineProfile, settings) -> None:
    """Refuse third-party cookies, except on favorite sites marked "relaxed"."""

    def accept(request) -> bool:
        try:
            if not request.thirdParty:
                return True
            if settings is not None:
                first = request.firstPartyUrl.host()
                if first and settings.tweaks_for(first)["relaxed"]:
                    return True
            return False
        except Exception:
            return True

    try:
        profile.cookieStore().setCookieFilter(accept)
        profile._superwebby_cookie_filter = accept  # keep a reference alive
    except Exception:
        profile._superwebby_cookie_filter = None


class WebPage(QWebEnginePage):
    new_tab_requested = pyqtSignal(QWebEnginePage, object)
    fullscreen_requested = pyqtSignal(QWebEnginePage, bool)
    link_in_new_tab = pyqtSignal(QUrl)

    def __init__(self, profile: QWebEngineProfile, window, parent=None) -> None:
        super().__init__(profile, parent)
        self.window = window
        self.featurePermissionRequested.connect(self._deny_quietly)
        self.fullScreenRequested.connect(self._fullscreen)

    def _deny_quietly(self, origin: QUrl, feature) -> None:
        grant = QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        # Clipboard is part of normal page use; allow it without a prompt.
        if feature == QWebEnginePage.Feature.ClipboardReadWrite:
            grant = QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
        self.setFeaturePermission(origin, feature, grant)

    def _fullscreen(self, request) -> None:
        try:
            accept = request.toggleOn()
            request.accept()
        except Exception:
            accept = False
        self.fullscreen_requested.emit(self, bool(accept))

    def _new_window_requested(self, request) -> None:
        # Handled in createWindow; accept if still pending on some Qt versions.
        try:
            dest = request.requestedUrl()
            if dest.isValid() and not dest.isEmpty():
                self.link_in_new_tab.emit(dest)
        except Exception:
            pass

    def createWindow(self, wintype):  # noqa: N802
        background = wintype == QWebEnginePage.WebWindowType.WebBrowserBackgroundTab
        page = self.window.allocate_tab(background=background)
        return page

    def javaScriptAlert(self, security_origin: QUrl, msg: str) -> None:  # noqa: N802
        # Swallow nothing harmful — still show alerts, but never a browser-level nag.
        super().javaScriptAlert(security_origin, msg)

    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame: bool) -> bool:  # noqa: N802
        if is_main_frame:
            self._apply_site_tweaks(url)
        return True

    def _apply_site_tweaks(self, url: QUrl) -> None:
        """Per-site fixes: turn forced dark mode off where it breaks a site."""
        settings = getattr(self.profile(), "_superwebby_settings", None)
        if settings is None:
            return
        attr = QWebEngineSettings.WebAttribute
        if not hasattr(attr, "ForceDarkMode"):
            return
        tweaks = settings.tweaks_for(url.host())
        try:
            self.settings().setAttribute(attr.ForceDarkMode, not tweaks["no_dark"])
        except Exception:
            pass


class WebView(QWebEngineView):
    midclick_new_tab = pyqtSignal(QUrl)

    def __init__(self, page: WebPage, parent=None) -> None:
        super().__init__(parent)
        self.setPage(page)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def createWindow(self, wintype):  # noqa: N802
        page = self.page().createWindow(wintype)
        return page.view() if page is not None else None

    def _menu(self, pos) -> None:
        page = self.page()
        data = page.contextMenuData() if hasattr(page, "contextMenuData") else None
        menu = QMenu(self)
        link = QUrl()
        if data is not None:
            try:
                link = data.linkUrl()
            except Exception:
                link = QUrl()
        if link.isValid() and not link.isEmpty():
            open_tab = QAction("Open link in new tab", menu)
            open_tab.triggered.connect(lambda: self.midclick_new_tab.emit(link))
            copy_link = QAction("Copy link address", menu)
            copy_link.triggered.connect(lambda: _copy(link.toString()))
            menu.addAction(open_tab)
            menu.addAction(copy_link)
            menu.addSeparator()
        menu.addAction(page.action(QWebEnginePage.WebAction.Back))
        menu.addAction(page.action(QWebEnginePage.WebAction.Forward))
        menu.addAction(page.action(QWebEnginePage.WebAction.Reload))
        menu.addSeparator()
        menu.addAction(page.action(QWebEnginePage.WebAction.Copy))
        menu.addAction(page.action(QWebEnginePage.WebAction.Paste))
        menu.addAction(page.action(QWebEnginePage.WebAction.SelectAll))
        menu.addSeparator()
        inspect = QAction("View page source", menu)
        inspect.triggered.connect(
            lambda: self.midclick_new_tab.emit(QUrl("view-source:" + self.url().toString()))
        )
        menu.addAction(inspect)
        menu.exec(self.mapToGlobal(pos))


def _copy(text: str) -> None:
    from PyQt6.QtWidgets import QApplication

    QApplication.clipboard().setText(text)
