"""
error_handler.py
================
Tratamento centralizado de erros da aplicação.

Fornece:
- Diálogo de erro amigável
- Logging automático de erros
- Relatório de erros
"""

import sys
import traceback
from typing import Optional, Callable
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QWidget, QMessageBox,
    QApplication
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont

from utils.logger import get_logger, log_exception
from utils.constants import APP_INFO, Icons, Paths

import os

logger = get_logger("error_handler")


class ErrorDialog(QDialog):
    """Diálogo de erro amigável."""
    
    def __init__(
        self,
        title: str,
        message: str,
        details: str = None,
        parent: QWidget = None
    ):
        super().__init__(parent)
        
        self._details = details
        
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        self._setup_ui(title, message, details)
    
    def _setup_ui(self, title: str, message: str, details: str):
        """Configura a interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Ícone e título
        header_layout = QHBoxLayout()
        
        icon_label = QLabel("❌")
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)
        
        title_layout = QVBoxLayout()
        
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #f44336;")
        title_layout.addWidget(title_label)
        
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #cccccc;")
        title_layout.addWidget(message_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Detalhes (colapsável)
        if details:
            self._details_text = QTextEdit()
            self._details_text.setPlainText(details)
            self._details_text.setReadOnly(True)
            self._details_text.setMaximumHeight(200)
            self._details_text.setStyleSheet("""
                QTextEdit {
                    background-color: #252526;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    font-family: Consolas, monospace;
                    font-size: 9pt;
                }
            """)
            self._details_text.setVisible(False)
            layout.addWidget(self._details_text)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        if details:
            self._btn_details = QPushButton("Mostrar Detalhes")
            self._btn_details.clicked.connect(self._toggle_details)
            btn_layout.addWidget(self._btn_details)
        
        btn_layout.addStretch()
        
        btn_copy = QPushButton("Copiar Erro")
        btn_copy.clicked.connect(self._copy_error)
        btn_layout.addWidget(btn_copy)
        
        btn_close = QPushButton("Fechar")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def _toggle_details(self):
        """Alterna visibilidade dos detalhes."""
        visible = self._details_text.isVisible()
        self._details_text.setVisible(not visible)
        self._btn_details.setText(
            "Ocultar Detalhes" if not visible else "Mostrar Detalhes"
        )
        self.adjustSize()
    
    def _copy_error(self):
        """Copia erro para clipboard."""
        text = f"Erro: {self.windowTitle()}\n\n"
        if self._details:
            text += f"Detalhes:\n{self._details}"
        
        QApplication.clipboard().setText(text)


class CriticalErrorDialog(QDialog):
    """Diálogo para erros críticos/fatais."""
    
    def __init__(
        self,
        error_type: str,
        error_message: str,
        traceback_text: str,
        parent: QWidget = None
    ):
        super().__init__(parent)
        
        self.setWindowTitle("Erro Crítico")
        self.setMinimumSize(600, 400)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        self._error_type = error_type
        self._error_message = error_message
        self._traceback = traceback_text
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura a interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("⛔ Ocorreu um erro crítico")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("color: #f44336;")
        layout.addWidget(header)
        
        # Mensagem
        msg = QLabel(
            "O aplicativo encontrou um erro inesperado. "
            "Por favor, envie o relatório abaixo para o suporte técnico."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("color: #9d9d9d;")
        layout.addWidget(msg)
        
        # Tipo do erro
        error_label = QLabel(f"Erro: {self._error_type}")
        error_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        layout.addWidget(error_label)
        
        # Mensagem do erro
        msg_label = QLabel(self._error_message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(msg_label)
        
        # Traceback
        trace_label = QLabel("Detalhes técnicos:")
        trace_label.setStyleSheet("color: #9d9d9d; margin-top: 10px;")
        layout.addWidget(trace_label)
        
        trace_text = QTextEdit()
        trace_text.setPlainText(self._generate_report())
        trace_text.setReadOnly(True)
        trace_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                font-family: Consolas, monospace;
                font-size: 9pt;
            }
        """)
        layout.addWidget(trace_text)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        btn_copy = QPushButton("📋 Copiar Relatório")
        btn_copy.clicked.connect(lambda: self._copy_report(trace_text.toPlainText()))
        btn_layout.addWidget(btn_copy)
        
        btn_save = QPushButton("💾 Salvar Relatório")
        btn_save.clicked.connect(lambda: self._save_report(trace_text.toPlainText()))
        btn_layout.addWidget(btn_save)
        
        btn_layout.addStretch()
        
        btn_restart = QPushButton("🔄 Reiniciar")
        btn_restart.clicked.connect(self._restart_app)
        btn_layout.addWidget(btn_restart)
        
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
    
    def _generate_report(self) -> str:
        """Gera relatório de erro."""
        import platform
        
        report = []
        report.append("=" * 60)
        report.append("RELATÓRIO DE ERRO - CSCollectManager")
        report.append("=" * 60)
        report.append("")
        report.append(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Versão: {APP_INFO.VERSION} (Build {APP_INFO.BUILD})")
        report.append(f"Sistema: {platform.system()} {platform.version()}")
        report.append(f"Python: {sys.version}")
        report.append("")
        report.append("-" * 60)
        report.append(f"Tipo: {self._error_type}")
        report.append(f"Mensagem: {self._error_message}")
        report.append("-" * 60)
        report.append("")
        report.append("TRACEBACK:")
        report.append(self._traceback)
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def _copy_report(self, text: str):
        """Copia relatório para clipboard."""
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copiado", "Relatório copiado para a área de transferência.")
    
    def _save_report(self, text: str):
        """Salva relatório em arquivo."""
        from PySide6.QtWidgets import QFileDialog
        
        filename = f"error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        default_path = os.path.join(Paths.LOGS_DIR, filename)
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Relatório",
            default_path,
            "Arquivos de Texto (*.txt)"
        )
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
            QMessageBox.information(self, "Salvo", f"Relatório salvo em:\n{filepath}")
    
    def _restart_app(self):
        """Reinicia a aplicação."""
        # Simples restart via exit code
        QApplication.exit(1000)


class ErrorHandler(QObject):
    """
    Manipulador global de erros.
    
    Captura exceções não tratadas e exibe diálogo amigável.
    """
    
    error_occurred = Signal(str, str, str)  # type, message, traceback
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        super().__init__()
        self._initialized = True
        self._parent_widget = None
    
    def setup(self, parent_widget: QWidget = None):
        """
        Configura o handler de erros.
        
        Args:
            parent_widget: Widget pai para diálogos
        """
        self._parent_widget = parent_widget
        
        # Instala hook de exceção
        sys.excepthook = self._exception_hook
    
    def _exception_hook(self, exc_type, exc_value, exc_tb):
        """Hook para exceções não tratadas."""
        # Log do erro
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(f"Exceção não tratada:\n{tb_text}")
        
        # Exibe diálogo
        self.show_critical_error(
            error_type=exc_type.__name__,
            error_message=str(exc_value),
            traceback_text=tb_text
        )
    
    def show_error(
        self,
        title: str,
        message: str,
        details: str = None,
        log: bool = True
    ):
        """
        Exibe diálogo de erro.
        
        Args:
            title: Título do erro
            message: Mensagem amigável
            details: Detalhes técnicos
            log: Se deve logar o erro
        """
        if log:
            logger.error(f"{title}: {message}")
            if details:
                logger.debug(f"Detalhes: {details}")
        
        dialog = ErrorDialog(title, message, details, self._parent_widget)
        dialog.exec()
    
    def show_critical_error(
        self,
        error_type: str,
        error_message: str,
        traceback_text: str
    ):
        """Exibe diálogo de erro crítico."""
        dialog = CriticalErrorDialog(
            error_type,
            error_message,
            traceback_text,
            self._parent_widget
        )
        dialog.exec()
    
    def show_warning(self, title: str, message: str):
        """Exibe aviso."""
        logger.warning(f"{title}: {message}")
        QMessageBox.warning(self._parent_widget, title, message)
    
    def show_info(self, title: str, message: str):
        """Exibe informação."""
        logger.info(f"{title}: {message}")
        QMessageBox.information(self._parent_widget, title, message)


# Instância global
_error_handler = ErrorHandler()


def setup_exception_handler(parent_widget: QWidget = None):
    """Configura o hook global de exceções não tratadas."""
    _error_handler.setup(parent_widget)


def setup_error_handler(parent_widget: QWidget = None):
    """Configura o manipulador global de erros."""
    _error_handler.setup(parent_widget)


def show_error(title: str, message: str, details: str = None):
    """Exibe erro."""
    _error_handler.show_error(title, message, details)


def show_warning(title: str, message: str):
    """Exibe aviso."""
    _error_handler.show_warning(title, message)


def show_info(title: str, message: str):
    """Exibe informação."""
    _error_handler.show_info(title, message)


def handle_exception(func: Callable) -> Callable:
    """
    Decorator para tratamento de exceções em funções.
    
    Uso:
        @handle_exception
        def minha_funcao():
            ...
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Erro em {func.__name__}")
            show_error(
                "Erro",
                f"Ocorreu um erro ao executar a operação.",
                f"{type(e).__name__}: {str(e)}"
            )
            return None
    return wrapper
