"""
base_controller.py
==================
Classe base para todos os controllers do sistema.

Fornece funcionalidades comuns como:
- Gestão de estado
- Comunicação com views via signals
- Tratamento de erros padronizado
"""

from PySide6.QtCore import QObject, Signal
from typing import Optional, Any


class BaseController(QObject):
    """
    Controller base com funcionalidades comuns.
    
    Signals:
        error_occurred: Emitido quando ocorre um erro
        loading_started: Emitido quando uma operação de carregamento inicia
        loading_finished: Emitido quando uma operação de carregamento termina
    """
    
    error_occurred = Signal(str)  # mensagem de erro
    loading_started = Signal(str)  # mensagem de loading
    loading_finished = Signal()
    status_changed = Signal(str)  # mensagem de status
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_loading = False
    
    @property
    def is_loading(self) -> bool:
        """Retorna se há uma operação em andamento."""
        return self._is_loading
    
    def set_loading(self, loading: bool, message: str = ""):
        """Define estado de carregamento."""
        self._is_loading = loading
        if loading:
            self.loading_started.emit(message)
        else:
            self.loading_finished.emit()
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """
        Trata erros de forma padronizada.
        
        Args:
            error: Exceção ocorrida
            context: Contexto onde o erro ocorreu
        """
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.error_occurred.emit(error_msg)
    
    def update_status(self, message: str) -> None:
        """Atualiza mensagem de status."""
        self.status_changed.emit(message)
