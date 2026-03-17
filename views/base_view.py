"""
base_view.py
============
Classe base para todas as views do sistema.
"""

from PySide6.QtWidgets import (
    QWidget, QMessageBox, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from utils.config import AppConfig


class BaseView(QWidget):
    """
    View base com funcionalidades comuns.
    
    Fornece:
    - Métodos de exibição de mensagens
    - Configuração padrão de janela
    - Loading overlay
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_base()
    
    def _setup_base(self):
        """Configuração base da janela."""
        # Configura ícone
        icon_path = AppConfig.get_asset_path("logo.png")
        self.setWindowIcon(QIcon(icon_path))
    
    def show_error(self, message: str, title: str = "Erro") -> None:
        """
        Exibe mensagem de erro.
        
        Args:
            message: Mensagem de erro
            title: Título da janela
        """
        QMessageBox.critical(self, title, message)
    
    def show_warning(self, message: str, title: str = "Aviso") -> None:
        """
        Exibe mensagem de aviso.
        
        Args:
            message: Mensagem de aviso
            title: Título da janela
        """
        QMessageBox.warning(self, title, message)
    
    def show_info(self, message: str, title: str = "Informação") -> None:
        """
        Exibe mensagem informativa.
        
        Args:
            message: Mensagem
            title: Título da janela
        """
        QMessageBox.information(self, title, message)
    
    def show_success(self, message: str, title: str = "Sucesso") -> None:
        """
        Exibe mensagem de sucesso.
        
        Args:
            message: Mensagem
            title: Título da janela
        """
        QMessageBox.information(self, title, message)
    
    def ask_confirmation(
        self,
        message: str,
        title: str = "Confirmação"
    ) -> bool:
        """
        Exibe diálogo de confirmação.
        
        Args:
            message: Mensagem de confirmação
            title: Título da janela
            
        Returns:
            True se confirmou
        """
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    def set_loading(self, loading: bool, message: str = "Carregando..."):
        """
        Define estado de carregamento.
        
        Args:
            loading: Se está carregando
            message: Mensagem de loading
        """
        self.setEnabled(not loading)
        # Subclasses podem implementar loading overlay
    
    def center_on_screen(self):
        """Centraliza a janela na tela."""
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
