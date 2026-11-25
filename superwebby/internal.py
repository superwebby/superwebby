"""Native internal pages so new-tab / about / shield stay fast and GPU-independent."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from superwebby import __version__
from superwebby.theme import ACCENT, BORDER, MUTED, SURFACE, SURFACE2, TEXT


class Tile(QPushButton):
    def __init__(self, title: str, subtitle: str, url: str, parent=None) -> None:
        super().__init__(parent)
        self.url = url
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 12px;
                padding: 12px 14px;
            }}
            QPushButton:hover {{ border-color: {ACCENT}; background: {SURFACE2}; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        t = QLabel(title)
        t.setStyleSheet(f"font-weight: 600; color: {TEXT}; background: transparent; border: 0;")
        t.setWordWrap(True)
        s = QLabel(subtitle)
        s.setStyleSheet(f"color: {MUTED}; background: transparent; border: 0; font-size: 12px;")
        s.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(t)
        layout.addWidget(s)


class InternalPage(QWidget):
    navigate = pyqtSignal(str)
    title_changed = pyqtSignal(str)

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self.window = window
        self.current = "superwebby://newtab"
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._inner = QWidget()
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(48, 40, 48, 40)
        self._layout.setSpacing(14)
        self._scroll.setWidget(self._inner)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._scroll)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _wrap(self, *widgets: QWidget) -> None:
        self._clear()
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)
        for widget in widgets:
            box.addWidget(widget)
        box.addStretch(1)
        holder.setMaximumWidth(820)
        holder.setMinimumWidth(420)
        center = QWidget()
        c = QHBoxLayout(center)
        c.setContentsMargins(0, 0, 0, 0)
        c.addStretch(1)
        c.addWidget(holder, 1)
        c.addStretch(1)
        self._layout.addWidget(center)

    def _mark(self) -> QLabel:
        mark = QLabel("S")
        mark.setFixedSize(56, 56)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            f"""
            QLabel {{
                background: #121826;
                color: {ACCENT};
                border: 1px solid {BORDER};
                border-radius: 16px;
                font-size: 26px;
                font-weight: 700;
            }}
            """
        )
        return mark

    def _h1(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"font-size: 28px; font-weight: 650; letter-spacing: -0.5px; color: {TEXT};")
        return label

    def _sub(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color: {MUTED}; font-size: 14px;")
        return label

    def show_url(self, url: str) -> None:
        name = url.split("://", 1)[-1].strip("/").lower() or "newtab"
        if name in {"newtab", "home", "start"}:
            self.show_newtab()
        elif name == "history":
            self.show_history()
        elif name == "downloads":
            self.show_downloads()
        elif name == "about":
            self.show_about()
        elif name in {"blocked", "shield"}:
            self.show_shield()
        else:
            self.show_about()

    def show_newtab(self) -> None:
        self.current = "superwebby://newtab"
        search = QLineEdit()
        search.setObjectName("omnibox")
        search.setPlaceholderText("Search DuckDuckGo or paste an address")
        search.setMinimumHeight(42)
        go = QPushButton("Search")
        go.setDefault(True)

        def submit() -> None:
            text = search.text().strip()
            if not text:
                return
            # local import to avoid a module cycle at load time
            from superwebby.window import interpret_input

            self.navigate.emit(interpret_input(text))

        search.returnPressed.connect(submit)
        go.clicked.connect(submit)
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(search, 1)
        hl.addWidget(go)

        widgets: list[QWidget] = [
            self._mark(),
            self._h1("Superwebby"),
            self._sub("A painless browser. No nags, no telemetry, no wizard. Type and go."),
            row,
        ]
        frequent = self.window.history.frequent() if self.window else []
        recent = self.window.history.recent(12) if self.window else []
        tiles: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for item in list(frequent) + list(recent):
            parsed = urlparse(item.url)
            key = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
            if key in seen:
                continue
            seen.add(key)
            host = parsed.hostname or item.url
            tiles.append((item.title or host, host, item.url))
            if len(tiles) >= 8:
                break
        if tiles:
            heading = QLabel("JUMP BACK IN")
            heading.setStyleSheet(
                f"color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px;"
            )
            widgets.append(heading)
            grid_host = QWidget()
            grid = QGridLayout(grid_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(10)
            for i, (title, sub, url) in enumerate(tiles):
                tile = Tile(title[:48], sub, url)
                tile.clicked.connect(lambda *_a, u=url: self.navigate.emit(u))
                grid.addWidget(tile, i // 4, i % 4)
            widgets.append(grid_host)

        hints = QLabel(
            "Ctrl+L address   ·   Ctrl+K command palette   ·   Ctrl+J downloads   ·   "
            "Ctrl+H history   ·   Ctrl+T new tab"
        )
        hints.setWordWrap(True)
        hints.setStyleSheet(f"color: {MUTED}; font-size: 13px; padding-top: 18px;")
        widgets.append(hints)
        self._wrap(*widgets)
        self.title_changed.emit("New Tab")
        search.setFocus()

    def show_history(self) -> None:
        self.current = "superwebby://history"
        visits = self.window.history.recent(80) if self.window else []
        widgets: list[QWidget] = [
            self._h1("History"),
            self._sub("Local only. Nothing is synced or reported. Ctrl+H also toggles the history panel."),
        ]
        if not visits:
            widgets.append(self._sub("No history yet."))
        for visit in visits:
            host = urlparse(visit.url).hostname or ""
            tile = Tile(visit.title or visit.url, f"{host}  ·  {visit.count} visit(s)", visit.url)
            tile.clicked.connect(lambda *_a, u=visit.url: self.navigate.emit(u))
            widgets.append(tile)
        self._wrap(*widgets)
        self.title_changed.emit("History")

    def show_downloads(self) -> None:
        self.current = "superwebby://downloads"
        items = self.window.downloads.as_dicts() if self.window else []
        widgets: list[QWidget] = [
            self._h1("Downloads"),
            self._sub("Saved automatically to your Downloads folder. Ctrl+J toggles the downloads panel."),
        ]
        if not items:
            widgets.append(self._sub("No downloads yet. They land quietly in ~/Downloads."))
        for item in items:
            tile = Tile(str(item.get("name") or "file"), f"{item.get('state')}  ·  {item.get('path')}", item.get("url") or "")
            widgets.append(tile)
        self._wrap(*widgets)
        self.title_changed.emit("Downloads")

    def show_about(self) -> None:
        self.current = "superwebby://about"
        domains = len(self.window.blocker.domains) if self.window else 0
        total = self.window.blocker.total_blocked if self.window else 0
        self._wrap(
            self._mark(),
            self._h1(f"Superwebby {__version__}"),
            self._sub(
                "A from-scratch desktop browser. Not a reskin of Chromium UI, Brave, Firefox, "
                "Ladybird, qutebrowser, or surf — though it uses Qt WebEngine so pages actually render."
            ),
            self._sub(
                f"Built-in ad and tracker blocking ({domains:,} domains), no telemetry, no sign-in nags, "
                "no first-run wizard, automatic downloads, auto dark mode, a command palette, "
                "and a real Ctrl+J downloads panel."
            ),
            self._sub(f"Blocked this session: {total}. License: GPL-3.0-or-later."),
        )
        self.title_changed.emit("About Superwebby")

    def show_shield(self) -> None:
        self.current = "superwebby://shield"
        url = self.window.current_url() if self.window else ""
        stats = self.window.blocker.stats_for(url) if self.window else None
        total = self.window.blocker.total_blocked if self.window else 0
        widgets: list[QWidget] = [
            self._h1("Shield"),
            self._sub(
                f"{stats.count if stats else 0} request(s) blocked on this page. {total} this session."
            ),
            self._sub(url or ""),
        ]
        hosts = sorted(stats.hosts.items(), key=lambda kv: (-kv[1], kv[0])) if stats else []
        if not hosts:
            widgets.append(self._sub("Nothing blocked on this page."))
        for host, count in hosts:
            widgets.append(self._sub(f"{host}  —  {count}"))
        self._wrap(*widgets)
        self.title_changed.emit("Shield")
