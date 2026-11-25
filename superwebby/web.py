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


def _inject_scripts(profile: QWebEngineProfile, cookie_janitor: bool) -> None:
    collection = profile.scripts()
    if cookie_janitor:
        js_path = bundled_cookie_js()
        if js_path.is_file():
            script = QWebEngineScript()
            script.setName("superwebby-cookie-janitor")
            script.setSourceCode(js_path.read_text(encoding="utf-8"))
            script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
            script.setRunsOnSubFrames(True)
            script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
            collection.insert(script)
    # Quiet the viewport and respect our dark chrome without site nags.
    css = QWebEngineScript()
    css.setName("superwebby-color-scheme")
    css.setSourceCode(
        """
        (function () {
          try {
            document.documentElement.style.colorScheme = "dark";
          } catch (e) {}
        })();
        """
    )
    css.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    css.setRunsOnSubFrames(True)
    css.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    collection.insert(css)


def apply_settings(settings: QWebEngineSettings) -> None:
    attr = QWebEngineSettings.WebAttribute
    settings.setAttribute(attr.JavascriptEnabled, True)
    settings.setAttribute(attr.JavascriptCanOpenWindows, True)
    settings.setAttribute(attr.LocalStorageEnabled, True)
    settings.setAttribute(attr.ErrorPageEnabled, True)
    settings.setAttribute(attr.FullScreenSupportEnabled, True)
    settings.setAttribute(attr.PluginsEnabled, False)
    settings.setAttribute(attr.DnsPrefetchEnabled, False)
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


def create_profile(blocker, incognito: bool = False) -> QWebEngineProfile:
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
    apply_settings(profile.settings())
    profile.setUrlRequestInterceptor(blocker)
    _inject_scripts(profile, cookie_janitor=True)
    # Keep a normal Chromium-family UA so sites work, but don't spoof Brave/Chrome brands.
    ua = profile.httpUserAgent()
    if "Superwebby" not in ua:
        profile.setHttpUserAgent(ua.replace("QtWebEngine", "Superwebby") + " Superwebby/1.0")
    return profile


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
        return True


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
