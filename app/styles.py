"""
styles.py
=========
Estilos e temas da aplicação CSCollectManager.

Tema escuro profissional com suporte a ícones.
"""


class DarkTheme:
    """Tema escuro completo para a aplicação."""
    
    # Cores base
    BG_PRIMARY = "#0f1826"
    BG_SECONDARY = "#1a2740"
    BG_TERTIARY = "#16223c"
    BG_HOVER = "#2a3a57"
    BG_SELECTED = "#3d5a80"
    
    FG_PRIMARY = "#e6edf6"
    FG_SECONDARY = "#9db3d1"
    FG_DISABLED = "#6b7f9e"
    
    BORDER = "#2a3a57"
    BORDER_FOCUS = "#3e9cf7"
    
    ACCENT = "#3e9cf7"
    ACCENT_HOVER = "#5aa9f9"
    ACCENT_PRESSED = "#0e42b0"
    
    SUCCESS = "#4caf50"
    WARNING = "#ff9800"
    ERROR = "#f44336"
    INFO = "#2196f3"
    
    # Stylesheet completo
    STYLESHEET = """
    /* ===== GLOBAL ===== */
    QWidget {
        background-color: #0f1826;
        color: #e6edf6;
        font-family: "Segoe UI", "Roboto", sans-serif;
        font-size: 10pt;
        selection-background-color: #3e9cf7;
        selection-color: white;
    }
    
    /* ===== MAIN WINDOW ===== */
    QMainWindow {
        background-color: #0f1826;
    }
    
    QMainWindow::separator {
        background-color: #2a3a57;
        width: 2px;
        height: 2px;
    }
    
    /* ===== MENU BAR ===== */
    QMenuBar {
        background-color: #16223c;
        color: #e6edf6;
        border-bottom: 1px solid #2a3a57;
        padding: 2px;
    }
    
    QMenuBar::item {
        background: transparent;
        padding: 6px 12px;
        border-radius: 8px;
    }
    
    QMenuBar::item:selected {
        background-color: #2a3a57;
    }
    
    QMenuBar::item:pressed {
        background-color: #3e9cf7;
    }
    
    QMenu {
        background-color: #1a2740;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        padding: 4px;
    }
    
    QMenu::item {
        padding: 8px 32px 8px 24px;
        border-radius: 8px;
        margin: 2px;
    }
    
    QMenu::item:selected {
        background-color: #3d5a80;
    }
    
    QMenu::separator {
        height: 1px;
        background-color: #2a3a57;
        margin: 4px 8px;
    }
    
    QMenu::icon {
        padding-left: 8px;
    }
    
    /* ===== TOOLBAR ===== */
    QToolBar {
        background-color: #16223c;
        border: none;
        border-bottom: 1px solid #2a3a57;
        padding: 4px 8px;
        spacing: 4px;
    }
    
    QToolBar::separator {
        background-color: #2a3a57;
        width: 1px;
        margin: 4px 8px;
    }
    
    QToolButton {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 6px 12px;
        color: #e6edf6;
    }
    
    QToolButton:hover {
        background-color: #2a3a57;
        border-color: #2a3a57;
    }
    
    QToolButton:pressed {
        background-color: #1d6bb0;
    }
    
    QToolButton:checked {
        background-color: #1d6bb0;
        border-color: #3e9cf7;
    }
    
    /* ===== BUTTONS ===== */
    QPushButton {
        background-color: #2a3a57;
        color: #e6edf6;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        padding: 8px 16px;
        min-height: 20px;
        min-width: 80px;
    }
    
    QPushButton:hover {
        background-color: #35507e;
        border-color: #35507e;
    }
    
    QPushButton:pressed {
        background-color: #3e9cf7;
        border-color: #3e9cf7;
    }
    
    QPushButton:disabled {
        background-color: #16223c;
        color: #6b7f9e;
        border-color: #16223c;
    }
    
    QPushButton:default {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3e9cf7, stop:1 #1d6bb0);
        color: #ffffff;
        border: none;
        font-weight: bold;
    }

    QPushButton:default:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5aa9f9, stop:1 #2a7cc4);
    }

    QPushButton:default:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d6bb0, stop:1 #0e42b0);
    }
    
    /* ===== INPUT FIELDS ===== */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
        background-color: #1a2740;
        color: #e6edf6;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        padding: 8px;
        selection-background-color: #3e9cf7;
    }
    
    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {
        border-color: #35507e;
    }
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
        border-color: #3e9cf7;
    }
    
    QLineEdit:disabled, QTextEdit:disabled {
        background-color: #16223c;
        color: #6b7f9e;
    }
    
    /* ===== COMBO BOX ===== */
    QComboBox {
        background-color: #1a2740;
        color: #e6edf6;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        padding: 8px 12px;
        min-height: 20px;
    }
    
    QComboBox:hover {
        border-color: #35507e;
    }
    
    QComboBox:focus {
        border-color: #3e9cf7;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #e6edf6;
        margin-right: 8px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #1a2740;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        selection-background-color: #3d5a80;
        outline: none;
    }
    
    /* ===== TABLE VIEW ===== */
    QTableView {
        background-color: #0f1826;
        alternate-background-color: #1a2740;
        color: #e6edf6;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        gridline-color: #2a3a57;
        selection-background-color: #3d5a80;
    }
    
    QTableView::item {
        padding: 4px 8px;
        border: none;
    }
    
    QTableView::item:selected {
        background-color: #3d5a80;
    }
    
    QTableView::item:hover {
        background-color: #16223c;
    }
    
    QHeaderView {
        background-color: #16223c;
        border: none;
    }
    
    QHeaderView::section {
        background-color: #16223c;
        color: #e6edf6;
        border: none;
        border-right: 1px solid #2a3a57;
        border-bottom: 1px solid #2a3a57;
        padding: 8px 12px;
        font-weight: bold;
    }
    
    QHeaderView::section:hover {
        background-color: #2a3a57;
    }
    
    QHeaderView::section:pressed {
        background-color: #1d6bb0;
    }
    
    /* ===== SCROLL BARS ===== */
    QScrollBar:vertical {
        background-color: #0f1826;
        width: 12px;
        margin: 0;
    }
    
    QScrollBar::handle:vertical {
        background-color: #5a5a5a;
        min-height: 30px;
        border-radius: 8px;
        margin: 2px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #7a7a7a;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    
    QScrollBar:horizontal {
        background-color: #0f1826;
        height: 12px;
        margin: 0;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #5a5a5a;
        min-width: 30px;
        border-radius: 8px;
        margin: 2px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #7a7a7a;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0;
    }
    
    /* ===== GROUP BOX ===== */
    QGroupBox {
        border: 1px solid #2a3a57;
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 12px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: #e6edf6;
    }
    
    /* ===== TABS ===== */
    QTabWidget::pane {
        border: 1px solid #2a3a57;
        border-radius: 8px;
        background-color: #0f1826;
    }
    
    QTabBar::tab {
        background-color: #16223c;
        color: #9db3d1;
        border: none;
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    
    QTabBar::tab:selected {
        background-color: #0f1826;
        color: #e6edf6;
        border-bottom: 2px solid #3e9cf7;
    }
    
    QTabBar::tab:hover:!selected {
        background-color: #2a3a57;
        color: #e6edf6;
    }
    
    /* ===== PROGRESS BAR ===== */
    QProgressBar {
        background-color: #2a3a57;
        border: none;
        border-radius: 8px;
        text-align: center;
        color: #e6edf6;
        height: 20px;
    }
    
    QProgressBar::chunk {
        background-color: #3e9cf7;
        border-radius: 8px;
    }
    
    /* ===== STATUS BAR ===== */
    QStatusBar {
        background-color: #3e9cf7;
        color: white;
        border: none;
        padding: 2px;
    }
    
    QStatusBar::item {
        border: none;
    }
    
    QStatusBar QLabel {
        background-color: transparent;
        color: white;
        padding: 0 8px;
    }
    
    /* ===== SPLITTER ===== */
    QSplitter::handle {
        background-color: #2a3a57;
    }
    
    QSplitter::handle:horizontal {
        width: 2px;
    }
    
    QSplitter::handle:vertical {
        height: 2px;
    }
    
    QSplitter::handle:hover {
        background-color: #3e9cf7;
    }
    
    /* ===== DIALOG ===== */
    QDialog {
        background-color: #0f1826;
    }
    
    /* ===== MESSAGE BOX ===== */
    QMessageBox {
        background-color: #0f1826;
    }
    
    QMessageBox QLabel {
        color: #e6edf6;
    }
    
    /* ===== TOOLTIPS ===== */
    QToolTip {
        background-color: #1a2740;
        color: #e6edf6;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        padding: 6px 10px;
    }
    
    /* ===== CHECKBOX ===== */
    QCheckBox {
        spacing: 8px;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #2a3a57;
        border-radius: 3px;
        background-color: #1a2740;
    }
    
    QCheckBox::indicator:hover {
        border-color: #35507e;
    }
    
    QCheckBox::indicator:checked {
        background-color: #3e9cf7;
        border-color: #3e9cf7;
    }
    
    QCheckBox::indicator:checked:hover {
        background-color: #5aa9f9;
        border-color: #5aa9f9;
    }
    
    /* ===== RADIO BUTTON ===== */
    QRadioButton {
        spacing: 8px;
    }
    
    QRadioButton::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #2a3a57;
        border-radius: 10px;
        background-color: #1a2740;
    }
    
    QRadioButton::indicator:hover {
        border-color: #35507e;
    }
    
    QRadioButton::indicator:checked {
        background-color: #3e9cf7;
        border-color: #3e9cf7;
    }
    
    /* ===== LIST VIEW ===== */
    QListView, QListWidget {
        background-color: #0f1826;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        outline: none;
    }
    
    QListView::item, QListWidget::item {
        padding: 8px;
        border-radius: 8px;
        margin: 2px;
    }
    
    QListView::item:selected, QListWidget::item:selected {
        background-color: #3d5a80;
    }
    
    QListView::item:hover, QListWidget::item:hover {
        background-color: #16223c;
    }
    
    /* ===== TREE VIEW ===== */
    QTreeView {
        background-color: #0f1826;
        border: 1px solid #2a3a57;
        border-radius: 8px;
        outline: none;
    }
    
    QTreeView::item {
        padding: 4px;
    }
    
    QTreeView::item:selected {
        background-color: #3d5a80;
    }
    
    QTreeView::item:hover {
        background-color: #16223c;
    }
    
    QTreeView::branch:has-children:closed {
        border-image: none;
        image: none;
    }
    
    QTreeView::branch:has-children:open {
        border-image: none;
        image: none;
    }
    
    /* ===== SLIDER ===== */
    QSlider::groove:horizontal {
        border: none;
        height: 4px;
        background-color: #2a3a57;
        border-radius: 2px;
    }
    
    QSlider::handle:horizontal {
        background-color: #3e9cf7;
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }
    
    QSlider::handle:horizontal:hover {
        background-color: #5aa9f9;
    }
    
    /* ===== FRAME ===== */
    QFrame[frameShape="4"], /* HLine */
    QFrame[frameShape="5"]  /* VLine */ {
        background-color: #2a3a57;
    }
    
    /* ===== LABEL ===== */
    QLabel {
        background-color: transparent;
    }
    
    QLabel[class="title"] {
        font-size: 14pt;
        font-weight: bold;
        color: #ffffff;
    }
    
    QLabel[class="subtitle"] {
        font-size: 11pt;
        color: #9db3d1;
    }
    
    QLabel[class="error"] {
        color: #f44336;
    }
    
    QLabel[class="success"] {
        color: #4caf50;
    }
    
    QLabel[class="warning"] {
        color: #ff9800;
    }
    """


class LightTheme:
    """Tema claro para a aplicação."""
    
    # Cores base
    BG_PRIMARY = "#ffffff"
    BG_SECONDARY = "#f5f5f5"
    BG_TERTIARY = "#e0e0e0"
    
    FG_PRIMARY = "#333333"
    FG_SECONDARY = "#6b7f9e"
    
    ACCENT = "#3e9cf7"
    
    # Stylesheet (simplificado)
    STYLESHEET = """
    QWidget {
        background-color: #ffffff;
        color: #333333;
        font-family: "Segoe UI";
        font-size: 10pt;
    }
    
    QPushButton {
        background-color: #e0e0e0;
        border: 1px solid #e6edf6;
        border-radius: 8px;
        padding: 8px 16px;
    }
    
    QPushButton:hover {
        background-color: #d0d0d0;
    }
    
    QPushButton:pressed {
        background-color: #3e9cf7;
        color: white;
    }
    
    QLineEdit {
        background-color: #ffffff;
        border: 1px solid #e6edf6;
        border-radius: 8px;
        padding: 8px;
    }
    
    QLineEdit:focus {
        border-color: #3e9cf7;
    }
    
    QTableView {
        background-color: #ffffff;
        alternate-background-color: #f5f5f5;
        border: 1px solid #e6edf6;
    }
    """


def get_theme_stylesheet(theme: str = "dark") -> str:
    """
    Retorna stylesheet do tema.
    
    Args:
        theme: 'dark' ou 'light'
        
    Returns:
        Stylesheet CSS
    """
    if theme == "light":
        return LightTheme.STYLESHEET
    return DarkTheme.STYLESHEET


def apply_theme(app, theme: str = "dark"):
    """
    Aplica tema à aplicação.
    
    Args:
        app: QApplication
        theme: 'dark' ou 'light'
    """
    app.setStyleSheet(get_theme_stylesheet(theme))
