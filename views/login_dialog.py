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
    QSizePolicy, QStackedWidget, QWidget
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QThread
from PySide6.QtGui import QFont, QPixmap, QIcon, QCursor

from utils.constants import APP_INFO
from utils.logger import get_logger
from utils.config import AppConfig
from app.styles import get_active_theme
from pathlib import Path
import re
from services import licenca_online
import sys


def _extract_api_token(token: str) -> str:
    """Retorna apenas a parte do token da API (antes do '.' da assinatura Neon).

    Formato no .key: 'api_token.neon_signature'  ->  retorna 'api_token'
    Formato HMAC assinado ou token simples       ->  retorna o token inteiro
    """
    if not token:
        return token
    parts = token.split('.')
    # Token puro com assinatura Neon: primeira parte é hex MD5 (32 chars), segunda é base64url
    if len(parts) == 2 and len(parts[0]) == 32 and parts[0].isalnum():
        return parts[0]
    return token

# Importações para persistência e autenticação
import login as login_module
from authentication import DBConfig, verify_user, get_connection

logger = get_logger(__name__)


# Caminho padrão do arquivo de conexões
CSLOGIN_PATH = r"C:\CEOSoftware\CSLogin.xml"

# Caminho do logo (usa o ícone da aplicação)
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico")

# Logo em PNG (ícone azul transparente da marca) — usado no cabeçalho da tela
LOGO_PNG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")


# ==========================================================================
# Paleta de cores — harmonizada com o splash (app/splash.py) no escuro;
# adaptada ao tema ativo (app/styles.py) para o claro.
# ==========================================================================
_active_theme = get_active_theme()
_is_light_theme = _active_theme.__name__ == "LightTheme"


class _C:
    """Tokens de cor da tela de login, adaptados ao tema ativo."""

    # Cores semânticas de status (aviso/erro/sucesso) — reaproveitam
    # diretamente os tokens do tema ativo em app/styles.py.
    WARNING = _active_theme.WARNING
    ERROR = _active_theme.ERROR
    SUCCESS = _active_theme.SUCCESS

    if _is_light_theme:
        BG_DIALOG = "#f3f5f9"       # fundo (canvas claro)
        BG_PANEL = "#e8ecf3"        # caixas de info
        BG_INPUT = "#ffffff"        # campos
        BG_INPUT_HOVER = "#eef2f8"
        BORDER = "#d7deea"
        BORDER_HOVER = "#b8c6dc"
        ACCENT = "#2f7dd8"          # azul de marca (aprofundado p/ contraste no branco)
        ACCENT_DEEP = "#1d6bb0"
        ACCENT_DARK = "#123f73"
        TEXT = "#1b2433"
        TEXT_MUTED = "#55617a"
        TEXT_FAINT = "#a3adc0"
        SELECTION = "#1d6bb0"        # mantém combinação azul-escuro + texto branco
        BTN_DISABLED_BG = "#e2e7f0"
        BTN_DISABLED_FG = "#a3adc0"
        HOVER_LIGHT = "#3e9cf7"      # gradiente de hover do botão primário
        HOVER_DEEP = "#1d6bb0"
        ALT_ROW = "#eef2f8"          # linha alternada de tabela
    else:
        BG_DIALOG = "#0f1826"       # fundo (azul-marinho profundo, casa com #0e42b0)
        BG_PANEL = "#16223c"        # caixas de info
        BG_INPUT = "#1a2740"        # campos
        BG_INPUT_HOVER = "#20304e"
        BORDER = "#2a3a57"
        BORDER_HOVER = "#35507e"
        ACCENT = "#3e9cf7"          # azul claro (foco/realces)
        ACCENT_DEEP = "#1d6bb0"
        ACCENT_DARK = "#0e42b0"
        TEXT = "#e6edf6"
        TEXT_MUTED = "#9db3d1"
        TEXT_FAINT = "#6b7f9e"
        SELECTION = "#1d6bb0"
        BTN_DISABLED_BG = "#24314a"
        BTN_DISABLED_FG = "#5a6b86"
        HOVER_LIGHT = "#5aa9f9"      # gradiente de hover do botão primário
        HOVER_DEEP = "#2a7cc4"
        ALT_ROW = "#131f36"          # linha alternada de tabela


def _primary_button_qss() -> str:
    """QSS do botão primário (gradiente azul do splash)."""
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {_C.ACCENT}, stop:1 {_C.ACCENT_DEEP});
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 10px 24px;
            font-weight: bold;
            font-size: 11pt;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {_C.HOVER_LIGHT}, stop:1 {_C.HOVER_DEEP});
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {_C.ACCENT_DEEP}, stop:1 {_C.ACCENT_DARK});
        }}
        QPushButton:disabled {{
            background: {_C.BTN_DISABLED_BG};
            color: {_C.BTN_DISABLED_FG};
        }}
    """


def _secondary_button_qss() -> str:
    """QSS do botão secundário (navy sutil)."""
    return f"""
        QPushButton {{
            background-color: {_C.BG_INPUT};
            color: {_C.TEXT_MUTED};
            border: 1px solid {_C.BORDER};
            border-radius: 8px;
            padding: 10px 20px;
        }}
        QPushButton:hover {{
            background-color: {_C.BG_INPUT_HOVER};
            color: {_C.TEXT};
            border-color: {_C.ACCENT_DEEP};
        }}
    """


def _friendly_connection_error(error: Exception, banco: str = "", servidor: str = "") -> str:
    """Converte erros técnicos de conexão em mensagens amigáveis ao usuário."""
    msg = str(error)
    msg_lower = msg.lower()

    if "cannot open database" in msg_lower or "não foi possível abrir" in msg_lower:
        db_label = f'"{banco}"' if banco else "selecionada"
        return (
            f"❌ Base de dados {db_label} não encontrada no servidor.\n\n"
            "Verifique se:\n"
            "  • O nome da base de dados está correto no CSLogin.xml\n"
            "  • A base de dados existe e está acessível\n"
            "  • Você tem permissão de acesso a ela"
        )
    if "login failed" in msg_lower or "falha no login" in msg_lower:
        return (
            f"❌ Falha de autenticação no servidor{f' {servidor}' if servidor else ''}.\n\n"
            "Verifique se:\n"
            "  • Sua conta Windows tem acesso ao SQL Server\n"
            "  • O servidor está acessível na rede"
        )
    if "network-related" in msg_lower or "server was not found" in msg_lower or "não foi possível conectar" in msg_lower:
        srv_label = f'"{servidor}"' if servidor else "configurado"
        return (
            f"❌ Servidor {srv_label} não encontrado ou inacessível.\n\n"
            "Verifique se:\n"
            "  • O nome do servidor está correto\n"
            "  • O SQL Server está em execução\n"
            "  • A rede/firewall permite a conexão"
        )
    if "driver" in msg_lower and "sql server" in msg_lower:
        return (
            "❌ Driver ODBC para SQL Server não encontrado.\n\n"
            "Instale o 'ODBC Driver 17 for SQL Server' (ou superior) "
            "disponível no site da Microsoft."
        )
    # Mensagem genérica mais legível
    return f"❌ Não foi possível conectar ao banco de dados.\n\nDetalhe técnico: {msg}"


class ConnectionWorker(QThread):
    """Worker para conectar ao banco e carregar empresas em background."""
    
    finished = Signal(bool, str, list)  # sucesso, mensagem, empresas
    
    def __init__(self, connection_data: dict):
        """
        Inicializa o worker de conexão.

        Args:
            connection_data: Dicionário com as chaves ``server``, ``database``
                e ``type`` (tipo do banco, ex.: ``"MSSQL"``).
        """
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
                        ORDER BY CodEmpresa
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
            self.finished.emit(False, _friendly_connection_error(e, banco, servidor), [])
    
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
                ORDER BY CodEmpresa
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
            self.finished.emit(False, _friendly_connection_error(e, banco, servidor), [])


class LicencaOnlineWorker(QThread):
    """Worker para sincronizar a licença online (Neon, via CSCollectAPI) em
    background, sem travar a UI — a checagem online (no máximo uma por dia,
    ver `services/licenca_online.py`) pode levar até 60s na primeira
    verificação do dia (ex.: cold start do servidor no Render).

    Tenta cada arquivo .key candidato em sequência até um dar certo, mesma
    lógica que antes rodava direto na thread da UI.
    """

    finished = Signal(str, object, object)  # caminho do .key usado, payload (dict|None), erro (str|None)

    def __init__(self, key_files: list):
        super().__init__()
        self._key_files = key_files

    def run(self):
        payload_dict = None
        erro = None
        cand_path = ""
        for cand in self._key_files:
            try:
                payload_dict = licenca_online.sincronizar_licenca(str(cand))
                cand_path = str(cand)
                break
            except Exception as exc:
                erro = str(exc)
                continue
        self.finished.emit(cand_path, payload_dict, erro)


class AuthWorker(QThread):
    """Worker para autenticar usuário em background."""
    
    finished = Signal(bool, str, dict)  # sucesso, mensagem, dados_usuario
    
    def __init__(self, username: str, password: str, db_config: DBConfig):
        """
        Inicializa o worker de autenticação.

        Args:
            username: Nome de usuário para autenticar.
            password: Senha do usuário.
            db_config: Configuração de conexão com o banco de dados.
        """
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
        """
        Inicializa o diálogo de login.

        Carrega as conexões disponíveis a partir do arquivo ``CSLogin.xml``,
        configura a interface em três etapas (conexão, empresa e autenticação)
        e verifica a licença do sistema na inicialização.

        Args:
            parent: Widget pai (opcional).
        """
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
        self._licenca_token_raw: str = ""  # Token bruto do arquivo .key (para api_authorization)
        self._license_worker: Optional[LicencaOnlineWorker] = None
        self._startup_license_worker: Optional[LicencaOnlineWorker] = None
        self._license_connection: dict = {}  # Conexão sendo validada (usada no callback assíncrono)
        self._license_on_success = None  # Callback chamado quando a licença é validada com sucesso
        self._license_elapsed_timer: Optional[QTimer] = None  # Contador de segundos exibido durante a verificação
        self._license_elapsed_seconds: int = 0
        
        self._setup_ui()
        self._connect_signals()
        self._load_connections()
        # Carrega/verifica o arquivo de licença imediatamente ao abrir a tela
        try:
            self._load_license_on_start()
        except Exception:
            pass
    
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
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_C.BG_DIALOG};
            }}
            QLabel {{
                color: {_C.TEXT};
                background: transparent;
            }}
            QLineEdit, QComboBox {{
                background-color: {_C.BG_INPUT};
                border: 1px solid {_C.BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {_C.TEXT};
                min-height: 20px;
                selection-background-color: {_C.ACCENT_DEEP};
                selection-color: #ffffff;
            }}
            QLineEdit:hover, QComboBox:hover {{
                border-color: {_C.BORDER_HOVER};
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {_C.ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {_C.TEXT_MUTED};
                margin-right: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {_C.BG_INPUT};
                border: 1px solid {_C.BORDER};
                selection-background-color: {_C.SELECTION};
                color: {_C.TEXT};
                outline: none;
            }}
            QGroupBox {{
                color: {_C.TEXT};
                font-weight: bold;
                border: 1px solid {_C.BORDER};
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: {_C.ACCENT};
            }}
            QTableWidget {{
                background-color: {_C.BG_DIALOG};
                alternate-background-color: {_C.ALT_ROW};
                border: 1px solid {_C.BORDER};
                border-radius: 8px;
                gridline-color: {_C.BORDER};
                color: {_C.TEXT};
                outline: none;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {_C.SELECTION};
                color: #ffffff;
            }}
            QTableWidget::item:hover {{
                background-color: {_C.BG_INPUT_HOVER};
            }}
            QHeaderView::section {{
                background-color: {_C.BG_PANEL};
                color: {_C.TEXT_MUTED};
                padding: 8px;
                border: none;
                border-right: 1px solid {_C.BORDER};
                border-bottom: 1px solid {_C.BORDER};
                font-weight: bold;
            }}
            QScrollBar:vertical {{
                background: {_C.BG_DIALOG};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {_C.BORDER};
                border-radius: 5px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_C.ACCENT_DEEP};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
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
        line.setStyleSheet(f"background-color: {_C.BORDER};")
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
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {_C.BG_INPUT};
                border: none;
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background-color: {_C.ACCENT};
                border-radius: 1px;
            }}
        """)
        self._progress.hide()
        main_layout.addWidget(self._progress)
        
        # ===== RODAPÉ =====
        footer = QLabel(f"v{APP_INFO.VERSION} • {APP_INFO.COMPANY}")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"color: {_C.TEXT_FAINT}; font-size: 9pt;")
        main_layout.addWidget(footer)
    
    def _create_header(self) -> QWidget:
        """Cria header em faixa com o gradiente do splash, logo e título."""
        header = QFrame()
        header.setObjectName("LoginHeader")
        header.setStyleSheet(f"""
            QFrame#LoginHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {_C.ACCENT}, stop:0.5 {_C.ACCENT_DEEP}, stop:1 {_C.ACCENT_DARK});
                border-radius: 12px;
            }}
            QFrame#LoginHeader QLabel {{
                background: transparent;
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(18)

        # Logo (ícone azul transparente da marca)
        logo_lbl = QLabel()
        logo_lbl.setFixedWidth(56)
        if os.path.exists(LOGO_PNG_PATH):
            pm = QPixmap(LOGO_PNG_PATH)
            if not pm.isNull():
                logo_lbl.setPixmap(pm.scaled(
                    56, 56,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        layout.addWidget(logo_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # Título + subtítulo
        text_box = QVBoxLayout()
        text_box.setSpacing(3)
        text_box.setContentsMargins(0, 0, 0, 0)

        title = QLabel(APP_INFO.NAME)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        text_box.addWidget(title)

        subtitle = QLabel("Sistema de exportação de carga e contagens de estoque")
        subtitle.setStyleSheet("color: #dbe8ff; font-size: 9.5pt;")
        subtitle.setWordWrap(True)
        text_box.addWidget(subtitle)

        layout.addLayout(text_box, 1)

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
        xml_info.setStyleSheet(f"color: {_C.TEXT_FAINT}; font-size: 9pt;")
        group_layout.addWidget(xml_info)

        # Combo de conexões
        lbl_connection = QLabel("Base de dados:")
        group_layout.addWidget(lbl_connection)
        
        self._cmb_connection = QComboBox()
        self._cmb_connection.setMinimumHeight(40)
        group_layout.addWidget(self._cmb_connection)
        
        # Detalhes da conexão selecionada
        self._lbl_connection_details = QLabel("")
        self._lbl_connection_details.setStyleSheet(f"""
            background-color: {_C.BG_PANEL};
            border: 1px solid {_C.BORDER};
            border-radius: 8px;
            padding: 12px;
            color: {_C.TEXT_MUTED};
            font-size: 9pt;
        """)
        self._lbl_connection_details.setWordWrap(True)
        self._lbl_connection_details.hide()
        group_layout.addWidget(self._lbl_connection_details)

        # Label para exibir o caption da licença. O caminho completo aparecerá em tooltip ao passar o mouse.
        self._lbl_license_file = QLabel("Licença")
        self._lbl_license_file.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 8pt;")
        self._lbl_license_file.setToolTip("")
        self._lbl_license_file.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        group_layout.addWidget(self._lbl_license_file)

        # Label para exibir a data de validade da licença
        self._lbl_license_expiry = QLabel("")
        self._lbl_license_expiry.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 8pt;")
        self._lbl_license_expiry.hide()
        group_layout.addWidget(self._lbl_license_expiry)
        
        # Status de conexão
        self._lbl_connection_status = QLabel("")
        self._lbl_connection_status.setStyleSheet("font-size: 8pt;")
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
        self._btn_connect.setStyleSheet(_primary_button_qss())
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
        self._lbl_selected_connection.setStyleSheet(f"""
            background-color: {_C.BG_PANEL};
            border: 1px solid {_C.BORDER};
            border-radius: 8px;
            padding: 10px 12px;
            color: {_C.TEXT_MUTED};
            font-size: 9pt;
        """)
        layout.addWidget(self._lbl_selected_connection)

        # Grupo de empresa
        group = QGroupBox("🏢 Selecione a Empresa")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)
        group_layout.setContentsMargins(16, 20, 16, 16)

        # Lista suspensa de empresas
        lbl_empresa = QLabel("Empresa:")
        group_layout.addWidget(lbl_empresa)

        self._cmb_empresa = QComboBox()
        self._cmb_empresa.setMinimumHeight(40)
        group_layout.addWidget(self._cmb_empresa)

        # Legenda com a quantidade de empresas carregadas
        self._lbl_empresa_count = QLabel("")
        self._lbl_empresa_count.setStyleSheet(f"color: {_C.TEXT_FAINT}; font-size: 8pt;")
        group_layout.addWidget(self._lbl_empresa_count)

        layout.addWidget(group)

        layout.addStretch()

        # Botões
        btn_layout = QHBoxLayout()
        
        self._btn_back_empresa = QPushButton("←  Voltar")
        self._btn_back_empresa.setMinimumSize(100, 40)
        self._btn_back_empresa.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_back_empresa.setStyleSheet(_secondary_button_qss())
        btn_layout.addWidget(self._btn_back_empresa)
        
        btn_layout.addStretch()
        
        self._btn_next_empresa = QPushButton("Avançar  →")
        self._btn_next_empresa.setMinimumSize(160, 44)
        self._btn_next_empresa.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_next_empresa.setEnabled(False)
        self._btn_next_empresa.setStyleSheet(_primary_button_qss())
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
        self._lbl_selected_context.setStyleSheet(f"""
            background-color: {_C.BG_PANEL};
            border: 1px solid {_C.BORDER};
            border-radius: 8px;
            padding: 12px;
            color: {_C.TEXT_MUTED};
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
        self._btn_back_auth.setStyleSheet(_secondary_button_qss())
        btn_layout.addWidget(self._btn_back_auth)
        
        btn_layout.addStretch()
        
        self._btn_login = QPushButton("✅  Entrar")
        self._btn_login.setMinimumSize(160, 44)
        self._btn_login.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_login.setEnabled(False)
        self._btn_login.setStyleSheet(_primary_button_qss())
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
        self._cmb_empresa.currentIndexChanged.connect(self._on_empresa_selected)
        
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
                self._lbl_connection_status.setStyleSheet(f"color: {_C.WARNING}; font-size: 9pt;")
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
                self._lbl_connection_status.setStyleSheet(f"color: {_C.WARNING}; font-size: 9pt;")
            elif default_index > 0:
                # Seleciona última conexão usada
                self._cmb_connection.setCurrentIndex(default_index)
            
        except Exception as e:
            logger.error(f"Erro ao carregar conexões: {e}")
            self._lbl_connection_status.setText(f"❌ Erro ao ler arquivo: {str(e)}")
    
    def _discover_key_files(self) -> list:
        """Procura arquivos .key em locais comuns: pasta do app, cwd e
        C:\\ceosoftware. Quando empacotado, inclui também o _MEIPASS e a
        pasta do executável. Remove duplicatas mantendo a ordem."""
        search_paths = [Path(AppConfig.BASE_DIR), Path.cwd(), Path(r"C:\ceosoftware")]
        try:
            if getattr(sys, 'frozen', False):
                meipass = getattr(sys, '_MEIPASS', None)
                if meipass:
                    search_paths.insert(0, Path(meipass))
                exe_dir = Path(sys.executable).parent
                search_paths.insert(0, exe_dir)
        except Exception:
            pass
        key_files = []
        for p in search_paths:
            try:
                if p.exists():
                    key_files.extend(list(p.glob("*.key")))
            except Exception:
                continue
        seen = set()
        key_files_unique = []
        for k in key_files:
            kp = str(k.resolve())
            if kp not in seen:
                seen.add(kp)
                key_files_unique.append(k)
        return key_files_unique

    def _render_licenca_labels(self, cand_path: str, payload_dict: dict):
        """Atualiza os labels de arquivo/validade da licença exibidos na tela de login."""
        try:
            _nome_key = os.path.basename(cand_path)
            self._lbl_license_file.setToolTip(cand_path)
            self._lbl_license_file.setText(f"📄 Licença: {_nome_key}")
            self._lbl_license_file.show()
        except Exception:
            pass

        _val = payload_dict.get('validade') or ''
        _tipo = (payload_dict.get('tipo_licenca') or '').strip()
        _tipo_sufixo = f" · Licença {_tipo}" if _tipo else ""
        try:
            if _val:
                from datetime import datetime, date, timezone as _tz
                _expirada = False
                if 'T' in _val or _val.endswith('Z'):
                    _v = _val.replace('Z', '+00:00')
                    _dt = datetime.fromisoformat(_v)
                    if _dt.tzinfo is None:
                        _dt = _dt.replace(tzinfo=_tz.utc)
                    _val_fmt = _dt.strftime('%d/%m/%Y')
                    _expirada = _dt < datetime.now(_tz.utc)
                else:
                    _dt = date.fromisoformat(_val)
                    _val_fmt = _dt.strftime('%d/%m/%Y')
                    _expirada = _dt < date.today()
                if _expirada:
                    self._lbl_license_expiry.setText(f"⚠️ Validade: {_val_fmt} (expirada){_tipo_sufixo}")
                    self._lbl_license_expiry.setStyleSheet(f"color: {_C.ERROR}; font-size: 8pt;")
                else:
                    self._lbl_license_expiry.setText(f"📅 Validade: {_val_fmt}{_tipo_sufixo}")
                    self._lbl_license_expiry.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 8pt;")
                self._lbl_license_expiry.show()
            elif _tipo:
                self._lbl_license_expiry.setText(f"🔑 Licença {_tipo}")
                self._lbl_license_expiry.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 8pt;")
                self._lbl_license_expiry.show()
            else:
                self._lbl_license_expiry.hide()
        except Exception:
            self._lbl_license_expiry.hide()

    def _licenca_expirada_bloqueia(self, payload_dict: dict) -> bool:
        """Se `validade` já passou, mostra o critical de licença expirada e
        retorna True (chamador deve interromper o fluxo)."""
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
                        self._lbl_license_expiry.setStyleSheet(f"color: {_C.ERROR}; font-size: 8pt;")
                        QMessageBox.critical(self, "Licença expirada", "A licença de uso está expirada. Contate o suporte.")
                        return True
                else:
                    from datetime import date
                    if date.fromisoformat(validade) < date.today():
                        self._lbl_license_expiry.setStyleSheet(f"color: {_C.ERROR}; font-size: 8pt;")
                        QMessageBox.critical(self, "Licença expirada", "A licença de uso está expirada. Contate o suporte.")
                        return True
        except Exception:
            pass
        return False

    def _armazenar_licenca_payload(self, cand_path: str, payload_dict: dict):
        """Guarda o payload validado em `self._licenca_payload`/`self._licenca_token_raw`."""
        self._licenca_payload = payload_dict
        # Registrar api_authorization descriptografado (vindo do Neon) no AppConfig
        _api_auth = payload_dict.get('_api_authorization', '')
        if _api_auth:
            AppConfig.set_api_authorization_override(_api_auth)
        try:
            import json as _json
            _kraw = None
            for _enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
                try:
                    with open(cand_path, 'r', encoding=_enc) as _kf:
                        _kraw = _kf.read().strip()
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if _kraw:
                try:
                    _kdata = _json.loads(_kraw)
                    self._licenca_token_raw = _extract_api_token(_kdata.get('token', _kraw))
                except Exception:
                    self._licenca_token_raw = _extract_api_token(_kraw)
        except Exception:
            pass

    def _validate_license_for_connection(self, connection: dict, on_success=None):
        """
        Inicia (em background) a leitura/validação do arquivo .key contra a
        conexão fornecida. Valida presença de `sql_servidor` e `sql_banco`
        (<=30 chars) e se os campos batem com a conexão selecionada. Ao
        terminar, armazena o payload em `self._licenca_payload` e chama
        `on_success()` — a verificação online (no máximo uma por dia) pode
        levar até 60s na primeira do dia, por isso roda numa QThread
        (`LicencaOnlineWorker`) com um spinner na tela, em vez de travar a UI.
        """
        try:
            self._lbl_license_file.hide()
        except Exception:
            pass

        key_files = self._discover_key_files()
        if not key_files:
            QMessageBox.critical(self, "Arquivo de licença não encontrado", "Arquivo .key não encontrado, o sistema não poderá ser aberto.\nEntre em contato com o suporte para obter uma licença válida.")
            return

        self._license_connection = connection
        self._license_on_success = on_success

        self._progress.setRange(0, 0)  # Indeterminado (spinner)
        self._progress.show()
        self._btn_connect.setEnabled(False)
        self._iniciar_contador_verificacao_licenca()

        self._license_worker = LicencaOnlineWorker(key_files)
        self._license_worker.finished.connect(self._on_connection_license_finished)
        self._license_worker.start()

    def _iniciar_contador_verificacao_licenca(self):
        """Mostra e atualiza a cada segundo o texto "Verificando licença
        online... (Ns)" em `self._lbl_connection_status`, para o usuário
        acompanhar visualmente que o processo está avançando (não travado),
        até o limite de `licenca_online.TIMEOUT_SEGUNDOS`.
        """
        self._license_elapsed_seconds = 0
        self._lbl_connection_status.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 9pt;")
        # Exibe "(0s)" imediatamente, sem esperar o primeiro tick do timer (1s depois)
        self._lbl_connection_status.setText(
            f"⏳ Verificando licença online... ({self._license_elapsed_seconds}s)"
        )

        def _tick():
            self._license_elapsed_seconds += 1
            self._lbl_connection_status.setText(
                f"⏳ Verificando licença online... ({self._license_elapsed_seconds}s)"
            )

        if self._license_elapsed_timer is None:
            self._license_elapsed_timer = QTimer(self)
            self._license_elapsed_timer.timeout.connect(_tick)
        else:
            self._license_elapsed_timer.timeout.disconnect()
            self._license_elapsed_timer.timeout.connect(_tick)
        self._license_elapsed_timer.start(1000)

    def _parar_contador_verificacao_licenca(self):
        if self._license_elapsed_timer is not None:
            self._license_elapsed_timer.stop()

    def _on_connection_license_finished(self, cand_path: str, payload_dict, erro):
        """Callback do `LicencaOnlineWorker` disparado por `_validate_license_for_connection`."""
        self._parar_contador_verificacao_licenca()
        self._progress.hide()
        self._progress.setRange(0, 100)
        # O botão "Conectar" só é reabilitado se a licença for válida — ver
        # o resto deste método; em caso de falha, o usuário troca de conexão
        # (o que já reabilita o botão via `_on_connection_changed`) ou
        # resolve a licença antes de tentar de novo.

        if payload_dict is None:
            self._lbl_connection_status.setText("❌ Falha ao validar licença.")
            self._lbl_connection_status.setStyleSheet(f"color: {_C.ERROR}; font-size: 9pt;")
            QMessageBox.critical(self, "Erro de licença", f"Não foi possível validar nenhum arquivo de licença.\n{erro or ''}")
            return

        self._render_licenca_labels(cand_path, payload_dict)

        if self._licenca_expirada_bloqueia(payload_dict):
            return

        # Validação de sql_servidor/sql_banco (apenas para licenças que contêm esses campos)
        connection = self._license_connection or {}
        sql_servidor = (payload_dict.get('sql_servidor') or '').strip()
        sql_banco = (payload_dict.get('sql_banco') or '').strip()
        if sql_servidor and sql_banco:
            if len(sql_servidor) > 30 or len(sql_banco) > 30:
                QMessageBox.critical(self, "Campo inválido", "Arquivo de licença inválido: 'sql_servidor' ou 'sql_banco' excede 30 caracteres.")
                return
            conn_srv = (connection.get('server') or '').strip()
            conn_db = (connection.get('database') or '').strip()
            if conn_srv.lower() != sql_servidor.lower() or conn_db.lower() != sql_banco.lower():
                QMessageBox.critical(
                    self,
                    "Servidor ou banco inválidos",
                    f"A licença autoriza:\n"
                    f"  Servidor: {sql_servidor}\n"
                    f"  Banco:    {sql_banco}\n\n"
                    f"Conexão selecionada:\n"
                    f"  Servidor: {conn_srv}\n"
                    f"  Banco:    {conn_db}"
                )
                return

        self._armazenar_licenca_payload(cand_path, payload_dict)

        # Licença válida: só agora o botão "Conectar" é liberado de novo.
        self._btn_connect.setEnabled(True)
        self._lbl_connection_status.setText("✅ Licença válida.")
        self._lbl_connection_status.setStyleSheet(f"color: {_C.SUCCESS}; font-size: 9pt;")

        on_success = self._license_on_success
        self._license_on_success = None
        if on_success:
            on_success()

    def _load_license_on_start(self):
        """Carrega e verifica um arquivo .key (em background) imediatamente
        após abrir a tela de login.

        Esta rotina apenas verifica validade e armazena o payload em
        `self._licenca_payload`. A correspondência com a conexão selecionada será
        feita quando o usuário tentar conectar (via `_validate_license_for_connection`).
        """
        key_files = self._discover_key_files()
        if not key_files:
            QMessageBox.critical(self, "Arquivo de licença não encontrado", "Arquivo .key não encontrado. O sistema não poderá ser aberto sem uma licença válida.")
            return

        self._startup_license_worker = LicencaOnlineWorker(key_files)
        self._startup_license_worker.finished.connect(self._on_startup_license_finished)
        self._startup_license_worker.start()

    def _on_startup_license_finished(self, cand_path: str, payload_dict, erro):
        """Callback do `LicencaOnlineWorker` disparado por `_load_license_on_start`."""
        if payload_dict is None:
            QMessageBox.critical(self, "Erro de licença", f"Não foi possível validar o arquivo de licença.\n{erro or ''}")
            return

        self._render_licenca_labels(cand_path, payload_dict)

        if self._licenca_expirada_bloqueia(payload_dict):
            return

        self._armazenar_licenca_payload(cand_path, payload_dict)

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
        self._lbl_connection_status.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 9pt;")
        
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
            self._lbl_connection_status.setStyleSheet(f"color: {_C.SUCCESS}; font-size: 9pt;")

            self._empresas = empresas
            # Ao conectar com sucesso, valida o arquivo .key (online, em
            # background) contra a conexão; ao terminar, avança para a
            # seleção de empresa (ou mostra o erro apropriado).
            self._validate_license_for_connection(self._selected_connection, on_success=self._advance_after_license_ok)
        else:
            self._lbl_connection_status.setText("❌ Falha ao conectar. Verifique os dados da conexão.")
            self._lbl_connection_status.setStyleSheet(f"color: {_C.ERROR}; font-size: 9pt;")
            QMessageBox.warning(
                self,
                "Erro de Conexão",
                message
            )

    def _advance_after_license_ok(self):
        """Continuação de `_on_connection_finished` após a licença ser
        validada com sucesso (via `_validate_license_for_connection`) para a
        conexão recém-testada."""
        if self._empresas:
            QTimer.singleShot(500, self._show_empresa_step)
        else:
            QMessageBox.warning(self, "Aviso", "Nenhuma empresa encontrada no banco de dados.")

    def _show_empresa_step(self):
        """Mostra etapa de seleção de empresa."""
        # Atualiza info da conexão
        conn = self._selected_connection
        self._lbl_selected_connection.setText(
            f"🔌 Servidor: {conn.get('server')}  ·  Tipo: {conn.get('type')}\n"
            f"🗂️ Base de dados: {conn.get('database')}"
        )
        
        # Carrega último login para pré-selecionar empresa
        last_login = login_module.load_last_login()
        default_index = -1

        # Popula combo de empresas
        self._cmb_empresa.clear()

        for idx, emp in enumerate(self._empresas):
            codigo = str(emp.get("codigo", ""))
            nome = emp.get("nome", "")
            label = f"{codigo} — {nome}"
            self._cmb_empresa.addItem(label, emp)

            # Verifica se é a última empresa selecionada
            if last_login:
                if (conn.get("server", "").lower() == last_login.get("srv", "").lower() and
                    conn.get("database", "").lower() == last_login.get("db", "").lower() and
                    codigo == str(last_login.get("codempresa", ""))):
                    default_index = idx

        qtd = len(self._empresas)
        self._lbl_empresa_count.setText(
            f"{qtd} empresa{'s' if qtd != 1 else ''} disponíve{'is' if qtd != 1 else 'l'} nesta base"
        )

        # Muda para step de empresa
        self._stack.setCurrentIndex(self.STEP_EMPRESA)

        # Seleciona última empresa usada (ou mantém a primeira, já selecionada
        # automaticamente pelo QComboBox ao popular)
        if default_index >= 0:
            self._cmb_empresa.setCurrentIndex(default_index)
        self._on_empresa_selected()

    def _on_empresa_selected(self):
        """Quando empresa é selecionada."""
        self._btn_next_empresa.setEnabled(self._cmb_empresa.currentData() is not None)
    
    def _on_back_to_connection(self):
        """Volta para seleção de conexão."""
        self._stack.setCurrentIndex(self.STEP_CONNECTION)
        self._selected_empresa = None
    
    def _on_next_to_auth(self):
        """Avança para etapa de autenticação."""
        empresa = self._cmb_empresa.currentData()

        if not empresa:
            return

        self._selected_empresa = empresa

        if not self._licenca_payload:
            # Por algum motivo o payload não foi carregado ao conectar —
            # tenta agora (em background, mesma checagem de sql_servidor/
            # sql_banco), e só continua no callback de sucesso.
            self._validate_license_for_connection(
                self._selected_connection,
                on_success=lambda: self._continuar_next_to_auth(empresa)
            )
            return

        self._continuar_next_to_auth(empresa)

    def _continuar_next_to_auth(self, empresa: dict):
        """Continuação de `_on_next_to_auth` — chamada direto quando a
        licença já está carregada, ou pelo callback assíncrono quando
        precisou ser (re)validada agora."""
        try:
            cnpj_raw = (empresa.get('cnpj') or "").strip()
            cnpj_clean = re.sub(r"\D", "", cnpj_raw)
            if not cnpj_clean:
                QMessageBox.critical(self, "Empresa sem CNPJ", "A empresa selecionada não possui CNPJ cadastrado. Não é possível validar autorização.")
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
        self._lbl_auth_status.setStyleSheet(f"color: {_C.TEXT_MUTED}; font-size: 9pt;")
        
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
            self._lbl_auth_status.setStyleSheet(f"color: {_C.SUCCESS}; font-size: 9pt;")
            
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
            self._lbl_auth_status.setStyleSheet(f"color: {_C.ERROR}; font-size: 9pt;")
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
            "licenca": self._licenca_payload or {},
            "licenca_token": self._licenca_token_raw
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
