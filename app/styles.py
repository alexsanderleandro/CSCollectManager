"""
styles.py
=========
Estilos e temas da aplicação CSCollectManager.

Tema escuro profissional com suporte a ícones.
"""


class DarkTheme:
    """Tema escuro completo para a aplicação."""
    
    # Cores base
    BG_PRIMARY = "#1e1e1e"
    BG_SECONDARY = "#252526"
    BG_TERTIARY = "#2d2d30"
    BG_HOVER = "#3e3e42"
    BG_SELECTED = "#094771"
    
    FG_PRIMARY = "#cccccc"
    FG_SECONDARY = "#9d9d9d"
    FG_DISABLED = "#666666"
    
    BORDER = "#3e3e42"
    BORDER_FOCUS = "#0078d4"
    
    ACCENT = "#0078d4"
    ACCENT_HOVER = "#1e8ad4"
    ACCENT_PRESSED = "#005a9e"
    
    SUCCESS = "#4caf50"
    WARNING = "#ff9800"
    ERROR = "#f44336"
    INFO = "#2196f3"
    
    # Stylesheet completo
    STYLESHEET = """
    /* ===== GLOBAL ===== */
    QWidget {
        background-color: #1e1e1e;
        color: #cccccc;
        font-family: "Segoe UI", "Roboto", sans-serif;
        font-size: 10pt;
        selection-background-color: #0078d4;
        selection-color: white;
    }
    
    /* ===== MAIN WINDOW ===== */
    QMainWindow {
        background-color: #1e1e1e;
    }
    
    QMainWindow::separator {
        background-color: #3e3e42;
        width: 2px;
        height: 2px;
    }
    
    /* ===== MENU BAR ===== */
    QMenuBar {
        background-color: #2d2d30;
        color: #cccccc;
        border-bottom: 1px solid #3e3e42;
        padding: 2px;
    }
    
    QMenuBar::item {
        background: transparent;
        padding: 6px 12px;
        border-radius: 4px;
    }
    
    QMenuBar::item:selected {
        background-color: #3e3e42;
    }
    
    QMenuBar::item:pressed {
        background-color: #0078d4;
    }
    
    QMenu {
        background-color: #252526;
        border: 1px solid #3e3e42;
        border-radius: 6px;
        padding: 4px;
    }
    
    QMenu::item {
        padding: 8px 32px 8px 24px;
        border-radius: 4px;
        margin: 2px;
    }
    
    QMenu::item:selected {
        background-color: #094771;
    }
    
    QMenu::separator {
        height: 1px;
        background-color: #3e3e42;
        margin: 4px 8px;
    }
    
    QMenu::icon {
        padding-left: 8px;
    }
    
    /* ===== TOOLBAR ===== */
    QToolBar {
        background-color: #2d2d30;
        border: none;
        border-bottom: 1px solid #3e3e42;
        padding: 4px 8px;
        spacing: 4px;
    }
    
    QToolBar::separator {
        background-color: #3e3e42;
        width: 1px;
        margin: 4px 8px;
    }
    
    QToolButton {
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 6px 12px;
        color: #cccccc;
    }
    
    QToolButton:hover {
        background-color: #3e3e42;
        border-color: #3e3e42;
    }
    
    QToolButton:pressed {
        background-color: #094771;
    }
    
    QToolButton:checked {
        background-color: #094771;
        border-color: #0078d4;
    }
    
    /* ===== BUTTONS ===== */
    QPushButton {
        background-color: #3e3e42;
        color: #cccccc;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 8px 16px;
        min-height: 20px;
        min-width: 80px;
    }
    
    QPushButton:hover {
        background-color: #505050;
        border-color: #505050;
    }
    
    QPushButton:pressed {
        background-color: #0078d4;
        border-color: #0078d4;
    }
    
    QPushButton:disabled {
        background-color: #2d2d30;
        color: #666666;
        border-color: #2d2d30;
    }
    
    QPushButton:default {
        background-color: #0078d4;
        border-color: #0078d4;
    }
    
    QPushButton:default:hover {
        background-color: #1e8ad4;
        border-color: #1e8ad4;
    }
    
    /* ===== INPUT FIELDS ===== */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 8px;
        selection-background-color: #0078d4;
    }
    
    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {
        border-color: #505050;
    }
    
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
        border-color: #0078d4;
    }
    
    QLineEdit:disabled, QTextEdit:disabled {
        background-color: #2d2d30;
        color: #666666;
    }
    
    /* ===== COMBO BOX ===== */
    QComboBox {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 8px 12px;
        min-height: 20px;
    }
    
    QComboBox:hover {
        border-color: #505050;
    }
    
    QComboBox:focus {
        border-color: #0078d4;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    
    QComboBox::down-arrow {
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid #cccccc;
        margin-right: 8px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #252526;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        selection-background-color: #094771;
        outline: none;
    }
    
    /* ===== TABLE VIEW ===== */
    QTableView {
        background-color: #1e1e1e;
        alternate-background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        gridline-color: #3e3e42;
        selection-background-color: #094771;
    }
    
    QTableView::item {
        padding: 4px 8px;
        border: none;
    }
    
    QTableView::item:selected {
        background-color: #094771;
    }
    
    QTableView::item:hover {
        background-color: #2d2d30;
    }
    
    QHeaderView {
        background-color: #2d2d30;
        border: none;
    }
    
    QHeaderView::section {
        background-color: #2d2d30;
        color: #cccccc;
        border: none;
        border-right: 1px solid #3e3e42;
        border-bottom: 1px solid #3e3e42;
        padding: 8px 12px;
        font-weight: bold;
    }
    
    QHeaderView::section:hover {
        background-color: #3e3e42;
    }
    
    QHeaderView::section:pressed {
        background-color: #094771;
    }
    
    /* ===== SCROLL BARS ===== */
    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 12px;
        margin: 0;
    }
    
    QScrollBar::handle:vertical {
        background-color: #5a5a5a;
        min-height: 30px;
        border-radius: 6px;
        margin: 2px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #7a7a7a;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    
    QScrollBar:horizontal {
        background-color: #1e1e1e;
        height: 12px;
        margin: 0;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #5a5a5a;
        min-width: 30px;
        border-radius: 6px;
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
        border: 1px solid #3e3e42;
        border-radius: 6px;
        margin-top: 12px;
        padding-top: 12px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
        color: #cccccc;
    }
    
    /* ===== TABS ===== */
    QTabWidget::pane {
        border: 1px solid #3e3e42;
        border-radius: 4px;
        background-color: #1e1e1e;
    }
    
    QTabBar::tab {
        background-color: #2d2d30;
        color: #9d9d9d;
        border: none;
        padding: 10px 20px;
        margin-right: 2px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    
    QTabBar::tab:selected {
        background-color: #1e1e1e;
        color: #cccccc;
        border-bottom: 2px solid #0078d4;
    }
    
    QTabBar::tab:hover:!selected {
        background-color: #3e3e42;
        color: #cccccc;
    }
    
    /* ===== PROGRESS BAR ===== */
    QProgressBar {
        background-color: #3e3e42;
        border: none;
        border-radius: 4px;
        text-align: center;
        color: #cccccc;
        height: 20px;
    }
    
    QProgressBar::chunk {
        background-color: #0078d4;
        border-radius: 4px;
    }
    
    /* ===== STATUS BAR ===== */
    QStatusBar {
        background-color: #007acc;
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
        background-color: #3e3e42;
    }
    
    QSplitter::handle:horizontal {
        width: 2px;
    }
    
    QSplitter::handle:vertical {
        height: 2px;
    }
    
    QSplitter::handle:hover {
        background-color: #0078d4;
    }
    
    /* ===== DIALOG ===== */
    QDialog {
        background-color: #1e1e1e;
    }
    
    /* ===== MESSAGE BOX ===== */
    QMessageBox {
        background-color: #1e1e1e;
    }
    
    QMessageBox QLabel {
        color: #cccccc;
    }
    
    /* ===== TOOLTIPS ===== */
    QToolTip {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 6px 10px;
    }
    
    /* ===== CHECKBOX ===== */
    QCheckBox {
        spacing: 8px;
    }
    
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #3e3e42;
        border-radius: 3px;
        background-color: #252526;
    }
    
    QCheckBox::indicator:hover {
        border-color: #505050;
    }
    
    QCheckBox::indicator:checked {
        background-color: #0078d4;
        border-color: #0078d4;
    }
    
    QCheckBox::indicator:checked:hover {
        background-color: #1e8ad4;
        border-color: #1e8ad4;
    }
    
    /* ===== RADIO BUTTON ===== */
    QRadioButton {
        spacing: 8px;
    }
    
    QRadioButton::indicator {
        width: 18px;
        height: 18px;
        border: 2px solid #3e3e42;
        border-radius: 10px;
        background-color: #252526;
    }
    
    QRadioButton::indicator:hover {
        border-color: #505050;
    }
    
    QRadioButton::indicator:checked {
        background-color: #0078d4;
        border-color: #0078d4;
    }
    
    /* ===== LIST VIEW ===== */
    QListView, QListWidget {
        background-color: #1e1e1e;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        outline: none;
    }
    
    QListView::item, QListWidget::item {
        padding: 8px;
        border-radius: 4px;
        margin: 2px;
    }
    
    QListView::item:selected, QListWidget::item:selected {
        background-color: #094771;
    }
    
    QListView::item:hover, QListWidget::item:hover {
        background-color: #2d2d30;
    }
    
    /* ===== TREE VIEW ===== */
    QTreeView {
        background-color: #1e1e1e;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        outline: none;
    }
    
    QTreeView::item {
        padding: 4px;
    }
    
    QTreeView::item:selected {
        background-color: #094771;
    }
    
    QTreeView::item:hover {
        background-color: #2d2d30;
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
        background-color: #3e3e42;
        border-radius: 2px;
    }
    
    QSlider::handle:horizontal {
        background-color: #0078d4;
        width: 16px;
        height: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }
    
    QSlider::handle:horizontal:hover {
        background-color: #1e8ad4;
    }
    
    /* ===== FRAME ===== */
    QFrame[frameShape="4"], /* HLine */
    QFrame[frameShape="5"]  /* VLine */ {
        background-color: #3e3e42;
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
        color: #9d9d9d;
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
    FG_SECONDARY = "#666666"
    
    ACCENT = "#0078d4"
    
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
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 8px 16px;
    }
    
    QPushButton:hover {
        background-color: #d0d0d0;
    }
    
    QPushButton:pressed {
        background-color: #0078d4;
        color: white;
    }
    
    QLineEdit {
        background-color: #ffffff;
        border: 1px solid #cccccc;
        border-radius: 4px;
        padding: 8px;
    }
    
    QLineEdit:focus {
        border-color: #0078d4;
    }
    
    QTableView {
        background-color: #ffffff;
        alternate-background-color: #f5f5f5;
        border: 1px solid #cccccc;
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
