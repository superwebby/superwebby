"""Dark-first Fusion palette. No first-run themes, no accent nags."""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory

# Ink and ember — readable dark chrome that stays out of the way.
BG = "#0e1116"
SURFACE = "#161b22"
SURFACE2 = "#1c2330"
RAISED = "#222a38"
BORDER = "#2d3646"
TEXT = "#e6edf3"
MUTED = "#8b9bb0"
ACCENT = "#ff6b3d"
ACCENT2 = "#7c9cff"
OK = "#3dd68c"
WARN = "#ffd166"
DANGER = "#ff6b6b"
OMNIBOX = "#0b0e13"


def is_dark_color_scheme(app: QApplication) -> bool:
    try:
        from PyQt6.QtCore import Qt

        scheme = app.styleHints().colorScheme()
        # 1 = ColorScheme.Light, 2 = Dark in Qt 6.5+
        if int(scheme) == 1:
            return False
    except Exception:
        pass
    return True


def apply(app: QApplication, force_dark: bool = True) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    if not force_dark and not is_dark_color_scheme(app):
        app.setStyleSheet(_light_qss())
        return
    pal = QPalette()
    bg = QColor(BG)
    surface = QColor(SURFACE)
    text = QColor(TEXT)
    muted = QColor(MUTED)
    accent = QColor(ACCENT)
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, QColor(OMNIBOX))
    pal.setColor(QPalette.ColorRole.AlternateBase, surface)
    pal.setColor(QPalette.ColorRole.ToolTipBase, surface)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, QColor(SURFACE2))
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link, QColor(ACCENT2))
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#140800"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, muted)
    app.setPalette(pal)
    app.setStyleSheet(_dark_qss())


def _dark_qss() -> str:
    return f"""
    QMainWindow, QWidget {{
        background: {BG};
        color: {TEXT};
        font-size: 13px;
    }}
    QToolBar {{
        background: {SURFACE};
        border: 0;
        border-bottom: 1px solid {BORDER};
        spacing: 4px;
        padding: 4px 8px;
    }}
    QToolBar QToolButton {{
        background: transparent;
        color: {TEXT};
        border: 1px solid transparent;
        border-radius: 7px;
        padding: 4px 7px;
        min-width: 22px;
        min-height: 22px;
    }}
    QToolBar QToolButton:hover {{ background: {RAISED}; border-color: {BORDER}; }}
    QToolBar QToolButton:pressed {{ background: {BORDER}; }}
    QToolBar QToolButton:checked {{
        background: #2a1a14;
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    QLineEdit#omnibox {{
        background: {OMNIBOX};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 6px 12px;
        selection-background-color: {ACCENT};
        selection-color: #140800;
    }}
    QLineEdit#omnibox:focus {{
        border-color: {ACCENT};
    }}
    QTabWidget::pane {{
        border: 0;
        background: {BG};
    }}
    QTabBar {{
        background: {SURFACE};
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background: {SURFACE};
        color: {MUTED};
        border: 0;
        border-right: 1px solid {BORDER};
        padding: 7px 14px;
        min-width: 80px;
        max-width: 220px;
    }}
    QTabBar::tab:selected {{
        background: {BG};
        color: {TEXT};
        border-bottom: 2px solid {ACCENT};
    }}
    QTabBar::tab:hover {{ color: {TEXT}; background: {SURFACE2}; }}
    QTabBar::close-button {{
        image: none;
    }}
    QPushButton {{
        background: {SURFACE2};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 5px 10px;
    }}
    QPushButton:hover {{ background: {RAISED}; }}
    QPushButton:pressed {{ background: {BORDER}; }}
    QListWidget, QTreeWidget, QTextEdit, QPlainTextEdit {{
        background: {OMNIBOX};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
    QListWidget::item:selected {{ background: #2a1a14; color: {TEXT}; }}
    QListWidget::item:hover {{ background: {SURFACE2}; }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        min-height: 24px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {BORDER};
        min-width: 24px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QProgressBar {{
        background: {SURFACE2};
        border: 0;
        border-radius: 3px;
        text-align: center;
        color: {TEXT};
        height: 8px;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
        border-radius: 3px;
    }}
    QMenu {{
        background: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 4px;
    }}
    QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {RAISED}; }}
    QStatusBar {{
        background: {SURFACE};
        color: {MUTED};
        border-top: 1px solid {BORDER};
    }}
    QSplitter::handle {{ background: {BORDER}; }}
    QFrame#panel {{
        background: {SURFACE};
        border-top: 1px solid {BORDER};
    }}
    QFrame#palette {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}
    QFrame#findbar {{
        background: {SURFACE};
        border-top: 1px solid {BORDER};
    }}
    QToolTip {{
        background: {SURFACE2};
        color: {TEXT};
        border: 1px solid {BORDER};
        padding: 4px 8px;
    }}
    """


def _light_qss() -> str:
    return """
    QMainWindow, QWidget { font-size: 13px; }
    QLineEdit#omnibox {
        border: 1px solid #c9d1d9;
        border-radius: 10px;
        padding: 6px 12px;
    }
    """
