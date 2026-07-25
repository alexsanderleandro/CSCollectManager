"""
help_dialog.py
===============
Diálogo de ajuda/documentação do LogScan Manager.

Exibe o conteúdo de docs/ajuda_usuario.md (Markdown), versionado
automaticamente por update_version.py junto com version.py.
"""

import os
import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from utils.constants import APP_INFO
from app.styles import themed_qss

# Caminho do ícone da janela (mesmo padrão de about_dialog.py)
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico")


def _docs_path(filename: str) -> str:
    """Resolve o caminho de um arquivo em docs/, tanto em modo dev quanto empacotado.

    Em modo dev, resolve relativo à raiz do repositório (irmã da pasta views/).
    Quando empacotado via PyInstaller, usa sys._MEIPASS (onde o .spec inclui
    ('docs', 'docs') em datas).
    """
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', None) or os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, "docs", filename)


class HelpDialog(QDialog):
    """Diálogo de ajuda com a documentação de uso do aplicativo."""

    def __init__(self, parent=None):
        """
        Inicializa o diálogo de ajuda.

        Args:
            parent: Widget pai (opcional).
        """
        super().__init__(parent)

        self.setWindowTitle(f"Ajuda — {APP_INFO.NAME}")

        if os.path.exists(LOGO_PATH):
            self.setWindowIcon(QIcon(LOGO_PATH))

        self.resize(760, 640)
        self.setMinimumSize(520, 400)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )

        self._setup_ui()

    def _setup_ui(self):
        """Configura a interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Cabeçalho
        header = QHBoxLayout()
        icon_label = QLabel("📖")
        icon_label.setStyleSheet("font-size: 22pt;")
        header.addWidget(icon_label)

        title_label = QLabel(f"Ajuda — {APP_INFO.NAME}")
        title_label.setStyleSheet(themed_qss("font-size: 15pt; font-weight: bold; color: {{FG_PRIMARY}};"))
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(themed_qss("background-color: {{BORDER}};"))
        layout.addWidget(separator)

        # Conteúdo (markdown renderizado)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(themed_qss("""
            QTextBrowser {
                background-color: {{BG_SECONDARY}};
                color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}};
                border-radius: 8px;
                padding: 12px;
                font-size: 11pt;
            }
        """))
        self._browser.setMarkdown(self._load_content())
        layout.addWidget(self._browser, 1)

        # Botão fechar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Fechar")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_content(self) -> str:
        """Carrega o conteúdo Markdown do arquivo de ajuda."""
        path = _docs_path("ajuda_usuario.md")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return (
                "# Ajuda indisponível\n\n"
                "Não foi possível carregar o arquivo de documentação "
                f"(`{path}`)."
            )
