"""Main browser window, shortcuts, tabs, and panels."""

from __future__ import annotations

from urllib.parse import quote_plus, urlparse
import re

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWidgets import (
    QCompleter,
    QMenu,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from superwebby.downloads import DownloadsPanel
from superwebby.history import HistoryStore
from superwebby.palette import CommandPalette, PaletteItem
from superwebby.pages import SuperwebbySchemeHandler
from superwebby.theme import ACCENT, MUTED, TEXT
from superwebby.web import WebPage, WebView

NEWTAB = "superwebby://newtab"
GITHUB_URL = "https://github.com/superwebby/superwebby"
DIRTY_BROWSER = "Dirty Browser"
HIGH_SPEED = "High Speed"
_PRIVATE_PROFILE = None  # one shared off-the-record profile for Dirty Browser windows
SEARCH = "https://duckduckgo.com/?q={query}"
URLISH = re.compile(
    r"^(localhost(:\d+)?([/?#].*)?|"
    r"(\d{1,3}\.){3}\d{1,3}(:\d+)?([/?#].*)?|"
    r"[a-zA-Z][a-zA-Z0-9+\-.]*://.*|"
    r"([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(:\d+)?([/?#].*)?)$"
)


def interpret_input(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return NEWTAB
    if raw.startswith("superwebby://") or raw.startswith("view-source:"):
        return raw
    if raw.startswith("file:"):
        return raw
    if raw.startswith("//"):
        return "https:" + raw
    if URLISH.match(raw) and " " not in raw:
        if "://" not in raw:
            return "https://" + raw
        return raw
    return SEARCH.format(query=quote_plus(raw))



class BrowserTab(QWidget):
    """A tab that can show either a native internal page or a WebEngine view."""

    def __init__(self, page: WebPage, window: "BrowserWindow", parent=None) -> None:
        super().__init__(parent)
        self.browser_window = window
        self.page = page
        self.view = WebView(page, self)
        self.view._loading = False
        self.internal = None  # set after InternalPage import
        from superwebby.internal import InternalPage

        self.internal = InternalPage(window, self)
        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.internal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stack, 1)
        self.internal.navigate.connect(window.navigate)
        self.internal.title_changed.connect(lambda title: window._title_changed(self, title))

    def is_internal(self) -> bool:
        return self.stack.currentWidget() is self.internal

    def url_string(self) -> str:
        if self.is_internal():
            return self.internal.current
        return self.view.url().toString()

    def title_string(self) -> str:
        if self.is_internal():
            return self.view.windowTitle() or "New Tab"
        return self.view.title() or "New Tab"

    def show_internal(self, url: str) -> None:
        self.internal.show_url(url)
        self.stack.setCurrentWidget(self.internal)

    def show_web(self, url: str) -> None:
        self.view.setUrl(QUrl(url))
        self.stack.setCurrentWidget(self.view)

    def go_internal_or_web(self, url: str) -> None:
        if url.startswith("superwebby://"):
            self.show_internal(url)
        else:
            self.show_web(url)


class BrowserWindow(QMainWindow):
    def __init__(self, profile, blocker, history: HistoryStore, icon: QIcon, incognito: bool = False, settings=None) -> None:
        super().__init__()
        if settings is None:
            from superwebby.settings import Settings

            settings = Settings.load()
        self.settings = settings
        self._pending_urls: dict[int, str] = {}
        self.profile = profile
        self.blocker = blocker
        self.history = history
        self.incognito = incognito
        self.setWindowTitle("Superwebby" + (f" ({DIRTY_BROWSER} · Private)" if incognito else ""))
        self.setWindowIcon(icon)
        self.setMinimumSize(900, 600)
        self.resize(1280, 820)
        self._zoom = 1.0
        self._fullscreen_view: WebView | None = None

        self.scheme_handler = SuperwebbySchemeHandler(self, self)
        profile.installUrlSchemeHandler(b"superwebby", self.scheme_handler)

        root = QWidget(self)
        self.setCentralWidget(root)
        self.vbox = QVBoxLayout(root)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)

        self._build_toolbar()
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.tabCloseRequested.connect(self._close_tab_at)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabBarDoubleClicked.connect(self._tabbar_dblclick)
        self.vbox.addWidget(self.tabs, 1)

        self.findbar = self._build_findbar()
        self.vbox.addWidget(self.findbar)

        self.downloads = DownloadsPanel(self)
        self.vbox.addWidget(self.downloads)
        profile.downloadRequested.connect(self._on_download)

        self.history_panel = self._build_history_panel()
        self.vbox.addWidget(self.history_panel)

        self.palette = CommandPalette(root)
        self._bind_shortcuts()
        self.blocker.blocked.connect(lambda *_: self._refresh_shield())

        self._progress = 0
        self._badge_timer = QTimer(self)
        self._badge_timer.setInterval(400)
        self._badge_timer.timeout.connect(self._refresh_shield)
        self._badge_timer.start()

    # --- construction -------------------------------------------------
    def _build_toolbar(self) -> None:
        bar = QToolBar("Navigation")
        bar.setMovable(False)
        bar.setIconSize(QSize(16, 16))
        bar.setFloatable(False)
        self.addToolBar(bar)
        self.toolbar = bar

        def tb(text: str, tip: str, slot, checkable: bool = False) -> QToolButton:
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.setAutoRaise(True)
            btn.setCheckable(checkable)
            btn.clicked.connect(slot)
            bar.addWidget(btn)
            return btn

        self.back_btn = tb("‹", "Back  (Alt+Left)", self.go_back)
        self.fwd_btn = tb("›", "Forward  (Alt+Right)", self.go_forward)
        self.reload_btn = tb("↻", "Reload  (Ctrl+R)", self.reload)
        tb("Home", "New tab page  (Alt+Home)", lambda: self.navigate(NEWTAB))

        self.omnibox = QLineEdit()
        self.omnibox.setObjectName("omnibox")
        self.omnibox.setPlaceholderText("Search or enter address")
        self.omnibox.setClearButtonEnabled(True)
        self.omnibox.returnPressed.connect(self._omnibox_go)
        self.omnibox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bar.addWidget(self.omnibox)

        self.shield_btn = tb("0", "Blocked requests on this page", self._open_shield)
        self.dl_btn = tb("↓", "Downloads  (Ctrl+J)", self.toggle_downloads, checkable=True)
        self.hist_btn = tb("Hist", "History  (Ctrl+H)", self.toggle_history, checkable=True)
        self.audit_btn = tb("Audit", "Security audit  (superwebby://audit)", self.open_audit)
        self.speed_btn = tb("⚡", "High Speed mode: core blocklist only, no janitor, prefetch on.\n"
                            "YouTube ad blocking stays on.", lambda: self.set_high_speed(not self.settings.high_speed),
                            checkable=True)
        tb("Cmd", "Command palette  (Ctrl+K)", self.open_palette)
        self.menu_btn = QToolButton()
        self.menu_btn.setText("☰")
        self.menu_btn.setToolTip("Menu")
        self.menu_btn.setAutoRaise(True)
        self.menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.main_menu = self._build_main_menu()
        self.menu_btn.setMenu(self.main_menu)
        bar.addWidget(self.menu_btn)
        self._sync_speed_ui()

        self._completer = QCompleter([])
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.omnibox.setCompleter(self._completer)

    def _build_main_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("mainMenu")

        def act(text: str, slot, shortcut: str = "", checkable: bool = False) -> QAction:
            action = QAction(text, menu)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
                action.setShortcutVisibleInContextMenu(True)
            action.setCheckable(checkable)
            action.triggered.connect(slot)
            menu.addAction(action)
            return action

        act("New Tab", lambda: self.open_tab(), "Ctrl+T")
        act("New Window", self.new_window, "Ctrl+N")
        self.dirty_action = act(DIRTY_BROWSER, self.open_dirty_browser, "Ctrl+Shift+N")
        self.dirty_action.setToolTip("Private window: nothing saved to disk")
        menu.addSeparator()
        self.speed_action = act(HIGH_SPEED, lambda checked: self.set_high_speed(checked), checkable=True)
        act("Security Audit", self.open_audit)
        act("Settings && Favorite Sites", lambda: self.navigate("superwebby://settings"))
        act("Shield (blocked requests)", self._open_shield)
        menu.addSeparator()
        act("Downloads", self.toggle_downloads, "Ctrl+J")
        act("History", self.toggle_history, "Ctrl+H")
        menu.addSeparator()
        act("About Superwebby", lambda: self.navigate("superwebby://about"))
        act("Superwebby on GitHub", lambda: self.open_tab(GITHUB_URL))
        menu.addSeparator()
        act("Quit", self.close, "Ctrl+Q")
        return menu

    # --- Dirty Browser / High Speed / audit ---------------------------
    def open_dirty_browser(self) -> "BrowserWindow":
        """Open a private (off-the-record) window. Nothing is written to disk."""
        global _PRIVATE_PROFILE
        from superwebby.web import create_profile

        if self.incognito:
            profile = self.profile
        else:
            if _PRIVATE_PROFILE is None:
                _PRIVATE_PROFILE = create_profile(self.blocker, incognito=True, settings=self.settings)
            profile = _PRIVATE_PROFILE
        private_history = HistoryStore(None, enabled=False) if not self.incognito else self.history
        win = BrowserWindow(profile, self.blocker, private_history, self.windowIcon(), True, settings=self.settings)
        win.show()
        win.open_tab()
        self._siblings().append(win)
        return win

    def set_high_speed(self, on: bool) -> None:
        on = bool(on)
        self.settings.high_speed = on
        try:
            self.settings.save()
        except OSError:
            pass
        self.blocker.set_high_speed(on)
        from superwebby.web import apply_settings, refresh_scripts

        profiles = {id(self.profile): self.profile}
        if _PRIVATE_PROFILE is not None:
            profiles[id(_PRIVATE_PROFILE)] = _PRIVATE_PROFILE
        for profile in profiles.values():
            refresh_scripts(profile, self.settings)
            apply_settings(profile.settings(), high_speed=on)
        from PyQt6.QtWidgets import QApplication

        for win in QApplication.topLevelWidgets():
            if not isinstance(win, BrowserWindow):
                continue
            try:
                win._sync_speed_ui()
            except RuntimeError:
                pass

    def _sync_speed_ui(self) -> None:
        on = bool(self.settings.high_speed)
        if hasattr(self, "speed_action"):
            self.speed_action.blockSignals(True)
            self.speed_action.setChecked(on)
            self.speed_action.blockSignals(False)
        if hasattr(self, "speed_btn"):
            self.speed_btn.setChecked(on)
            self.speed_btn.setText("⚡ High Speed" if on else "⚡")

    def open_audit(self) -> None:
        self.open_tab("superwebby://audit")

    def settings_changed(self) -> None:
        """Re-apply per-site tweaks after favorites change."""
        from superwebby.web import refresh_scripts

        refresh_scripts(self.profile, self.settings)
        if _PRIVATE_PROFILE is not None and _PRIVATE_PROFILE is not self.profile:
            refresh_scripts(_PRIVATE_PROFILE, self.settings)

    def _build_findbar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("findbar")
        frame.setVisible(False)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.addWidget(QLabel("Find"))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in page")
        self.find_input.setObjectName("omnibox")
        self.find_input.returnPressed.connect(lambda: self._find(False))
        self.find_input.textChanged.connect(lambda _t: self._find(False, incremental=True))
        layout.addWidget(self.find_input, 1)
        prev = QPushButton("Previous")
        nxt = QPushButton("Next")
        close = QPushButton("Done")
        prev.clicked.connect(lambda: self._find(True))
        nxt.clicked.connect(lambda: self._find(False))
        close.clicked.connect(self.hide_find)
        layout.addWidget(prev)
        layout.addWidget(nxt)
        layout.addWidget(close)
        return frame

    def _build_history_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        frame.setVisible(False)
        frame.setMinimumHeight(200)
        frame.setMaximumHeight(280)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        header = QHBoxLayout()
        title = QLabel("History")
        title.setStyleSheet("font-weight: 650; font-size: 14px;")
        hint = QLabel("Local only  ·  Ctrl+H to hide")
        hint.setStyleSheet(f"color: {MUTED};")
        search = QLineEdit()
        search.setObjectName("omnibox")
        search.setPlaceholderText("Filter history")
        search.setFixedWidth(260)
        search.textChanged.connect(self._fill_history)
        header.addWidget(title)
        header.addWidget(hint, 1)
        header.addWidget(search)
        layout.addLayout(header)
        self.history_search = search
        self.history_list = QListWidget()
        self.history_list.itemActivated.connect(self._history_activate)
        self.history_list.itemClicked.connect(self._history_activate)
        layout.addWidget(self.history_list, 1)
        return frame

    def _bind_shortcuts(self) -> None:
        def sc(seq: str, slot, context=Qt.ShortcutContext.WindowShortcut) -> None:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(context)
            shortcut.activated.connect(slot)

        sc("Ctrl+T", lambda: self.open_tab())
        sc("Ctrl+W", self.close_current_tab)
        sc("Ctrl+Shift+T", self.reopen_tab)
        sc("Ctrl+Tab", lambda: self._cycle_tab(1))
        sc("Ctrl+PgDown", lambda: self._cycle_tab(1))
        sc("Ctrl+Shift+Tab", lambda: self._cycle_tab(-1))
        sc("Ctrl+PgUp", lambda: self._cycle_tab(-1))
        sc("Ctrl+L", self.focus_omnibox)
        sc("Alt+D", self.focus_omnibox)
        sc("F6", self.focus_omnibox)
        sc("Ctrl+K", self.open_palette)
        sc("Ctrl+J", self.toggle_downloads)
        sc("Ctrl+H", self.toggle_history)
        sc("Ctrl+R", self.reload)
        sc("F5", self.reload)
        sc("Ctrl+Shift+R", self.hard_reload)
        sc("Shift+F5", self.hard_reload)
        sc("Ctrl+F", self.show_find)
        sc("F3", lambda: self._find(False))
        sc("Ctrl+G", lambda: self._find(False))
        sc("Ctrl+Shift+G", lambda: self._find(True))
        sc("Ctrl+=", lambda: self._zoom_by(0.1))
        sc("Ctrl++", lambda: self._zoom_by(0.1))
        sc("Ctrl+-", lambda: self._zoom_by(-0.1))
        sc("Ctrl+0", self._zoom_reset)
        sc("Alt+Left", self.go_back)
        sc("Alt+Right", self.go_forward)
        sc("Alt+Home", lambda: self.navigate(NEWTAB))
        sc("Ctrl+Q", self.close)
        sc("Ctrl+Shift+W", self.close)
        sc("Ctrl+N", self.new_window)
        sc("Ctrl+Shift+N", self.open_dirty_browser)
        sc("Ctrl+Shift+P", self.open_dirty_browser)
        sc("F11", self.toggle_window_fullscreen)
        sc("Escape", self._escape)
        for n in range(1, 9):
            sc(f"Ctrl+{n}", lambda n=n: self._goto_tab(n - 1))
        sc("Ctrl+9", lambda: self._goto_tab(self.tabs.count() - 1))
        sc("Ctrl+Enter", self._omnibox_www, context=Qt.ShortcutContext.WidgetWithChildrenShortcut)

    # --- tabs ---------------------------------------------------------
    def allocate_tab(self, background: bool = False, url: str | None = None) -> WebPage:
        page = WebPage(self.profile, self)
        tab = BrowserTab(page, self)
        view = tab.view
        view.midclick_new_tab.connect(lambda q: self.open_tab(q.toString(), background=False))
        view.titleChanged.connect(lambda title, t=tab: self._title_changed(t, title))
        view.iconChanged.connect(lambda icon, t=tab: self._icon_changed(t, icon))
        view.urlChanged.connect(lambda q, t=tab: self._url_changed(t, q))
        view.loadStarted.connect(lambda v=view: setattr(v, "_loading", True))
        view.loadProgress.connect(lambda p, t=tab: self._progress_changed(t, p))
        view.loadFinished.connect(lambda ok, t=tab: self._load_finished(t, ok))
        page.fullscreen_requested.connect(self._page_fullscreen)
        index = self.tabs.addTab(tab, "New Tab")
        if not background:
            self.tabs.setCurrentIndex(index)
        if url:
            tab.go_internal_or_web(url)
        else:
            tab.show_internal(NEWTAB)
        return page

    def open_tab(self, url: str = NEWTAB, background: bool = False) -> WebPage:
        return self.allocate_tab(background=background, url=url)

    def current_tab(self) -> BrowserTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, BrowserTab) else None

    def current_view(self) -> WebView | None:
        tab = self.current_tab()
        if tab is not None:
            return tab.view
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, WebView) else None

    def current_url(self) -> str:
        tab = self.current_tab()
        if tab is not None:
            return tab.url_string()
        view = self.current_view()
        return view.url().toString() if view else ""

    def _index_of(self, widget: QWidget) -> int:
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab is widget:
                return i
            if isinstance(tab, BrowserTab) and (tab.view is widget or tab.internal is widget):
                return i
        return -1

    def _tab_of(self, widget: QWidget) -> BrowserTab | None:
        if isinstance(widget, BrowserTab):
            return widget
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, BrowserTab) and (tab.view is widget or tab.internal is widget):
                return tab
        return None

    def _close_tab_at(self, index: int) -> None:
        if index < 0 or index >= self.tabs.count():
            return
        widget = self.tabs.widget(index)
        url, title = "", ""
        if isinstance(widget, BrowserTab):
            url = widget.url_string()
            title = self.tabs.tabText(index)
        elif isinstance(widget, WebView):
            url = widget.url().toString()
            title = widget.title()
        self.history.push_closed(url, title)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        if self.tabs.count() == 0:
            self.open_tab()

    def close_current_tab(self) -> None:
        self._close_tab_at(self.tabs.currentIndex())

    def reopen_tab(self) -> None:
        closed = self.history.pop_closed()
        if closed:
            self.open_tab(closed.url)

    def _cycle_tab(self, delta: int) -> None:
        n = self.tabs.count()
        if n <= 1:
            return
        self.tabs.setCurrentIndex((self.tabs.currentIndex() + delta) % n)

    def _goto_tab(self, index: int) -> None:
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)

    def _tabbar_dblclick(self, index: int) -> None:
        if index == -1:
            self.open_tab()

    def _tab_changed(self, _index: int) -> None:
        tab = self.current_tab()
        if tab is None:
            return
        pending = self._pending_urls.pop(id(tab), None)
        if pending:
            tab.go_internal_or_web(pending)
        self._sync_chrome(tab)
        self._refresh_shield()

    def _title_changed(self, widget: QWidget, title: str) -> None:
        index = self._index_of(widget)
        if index >= 0:
            self.tabs.setTabText(index, (title or "New Tab")[:48])
        tab = self.current_tab()
        if tab is not None and (widget is tab or widget is tab.view or widget is tab.internal):
            suffix = f" ({DIRTY_BROWSER} · Private)" if self.incognito else ""
            self.setWindowTitle(f"{title or 'Superwebby'} — Superwebby{suffix}")

    def _icon_changed(self, widget: QWidget, icon: QIcon) -> None:
        index = self._index_of(widget)
        if index >= 0 and not icon.isNull():
            self.tabs.setTabIcon(index, icon)

    def _url_changed(self, widget: QWidget, url: QUrl) -> None:
        tab = self.current_tab()
        if tab is not None and (widget is tab or widget is tab.view):
            self._sync_chrome(tab)

    def _progress_changed(self, widget: QWidget, progress: int) -> None:
        tab = self.current_tab()
        if tab is not None and (widget is tab or widget is tab.view):
            self._progress = progress
            self._update_reload_label()

    def _load_finished(self, widget: QWidget, _ok: bool) -> None:
        tab = self._tab_of(widget)
        view = tab.view if tab is not None else widget
        if not isinstance(view, WebView):
            return
        view._loading = False
        url = view.url().toString()
        title = view.title() or url
        self.history.record(url, title)
        if tab is self.current_tab():
            self._progress = 100
            self._update_reload_label()
            self._sync_chrome(tab)
            self._refresh_completer()

    def _sync_chrome(self, widget: QWidget) -> None:
        tab = widget if isinstance(widget, BrowserTab) else self._tab_of(widget)
        if tab is None:
            return
        if not self.omnibox.hasFocus():
            url = tab.url_string()
            if url.startswith("superwebby://newtab"):
                self.omnibox.clear()
            else:
                self.omnibox.setText(url)
        view = tab.view
        try:
            self.back_btn.setEnabled(view.history().canGoBack() and not tab.is_internal())
            self.fwd_btn.setEnabled(view.history().canGoForward() and not tab.is_internal())
        except Exception:
            self.back_btn.setEnabled(False)
            self.fwd_btn.setEnabled(False)
        self._update_reload_label()
        self.dl_btn.setChecked(self.downloads.isVisible())
        self.hist_btn.setChecked(self.history_panel.isVisible())

    def _update_reload_label(self) -> None:
        view = self.current_view()
        if view is not None and getattr(view, '_loading', False):
            self.reload_btn.setText("✕")
            self.reload_btn.setToolTip("Stop  (Escape)")
        else:
            self.reload_btn.setText("↻")
            self.reload_btn.setToolTip("Reload  (Ctrl+R)")

    # --- navigation ---------------------------------------------------
    def navigate(self, url: str) -> None:
        tab = self.current_tab()
        if tab is None:
            self.open_tab(url)
            return
        tab.go_internal_or_web(url)
        self._sync_chrome(tab)

    def _omnibox_go(self) -> None:
        self.navigate(interpret_input(self.omnibox.text()))

    def _omnibox_www(self) -> None:
        if not self.omnibox.hasFocus():
            return
        text = self.omnibox.text().strip()
        if text and " " not in text and "://" not in text and "." not in text:
            self.navigate("https://www." + text + ".com")
        else:
            self._omnibox_go()

    def focus_omnibox(self) -> None:
        self.omnibox.setFocus()
        self.omnibox.selectAll()

    def go_back(self) -> None:
        view = self.current_view()
        if view:
            view.back()

    def go_forward(self) -> None:
        view = self.current_view()
        if view:
            view.forward()

    def reload(self) -> None:
        view = self.current_view()
        if view is None:
            return
        if getattr(view, '_loading', False):
            view.stop()
        else:
            view.reload()

    def hard_reload(self) -> None:
        view = self.current_view()
        if view:
            view.triggerPageAction(QWebEnginePage.WebAction.ReloadAndBypassCache)

    def _on_download(self, request) -> None:
        self.downloads.handle(request)
        # Quiet: badge the button, do not steal focus or pop a save dialog.
        n = len(self.downloads.items)
        self.dl_btn.setText(f"↓ {n}" if n else "↓")
        self.dl_btn.setToolTip(f"{n} download(s)  ·  Ctrl+J")

    def toggle_downloads(self) -> None:
        visible = not self.downloads.isVisible()
        self.downloads.setVisible(visible)
        if visible:
            self.history_panel.setVisible(False)
            self.hist_btn.setChecked(False)
        self.dl_btn.setChecked(visible)
        self.downloads.setFocus()

    def toggle_history(self) -> None:
        visible = not self.history_panel.isVisible()
        self.history_panel.setVisible(visible)
        if visible:
            self.downloads.setVisible(False)
            self.dl_btn.setChecked(False)
            self._fill_history(self.history_search.text())
            self.history_search.setFocus()
        self.hist_btn.setChecked(visible)

    def _fill_history(self, query: str = "") -> None:
        self.history_list.clear()
        for visit in self.history.search(query, limit=80):
            host = urlparse(visit.url).hostname or ""
            row = QListWidgetItem(f"{visit.title}\n{host}  ·  {visit.url}")
            row.setData(Qt.ItemDataRole.UserRole, visit.url)
            self.history_list.addItem(row)

    def _history_activate(self, item: QListWidgetItem) -> None:
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.navigate(url)
            self.history_panel.setVisible(False)
            self.hist_btn.setChecked(False)

    def _open_shield(self) -> None:
        self.open_tab("superwebby://shield")

    def _refresh_shield(self) -> None:
        url = self.current_url()
        stats = self.blocker.stats_for(url)
        self.shield_btn.setText(str(stats.count))
        if stats.count:
            top = ", ".join(f"{h} ({n})" for h, n in list(stats.hosts.items())[:6])
            self.shield_btn.setToolTip(f"{stats.count} blocked on this page\n{top}")
        else:
            self.shield_btn.setToolTip("No trackers blocked on this page yet")

    def _refresh_completer(self) -> None:
        urls = [v.url for v in self.history.recent(40)]
        self._completer.model().setStringList(urls) if hasattr(self._completer.model(), "setStringList") else None
        from PyQt6.QtCore import QStringListModel

        self._completer.setModel(QStringListModel(urls, self._completer))

    # --- find / zoom / palette ----------------------------------------
    def show_find(self) -> None:
        self.findbar.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find(self) -> None:
        self.findbar.setVisible(False)
        view = self.current_view()
        if view:
            view.findText("")
            view.setFocus()

    def _find(self, backward: bool = False, incremental: bool = False) -> None:
        view = self.current_view()
        if view is None:
            return
        text = self.find_input.text()
        flags = QWebEnginePage.FindFlag(0)
        if backward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        view.findText(text, flags)

    def _zoom_by(self, delta: float) -> None:
        view = self.current_view()
        if view is None:
            return
        factor = max(0.3, min(3.0, view.zoomFactor() + delta))
        view.setZoomFactor(factor)

    def _zoom_reset(self) -> None:
        view = self.current_view()
        if view:
            view.setZoomFactor(1.0)

    def open_palette(self) -> None:
        items: list[PaletteItem] = []

        def add(title, subtitle, kind, handler, keywords=""):
            items.append(PaletteItem(title, subtitle, kind, handler, keywords))

        add("New tab", "Ctrl+T", "Command", lambda: self.open_tab(), "open")
        add("Downloads panel", "Ctrl+J", "Command", self.toggle_downloads, "files save brave")
        add("History panel", "Ctrl+H", "Command", self.toggle_history, "visited")
        add("Focus address bar", "Ctrl+L", "Command", self.focus_omnibox, "omnibox url")
        add("Reload", "Ctrl+R", "Command", self.reload, "refresh")
        add("Hard reload", "Ctrl+Shift+R", "Command", self.hard_reload, "bypass cache")
        add("Find in page", "Ctrl+F", "Command", self.show_find, "search")
        add("New window", "Ctrl+N", "Command", self.new_window, "")
        add(DIRTY_BROWSER, "Private window  ·  Ctrl+Shift+N", "Command", self.open_dirty_browser, "private incognito dirty")
        add(
            f"{HIGH_SPEED}: turn {'off' if self.settings.high_speed else 'on'}",
            "Core blocklist, no janitor, prefetch on; YouTube ads stay blocked",
            "Command", lambda: self.set_high_speed(not self.settings.high_speed), "fast speed turbo high",
        )
        add("Security audit", "superwebby://audit", "Command", self.open_audit, "audit security cve sandbox")
        add("Settings & favorite sites", "superwebby://settings", "Command",
            lambda: self.navigate("superwebby://settings"), "favorite pin preferences")
        add("Superwebby on GitHub", GITHUB_URL, "Command", lambda: self.open_tab(GITHUB_URL), "github source repo")
        add("Close tab", "Ctrl+W", "Command", self.close_current_tab, "")
        add("Reopen closed tab", "Ctrl+Shift+T", "Command", self.reopen_tab, "undo")
        add("About Superwebby", "superwebby://about", "Command", lambda: self.navigate("superwebby://about"), "version")
        add("Shield / blocked requests", "superwebby://shield", "Command", lambda: self.navigate("superwebby://shield"), "ads trackers")
        add("Home / new tab page", "superwebby://newtab", "Command", lambda: self.navigate(NEWTAB), "start")
        add("Toggle fullscreen", "F11", "Command", self.toggle_window_fullscreen, "")
        add("Clear history", "Local only", "Command", self._clear_history, "forget delete")

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            title = self.tabs.tabText(i)
            if isinstance(widget, BrowserTab):
                url = widget.url_string()
            elif isinstance(widget, WebView):
                url = widget.url().toString()
            else:
                url = ""
            add(title or "Tab", url, "Tab", lambda i=i: self._goto_tab(i), url)

        for visit in self.history.recent(25):
            add(visit.title, visit.url, "History", lambda u=visit.url: self.navigate(u), visit.url)

        self.palette.show_palette(items)

    def _clear_history(self) -> None:
        self.history.clear()
        self._fill_history("")

    def new_window(self) -> None:
        win = BrowserWindow(self.profile, self.blocker, self.history, self.windowIcon(), self.incognito, settings=self.settings)
        win.show()
        win.open_tab()
        self._siblings().append(win)

    def _siblings(self) -> list:
        bag = getattr(self.profile, "_superwebby_windows", None)
        if bag is None:
            bag = []
            setattr(self.profile, "_superwebby_windows", bag)
        return bag

    def toggle_window_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _page_fullscreen(self, page: WebPage, enable: bool) -> None:
        view = page.view()
        if enable:
            self._fullscreen_view = view if isinstance(view, WebView) else None
            self.showFullScreen()
        else:
            self.showNormal()
            self._fullscreen_view = None

    def _escape(self) -> None:
        if self.palette.isVisible():
            self.palette.hide_palette()
            return
        if self.findbar.isVisible():
            self.hide_find()
            return
        if self.downloads.isVisible() or self.history_panel.isVisible():
            self.downloads.setVisible(False)
            self.history_panel.setVisible(False)
            self.dl_btn.setChecked(False)
            self.hist_btn.setChecked(False)
            return
        if self.isFullScreen():
            view = self.current_view()
            if view:
                view.triggerPageAction(QWebEnginePage.WebAction.ExitFullScreen)
            self.showNormal()
            return
        view = self.current_view()
        if view and getattr(view, '_loading', False):
            view.stop()

    # --- session ------------------------------------------------------
    def restore_or_start(self, startup_url: str | None = None) -> None:
        if startup_url:
            self.open_tab(startup_url)
            return
        tabs = self.history.load_session()
        if not tabs:
            self.open_tab()
            return
        active = 0
        lazy = bool(self.settings.high_speed)
        for index, (url, title, is_active) in enumerate(tabs):
            if lazy and not is_active and not url.startswith("superwebby://"):
                # High Speed: restore background tabs without loading them.
                self.open_tab(NEWTAB, background=True)
                tab = self.tabs.widget(self.tabs.count() - 1)
                self._pending_urls[id(tab)] = url
                self.tabs.setTabText(self.tabs.count() - 1, (title or url)[:48])
            else:
                self.open_tab(url, background=True)
            if is_active:
                active = index
        if self.tabs.count() == 0:
            self.open_tab()
        else:
            self.tabs.setCurrentIndex(min(active, self.tabs.count() - 1))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        tabs = []
        current = self.tabs.currentIndex()
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, BrowserTab) and id(widget) in self._pending_urls:
                url = self._pending_urls[id(widget)]
            elif isinstance(widget, BrowserTab):
                url = widget.url_string()
            elif isinstance(widget, WebView):
                url = widget.url().toString()
            else:
                url = ""
            title = self.tabs.tabText(i)
            tabs.append((url, title, i == current))
        self.history.save_session(tabs)
        event.accept()
