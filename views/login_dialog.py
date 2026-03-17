"""
login_dialog.py
===============
Diálogo de login profissional com seleção de base e empresa.

Fluxo:
1. Carrega conexões do cslogin.xml
2. Usuário seleciona base de dados
3. Testa conexão e carrega empresas
4. Usuário seleciona empresa e faz login
"""

import os
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox,
    QGroupBox, QFrame, QMessageBox, QProgressBar, QSpacerItem,
    QSizePolicy, QStackedWidget, QWidget
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QFont, QPixmap, QIcon, QCursor

from utils.constants import APP_INFO
from utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionWorker(QThread):
    """Worker para testar conexão em background."""
    
    finished = Signal(bool, str, list)  # sucesso, mensagem, empresas
    
    def __init__(self, connection_data: dict):
        super().__init__()
        self._connection_data = connection_data
    
    def run(self):
        """Executa teste de conexão."""
        try:
            # Simula teste de conexão
            import time
            time.sleep(1)
            
            # TODO: Implementar teste real com SQLAlchemy
            # Por enquanto, retorna sucesso com empresas de exemplo
            empresas = [
                {"codigo": 1, "nome": "EMPRESA MATRIZ LTDA"},
                {"codigo": 2, "nome": "FILIAL SÃO PAULO"},
                {"codigo": 3, "nome": "FILIAL RIO DE JANEIRO"},
            ]
            
            self.finished.emit(True, "Conexão estabelecida!", empresas)
            
        except Exception as e:
            logger.error(f"Erro ao conectar: {e}")
            self.finished.emit(False, str(e), [])


class LoginDialog(QDialog):
    """
    Diálogo de login profissional.
    
    Signals:
        login_successful: Emitido com dados do login
    """
    
    login_successful = Signal(dict)
    
    # Etapas do login
    STEP_CONNECTION = 0
    STEP_LOGIN = 1
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Estado
        self._connections = []
        self._empresas = []
        self._selected_connection = None
        self._current_step = self.STEP_CONNECTION
        self._worker: Optional[ConnectionWorker] = None
        
        self._setup_ui()
        self._connect_signals()
        self._load_connections()
    
    def _setup_ui(self):
        """Configura interface."""
        self.setWindowTitle(f"{APP_INFO.NAME} - Login")
        self.setFixedSize(480, 580)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #cccccc;
            }
            QLineEdit, QComboBox {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px 12px;
                color: #cccccc;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 10px;
            }
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QCheckBox {
                color: #cccccc;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #3e3e42;
                border-radius: 3px;
                background-color: #2d2d30;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)
        
        # ===== HEADER =====
        header = self._create_header()
        main_layout.addWidget(header)
        
        # ===== SEPARADOR =====
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #3e3e42;")
        line.setMaximumHeight(1)
        main_layout.addWidget(line)
        
        # ===== STACK DE ETAPAS =====
        self._stack = QStackedWidget()
        
        # Etapa 1: Seleção de conexão
        self._stack.addWidget(self._create_connection_step())
        
        # Etapa 2: Login
        self._stack.addWidget(self._create_login_step())
        
        main_layout.addWidget(self._stack)
        
        # ===== PROGRESS BAR =====
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setMaximumHeight(3)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #2d2d30;
                border: none;
                border-radius: 1px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 1px;
            }
        """)
        self._progress.hide()
        main_layout.addWidget(self._progress)
        
        # ===== RODAPÉ =====
        footer = QLabel(f"v{APP_INFO.VERSION} • {APP_INFO.COMPANY}")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #666666; font-size: 9pt;")
        main_layout.addWidget(footer)
    
    def _create_header(self) -> QWidget:
        """Cria header com logo e título."""
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Logo/Ícone
        icon_label = QLabel("📦")
        icon_label.setFont(QFont("Segoe UI", 40))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Título
        title = QLabel(APP_INFO.NAME)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)
        
        # Subtítulo
        subtitle = QLabel("Sistema de Exportação para Coletores")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #9d9d9d; font-size: 10pt;")
        layout.addWidget(subtitle)
        
        return header
    
    def _create_connection_step(self) -> QWidget:
        """Cria etapa de seleção de conexão."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 16, 0, 0)
        
        # Grupo de conexão
        group = QGroupBox("🔌 Conexão com Banco de Dados")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)
        group_layout.setContentsMargins(16, 20, 16, 16)
        
        # Combo de conexões
        lbl_connection = QLabel("Base de Dados:")
        group_layout.addWidget(lbl_connection)
        
        self._cmb_connection = QComboBox()
        self._cmb_connection.addItem("Selecione uma base de dados...")
        group_layout.addWidget(self._cmb_connection)
        
        # Botão de teste
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._btn_test = QPushButton("🔍 Testar Conexão")
        self._btn_test.setMinimumSize(140, 36)
        self._btn_test.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_test.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #2d2d30;
                color: #666666;
            }
        """)
        self._btn_test.setEnabled(False)
        btn_layout.addWidget(self._btn_test)
        group_layout.addLayout(btn_layout)
        
        # Status de conexão
        self._lbl_connection_status = QLabel("")
        self._lbl_connection_status.setStyleSheet("font-size: 9pt;")
        self._lbl_connection_status.setWordWrap(True)
        group_layout.addWidget(self._lbl_connection_status)
        
        layout.addWidget(group)
        
        # Grupo de empresa
        self._grp_empresa = QGroupBox("🏢 Empresa")
        self._grp_empresa.setEnabled(False)
        empresa_layout = QVBoxLayout(self._grp_empresa)
        empresa_layout.setSpacing(12)
        empresa_layout.setContentsMargins(16, 20, 16, 16)
        
        lbl_empresa = QLabel("Selecione a Empresa:")
        empresa_layout.addWidget(lbl_empresa)
        
        self._cmb_empresa = QComboBox()
        self._cmb_empresa.addItem("Selecione uma empresa...")
        empresa_layout.addWidget(self._cmb_empresa)
        
        layout.addWidget(self._grp_empresa)
        
        layout.addStretch()
        
        # Botão avançar
        btn_layout2 = QHBoxLayout()
        btn_layout2.addStretch()
        
        self._btn_next = QPushButton("Avançar  →")
        self._btn_next.setMinimumSize(140, 40)
        self._btn_next.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_next.setEnabled(False)
        self._btn_next.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e8ad4;
            }
            QPushButton:disabled {
                background-color: #3e3e42;
                color: #666666;
            }
        """)
        btn_layout2.addWidget(self._btn_next)
        layout.addLayout(btn_layout2)
        
        return widget
    
    def _create_login_step(self) -> QWidget:
        """Cria etapa de login."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 16, 0, 0)
        
        # Info da conexão selecionada
        self._lbl_selected_info = QLabel("")
        self._lbl_selected_info.setStyleSheet("""
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 12px;
            color: #9d9d9d;
        """)
        layout.addWidget(self._lbl_selected_info)
        
        # Grupo de credenciais
        group = QGroupBox("👤 Credenciais")
        group_layout = QFormLayout(group)
        group_layout.setSpacing(12)
        group_layout.setContentsMargins(16, 20, 16, 16)
        
        self._txt_usuario = QLineEdit()
        self._txt_usuario.setPlaceholderText("Digite seu usuário")
        group_layout.addRow("Usuário:", self._txt_usuario)
        
        self._txt_senha = QLineEdit()
        self._txt_senha.setPlaceholderText("Digite sua senha")
        self._txt_senha.setEchoMode(QLineEdit.EchoMode.Password)
        group_layout.addRow("Senha:", self._txt_senha)
        
        self._chk_lembrar = QCheckBox("Lembrar usuário")
        group_layout.addRow("", self._chk_lembrar)
        
        layout.addWidget(group)
        
        # Mensagem de erro
        self._lbl_login_error = QLabel("")
        self._lbl_login_error.setStyleSheet("color: #f44336; font-size: 9pt;")
        self._lbl_login_error.setWordWrap(True)
        self._lbl_login_error.hide()
        layout.addWidget(self._lbl_login_error)
        
        layout.addStretch()
        
        # Botões
        btn_layout = QHBoxLayout()
        
        self._btn_back = QPushButton("←  Voltar")
        self._btn_back.setMinimumSize(100, 40)
        self._btn_back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_back.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_layout.addWidget(self._btn_back)
        
        btn_layout.addStretch()
        
        self._btn_login = QPushButton("🔐  Entrar")
        self._btn_login.setMinimumSize(140, 40)
        self._btn_login.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_login.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #1e8ad4;
            }
            QPushButton:disabled {
                background-color: #3e3e42;
                color: #666666;
            }
        """)
        btn_layout.addWidget(self._btn_login)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _connect_signals(self):
        """Conecta sinais."""
        self._cmb_connection.currentIndexChanged.connect(self._on_connection_changed)
        self._cmb_empresa.currentIndexChanged.connect(self._on_empresa_changed)
        self._btn_test.clicked.connect(self._on_test_connection)
        self._btn_next.clicked.connect(self._on_next)
        self._btn_back.clicked.connect(self._on_back)
        self._btn_login.clicked.connect(self._on_login)
        self._txt_senha.returnPressed.connect(self._on_login)
    
    def _load_connections(self):
        """Carrega conexões disponíveis."""
        try:
            from login import read_connections
            
            connections = read_connections()
            self._connections = []
            
            self._cmb_connection.clear()
            self._cmb_connection.addItem("Selecione uma base de dados...")
            
            for conn in connections:
                # ConnectionEntry é dataclass, converte para dict-like
                if hasattr(conn, 'servidor'):
                    conn_dict = {
                        "alias": conn.login_id or conn.servidor,
                        "server": conn.servidor,
                        "database": conn.banco,
                        "type": conn.tipo_banco,
                        "codempresa": conn.codempresa,
                        "nomeempresa": conn.nomeempresa
                    }
                    display = f"{conn_dict['alias']} - {conn_dict['database']}"
                    self._connections.append(conn_dict)
                    self._cmb_connection.addItem(display, conn_dict)
                else:
                    # É um dict normal
                    display = f"{conn.get('alias', conn.get('server', 'N/A'))} - {conn.get('database', 'N/A')}"
                    self._connections.append(conn)
                    self._cmb_connection.addItem(display, conn)
            
            logger.info(f"Carregadas {len(connections)} conexões")
            
        except Exception as e:
            logger.warning(f"Erro ao carregar conexões: {e}")
            # Adiciona conexão de exemplo para teste
            self._connections = [{
                "alias": "Servidor Local",
                "server": "SERVIDOR\\SQLEXPRESS",
                "database": "BANCO_DADOS",
                "type": "SQL Server"
            }]
            self._cmb_connection.addItem("Servidor Local - BANCO_DADOS", self._connections[0])
    
    def _on_connection_changed(self, index: int):
        """Quando conexão é alterada."""
        self._btn_test.setEnabled(index > 0)
        self._grp_empresa.setEnabled(False)
        self._cmb_empresa.clear()
        self._cmb_empresa.addItem("Selecione uma empresa...")
        self._btn_next.setEnabled(False)
        self._lbl_connection_status.setText("")
    
    def _on_empresa_changed(self, index: int):
        """Quando empresa é alterada."""
        self._btn_next.setEnabled(index > 0)
    
    def _on_test_connection(self):
        """Testa conexão selecionada."""
        index = self._cmb_connection.currentIndex()
        if index <= 0:
            return
        
        connection = self._cmb_connection.currentData()
        if not connection:
            return
        
        self._selected_connection = connection
        
        # Mostra progresso
        self._progress.setRange(0, 0)  # Indeterminado
        self._progress.show()
        self._btn_test.setEnabled(False)
        self._lbl_connection_status.setText("⏳ Testando conexão...")
        self._lbl_connection_status.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
        
        # Inicia worker
        self._worker = ConnectionWorker(connection)
        self._worker.finished.connect(self._on_connection_tested)
        self._worker.start()
    
    def _on_connection_tested(self, success: bool, message: str, empresas: list):
        """Callback do teste de conexão."""
        self._progress.hide()
        self._progress.setRange(0, 100)
        self._btn_test.setEnabled(True)
        
        if success:
            self._lbl_connection_status.setText(f"✅ {message}")
            self._lbl_connection_status.setStyleSheet("color: #4caf50; font-size: 9pt;")
            
            # Carrega empresas
            self._empresas = empresas
            self._cmb_empresa.clear()
            self._cmb_empresa.addItem("Selecione uma empresa...")
            
            for emp in empresas:
                self._cmb_empresa.addItem(emp.get("nome", "N/A"), emp)
            
            self._grp_empresa.setEnabled(True)
            
        else:
            self._lbl_connection_status.setText(f"❌ Erro: {message}")
            self._lbl_connection_status.setStyleSheet("color: #f44336; font-size: 9pt;")
            self._grp_empresa.setEnabled(False)
    
    def _on_next(self):
        """Avança para etapa de login."""
        empresa_idx = self._cmb_empresa.currentIndex()
        if empresa_idx <= 0:
            return
        
        empresa = self._cmb_empresa.currentData()
        connection = self._selected_connection
        
        # Atualiza info
        self._lbl_selected_info.setText(
            f"🔌 {connection.get('alias', 'N/A')} • {connection.get('database', 'N/A')}\n"
            f"🏢 {empresa.get('nome', 'N/A')}"
        )
        
        self._stack.setCurrentIndex(self.STEP_LOGIN)
        self._txt_usuario.setFocus()
    
    def _on_back(self):
        """Volta para seleção de conexão."""
        self._stack.setCurrentIndex(self.STEP_CONNECTION)
        self._lbl_login_error.hide()
    
    def _on_login(self):
        """Processa login."""
        usuario = self._txt_usuario.text().strip()
        senha = self._txt_senha.text()
        
        if not usuario:
            self._lbl_login_error.setText("Digite o usuário")
            self._lbl_login_error.show()
            self._txt_usuario.setFocus()
            return
        
        # Mostra progresso
        self._progress.setRange(0, 0)
        self._progress.show()
        self._btn_login.setEnabled(False)
        self._lbl_login_error.hide()
        
        # Simula autenticação
        QTimer.singleShot(800, lambda: self._do_login(usuario, senha))
    
    def _do_login(self, usuario: str, senha: str):
        """Executa login."""
        self._progress.hide()
        self._progress.setRange(0, 100)
        self._btn_login.setEnabled(True)
        
        # TODO: Implementar autenticação real
        # Por enquanto, aceita qualquer login
        
        empresa_idx = self._cmb_empresa.currentIndex()
        empresa = self._cmb_empresa.currentData() if empresa_idx > 0 else {}
        
        login_data = {
            "connection": self._selected_connection or {},
            "empresa": empresa,
            "usuario": {
                "codigo": usuario,
                "nome": usuario.upper(),
                "admin": True
            }
        }
        
        logger.info(f"Login realizado: {usuario}")
        
        self.login_successful.emit(login_data)
    
    def closeEvent(self, event):
        """Evento de fechamento."""
        # Se fechar login, encerra aplicação
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        
        event.accept()


# ===== TESTE =====
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    dialog = LoginDialog()
    dialog.login_successful.connect(lambda data: print(f"Login: {data}"))
    dialog.show()
    
    sys.exit(app.exec())
