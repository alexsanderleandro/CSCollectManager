"""
about_dialog.py
===============
Diálogo "Sobre" do sistema CSCollectManager.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QIcon

from utils.constants import APP_INFO, Icons

# Caminho do logotipo
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")


class AboutDialog(QDialog):
    """Diálogo com informações sobre o sistema."""
    
    def __init__(self, parent=None):
        """
        Inicializa o diálogo "Sobre".

        Args:
            parent: Widget pai (opcional).
        """
        super().__init__(parent)
        
        self.setWindowTitle(f"Sobre - {APP_INFO.NAME}")
        
        # Define ícone da janela
        if os.path.exists(LOGO_PATH):
            icon = QIcon(LOGO_PATH)
            self.setWindowIcon(icon)
        
        self.setFixedSize(450, 400)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura a interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Logo/Ícone
        icon_label = QLabel()
        icon_label.setText("📦")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)
        layout.addWidget(icon_label)
        
        # Nome da aplicação
        name_label = QLabel(APP_INFO.NAME)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(18)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #0078d4;")
        layout.addWidget(name_label)
        
        # Versão
        version_label = QLabel(f"Versão {APP_INFO.VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_font = QFont()
        version_font.setPointSize(11)
        version_label.setFont(version_font)
        version_label.setStyleSheet("color: #9d9d9d;")
        layout.addWidget(version_label)
        
        # Build
        build_label = QLabel(f"Build {APP_INFO.BUILD}")
        build_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        build_label.setStyleSheet("color: #666666; font-size: 9pt;")
        layout.addWidget(build_label)
        
        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3e3e42;")
        layout.addWidget(separator)
        
        # Descrição
        desc_label = QLabel(APP_INFO.DESCRIPTION)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #cccccc; padding: 10px;")
        layout.addWidget(desc_label)
        
        # Informações do desenvolvedor
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)
        
        # Autor
        author_label = QLabel(f"👤 Desenvolvido por: {APP_INFO.AUTHOR}")
        author_label.setStyleSheet("color: #cccccc;")
        info_layout.addWidget(author_label)
        
        # Email
        email_label = QLabel(f"📧 {APP_INFO.EMAIL}")
        email_label.setStyleSheet("color: #9d9d9d;")
        info_layout.addWidget(email_label)
        
        # Website
        website_label = QLabel(f"🌐 {APP_INFO.WEBSITE}")
        website_label.setStyleSheet("color: #0078d4;")
        website_label.setCursor(Qt.CursorShape.PointingHandCursor)
        info_layout.addWidget(website_label)
        
        layout.addWidget(info_frame)
        
        # Copyright
        copyright_label = QLabel(APP_INFO.COPYRIGHT)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setStyleSheet("color: #666666; font-size: 9pt;")
        layout.addWidget(copyright_label)
        
        layout.addStretch()
        
        # Botão fechar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("Fechar")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        btn_layout.addWidget(close_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class SystemInfoDialog(QDialog):
    """Diálogo com informações detalhadas do sistema."""
    
    def __init__(self, parent=None):
        """
        Inicializa o diálogo de informações do sistema.

        Exibe versões do Python, PySide6, SQLAlchemy e informações
        do sistema operacional em execução.

        Args:
            parent: Widget pai (opcional).
        """
        super().__init__(parent)
        
        self.setWindowTitle("Informações do Sistema")
        
        # Define ícone da janela
        if os.path.exists(LOGO_PATH):
            icon = QIcon(LOGO_PATH)
            self.setWindowIcon(icon)
        
        self.setMinimumSize(500, 400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura a interface."""
        import sys
        import platform
        
        try:
            from PySide6 import __version__ as pyside_version
        except ImportError:
            pyside_version = "N/A"
        
        try:
            import sqlalchemy
            sqlalchemy_version = sqlalchemy.__version__
        except ImportError:
            sqlalchemy_version = "N/A"
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título
        title = QLabel("📊 Informações do Sistema")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)
        
        # Informações
        info_items = [
            ("Aplicação", APP_INFO.NAME),
            ("Versão", APP_INFO.VERSION),
            ("Build", APP_INFO.BUILD),
            ("", ""),  # Espaço
            ("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            ("PySide6", pyside_version),
            ("SQLAlchemy", sqlalchemy_version),
            ("", ""),
            ("Sistema Operacional", platform.system()),
            ("Versão SO", platform.version()),
            ("Arquitetura", platform.machine()),
            ("Processador", platform.processor()[:50] if platform.processor() else "N/A"),
        ]
        
        for label, value in info_items:
            if not label and not value:
                # Espaçador
                layout.addSpacing(10)
                continue
            
            row = QHBoxLayout()
            
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color: #9d9d9d; font-weight: bold;")
            lbl.setMinimumWidth(150)
            row.addWidget(lbl)
            
            val = QLabel(str(value))
            val.setStyleSheet("color: #cccccc;")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(val)
            
            row.addStretch()
            layout.addLayout(row)
        
        layout.addStretch()
        
        # Botão
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("Fechar")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
