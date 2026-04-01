"""
login_dialog.py
===============
Diálogo de login profissional com seleção de base, empresa e autenticação.

Fluxo:
1. Carrega conexões do C:\\CEOSoftware\\CSLogin.xml
2. Usuário seleciona base de dados (TipoBanco, NomeServidor, NomeBanco)
3. Conecta ao banco e carrega empresas da tabela 'empresas'
4. Usuário seleciona empresa (CodEmpresa, Nome, CNPJ)
5. Usuário digita credenciais (login/senha) - último usuário é lembrado
6. Valida credenciais via stored procedure csspValidaSenha
7. Carrega o aplicativo
"""

import os
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox,
    QGroupBox, QFrame, QMessageBox, QProgressBar, QSpacerItem,
    QSizePolicy, QStackedWidget, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QFont, QPixmap, QIcon, QCursor

from utils.constants import APP_INFO
from utils.logger import get_logger
from utils.config import AppConfig
from pathlib import Path
import re
import cscollectmanager_verify

# Importações para persistência e autenticação
import login as login_module
from authentication import DBConfig, verify_user, get_connection

logger = get_logger(__name__)


# Caminho padrão do arquivo de conexões
CSLOGIN_PATH = r"C:\CEOSoftware\CSLogin.xml"

# Caminho do logo (usa o ícone da aplicação)
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico")


class ConnectionWorker(QThread):
    """Worker para conectar ao banco e carregar empresas em background."""
    
    finished = Signal(bool, str, list)  # sucesso, mensagem, empresas
    
    def __init__(self, connection_data: dict):
        super().__init__()
        self._connection_data = connection_data
    
    def run(self):
        """Executa conexão e busca empresas."""
        try:
            servidor = self._connection_data.get("server", "")
            banco = self._connection_data.get("database", "")
            tipo = self._connection_data.get("type", "MSSQL")
            
            logger.info(f"Conectando a {servidor}/{banco}...")
            
            # Tenta importar e usar o DatabaseManager
            try:
                from database.connection import DatabaseManager
                from sqlalchemy import text
                
                # Configura conexão
                db = DatabaseManager()
                db.configure(servidor, banco)
                
                # Testa conexão e busca empresas
                with db.session() as session:
                    # Busca empresas da tabela
                    result = session.execute(text("""
                        SELECT 
                            CodEmpresa,
                            NomeEmpresa,
                            ISNULL(CNPJ, '') as CNPJ
                        FROM Empresas
                        ORDER BY NomeEmpresa
                    """))
                    
                    empresas = []
                    for row in result:
                        empresas.append({
                            "codigo": row[0],
                            "nome": row[1] or "",
                            "cnpj": row[2] or ""
                        })
                
                if empresas:
                    self.finished.emit(True, f"Conectado! {len(empresas)} empresa(s) encontrada(s).", empresas)
                else:
                    self.finished.emit(True, "Conectado! Nenhuma empresa encontrada.", [])
                    
            except ImportError as ie:
                logger.warning(f"DatabaseManager não disponível: {ie}")
                # Fallback: tenta conexão direta com pyodbc
                self._connect_pyodbc(servidor, banco)
            
        except Exception as e:
            logger.error(f"Erro ao conectar: {e}")
            self.finished.emit(False, str(e), [])
    
    def _connect_pyodbc(self, servidor: str, banco: str):
        """Conexão direta com pyodbc como fallback."""
        try:
            import pyodbc
            
            # Tenta encontrar driver disponível
            drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
            if not drivers:
                raise Exception("Nenhum driver SQL Server encontrado")
            
            driver = drivers[0]
            
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={servidor};"
                f"DATABASE={banco};"
                f"Trusted_Connection=yes;"
            )
            
            conn = pyodbc.connect(conn_str, timeout=10)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    CodEmpresa,
                    NomeEmpresa,
                    ISNULL(CNPJ, '') as CNPJ
                FROM Empresas
                ORDER BY NomeEmpresa
            """)
            
            empresas = []
            for row in cursor.fetchall():
                empresas.append({
                    "codigo": row[0],
                    "nome": row[1] or "",
                    "cnpj": row[2] or ""
                })
            
            cursor.close()
            conn.close()
            
            if empresas:
                self.finished.emit(True, f"Conectado! {len(empresas)} empresa(s) encontrada(s).", empresas)
            else:
                self.finished.emit(True, "Conectado! Nenhuma empresa encontrada.", [])
                
        except Exception as e:
            logger.error(f"Erro pyodbc: {e}")
            self.finished.emit(False, str(e), [])


class AuthWorker(QThread):
    """Worker para autenticar usuário em background."""
    
    finished = Signal(bool, str, dict)  # sucesso, mensagem, dados_usuario
    
    def __init__(self, username: str, password: str, db_config: DBConfig):
        super().__init__()
        self._username = username
        self._password = password
        self._db_config = db_config
    
    def run(self):
        """Executa autenticação."""
        try:
            logger.info(f"Autenticando usuário: {self._username}")
            
            user_data = verify_user(
                username=self._username,
                password=self._password,
                cfg=self._db_config,
                require_active=True,
                require_manager=False
            )
            
            if user_data:
                logger.info(f"Usuário autenticado: {user_data.get('NomeUsuario')}")
                self.finished.emit(True, "Autenticação bem-sucedida!", user_data)
            else:
                logger.warning(f"Falha na autenticação: {self._username}")
                self.finished.emit(False, "Usuário ou senha inválidos.", {})
                
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            self.finished.emit(False, f"Erro ao autenticar: {str(e)}", {})


class LoginDialog(QDialog):
    """
    Diálogo de login profissional.
    
    Signals:
        login_successful: Emitido com dados do login
    """
    
    login_successful = Signal(dict)
    
    # Etapas do login
    STEP_CONNECTION = 0
    STEP_EMPRESA = 1
    STEP_AUTH = 2
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Estado
        self._connections = []
        self._empresas = []
        self._selected_connection = None
        self._selected_empresa = None
        self._current_step = self.STEP_CONNECTION
        self._worker: Optional[ConnectionWorker] = None
        self._auth_worker: Optional[AuthWorker] = None
        self._licenca_payload: dict = {}  # Payload do arquivo .key (dispositivos, cnpjs, etc.)
        
        self._setup_ui()
        self._connect_signals()
        self._load_connections()
    
    def _setup_ui(self):
        """Configura interface."""
        self.setWindowTitle(f"{APP_INFO.NAME} - Login")
        
        # Define ícone da janela
        if os.path.exists(LOGO_PATH):
            icon = QIcon(LOGO_PATH)
            self.setWindowIcon(icon)
        
        self.setFixedSize(600, 750)
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
            QComboBox QAbstractItemView {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                selection-background-color: #094771;
                color: #cccccc;
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
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                gridline-color: #3e3e42;
                color: #cccccc;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #094771;
            }
            QTableWidget::item:hover {
                background-color: #2d2d30;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 8px;
                border: none;
                border-right: 1px solid #3e3e42;
                border-bottom: 1px solid #3e3e42;
                font-weight: bold;
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
        
        # Etapa 2: Seleção de empresa
        self._stack.addWidget(self._create_empresa_step())
        
        # Etapa 3: Autenticação
        self._stack.addWidget(self._create_auth_step())
        
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
        
        # Logo removido (não exibido)
        layout.addSpacing(8)
        
        # Título
        title = QLabel(APP_INFO.NAME)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #ffffff;")
        layout.addWidget(title)
        
        # Subtítulo
        subtitle = QLabel("Sistema de exportação de carga para o aplicativo CSCollect")
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
        group = QGroupBox("🔌 Selecione a base de dados")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)
        group_layout.setContentsMargins(16, 20, 16, 16)
        
        # Info do arquivo XML
        xml_info = QLabel(f"📄 Arquivo: {CSLOGIN_PATH}")
        xml_info.setStyleSheet("color: #666666; font-size: 9pt;")
        group_layout.addWidget(xml_info)
        
        # Combo de conexões
        lbl_connection = QLabel("Base de dados:")
        group_layout.addWidget(lbl_connection)
        
        self._cmb_connection = QComboBox()
        self._cmb_connection.setMinimumHeight(40)
        group_layout.addWidget(self._cmb_connection)
        
        # Detalhes da conexão selecionada
        self._lbl_connection_details = QLabel("")
        self._lbl_connection_details.setStyleSheet("""
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 12px;
            color: #9d9d9d;
            font-size: 9pt;
        """)
        self._lbl_connection_details.setWordWrap(True)
        self._lbl_connection_details.hide()
        group_layout.addWidget(self._lbl_connection_details)
        
        # Status de conexão
        self._lbl_connection_status = QLabel("")
        self._lbl_connection_status.setStyleSheet("font-size: 9pt;")
        self._lbl_connection_status.setWordWrap(True)
        group_layout.addWidget(self._lbl_connection_status)
        
        layout.addWidget(group)
        
        layout.addStretch()
        
        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_connect = QPushButton("🔗  Conectar")
        self._btn_connect.setMinimumSize(160, 44)
        self._btn_connect.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_connect.setEnabled(False)
        self._btn_connect.setStyleSheet("""
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
        btn_layout.addWidget(self._btn_connect)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_empresa_step(self) -> QWidget:
        """Cria etapa de seleção de empresa."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 16, 0, 0)
        
        # Info da conexão selecionada
        self._lbl_selected_connection = QLabel("")
        self._lbl_selected_connection.setStyleSheet("""
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 12px;
            color: #9d9d9d;
        """)
        layout.addWidget(self._lbl_selected_connection)
        
        # Grupo de empresa
        group = QGroupBox("🏢 Selecione a Empresa")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)
        group_layout.setContentsMargins(16, 20, 16, 16)
        
        # Tabela de empresas
        self._table_empresas = QTableWidget()
        self._table_empresas.setColumnCount(3)
        self._table_empresas.setHorizontalHeaderLabels(["Código", "Nome", "CNPJ"])
        self._table_empresas.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_empresas.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table_empresas.setAlternatingRowColors(True)
        self._table_empresas.verticalHeader().setVisible(False)
        self._table_empresas.setMinimumHeight(200)
        
        # Ajusta colunas
        header = self._table_empresas.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        group_layout.addWidget(self._table_empresas)
        
        layout.addWidget(group)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        self._btn_back_empresa = QPushButton("←  Voltar")
        self._btn_back_empresa.setMinimumSize(100, 40)
        self._btn_back_empresa.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_back_empresa.setStyleSheet("""
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
        btn_layout.addWidget(self._btn_back_empresa)
        
        btn_layout.addStretch()
        
        self._btn_next_empresa = QPushButton("Avançar  →")
        self._btn_next_empresa.setMinimumSize(160, 44)
        self._btn_next_empresa.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_next_empresa.setEnabled(False)
        self._btn_next_empresa.setStyleSheet("""
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
        btn_layout.addWidget(self._btn_next_empresa)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_auth_step(self) -> QWidget:
        """Cria etapa de autenticação de usuário."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 16, 0, 0)
        
        # Info da conexão e empresa selecionadas
        self._lbl_selected_context = QLabel("")
        self._lbl_selected_context.setStyleSheet("""
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 12px;
            color: #9d9d9d;
            font-size: 9pt;
        """)
        self._lbl_selected_context.setWordWrap(True)
        layout.addWidget(self._lbl_selected_context)
        
        # Grupo de autenticação
        group = QGroupBox("🔐 Autenticação")
        group_layout = QFormLayout(group)
        group_layout.setSpacing(16)
        group_layout.setContentsMargins(16, 24, 16, 16)
        
        # Campo de usuário
        self._txt_username = QLineEdit()
        self._txt_username.setPlaceholderText("Digite seu usuário...")
        self._txt_username.setMinimumHeight(40)
        group_layout.addRow("Usuário:", self._txt_username)
        
        # Campo de senha
        self._txt_password = QLineEdit()
        self._txt_password.setPlaceholderText("Digite sua senha...")
        self._txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_password.setMinimumHeight(40)
        group_layout.addRow("Senha:", self._txt_password)
        
        # Status de autenticação
        self._lbl_auth_status = QLabel("")
        self._lbl_auth_status.setStyleSheet("font-size: 9pt;")
        self._lbl_auth_status.setWordWrap(True)
        group_layout.addRow("", self._lbl_auth_status)
        
        layout.addWidget(group)
        
        layout.addStretch()
        
        # Botões
        btn_layout = QHBoxLayout()
        
        self._btn_back_auth = QPushButton("←  Voltar")
        self._btn_back_auth.setMinimumSize(100, 40)
        self._btn_back_auth.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_back_auth.setStyleSheet("""
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
        btn_layout.addWidget(self._btn_back_auth)
        
        btn_layout.addStretch()
        
        self._btn_login = QPushButton("✅  Entrar")
        self._btn_login.setMinimumSize(160, 44)
        self._btn_login.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_login.setEnabled(False)
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
        # Step 1 - Conexão
        self._cmb_connection.currentIndexChanged.connect(self._on_connection_changed)
        self._btn_connect.clicked.connect(self._on_connect)
        
        # Step 2 - Empresa
        self._btn_back_empresa.clicked.connect(self._on_back_to_connection)
        self._btn_next_empresa.clicked.connect(self._on_next_to_auth)
        self._table_empresas.itemSelectionChanged.connect(self._on_empresa_selected)
        self._table_empresas.doubleClicked.connect(self._on_next_to_auth)
        
        # Step 3 - Autenticação
        self._btn_back_auth.clicked.connect(self._on_back_to_empresa)
        self._btn_login.clicked.connect(self._on_login)
        self._txt_username.textChanged.connect(self._on_auth_fields_changed)
        self._txt_password.textChanged.connect(self._on_auth_fields_changed)
        self._txt_password.returnPressed.connect(self._on_login)
    
    def _load_connections(self):
        """Carrega conexões do arquivo CSLogin.xml."""
        try:
            import xml.etree.ElementTree as ET
            
            self._cmb_connection.clear()
            self._cmb_connection.addItem("Selecione uma base de dados...", None)
            
            # Verifica se arquivo existe
            if not os.path.exists(CSLOGIN_PATH):
                logger.warning(f"Arquivo não encontrado: {CSLOGIN_PATH}")
                self._lbl_connection_status.setText(f"⚠️ Arquivo não encontrado: {CSLOGIN_PATH}")
                self._lbl_connection_status.setStyleSheet("color: #ff9800; font-size: 9pt;")
                return
            
            # Lê XML
            tree = ET.parse(CSLOGIN_PATH)
            root = tree.getroot()
            
            self._connections = []
            
            # Carrega último login para pré-selecionar
            last_login = login_module.load_last_login()
            default_index = 0
            
            for conf in root.findall(".//Configuracao"):
                try:
                    entry = {
                        "login_id": conf.attrib.get("LoginID", ""),
                        "type": "",
                        "server": "",
                        "database": ""
                    }
                    
                    for child in conf:
                        tag = (child.tag or "").strip()
                        value = (child.text or "").strip()
                        
                        if tag == "TipoBanco":
                            entry["type"] = value
                        elif tag == "NomeServidor":
                            entry["server"] = value
                        elif tag == "NomeBanco":
                            entry["database"] = value
                    
                    if entry["server"] and entry["database"]:
                        self._connections.append(entry)
                        
                        # Formato de exibição: [TipoBanco] Servidor - Banco
                        display = f"[{entry['type']}] {entry['server']} - {entry['database']}"
                        self._cmb_connection.addItem(display, entry)
                        
                        # Verifica se é o último usado
                        if last_login:
                            if (entry["server"].lower() == last_login.get("srv", "").lower() and
                                entry["database"].lower() == last_login.get("db", "").lower()):
                                default_index = self._cmb_connection.count() - 1
                        
                except Exception as e:
                    logger.warning(f"Erro ao processar entrada: {e}")
                    continue
            
            logger.info(f"Carregadas {len(self._connections)} conexões de {CSLOGIN_PATH}")
            
            if not self._connections:
                self._lbl_connection_status.setText("⚠️ Nenhuma conexão encontrada no arquivo XML")
                self._lbl_connection_status.setStyleSheet("color: #ff9800; font-size: 9pt;")
            elif default_index > 0:
                # Seleciona última conexão usada
                self._cmb_connection.setCurrentIndex(default_index)
            
        except Exception as e:
            logger.error(f"Erro ao carregar conexões: {e}")
            self._lbl_connection_status.setText(f"❌ Erro ao ler arquivo: {str(e)}")
    
    def _validate_license_for_connection(self, connection: dict) -> bool:
        """
        Lê e valida o arquivo .key contra a conexão fornecida.
        Valida presença de `sql_servidor` e `sql_banco` (<=30 chars), verifica assinatura HMAC
        e se os campos batem com a conexão selecionada. Armazena payload em
        `self._licenca_payload` quando válido.
        """
        try:
            # Procura arquivos .key em locais comuns: pasta do app, cwd e C:\ceosoftware
            search_paths = [Path(AppConfig.BASE_DIR), Path.cwd(), Path(r"C:\ceosoftware")]
            key_files = []
            for p in search_paths:
                try:
                    if p.exists():
                        key_files.extend(list(p.glob("*.key")))
                except Exception:
                    continue
            # Remover duplicatas mantendo ordem
            seen = set()
            key_files_unique = []
            for k in key_files:
                kp = str(k.resolve())
                if kp not in seen:
                    seen.add(kp)
                    key_files_unique.append(k)
            key_files = key_files_unique
            if not key_files:
                QMessageBox.critical(self, "Arquivo de licença não encontrado", "Arquivo .key não encontrado, o sistema não poderá ser aberto.\nEntre em contato com o suporte para obter uma licença válida.")
                return False

            # Tenta verificar cada arquivo .key usando a biblioteca utilitária,
            # que espera uma MASTER_KEY (via argumento ou env MASTER_KEY).
            payload_dict = None
            licenca_erro = None
            # Obtém MASTER_KEY centralmente (env -> .env -> AppConfig file)
            try:
                from utils.master_key import load_master_key
                master_key, mk_source = load_master_key()
            except Exception:
                master_key = None

            for cand in key_files:
                try:
                    # Se master_key for None, a função utilitária tentará usar env internamente
                    if master_key is not None:
                        payload = cscollectmanager_verify.load_and_verify_file(str(cand), master_key)
                    else:
                        payload = cscollectmanager_verify.load_and_verify_file(str(cand))
                    payload_dict = payload
                    break
                except Exception as exc:
                    licenca_erro = str(exc)
                    continue

            if payload_dict is None:
                QMessageBox.critical(self, "Erro de licença", f"Não foi possível validar nenhum arquivo de licença.\n{licenca_erro or ''}")
                return False

            # Validação de campos obrigatórios: sql_servidor / sql_banco
            sql_servidor = (payload_dict.get('sql_servidor') or '').strip()
            sql_banco = (payload_dict.get('sql_banco') or '').strip()
            if not sql_servidor or not sql_banco:
                QMessageBox.critical(self, "Campo de licença ausente", "Arquivo de licença inválido: campo 'sql_servidor' ou 'sql_banco' ausente.")
                return False

            if len(sql_servidor) > 30 or len(sql_banco) > 30:
                QMessageBox.critical(self, "Campo inválido", "Arquivo de licença inválido: 'sql_servidor' ou 'sql_banco' excede 30 caracteres.")
                return False

            # A assinatura já foi verificada por cscollectmanager_verify.load_and_verify_file.
            # Verificar validade da licença (data)
            validade = payload_dict.get('validade') or ''
            try:
                if validade:
                    if 'T' in validade or validade.endswith('Z'):
                        from datetime import datetime, timezone
                        v = validade.replace('Z', '+00:00')
                        val_dt = datetime.fromisoformat(v)
                        if val_dt.tzinfo is None:
                            val_dt = val_dt.replace(tzinfo=timezone.utc)
                        if val_dt < datetime.now(timezone.utc):
                            QMessageBox.critical(self, "Licença expirada", "A licença de uso está expirada. Contate o suporte.")
                            return False
                    else:
                        from datetime import date
                        if date.fromisoformat(validade) < date.today():
                            QMessageBox.critical(self, "Licença expirada", "A licença de uso está expirada. Contate o suporte.")
                            return False
            except Exception:
                pass

            # Verifica se os campos sql_servidor/sql_banco batem com a conexão selecionada
            conn_srv = (connection.get('server') or '').strip()
            conn_db = (connection.get('database') or '').strip()
            if (conn_srv.lower() != sql_servidor.lower()) or (conn_db.lower() != sql_banco.lower()):
                QMessageBox.critical(self, "Servidor/Banco inválidos", "O servidor ou banco informado na licença não corresponde à conexão selecionada.")
                return False

            # Tudo OK: armazena payload
            self._licenca_payload = payload_dict
            return True
        except Exception as e:
            logger.error(f"Erro ao validar arquivo .key: {e}")
            QMessageBox.critical(self, "Erro de licença", "Erro ao validar arquivo .key. O sistema não pode prosseguir.")
            return False
            self._lbl_connection_status.setStyleSheet("color: #f44336; font-size: 9pt;")
    
    def _on_connection_changed(self, index: int):
        """Quando conexão é alterada."""
        self._btn_connect.setEnabled(index > 0)
        self._lbl_connection_status.setText("")
        
        if index > 0:
            conn = self._cmb_connection.currentData()
            if conn:
                details = (
                    f"🔹 Tipo: {conn.get('type', 'N/A')}\n"
                    f"🔹 Servidor: {conn.get('server', 'N/A')}\n"
                    f"🔹 Banco: {conn.get('database', 'N/A')}"
                )
                self._lbl_connection_details.setText(details)
                self._lbl_connection_details.show()
        else:
            self._lbl_connection_details.hide()
    
    def _on_connect(self):
        """Conecta ao banco selecionado."""
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
        self._btn_connect.setEnabled(False)
        self._cmb_connection.setEnabled(False)
        self._lbl_connection_status.setText("⏳ Conectando ao banco de dados...")
        self._lbl_connection_status.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
        
        # Inicia worker
        self._worker = ConnectionWorker(connection)
        self._worker.finished.connect(self._on_connection_finished)
        self._worker.start()
    
    def _on_connection_finished(self, success: bool, message: str, empresas: list):
        """Callback da conexão."""
        self._progress.hide()
        self._progress.setRange(0, 100)
        self._btn_connect.setEnabled(True)
        self._cmb_connection.setEnabled(True)
        
        if success:
            self._lbl_connection_status.setText(f"✅ {message}")
            self._lbl_connection_status.setStyleSheet("color: #4caf50; font-size: 9pt;")
            
            self._empresas = empresas
            # Ao conectar com sucesso, validaremos o arquivo .key contra a conexão
            try:
                valid = self._validate_license_for_connection(self._selected_connection)
            except Exception:
                valid = False

            if not valid:
                # Mensagem já exibida em _validate_license_for_connection
                return

            if empresas:
                # Avança para seleção de empresa
                QTimer.singleShot(500, self._show_empresa_step)
            else:
                QMessageBox.warning(
                    self, "Aviso",
                    "Nenhuma empresa encontrada no banco de dados."
                )
        else:
            self._lbl_connection_status.setText(f"❌ Erro: {message}")
            self._lbl_connection_status.setStyleSheet("color: #f44336; font-size: 9pt;")
    
    def _show_empresa_step(self):
        """Mostra etapa de seleção de empresa."""
        # Atualiza info da conexão
        conn = self._selected_connection
        self._lbl_selected_connection.setText(
            f"🔌 Conectado a: [{conn.get('type')}] {conn.get('server')} / {conn.get('database')}"
        )
        
        # Carrega último login para pré-selecionar empresa
        last_login = login_module.load_last_login()
        default_row = -1
        
        # Popula tabela de empresas
        self._table_empresas.setRowCount(0)
        
        for idx, emp in enumerate(self._empresas):
            row = self._table_empresas.rowCount()
            self._table_empresas.insertRow(row)
            
            # Código
            item_codigo = QTableWidgetItem(str(emp.get("codigo", "")))
            item_codigo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_codigo.setData(Qt.ItemDataRole.UserRole, emp)
            self._table_empresas.setItem(row, 0, item_codigo)
            
            # Nome
            item_nome = QTableWidgetItem(emp.get("nome", ""))
            self._table_empresas.setItem(row, 1, item_nome)
            
            # CNPJ
            cnpj = emp.get("cnpj", "")
            if cnpj:
                # Formata CNPJ
                cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "").replace(" ", "")
                if len(cnpj_clean) == 14:
                    cnpj = f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:]}"
            item_cnpj = QTableWidgetItem(cnpj)
            item_cnpj.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table_empresas.setItem(row, 2, item_cnpj)
            
            # Verifica se é a última empresa selecionada
            if last_login:
                if (conn.get("server", "").lower() == last_login.get("srv", "").lower() and
                    conn.get("database", "").lower() == last_login.get("db", "").lower() and
                    str(emp.get("codigo", "")) == str(last_login.get("codempresa", ""))):
                    default_row = row
        
        # Muda para step de empresa
        self._stack.setCurrentIndex(self.STEP_EMPRESA)
        self._btn_next_empresa.setEnabled(False)
        
        # Seleciona última empresa usada
        if default_row >= 0:
            self._table_empresas.selectRow(default_row)
    
    def _on_empresa_selected(self):
        """Quando empresa é selecionada."""
        selected = self._table_empresas.selectedItems()
        self._btn_next_empresa.setEnabled(len(selected) > 0)
    
    def _on_back_to_connection(self):
        """Volta para seleção de conexão."""
        self._stack.setCurrentIndex(self.STEP_CONNECTION)
        self._selected_empresa = None
    
    def _on_next_to_auth(self):
        """Avança para etapa de autenticação."""
        selected_rows = self._table_empresas.selectedItems()
        if not selected_rows:
            return
        
        # Pega dados da empresa selecionada
        row = selected_rows[0].row()
        item = self._table_empresas.item(row, 0)
        empresa = item.data(Qt.ItemDataRole.UserRole)
        
        if not empresa:
            return
        
        self._selected_empresa = empresa
        # Validação de CNPJ usando payload já validado para a conexão
        try:
            cnpj_raw = (empresa.get('cnpj') or "").strip()
            cnpj_clean = re.sub(r"\D", "", cnpj_raw)
            if not cnpj_clean:
                QMessageBox.critical(self, "Empresa sem CNPJ", "A empresa selecionada não possui CNPJ cadastrado. Não é possível validar autorização.")
                return

            # Se por algum motivo o payload não foi carregado ao conectar, tenta carregar agora
            if not self._licenca_payload:
                ok = self._validate_license_for_connection(self._selected_connection)
                if not ok:
                    return

            payload_dict = self._licenca_payload or {}
            raw_cnpjs = payload_dict.get('cnpjs', []) or []
            cnpjs_licenca = {re.sub(r"\D", "", str(c)) for c in raw_cnpjs}
            cnpjs_licenca = {c for c in cnpjs_licenca if len(c) == 14}

            if not cnpjs_licenca:
                QMessageBox.critical(self, "CNPJ não autorizado", "Nenhum CNPJ válido encontrado na licença. Contate o administrador do sistema.")
                return

            if cnpj_clean not in cnpjs_licenca:
                QMessageBox.warning(self, "CNPJ não liberado", "O CNPJ da empresa selecionada não está liberado nesta licença.\nContate o administrador do sistema.")
                return
        except Exception as e:
            logger.error(f"Erro ao validar arquivo .key: {e}")
            QMessageBox.critical(self, "Erro de licença", "Erro ao validar arquivo .key. O sistema não pode prosseguir.")
            return
        
        # Atualiza contexto
        conn = self._selected_connection
        self._lbl_selected_context.setText(
            f"🔌 Servidor: [{conn.get('type')}] {conn.get('server')} / {conn.get('database')}\n"
            f"🏢 Empresa: {empresa.get('codigo')} - {empresa.get('nome')}"
        )
        
        # Limpa campos
        self._txt_password.clear()
        self._lbl_auth_status.clear()
        
        # Carrega último usuário para este servidor/banco
        last_login = login_module.load_last_login()
        if last_login:
            if (conn.get("server", "").lower() == last_login.get("srv", "").lower() and
                conn.get("database", "").lower() == last_login.get("db", "").lower()):
                self._txt_username.setText(last_login.get("user", ""))
        
        # Muda para step de autenticação
        self._stack.setCurrentIndex(self.STEP_AUTH)
        
        # Foco no campo apropriado
        if self._txt_username.text():
            self._txt_password.setFocus()
        else:
            self._txt_username.setFocus()
    
    def _on_back_to_empresa(self):
        """Volta para seleção de empresa."""
        self._stack.setCurrentIndex(self.STEP_EMPRESA)
    
    def _on_auth_fields_changed(self):
        """Quando campos de autenticação mudam."""
        has_user = bool(self._txt_username.text().strip())
        has_pass = bool(self._txt_password.text())
        self._btn_login.setEnabled(has_user and has_pass)
        self._lbl_auth_status.clear()
    
    def _on_login(self):
        """Executa login."""
        username = self._txt_username.text().strip()
        password = self._txt_password.text()
        
        if not username or not password:
            return
        
        # Mostra progresso
        self._progress.setRange(0, 0)
        self._progress.show()
        self._btn_login.setEnabled(False)
        self._btn_back_auth.setEnabled(False)
        self._txt_username.setEnabled(False)
        self._txt_password.setEnabled(False)
        self._lbl_auth_status.setText("⏳ Autenticando...")
        self._lbl_auth_status.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
        
        # Cria configuração do banco
        conn = self._selected_connection
        db_config = DBConfig(
            server=conn.get("server", ""),
            database=conn.get("database", ""),
            auth="trusted"  # Windows Authentication padrão
        )
        
        # Inicia worker de autenticação
        self._auth_worker = AuthWorker(username, password, db_config)
        self._auth_worker.finished.connect(self._on_auth_finished)
        self._auth_worker.start()
    
    def _on_auth_finished(self, success: bool, message: str, user_data: dict):
        """Callback da autenticação."""
        self._progress.hide()
        self._progress.setRange(0, 100)
        self._btn_login.setEnabled(True)
        self._btn_back_auth.setEnabled(True)
        self._txt_username.setEnabled(True)
        self._txt_password.setEnabled(True)
        
        if success:
            self._lbl_auth_status.setText(f"✅ {message}")
            self._lbl_auth_status.setStyleSheet("color: #4caf50; font-size: 9pt;")
            
            # Salva último login
            conn = self._selected_connection
            empresa = self._selected_empresa
            login_module.save_last_login(
                user=self._txt_username.text().strip(),
                srv=conn.get("server", ""),
                db=conn.get("database", ""),
                codempresa=str(empresa.get("codigo", "")),
                nomeempresa=empresa.get("nome", "")
            )
            
            logger.info(f"Login bem-sucedido: {user_data.get('NomeUsuario')}")
            
            # Emite sinal de sucesso após breve delay
            QTimer.singleShot(500, lambda: self._emit_login_success(user_data))
        else:
            # Atualiza label de status e exibe caixa de diálogo explícita
            self._lbl_auth_status.setText(f"❌ {message}")
            self._lbl_auth_status.setStyleSheet("color: #f44336; font-size: 9pt;")
            self._txt_password.clear()
            self._txt_password.setFocus()

            try:
                QMessageBox.critical(self, "Falha no Login", message)
            except Exception:
                # Em alguns contextos a caixa pode falhar silenciosamente; apenas continue
                pass
    
    def _emit_login_success(self, user_data: dict):
        """Emite sinal de login bem-sucedido."""
        login_data = {
            "connection": self._selected_connection,
            "empresa": {
                "codigo": self._selected_empresa.get("codigo"),
                "nome": self._selected_empresa.get("nome"),
                "cnpj": self._selected_empresa.get("cnpj", "")
            },
            "usuario": {
                "codigo": user_data.get("CodUsuario", 0),
                "nome": user_data.get("NomeUsuario", ""),
                "admin": user_data.get("PDVGerenteSN", 0) == 1
            },
            "licenca": self._licenca_payload or {}
        }
        
        self.login_successful.emit(login_data)
    
    def closeEvent(self, event):
        """Evento de fechamento."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        
        if self._auth_worker and self._auth_worker.isRunning():
            self._auth_worker.terminate()
            self._auth_worker.wait()
        
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
