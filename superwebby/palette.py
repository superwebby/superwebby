"""Ctrl+K command palette: commands, open tabs, and history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


@dataclass
class PaletteItem:
    title: str
    subtitle: str
    kind: str
    handler: Callable[[], None]
    keywords: str = ""

    def haystack(self) -> str:
        return f"{self.title} {self.subtitle} {self.kind} {self.keywords}".lower()


class CommandPalette(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("palette")
        self.setVisible(False)
        self.setMinimumWidth(560)
        self.setMaximumWidth(720)
        self.items: list[PaletteItem] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)
        label = QLabel("Command palette")
        label.setStyleSheet("color: #8b9bb0; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase;")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search tabs, history, and commands…")
        self.input.setObjectName("omnibox")
        self.list = QListWidget()
        self.list.setMinimumHeight(280)
        self.list.setMaximumHeight(360)
        layout.addWidget(label)
        layout.addWidget(self.input)
        layout.addWidget(self.list)
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self._activate)
        self.list.itemActivated.connect(lambda *_: self._activate())
        self.list.itemClicked.connect(lambda *_: self._activate())
        self.input.installEventFilter(self)
        self.list.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Escape:
                self.hide_palette()
                return True
            if obj is self.input and event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._move(1 if event.key() == Qt.Key.Key_Down else -1)
                return True
            if obj is self.list and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate()
                return True
        return super().eventFilter(obj, event)

    def show_palette(self, items: list[PaletteItem]) -> None:
        self.items = items
        self.input.setText("")
        self._filter("")
        self.setVisible(True)
        self.raise_()
        self.input.setFocus()
        self._recenter()

    def hide_palette(self) -> None:
        self.setVisible(False)
        if self.parent() is not None:
            self.parent().setFocus()

    def _recenter(self) -> None:
        parent = self.parent()
        if parent is None:
            return
        self.adjustSize()
        w = min(640, max(520, parent.width() - 80))
        self.setFixedWidth(w)
        x = (parent.width() - self.width()) // 2
        y = max(48, int(parent.height() * 0.14))
        self.move(x, y)

    def _filter(self, text: str) -> None:
        needle = " ".join(text.lower().split())
        self.list.clear()
        for item in self.items:
            if needle and not all(part in item.haystack() for part in needle.split()):
                continue
            row = QListWidgetItem(f"{item.title}\n{item.kind}  ·  {item.subtitle}" if item.subtitle else f"{item.title}\n{item.kind}")
            row.setData(Qt.ItemDataRole.UserRole, item)
            self.list.addItem(row)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _move(self, delta: int) -> None:
        if not self.list.count():
            return
        row = max(0, min(self.list.count() - 1, self.list.currentRow() + delta))
        self.list.setCurrentRow(row)

    def _activate(self) -> None:
        row = self.list.currentItem()
        if row is None:
            return
        item = row.data(Qt.ItemDataRole.UserRole)
        self.hide_palette()
        if item is not None:
            item.handler()
