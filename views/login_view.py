"""
login_view.py
=============
Tela de login do sistema.
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QGroupBox, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QFont

from views.base_view import BaseView
from controllers.login_controller import LoginController
from utils.config import AppConfig
from models.connection import Connection
from models.user import User


class LoginView(BaseView):
    """
    Tela de login e seleção de base de dados.
    
    Signals:
        login_successful: Emitido quando login é bem sucedido
    """
    
    login_successful = Signal(object)  # User
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._controller = LoginController()
        self._connections = []
        self._companies = []
        
        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()
    
    def _setup_ui(self):
        """Configura interface do usuário."""
        self.setWindowTitle("CSCollectManager - Login")
        self.setFixedSize(450, 550)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)
        
        # Logo removido (não exibido)
        main_layout.addSpacing(8)
        
        # Título
        title_label = QLabel("CSCollectManager")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Sistema de Exportação para Coletores")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #666;")
        main_layout.addWidget(subtitle_label)
        
        # Separador
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)
        
        # Grupo de Conexão
        connection_group = QGroupBox("Conexão")
        connection_layout = QFormLayout(connection_group)
        connection_layout.setSpacing(10)
        
        self.cmb_connection = QComboBox()
        self.cmb_connection.setMinimumHeight(30)
        connection_layout.addRow("Base de Dados:", self.cmb_connection)
        
        self.cmb_company = QComboBox()
        self.cmb_company.setMinimumHeight(30)
        connection_layout.addRow("Empresa:", self.cmb_company)
        
        main_layout.addWidget(connection_group)
        
        # Grupo de Login
        login_group = QGroupBox("Credenciais")
        login_layout = QFormLayout(login_group)
        login_layout.setSpacing(10)
        
        self.txt_username = QLineEdit()
        self.txt_username.setMinimumHeight(30)
        self.txt_username.setPlaceholderText("Digite seu usuário")
        login_layout.addRow("Usuário:", self.txt_username)
        
        self.txt_password = QLineEdit()
        self.txt_password.setMinimumHeight(30)
        self.txt_password.setPlaceholderText("Digite sua senha")
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        login_layout.addRow("Senha:", self.txt_password)
        
        main_layout.addWidget(login_group)
        
        # Botões
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.btn_test = QPushButton("Testar Conexão")
        self.btn_test.setMinimumHeight(35)
        buttons_layout.addWidget(self.btn_test)
        
        self.btn_login = QPushButton("Entrar")
        self.btn_login.setMinimumHeight(35)
        self.btn_login.setDefault(True)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        buttons_layout.addWidget(self.btn_login)
        
        main_layout.addLayout(buttons_layout)
        
        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #666; font-size: 11px;")
        main_layout.addWidget(self.lbl_status)
        
        # Spacer
        main_layout.addStretch()
        
        # Centraliza na tela
        self.center_on_screen()
    
    def _connect_signals(self):
        """Conecta sinais aos slots."""
        # Controller signals
        self._controller.connections_loaded.connect(self._on_connections_loaded)
        self._controller.companies_loaded.connect(self._on_companies_loaded)
        self._controller.connection_tested.connect(self._on_connection_tested)
        self._controller.login_success.connect(self._on_login_success)
        self._controller.login_failed.connect(self._on_login_failed)
        self._controller.error_occurred.connect(self._on_error)
        self._controller.loading_started.connect(
            lambda msg: self._set_status(msg, loading=True)
        )
        self._controller.loading_finished.connect(
            lambda: self._set_status("")
        )
        
        # UI signals
        self.cmb_connection.currentIndexChanged.connect(self._on_connection_changed)
        self.btn_test.clicked.connect(self._on_test_clicked)
        self.btn_login.clicked.connect(self._on_login_clicked)
        self.txt_password.returnPressed.connect(self._on_login_clicked)
    
    def _load_initial_data(self):
        """Carrega dados iniciais."""
        self._controller.load_connections()
        
        # Carrega último login
        last_login = self._controller.get_last_login_info()
        if last_login:
            self.txt_username.setText(last_login.get("user", ""))
    
    def _on_connections_loaded(self, connections: list):
        """Callback quando conexões são carregadas."""
        self._connections = connections
        self.cmb_connection.clear()
        
        for conn in connections:
            self.cmb_connection.addItem(conn.display_name, conn)
        
        # Seleciona conexão padrão
        default_conn = self._controller.get_default_connection()
        if default_conn:
            for i in range(self.cmb_connection.count()):
                conn = self.cmb_connection.itemData(i)
                if (conn.server == default_conn.get("srv") and 
                    conn.database == default_conn.get("db")):
                    self.cmb_connection.setCurrentIndex(i)
                    break
    
    def _on_connection_changed(self, index: int):
        """Callback quando conexão é alterada."""
        if index >= 0:
            connection = self.cmb_connection.itemData(index)
            if connection:
                self._controller.select_connection(connection)
    
    def _on_companies_loaded(self, companies: list):
        """Callback quando empresas são carregadas."""
        self._companies = companies
        self.cmb_company.clear()
        
        for cod, nome in companies:
            self.cmb_company.addItem(f"{cod} - {nome}", (cod, nome))
        
        # Seleciona empresa padrão
        default_conn = self._controller.get_default_connection()
        if default_conn:
            cod_pref = default_conn.get("codempresa", "")
            for i in range(self.cmb_company.count()):
                data = self.cmb_company.itemData(i)
                if data and str(data[0]) == str(cod_pref):
                    self.cmb_company.setCurrentIndex(i)
                    break
    
    def _on_connection_tested(self, success: bool, message: str):
        """Callback do teste de conexão."""
        if success:
            self.show_success(message, "Teste de Conexão")
        else:
            self.show_error(message, "Teste de Conexão")
    
    def _on_test_clicked(self):
        """Handler do botão testar."""
        index = self.cmb_connection.currentIndex()
        if index >= 0:
            connection = self.cmb_connection.itemData(index)
            if connection:
                self._controller.test_connection(connection)
    
    def _on_login_clicked(self):
        """Handler do botão login."""
        username = self.txt_username.text().strip()
        password = self.txt_password.text()
        
        if not username:
            self.show_warning("Informe o usuário.", "Atenção")
            self.txt_username.setFocus()
            return
        
        if not password:
            self.show_warning("Informe a senha.", "Atenção")
            self.txt_password.setFocus()
            return
        
        # Obtém empresa selecionada
        company_data = self.cmb_company.currentData()
        company_code = str(company_data[0]) if company_data else ""
        company_name = str(company_data[1]) if company_data else ""
        
        self._controller.authenticate(
            username=username,
            password=password,
            company_code=company_code,
            company_name=company_name
        )
    
    def _on_login_success(self, user: User):
        """Callback de login bem sucedido."""
        self.login_successful.emit(user)
        self._open_main_window(user)
    
    def _on_login_failed(self, message: str):
        """Callback de falha no login."""
        self.show_error(message, "Falha no Login")
        self.txt_password.clear()
        self.txt_password.setFocus()
    
    def _on_error(self, message: str):
        """Callback de erro."""
        self.show_error(message)
    
    def _set_status(self, message: str, loading: bool = False):
        """Atualiza status e estado de loading."""
        self.lbl_status.setText(message)
        self.set_loading(loading)
    
    def _open_main_window(self, user: User):
        """Abre janela principal e fecha login."""
        from views.main_view import MainView
        
        self.main_window = MainView(user)
        self.main_window.show()
        self.close()
