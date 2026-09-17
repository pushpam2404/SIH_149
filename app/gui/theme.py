"""Visual theme: design tokens, bundled fonts, and the application stylesheet.

Everything visual lives here so views only set semantic hooks
(`objectName` / dynamic properties such as `variant="danger"`) instead of
hardcoding colours. Dark-only, tuned for a forensics/security tool:
slate surfaces, blue for primary actions, amber for attention, red
reserved strictly for destructive actions and failures.

Fonts (Fira Sans / Fira Code, SIL OFL — see assets/fonts/OFL.txt) are
loaded from the bundled assets; if they're missing the app falls back to
the platform UI and monospace fonts rather than failing.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

_ASSETS_DIR = Path(__file__).parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_ICONS_DIR = _ASSETS_DIR / "icons"

# --- Tokens -----------------------------------------------------------------

COLORS = {
    "bg": "#0B1220",
    "sidebar": "#0E1628",
    "surface": "#121B2E",
    "surface_alt": "#162136",
    "surface_raised": "#1A2640",
    "border": "#233250",
    "border_strong": "#31446A",
    "text": "#E6EDF7",
    "text_muted": "#9AA8BF",
    "text_subtle": "#8391A9",
    "primary": "#2563EB",
    "primary_hover": "#1D4ED8",
    "primary_pressed": "#1E40AF",
    "primary_soft": "#1B2D4F",
    "accent": "#F59E0B",
    "accent_soft": "#3A2A0E",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "danger_pressed": "#991B1B",
    "danger_soft": "#3A1A1F",
    "success": "#4ADE80",
    "success_soft": "#12301F",
    "danger_text": "#F87171",
    "primary_text": "#60A5FA",
    "info": "#38BDF8",
    "info_soft": "#0F2A3A",
    "selection": "#1E3A66",
}

TONE_COLORS = {
    "neutral": (COLORS["text_muted"], COLORS["surface_raised"]),
    "info": (COLORS["info"], COLORS["info_soft"]),
    "success": (COLORS["success"], COLORS["success_soft"]),
    "warning": (COLORS["accent"], COLORS["accent_soft"]),
    "danger": (COLORS["danger_text"], COLORS["danger_soft"]),
    "primary": (COLORS["primary_text"], COLORS["primary_soft"]),
}

RADIUS = {"sm": 6, "md": 8, "lg": 12}

UI_FONT_FALLBACKS = ["Fira Sans", ".AppleSystemUIFont", "Segoe UI", "Helvetica Neue", "Arial"]
MONO_FONT_FALLBACKS = ["Fira Code", "SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", "monospace"]


def _css_family(families: list[str]) -> str:
    return ", ".join(f'"{f}"' for f in families)


def load_fonts() -> None:
    if not _FONTS_DIR.is_dir():
        logger.info("bundled fonts not found at %s; using system fonts", _FONTS_DIR)
        return
    for font_file in sorted(_FONTS_DIR.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(font_file)) < 0:
            logger.warning("could not load font %s", font_file.name)


def mono_font(pixel_size: int = 12) -> QFont:
    font = QFont()
    font.setFamilies(MONO_FONT_FALLBACKS)
    font.setStyleHint(QFont.Monospace)
    font.setPixelSize(pixel_size)
    return font


def build_stylesheet() -> str:
    c = COLORS
    ui = _css_family(UI_FONT_FALLBACKS)
    mono = _css_family(MONO_FONT_FALLBACKS)
    check_icon = (_ICONS_DIR / "check.svg").as_posix()
    return f"""
* {{
    font-family: {ui};
    font-size: 13px;
    color: {c['text']};
    outline: none;
}}
QMainWindow, QWidget#AppRoot, QStackedWidget#Pages, QWidget#Page {{
    background: {c['bg']};
}}
QToolTip {{
    background: {c['surface_raised']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    padding: 6px 8px;
    border-radius: {RADIUS['sm']}px;
}}

/* ---------- Sidebar ---------- */
QFrame#Sidebar {{
    background: {c['sidebar']};
    border-right: 1px solid {c['border']};
}}
QLabel#BrandTitle {{
    font-size: 15px;
    font-weight: 600;
}}
QLabel#BrandSubtitle, QLabel#SidebarSection, QLabel#SidebarFooter {{
    color: {c['text_subtle']};
    font-size: 11px;
}}
QLabel#SidebarSection {{
    font-weight: 600;
    padding: 0 12px;
}}
QPushButton[nav="true"] {{
    text-align: left;
    padding: 9px 12px;
    border: none;
    border-radius: {RADIUS['md']}px;
    background: transparent;
    color: {c['text_muted']};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton[nav="true"]:hover {{
    background: {c['surface_alt']};
    color: {c['text']};
}}
QPushButton[nav="true"]:checked {{
    background: {c['primary_soft']};
    color: {c['text']};
    font-weight: 600;
}}
QPushButton[nav="true"]:focus {{
    border: 1px solid {c['primary']};
}}

/* ---------- Page header ---------- */
QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 600;
}}
QLabel#PageSubtitle {{
    color: {c['text_muted']};
    font-size: 13px;
}}

/* ---------- Cards ---------- */
QFrame#Card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['lg']}px;
}}
QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 600;
}}
QLabel#CardSubtitle, QLabel#Hint {{
    color: {c['text_muted']};
    font-size: 12px;
}}
QLabel#FieldLabel {{
    color: {c['text_muted']};
    font-size: 12px;
    font-weight: 500;
}}
QFrame#StatTile {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['lg']}px;
}}
QLabel#StatLabel {{
    color: {c['text_muted']};
    font-size: 12px;
    font-weight: 500;
}}
QLabel#StatValue {{
    font-size: 24px;
    font-weight: 600;
}}
QLabel#StatCaption {{
    color: {c['text_subtle']};
    font-size: 11px;
}}
QFrame#Callout {{
    background: {c['accent_soft']};
    border: 1px solid #5A4213;
    border-radius: {RADIUS['md']}px;
}}
QFrame#Callout QLabel {{
    color: #F8D38A;
    font-size: 12px;
}}
QFrame#DangerCallout {{
    background: {c['danger_soft']};
    border: 1px solid #5C2530;
    border-radius: {RADIUS['md']}px;
}}
QFrame#DangerCallout QLabel {{
    color: #FCA5A5;
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background: {c['surface_raised']};
    border: 1px solid {c['border_strong']};
    border-radius: {RADIUS['md']}px;
    padding: 8px 14px;
    min-height: 20px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: #213050;
    border-color: #3C5282;
}}
QPushButton:pressed {{
    background: #1A2744;
}}
QPushButton:focus {{
    border: 1px solid {c['primary']};
}}
QPushButton:disabled {{
    color: {c['text_subtle']};
    background: {c['surface_alt']};
    border-color: {c['border']};
}}
QPushButton[variant="primary"] {{
    background: {c['primary']};
    border: 1px solid {c['primary']};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{
    background: {c['primary_hover']};
    border-color: {c['primary_hover']};
}}
QPushButton[variant="primary"]:pressed {{
    background: {c['primary_pressed']};
}}
QPushButton[variant="danger"] {{
    background: {c['danger']};
    border: 1px solid {c['danger']};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton[variant="danger"]:hover {{
    background: {c['danger_hover']};
    border-color: {c['danger_hover']};
}}
QPushButton[variant="danger"]:pressed {{
    background: {c['danger_pressed']};
}}
QPushButton[variant="danger"]:disabled, QPushButton[variant="primary"]:disabled {{
    background: {c['surface_alt']};
    border-color: {c['border']};
    color: {c['text_subtle']};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {c['text_muted']};
}}
QPushButton[variant="ghost"]:hover {{
    background: {c['surface_alt']};
    color: {c['text']};
}}
QPushButton[size="lg"] {{
    padding: 11px 18px;
    font-size: 14px;
}}

/* ---------- Inputs ---------- */
QLineEdit, QComboBox, QSpinBox {{
    background: {c['surface_alt']};
    border: 1px solid {c['border_strong']};
    border-radius: {RADIUS['md']}px;
    padding: 7px 10px;
    min-height: 20px;
    selection-background-color: {c['selection']};
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: #3C5282;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {c['primary']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {c['surface_raised']};
    border: 1px solid {c['border_strong']};
    selection-background-color: {c['selection']};
    padding: 4px;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {c['border_strong']};
    background: {c['surface_alt']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['primary']};
}}
QCheckBox::indicator:checked {{
    background: {c['primary']};
    border-color: {c['primary']};
    image: url({check_icon});
}}

/* ---------- Tables & lists ---------- */
QTableWidget, QTableView, QListWidget {{
    background: {c['surface']};
    alternate-background-color: {c['surface_alt']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    gridline-color: transparent;
    selection-background-color: {c['selection']};
    selection-color: {c['text']};
}}
QTableWidget::item, QTableView::item {{
    padding: 0 8px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {c['selection']};
}}
QListWidget {{
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: {RADIUS['sm']}px;
}}
QListWidget::item:hover {{
    background: {c['surface_alt']};
}}
QListWidget::item:selected {{
    background: {c['selection']};
    color: {c['text']};
}}
QHeaderView::section {{
    background: {c['surface_alt']};
    color: {c['text_muted']};
    border: none;
    border-bottom: 1px solid {c['border']};
    padding: 8px;
    font-size: 11px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: {c['surface_alt']};
    border: none;
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: none;
    top: -1px;
}}
QTabBar {{
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    color: {c['text_muted']};
    padding: 8px 14px;
    margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:hover {{
    color: {c['text']};
}}
QTabBar::tab:selected {{
    color: {c['text']};
    border-bottom: 2px solid {c['primary_text']};
    font-weight: 600;
}}

/* ---------- Qt's own file dialog (used on every OS) ---------- */
QFileDialog QTreeView, QFileDialog QListView, QTreeView, QListView {{
    background: {c['surface']};
    alternate-background-color: {c['surface_alt']};
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    selection-background-color: {c['selection']};
    selection-color: {c['text']};
}}
QTreeView::item, QListView::item {{
    padding: 4px 6px;
}}
QTreeView::item:hover, QListView::item:hover {{
    background: {c['surface_alt']};
}}
QTreeView::item:selected, QListView::item:selected {{
    background: {c['selection']};
    color: {c['text']};
}}
QFileDialog QListView#sidebar {{
    background: {c['sidebar']};
}}
QToolButton {{
    background: {c['surface_raised']};
    border: 1px solid {c['border_strong']};
    border-radius: {RADIUS['sm']}px;
    padding: 4px;
}}
QToolButton:hover {{
    background: #213050;
}}
QToolButton:disabled {{
    background: {c['surface_alt']};
    border-color: {c['border']};
}}
QMenu {{
    background: {c['surface_raised']};
    border: 1px solid {c['border_strong']};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: {RADIUS['sm']}px;
}}
QMenu::item:selected {{
    background: {c['selection']};
}}

/* ---------- Progress & log ---------- */
QProgressBar {{
    background: {c['surface_alt']};
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {c['primary']};
    border-radius: 3px;
}}
QPlainTextEdit#Log {{
    background: #0A101C;
    border: 1px solid {c['border']};
    border-radius: {RADIUS['md']}px;
    padding: 8px;
    font-family: {mono};
    font-size: 12px;
    color: #B8C4D8;
    selection-background-color: {c['selection']};
}}
QLabel#StatusText {{
    font-weight: 500;
}}
QLabel#Mono {{
    font-family: {mono};
    font-size: 12px;
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['border_strong']};
    border-radius: 3px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #45598A;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border_strong']};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}

/* ---------- Dialogs ---------- */
QDialog, QMessageBox, QInputDialog {{
    background: {c['surface']};
}}
QMessageBox QLabel {{
    color: {c['text']};
}}
QSplitter::handle {{
    background: transparent;
}}
"""


def _palette() -> QPalette:
    c = COLORS
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(c["bg"]))
    pal.setColor(QPalette.WindowText, QColor(c["text"]))
    pal.setColor(QPalette.Base, QColor(c["surface"]))
    pal.setColor(QPalette.AlternateBase, QColor(c["surface_alt"]))
    pal.setColor(QPalette.Text, QColor(c["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(c["text_subtle"]))
    pal.setColor(QPalette.Button, QColor(c["surface_raised"]))
    pal.setColor(QPalette.ButtonText, QColor(c["text"]))
    pal.setColor(QPalette.Highlight, QColor(c["selection"]))
    pal.setColor(QPalette.HighlightedText, QColor(c["text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(c["surface_raised"]))
    pal.setColor(QPalette.ToolTipText, QColor(c["text"]))
    pal.setColor(QPalette.Link, QColor(c["primary"]))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(c["text_subtle"]))
    return pal


def apply_theme(app: QApplication) -> None:
    """Fusion style + dark palette + stylesheet. Fusion makes QSS render the
    same on macOS/Linux/Windows instead of mixing with native widget chrome."""
    load_fonts()
    # Qt-drawn dialogs everywhere (file pickers, message boxes, input dialogs),
    # so they follow this theme and look the same on Windows, Linux and macOS.
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    app.setStyle("Fusion")
    app.setPalette(_palette())
    ui_font = QFont()
    ui_font.setFamilies(UI_FONT_FALLBACKS)
    ui_font.setPixelSize(13)
    app.setFont(ui_font)
    app.setStyleSheet(build_stylesheet())
