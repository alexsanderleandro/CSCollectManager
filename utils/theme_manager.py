"""
theme_manager.py
================
Gerenciador de temas da aplicação.
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor


class ThemeManager:
    """
    Gerenciador de temas e estilos da aplicação.
    """
    
    # Tema escuro padrão
    DARK_THEME = """
        QWidget {
            background-color: #1e1e1e;
            color: #cccccc;
            font-family: "Segoe UI";
            font-size: 10pt;
        }
        
        QMainWindow {
            background-color: #1e1e1e;
        }
        
        QGroupBox {
            border: 1px solid #3e3e42;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            color: #cccccc;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        
        QPushButton {
            background-color: #3e3e42;
            color: #cccccc;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 8px 16px;
            min-height: 20px;
        }
        
        QPushButton:hover {
            background-color: #505050;
            border-color: #505050;
        }
        
        QPushButton:pressed {
            background-color: #0078d4;
        }
        
        QPushButton:disabled {
            background-color: #2d2d30;
            color: #666666;
        }
        
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 6px;
            selection-background-color: #0078d4;
        }
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
            border-color: #0078d4;
        }
        
        QComboBox {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 6px;
            min-height: 20px;
        }
        
        QComboBox:hover {
            border-color: #505050;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #cccccc;
            margin-right: 5px;
        }
        
        QComboBox QAbstractItemView {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #3e3e42;
            selection-background-color: #0078d4;
        }
        
        QTableWidget {
            background-color: #252526;
            color: #cccccc;
            gridline-color: #3e3e42;
            border: 1px solid #3e3e42;
            border-radius: 4px;
        }
        
        QTableWidget::item {
            padding: 5px;
        }
        
        QTableWidget::item:selected {
            background-color: #0078d4;
        }
        
        QHeaderView::section {
            background-color: #2d2d30;
            color: #cccccc;
            padding: 8px;
            border: none;
            border-right: 1px solid #3e3e42;
            border-bottom: 1px solid #3e3e42;
        }
        
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
            border: none;
        }
        
        QScrollBar::handle:vertical {
            background-color: #3e3e42;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #505050;
        }
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollBar:horizontal {
            background-color: #1e1e1e;
            height: 12px;
            border: none;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #3e3e42;
            border-radius: 6px;
            min-width: 20px;
        }
        
        QProgressBar {
            background-color: #3e3e42;
            border: none;
            border-radius: 4px;
            text-align: center;
            color: white;
        }
        
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 4px;
        }
        
        QMessageBox {
            background-color: #2d2d30;
        }
        
        QMessageBox QLabel {
            color: #cccccc;
        }
        
        QToolTip {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #3e3e42;
            padding: 5px;
        }
    """
    
    @classmethod
    def apply_theme(cls, app: QApplication, theme: str = "dark"):
        """
        Aplica tema à aplicação.
        
        Args:
            app: Instância do QApplication
            theme: Nome do tema (dark, light)
        """
        if theme == "dark":
            app.setStyleSheet(cls.DARK_THEME)
            cls._apply_dark_palette(app)
        # TODO: Implementar tema claro se necessário
    
    @classmethod
    def _apply_dark_palette(cls, app: QApplication):
        """Aplica paleta de cores escura."""
        palette = QPalette()
        
        # Cores base
        palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(204, 204, 204))
        palette.setColor(QPalette.ColorRole.Base, QColor(37, 37, 38))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 48))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(37, 37, 38))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(204, 204, 204))
        palette.setColor(QPalette.ColorRole.Text, QColor(204, 204, 204))
        palette.setColor(QPalette.ColorRole.Button, QColor(62, 62, 66))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(204, 204, 204))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 212))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        
        app.setPalette(palette)
