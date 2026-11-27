"""Native internal pages so new-tab / about / shield stay fast and GPU-independent."""

from __future__ import annotations

from html import escape
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
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
from superwebby.paths import data_dir
from superwebby.theme import ACCENT, BORDER, MUTED, SURFACE, SURFACE2, TEXT

GITHUB_URL = "https://github.com/superwebby/superwebby"
STATUS_COLORS = {"PASS": "#3dd68c", "WARN": "#f2c94c", "FAIL": "#ff5c5c", "INFO": "#7c9cff"}


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

    def _mark(self, size: int = 56) -> QLabel:
        logo = data_dir() / "logo-256.png"
        if logo.is_file():
            label = QLabel()
            pix = QPixmap(str(logo))
            if not pix.isNull():
                label.setPixmap(pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
                label.setFixedSize(size, size)
                label.setToolTip("Superwebby: a flower in the barrel, a peace sign made of people")
                return label
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
        elif name in {"audit", "security"}:
            self.show_audit()
        elif name in {"settings", "preferences", "favorites"}:
            self.show_settings()
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
        favorites = [f for f in self.window.settings.favorites if f.pinned] if self.window else []
        if favorites:
            heading = QLabel("YOUR FAVORITE SITES")
            heading.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
            widgets.append(heading)
            fav_host = QWidget()
            fav_grid = QGridLayout(fav_host)
            fav_grid.setContentsMargins(0, 0, 0, 0)
            fav_grid.setSpacing(10)
            for i, fav in enumerate(favorites[:8]):
                notes = [n for n, on in (("light mode", fav.no_dark), ("no janitor", fav.no_janitor),
                                         ("relaxed blocking", fav.relaxed)) if on]
                tile = Tile(fav.title or fav.host, "★ " + (" · ".join(notes) or "favorite"), "https://" + fav.host)
                tile.clicked.connect(lambda *_a, u="https://" + fav.host: self.navigate.emit(u))
                fav_grid.addWidget(tile, i // 4, i % 4)
            widgets.append(fav_host)
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
            "Ctrl+H history   ·   Ctrl+T new tab   ·   Ctrl+Shift+N Dirty Browser"
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
            self._link(f'Source, releases and issues: <a href="{GITHUB_URL}">{GITHUB_URL}</a>'),
            self._sub("Logo: a flower in a rifle's barrel over a peace sign made of people holding hands. "
                      "Superwebby is a peace project, not a weapons one."),
        )
        self.title_changed.emit("About Superwebby")

    def _link(self, html: str) -> QLabel:
        label = QLabel(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setOpenExternalLinks(False)
        label.linkActivated.connect(lambda url: self.navigate.emit(url))
        label.setStyleSheet(f"color: {TEXT}; font-size: 14px;")
        return label

    def _section(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setStyleSheet(f"color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; padding-top: 10px;")
        return label

    def show_audit(self) -> None:
        from superwebby.audit import run_audit

        self.current = "superwebby://audit"
        report = run_audit(self.window)
        counts = report["counts"]
        widgets: list[QWidget] = [
            self._mark(48),
            self._h1("Security audit"),
            self._sub(
                f"Superwebby {report['version']} · {report['mode']} mode · ran {report['ran_at']}. "
                f"These checks run live against this build. Warnings and failures are shown as they are."
            ),
            self._link(
                " &nbsp; ".join(
                    f'<span style="color:{STATUS_COLORS[k]};font-weight:700">{counts[k]} {k}</span>'
                    for k in ("PASS", "WARN", "FAIL")
                )
            ),
            self._section("Runtime checks"),
        ]
        for check in report["checks"]:
            widgets.append(self._audit_row(check["status"], check["name"], check["detail"], check.get("evidence", "")))
        static = report["static"]
        widgets.append(self._section("Static analysis (build time)"))
        widgets.append(self._audit_row(static.get("status", "WARN"), "Summary", static.get("summary", ""),
                                       static.get("generated", "")))
        for tool in static.get("tools", []):
            widgets.append(self._audit_row(tool.get("status", "WARN"), tool.get("name", "tool"),
                                           tool.get("summary", ""), "\n".join(tool.get("findings", [])[:12])))
        rerun = QPushButton("Run audit again")
        rerun.clicked.connect(self.show_audit)
        widgets.append(rerun)
        widgets.append(self._link(f'Method and history: <a href="{GITHUB_URL}/blob/main/AUDIT.md">AUDIT.md on GitHub</a>'))
        self._wrap(*widgets)
        self.title_changed.emit("Security audit")

    def _audit_row(self, status: str, name: str, detail: str, evidence: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}"
            "QLabel { border: 0; background: transparent; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 10, 12, 10)
        badge = QLabel(status)
        color = STATUS_COLORS.get(status, MUTED)
        badge.setFixedWidth(52)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: #0e1116; background: {color}; border-radius: 6px; font-weight: 700; font-size: 11px; padding: 3px;"
        )
        col = QVBoxLayout()
        title = QLabel(name)
        title.setStyleSheet(f"font-weight: 650; color: {TEXT};")
        body = QLabel(detail)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        col.addWidget(title)
        col.addWidget(body)
        if evidence:
            ev = QLabel(evidence)
            ev.setWordWrap(True)
            ev.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            ev.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
            col.addWidget(ev)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(col, 1)
        return frame

    def show_settings(self) -> None:
        self.current = "superwebby://settings"
        settings = self.window.settings
        widgets: list[QWidget] = [
            self._h1("Settings"),
            self._sub("No wizard. Change anything here whenever you like; it saves instantly."),
            self._section("Favorite sites"),
            self._sub(
                "Tell Superwebby your favorite sites. They are pinned on the start page, get any known "
                "site fixes automatically, and you can switch off dark mode, the cookie janitor, or "
                "strict blocking just for them if something breaks."
            ),
        ]
        add_row = QWidget()
        hl = QHBoxLayout(add_row)
        hl.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit()
        field.setObjectName("omnibox")
        field.setPlaceholderText("Your favorite site, e.g. music.youtube.com")
        add_btn = QPushButton("Add favorite")

        def add() -> None:
            if settings.add_favorite(field.text()):
                settings.save()
                self.window.settings_changed()
                self.show_settings()

        field.returnPressed.connect(add)
        add_btn.clicked.connect(add)
        hl.addWidget(field, 1)
        hl.addWidget(add_btn)
        widgets.append(add_row)
        if not settings.favorites:
            widgets.append(self._sub("No favorites yet."))
        for fav in list(settings.favorites):
            widgets.append(self._favorite_row(fav))
        widgets.append(self._section("Speed"))
        speed = QCheckBox("High Speed mode")
        speed.setChecked(settings.high_speed)
        speed.toggled.connect(self.window.set_high_speed)
        widgets.append(speed)
        widgets.append(self._sub("Instant startup (background tabs load when you open them), core ad/tracker "
                                 "list only, no cookie janitor, DNS prefetch on. YouTube and YouTube Music ads "
                                 "stay blocked."))
        widgets.append(self._section("More"))
        widgets.append(self._link(
            '<a href="superwebby://audit">Security audit</a> &nbsp;·&nbsp; '
            '<a href="superwebby://about">About</a> &nbsp;·&nbsp; '
            f'<a href="{GITHUB_URL}">GitHub</a>'
        ))
        widgets.append(self._sub(f"Settings file: {settings.path()}"))
        self._wrap(*widgets)
        self.title_changed.emit("Settings")

    def _favorite_row(self, fav) -> QFrame:
        settings = self.window.settings
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}"
                            "QLabel, QCheckBox { border: 0; background: transparent; }")
        col = QVBoxLayout(frame)
        col.setContentsMargins(12, 10, 12, 10)
        top = QHBoxLayout()
        name = QLabel("★ " + fav.host)
        name.setStyleSheet(f"font-weight: 650; color: {TEXT};")
        remove = QPushButton("Remove")

        def drop() -> None:
            settings.remove_favorite(fav.host)
            settings.save()
            self.window.settings_changed()
            self.show_settings()

        remove.clicked.connect(drop)
        top.addWidget(name, 1)
        top.addWidget(remove)
        col.addLayout(top)
        opts = QGridLayout()
        for idx, (key, label) in enumerate((("pinned", "Pin on start page"), ("no_dark", "No dark mode"),
                                            ("no_janitor", "No cookie janitor"), ("relaxed", "Relaxed blocking"))):
            box = QCheckBox(label)
            box.setChecked(bool(getattr(fav, key)))

            def toggled(on: bool, k=key) -> None:
                setattr(fav, k, bool(on))
                settings.save()
                self.window.settings_changed()

            box.toggled.connect(toggled)
            opts.addWidget(box, idx // 2, idx % 2)
        col.addLayout(opts)
        return frame

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
