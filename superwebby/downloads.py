"""Quiet automatic downloads and the Ctrl+J panel."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from superwebby.paths import downloads_dir


def _unique_path(directory: Path, filename: str) -> str:
    filename = filename or "download"
    candidate = directory / filename
    if not candidate.exists():
        return filename
    stem, suffix = Path(filename).stem, Path(filename).suffix
    index = 1
    while True:
        name = f"{stem} ({index}){suffix}"
        if not (directory / name).exists():
            return name
        index += 1


class DownloadItem(QWidget):
    def __init__(self, request: QWebEngineDownloadRequest, parent=None) -> None:
        super().__init__(parent)
        self.request = request
        self.name = request.downloadFileName() or request.suggestedFileName() or "download"
        self.directory = request.downloadDirectory()
        self.url = request.url().toString()
        self._state = "Starting"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self.title = QLabel(self.name)
        self.title.setStyleSheet("font-weight: 600;")
        self.status = QLabel(self._state)
        self.status.setStyleSheet("color: #8b9bb0;")
        top.addWidget(self.title, 1)
        top.addWidget(self.status, 0)
        layout.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(7)
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)

        actions = QHBoxLayout()
        self.open_btn = QPushButton("Open")
        self.folder_btn = QPushButton("Show")
        self.cancel_btn = QPushButton("Cancel")
        self.open_btn.clicked.connect(self.open_file)
        self.folder_btn.clicked.connect(self.show_folder)
        self.cancel_btn.clicked.connect(self.cancel)
        self.open_btn.setEnabled(False)
        actions.addWidget(self.open_btn)
        actions.addWidget(self.folder_btn)
        actions.addWidget(self.cancel_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        request.receivedBytesChanged.connect(self._refresh)
        request.totalBytesChanged.connect(self._refresh)
        request.stateChanged.connect(self._refresh)
        request.isFinishedChanged.connect(self._refresh)
        self._refresh()

    @property
    def path(self) -> Path:
        return Path(self.directory) / self.name

    def _refresh(self, *_args) -> None:
        req = self.request
        try:
            state = req.state()
            received = req.receivedBytes()
            total = req.totalBytes()
        except Exception:
            return
        if total and total > 0:
            self.bar.setRange(0, 100)
            self.bar.setValue(min(100, int(received * 100 / total)))
        else:
            self.bar.setRange(0, 0)
        done = QWebEngineDownloadRequest.DownloadState.DownloadCompleted
        cancelled = QWebEngineDownloadRequest.DownloadState.DownloadCancelled
        interrupted = QWebEngineDownloadRequest.DownloadState.DownloadInterrupted
        if state == done:
            self._state = "Done"
            self.bar.setRange(0, 100)
            self.bar.setValue(100)
            self.open_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
        elif state == cancelled:
            self._state = "Cancelled"
            self.cancel_btn.setEnabled(False)
        elif state == interrupted:
            reason = ""
            try:
                reason = req.interruptReasonString()
            except Exception:
                pass
            self._state = f"Interrupted{': ' + reason if reason else ''}"
            self.cancel_btn.setEnabled(False)
        else:
            if total and total > 0:
                self._state = f"{_fmt(received)} / {_fmt(total)}"
            else:
                self._state = _fmt(received)
        self.status.setText(self._state)

    def open_file(self) -> None:
        if self.path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))

    def show_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.directory))))

    def cancel(self) -> None:
        try:
            self.request.cancel()
        except Exception:
            pass

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "state": self._state,
            "path": str(self.path),
        }


def _fmt(n: int) -> str:
    n = max(0, int(n or 0))
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            if unit == "B":
                return f"{n} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


class DownloadsPanel(QFrame):
    openRequested = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setVisible(False)
        self.setMinimumHeight(180)
        self.setMaximumHeight(260)
        self.items: list[DownloadItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setStyleSheet("font-weight: 650; font-size: 14px;")
        hint = QLabel("Saved quietly to ~/Downloads  ·  Ctrl+J to hide")
        hint.setStyleSheet("color: #8b9bb0;")
        folder = QPushButton("Open folder")
        clear = QPushButton("Clear finished")
        folder.clicked.connect(self.open_folder)
        clear.clicked.connect(self.clear_finished)
        header.addWidget(title)
        header.addWidget(hint, 1)
        header.addWidget(folder)
        header.addWidget(clear)
        layout.addLayout(header)

        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.list, 1)

    def handle(self, request: QWebEngineDownloadRequest) -> None:
        directory = downloads_dir()
        directory.mkdir(parents=True, exist_ok=True)
        suggested = request.suggestedFileName() or request.downloadFileName() or "download"
        name = _unique_path(directory, suggested)
        request.setDownloadDirectory(str(directory))
        request.setDownloadFileName(name)
        request.accept()
        item = DownloadItem(request)
        self.items.insert(0, item)
        row = QListWidgetItem()
        row.setSizeHint(item.sizeHint() if item.sizeHint().height() > 0 else item.size())
        # Ensure a decent row height even before layout.
        if row.sizeHint().height() < 80:
            from PyQt6.QtCore import QSize

            row.setSizeHint(QSize(100, 88))
        self.list.insertItem(0, row)
        self.list.setItemWidget(row, item)
        self.changed.emit()

    def as_dicts(self) -> list[dict]:
        return [item.as_dict() for item in self.items]

    def open_folder(self) -> None:
        path = downloads_dir()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def clear_finished(self) -> None:
        kept: list[DownloadItem] = []
        for index in range(self.list.count() - 1, -1, -1):
            widget = self.list.itemWidget(self.list.item(index))
            if not isinstance(widget, DownloadItem):
                continue
            finished = widget._state in {"Done", "Cancelled"} or widget._state.startswith("Interrupted")
            if finished:
                self.list.takeItem(index)
            else:
                kept.append(widget)
        kept.reverse()
        self.items = kept
        self.changed.emit()

    def count_active(self) -> int:
        n = 0
        for item in self.items:
            if item._state not in {"Done", "Cancelled"} and not item._state.startswith("Interrupted"):
                n += 1
        return n
