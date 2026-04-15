"""
loading_overlay.py
==================
Widget de overlay de carregamento.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter


class LoadingOverlay(QWidget):
    """
    Overlay de carregamento semitransparente.
    
    Exibe uma mensagem e barra de progresso sobre o conteúdo.
    """
    
    def __init__(self, parent=None):
        """
        Inicializa o overlay de carregamento.

        Cria a interface com rótulo de mensagem e barra de progresso
        indeterminada. O widget começa oculto e deve ser exibido via
        :meth:`show_loading`.

        Args:
            parent: Widget pai sobre o qual o overlay será sobreposto.
        """
        super().__init__(parent)
        self._setup_ui()
        self.hide()
    
    def _setup_ui(self):
        """Configura interface."""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel("Carregando...")
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 180);
                padding: 20px 40px;
                border-radius: 10px;
            }
        """)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
        
        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background-color: rgba(255, 255, 255, 50);
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignCenter)
    
    def paintEvent(self, event):
        """Pinta o fundo semitransparente."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
    
    def show_loading(self, message: str = "Carregando..."):
        """
        Exibe overlay com mensagem.
        
        Args:
            message: Mensagem a exibir
        """
        self.label.setText(message)
        if self.parent():
            self.resize(self.parent().size())
        self.show()
        self.raise_()
    
    def hide_loading(self):
        """Oculta overlay."""
        self.hide()
    
    def set_progress(self, value: int, maximum: int = 100):
        """
        Define progresso.
        
        Args:
            value: Valor atual
            maximum: Valor máximo (0 para indeterminado)
        """
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)
