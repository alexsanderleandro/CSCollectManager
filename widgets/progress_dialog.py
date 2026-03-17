"""
progress_dialog.py
==================
Diálogos de progresso para operações longas.

Implementa:
- Barra de progresso com cancelamento
- Modo determinado e indeterminado
- Integração com workers
"""

from typing import Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QWidget, QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QIcon


class ProgressDialog(QDialog):
    """
    Diálogo de progresso com suporte a cancelamento.
    
    Signals:
        cancelled: Emitido quando usuário cancela
    """
    
    cancelled = Signal()
    
    def __init__(
        self,
        title: str = "Processando...",
        message: str = "",
        parent: QWidget = None,
        cancelable: bool = True,
        minimum: int = 0,
        maximum: int = 100,
        auto_close: bool = True
    ):
        """
        Inicializa o diálogo.
        
        Args:
            title: Título da janela
            message: Mensagem inicial
            parent: Widget pai
            cancelable: Se pode ser cancelado
            minimum: Valor mínimo do progresso
            maximum: Valor máximo (0 = indeterminado)
            auto_close: Fechar automaticamente ao concluir
        """
        super().__init__(parent)
        
        self._auto_close = auto_close
        self._was_cancelled = False
        
        self._setup_ui(title, message, cancelable, minimum, maximum)
    
    def _setup_ui(
        self,
        title: str,
        message: str,
        cancelable: bool,
        minimum: int,
        maximum: int
    ):
        """Configura a interface."""
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Mensagem
        self._label_message = QLabel(message)
        self._label_message.setWordWrap(True)
        self._label_message.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._label_message)
        
        # Barra de progresso
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(minimum)
        self._progress_bar.setMaximum(maximum)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setMinimumHeight(25)
        layout.addWidget(self._progress_bar)
        
        # Label de detalhes
        self._label_details = QLabel("")
        self._label_details.setStyleSheet("color: gray; font-size: 11px;")
        self._label_details.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._label_details)
        
        # Botões
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setMinimumWidth(100)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_cancel.setVisible(cancelable)
        button_layout.addWidget(self._btn_cancel)
        
        self._btn_close = QPushButton("Fechar")
        self._btn_close.setMinimumWidth(100)
        self._btn_close.clicked.connect(self.accept)
        self._btn_close.setVisible(False)
        button_layout.addWidget(self._btn_close)
        
        layout.addLayout(button_layout)
    
    @property
    def was_cancelled(self) -> bool:
        """Verifica se foi cancelado."""
        return self._was_cancelled
    
    @Slot(int)
    def set_value(self, value: int):
        """Define valor do progresso."""
        self._progress_bar.setValue(value)
        QApplication.processEvents()
    
    @Slot(str)
    def set_message(self, message: str):
        """Define mensagem principal."""
        self._label_message.setText(message)
        QApplication.processEvents()
    
    @Slot(str)
    def set_details(self, details: str):
        """Define detalhes do progresso."""
        self._label_details.setText(details)
        QApplication.processEvents()
    
    @Slot(int, int, float, str)
    def update_progress(
        self,
        current: int,
        total: int,
        percentage: float,
        message: str
    ):
        """
        Atualiza progresso completo.
        
        Args:
            current: Valor atual
            total: Valor total
            percentage: Percentual (0-100)
            message: Mensagem de status
        """
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(int(percentage))
        self._label_message.setText(message)
        self._label_details.setText(f"{current:,} de {total:,}")
        QApplication.processEvents()
    
    def set_indeterminate(self, indeterminate: bool = True):
        """Define modo indeterminado (barra animada)."""
        if indeterminate:
            self._progress_bar.setMaximum(0)
            self._progress_bar.setMinimum(0)
        else:
            self._progress_bar.setMaximum(100)
            self._progress_bar.setMinimum(0)
    
    @Slot()
    def finish(self, success: bool = True, message: str = None):
        """
        Finaliza o progresso.
        
        Args:
            success: Se foi bem-sucedido
            message: Mensagem final
        """
        self._progress_bar.setValue(self._progress_bar.maximum())
        
        if message:
            self._label_message.setText(message)
        
        if success:
            self._label_details.setText("Concluído com sucesso!")
            self._label_details.setStyleSheet("color: green; font-size: 11px;")
        else:
            self._label_details.setStyleSheet("color: red; font-size: 11px;")
        
        self._btn_cancel.setVisible(False)
        self._btn_close.setVisible(True)
        
        if self._auto_close and success:
            QTimer.singleShot(1500, self.accept)
    
    @Slot(Exception)
    def show_error(self, error: Exception):
        """Exibe erro."""
        self._progress_bar.setStyleSheet("""
            QProgressBar::chunk { background-color: #ff6b6b; }
        """)
        self._label_message.setText("Erro durante o processamento")
        self._label_details.setText(str(error))
        self._label_details.setStyleSheet("color: red; font-size: 11px;")
        
        self._btn_cancel.setVisible(False)
        self._btn_close.setVisible(True)
    
    def _on_cancel(self):
        """Handler de cancelamento."""
        self._was_cancelled = True
        self._label_message.setText("Cancelando...")
        self._btn_cancel.setEnabled(False)
        self.cancelled.emit()
    
    def closeEvent(self, event):
        """Impede fechar durante processamento."""
        if self._btn_cancel.isVisible() and self._btn_cancel.isEnabled():
            # Ainda está processando
            event.ignore()
            self._on_cancel()
        else:
            event.accept()


class ProgressOverlay(QWidget):
    """
    Overlay de progresso sobre um widget.
    
    Útil para mostrar progresso dentro de uma área específica
    sem bloquear toda a aplicação.
    """
    
    cancelled = Signal()
    
    def __init__(self, parent: QWidget):
        """
        Inicializa o overlay.
        
        Args:
            parent: Widget sobre o qual será exibido
        """
        super().__init__(parent)
        
        self._setup_ui()
        self.hide()
    
    def _setup_ui(self):
        """Configura a interface."""
        # Fundo semi-transparente
        self.setStyleSheet("""
            ProgressOverlay {
                background-color: rgba(255, 255, 255, 200);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Container central
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
        """)
        container.setMaximumWidth(350)
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        container_layout.setContentsMargins(20, 15, 20, 15)
        
        # Mensagem
        self._label_message = QLabel("Carregando...")
        self._label_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        self._label_message.setFont(font)
        container_layout.addWidget(self._label_message)
        
        # Barra de progresso
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(0)  # Indeterminado por padrão
        self._progress_bar.setMinimumHeight(20)
        self._progress_bar.setTextVisible(True)
        container_layout.addWidget(self._progress_bar)
        
        # Detalhes
        self._label_details = QLabel("")
        self._label_details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_details.setStyleSheet("color: gray; font-size: 10px;")
        container_layout.addWidget(self._label_details)
        
        # Botão cancelar
        self._btn_cancel = QPushButton("Cancelar")
        self._btn_cancel.setMaximumWidth(100)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_cancel.setVisible(False)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._btn_cancel)
        btn_layout.addStretch()
        container_layout.addLayout(btn_layout)
        
        layout.addWidget(container)
    
    def show_progress(
        self,
        message: str = "Carregando...",
        cancelable: bool = False
    ):
        """
        Exibe o overlay.
        
        Args:
            message: Mensagem a exibir
            cancelable: Se pode ser cancelado
        """
        self._label_message.setText(message)
        self._label_details.setText("")
        self._btn_cancel.setVisible(cancelable)
        self._progress_bar.setMaximum(0)  # Indeterminado
        
        # Redimensiona para cobrir o pai
        if self.parent():
            self.setGeometry(self.parent().rect())
        
        self.show()
        self.raise_()
        QApplication.processEvents()
    
    @Slot(int, int, float, str)
    def update_progress(
        self,
        current: int,
        total: int,
        percentage: float,
        message: str
    ):
        """Atualiza progresso."""
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(int(percentage))
        self._label_message.setText(message)
        self._label_details.setText(f"{current:,} de {total:,}")
        QApplication.processEvents()
    
    def hide_progress(self):
        """Oculta o overlay."""
        self.hide()
    
    def _on_cancel(self):
        """Handler de cancelamento."""
        self._label_message.setText("Cancelando...")
        self._btn_cancel.setEnabled(False)
        self.cancelled.emit()
    
    def resizeEvent(self, event):
        """Ajusta tamanho quando pai redimensiona."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
