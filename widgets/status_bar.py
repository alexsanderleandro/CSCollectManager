"""
status_bar.py
=============
Barra de status avançada com indicadores de progresso e status.
"""

from typing import Optional
from PySide6.QtWidgets import (
    QStatusBar, QLabel, QProgressBar, QWidget,
    QHBoxLayout, QFrame, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont

from utils.constants import Icons


class StatusIndicator(QLabel):
    """Indicador de status com ícone."""
    
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("padding: 0 8px;")
    
    def set_status(self, icon: str, text: str, color: str = None):
        """Define status."""
        self.setText(f"{icon} {text}")
        if color:
            self.setStyleSheet(f"padding: 0 8px; color: {color};")
        else:
            self.setStyleSheet("padding: 0 8px;")


class ConnectionIndicator(QWidget):
    """Indicador de conexão com o banco."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(4)
        
        self._icon = QLabel("🔌")
        layout.addWidget(self._icon)
        
        self._label = QLabel("Desconectado")
        self._label.setStyleSheet("color: #9d9d9d;")
        layout.addWidget(self._label)
    
    def set_connected(self, server: str = ""):
        """Define como conectado."""
        self._icon.setText("🟢")
        if server:
            self._label.setText(f"Conectado: {server}")
        else:
            self._label.setText("Conectado")
        self._label.setStyleSheet("color: #4caf50;")
    
    def set_disconnected(self):
        """Define como desconectado."""
        self._icon.setText("🔴")
        self._label.setText("Desconectado")
        self._label.setStyleSheet("color: #f44336;")
    
    def set_connecting(self):
        """Define como conectando."""
        self._icon.setText("🟡")
        self._label.setText("Conectando...")
        self._label.setStyleSheet("color: #ff9800;")


class ProgressIndicator(QWidget):
    """Indicador de progresso inline."""
    
    cancelled = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)
        
        self._label = QLabel("Processando...")
        self._label.setMinimumWidth(150)
        layout.addWidget(self._label)
        
        self._progress = QProgressBar()
        self._progress.setMinimumWidth(150)
        self._progress.setMaximumWidth(200)
        self._progress.setMaximumHeight(16)
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)
        
        self._btn_cancel = QPushButton("✕")
        self._btn_cancel.setMaximumSize(20, 20)
        self._btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #9d9d9d;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #f44336;
            }
        """)
        self._btn_cancel.clicked.connect(self.cancelled.emit)
        self._btn_cancel.setVisible(False)
        layout.addWidget(self._btn_cancel)
        
        self.hide()
    
    def show_progress(
        self,
        message: str = "Processando...",
        cancelable: bool = False
    ):
        """Exibe indicador de progresso."""
        self._label.setText(message)
        self._progress.setMaximum(0)  # Indeterminado
        self._btn_cancel.setVisible(cancelable)
        self.show()
    
    @Slot(int, int, str)
    def update_progress(self, current: int, total: int, message: str = None):
        """Atualiza progresso."""
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        if message:
            self._label.setText(message)
    
    def hide_progress(self):
        """Oculta indicador."""
        self.hide()


class AppStatusBar(QStatusBar):
    """
    Barra de status avançada da aplicação.
    
    Inclui:
    - Mensagem de status
    - Indicador de conexão
    - Indicador de progresso
    - Contador de registros
    - Informação do usuário
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
        self._setup_auto_clear()
    
    def _setup_ui(self):
        """Configura a interface."""
        self.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
                border: none;
                min-height: 28px;
            }
            QStatusBar::item {
                border: none;
            }
            QLabel {
                color: white;
                padding: 0 4px;
            }
        """)
        
        # Mensagem principal (lado esquerdo)
        self._message_label = QLabel("Pronto")
        self.addWidget(self._message_label, 1)
        
        # Separador vertical
        self._add_separator()
        
        # Indicador de progresso
        self._progress = ProgressIndicator()
        self.addWidget(self._progress)
        
        # ===== Widgets permanentes (lado direito) =====
        
        # Contador de registros
        self._records_label = QLabel("")
        self._records_label.setStyleSheet("color: rgba(255,255,255,0.8);")
        self.addPermanentWidget(self._records_label)
        
        self._add_separator(permanent=True)
        
        # Indicador de conexão
        self._connection = ConnectionIndicator()
        self.addPermanentWidget(self._connection)
        
        self._add_separator(permanent=True)
        
        # Usuário
        self._user_label = QLabel("")
        self._user_label.setStyleSheet("color: rgba(255,255,255,0.9);")
        self.addPermanentWidget(self._user_label)
        
        self._add_separator(permanent=True)
        
        # Versão
        from utils.constants import APP_INFO
        version_label = QLabel(f"v{APP_INFO.VERSION}")
        version_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 9pt;")
        self.addPermanentWidget(version_label)
    
    def _add_separator(self, permanent: bool = False):
        """Adiciona separador vertical."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background-color: rgba(255,255,255,0.3); margin: 4px 0;")
        sep.setMaximumWidth(1)
        
        if permanent:
            self.addPermanentWidget(sep)
        else:
            self.addWidget(sep)
    
    def _setup_auto_clear(self):
        """Configura limpeza automática de mensagens."""
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_message)
    
    def _clear_message(self):
        """Limpa mensagem temporária."""
        self._message_label.setText("Pronto")
    
    # ==========================================
    # PUBLIC API
    # ==========================================
    
    def show_message(self, message: str, timeout_ms: int = 0):
        """
        Exibe mensagem na barra de status.
        
        Args:
            message: Mensagem a exibir
            timeout_ms: Tempo para limpar (0 = permanente)
        """
        self._message_label.setText(message)
        
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)
    
    def show_success(self, message: str, timeout_ms: int = 5000):
        """Exibe mensagem de sucesso."""
        self._message_label.setText(f"✅ {message}")
        self._message_label.setStyleSheet("color: #a5d6a7;")
        
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)
            QTimer.singleShot(timeout_ms, lambda: self._message_label.setStyleSheet("color: white;"))
    
    def show_error(self, message: str, timeout_ms: int = 8000):
        """Exibe mensagem de erro."""
        self._message_label.setText(f"❌ {message}")
        self._message_label.setStyleSheet("color: #ef9a9a;")
        
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)
            QTimer.singleShot(timeout_ms, lambda: self._message_label.setStyleSheet("color: white;"))
    
    def show_warning(self, message: str, timeout_ms: int = 5000):
        """Exibe mensagem de aviso."""
        self._message_label.setText(f"⚠️ {message}")
        self._message_label.setStyleSheet("color: #ffe082;")
        
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)
            QTimer.singleShot(timeout_ms, lambda: self._message_label.setStyleSheet("color: white;"))
    
    def show_info(self, message: str, timeout_ms: int = 3000):
        """Exibe mensagem informativa."""
        self._message_label.setText(f"ℹ️ {message}")
        
        if timeout_ms > 0:
            self._clear_timer.start(timeout_ms)
    
    # ===== Progresso =====
    
    def show_progress(self, message: str = "Processando...", cancelable: bool = False):
        """Exibe indicador de progresso."""
        self._progress.show_progress(message, cancelable)
    
    def update_progress(self, current: int, total: int, message: str = None):
        """Atualiza progresso."""
        self._progress.update_progress(current, total, message)
    
    def hide_progress(self):
        """Oculta indicador de progresso."""
        self._progress.hide_progress()
    
    @property
    def progress_cancelled(self) -> Signal:
        """Sinal de cancelamento do progresso."""
        return self._progress.cancelled
    
    # ===== Conexão =====
    
    def set_connected(self, server: str = ""):
        """Define status como conectado."""
        self._connection.set_connected(server)
    
    def set_disconnected(self):
        """Define status como desconectado."""
        self._connection.set_disconnected()
    
    def set_connecting(self):
        """Define status como conectando."""
        self._connection.set_connecting()
    
    # ===== Usuário =====
    
    def set_user(self, username: str, company: str = ""):
        """Define usuário atual."""
        if company:
            self._user_label.setText(f"👤 {username} | {company}")
        else:
            self._user_label.setText(f"👤 {username}")
    
    def clear_user(self):
        """Limpa informação do usuário."""
        self._user_label.setText("")
    
    # ===== Registros =====
    
    def set_record_count(self, loaded: int, total: int = None, filtered: int = None):
        """
        Define contagem de registros.
        
        Args:
            loaded: Registros carregados
            total: Total disponível
            filtered: Total após filtro
        """
        parts = []
        
        if filtered is not None and filtered != loaded:
            parts.append(f"Exibindo: {filtered:,}")
        
        parts.append(f"Carregados: {loaded:,}")
        
        if total is not None and total != loaded:
            parts.append(f"Total: {total:,}")
        
        self._records_label.setText(" | ".join(parts))
    
    def clear_record_count(self):
        """Limpa contagem de registros."""
        self._records_label.setText("")
