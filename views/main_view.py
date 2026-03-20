"""
main_view.py
============
Janela principal do sistema.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QToolBar, QStatusBar, QLabel,
    QFrame, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction, QFont

from views.base_view import BaseView
from views.inventory_view import InventoryView
from controllers.main_controller import MainController
from models.user import User
from utils.config import AppConfig


class MainView(QMainWindow):
    """
    Janela principal do sistema CSCollectManager.
    
    Estrutura:
    - Menu/Toolbar superior
    - Painel lateral de navegação
    - Área central com conteúdo (stacked widget)
    - Barra de status inferior
    """
    
    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self._user = user
        self._controller = MainController(user)
        
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        
        # Navega para módulo inicial
        self._navigate_to("inventory")
    
    def _setup_ui(self):
        """Configura interface do usuário."""
        #self.setWindowTitle(f"CSCollectManager - {self._user.company_name}")
        #self.setMinimumSize(1024, 768)
        
        # Ícone da janela
        #icon_path = AppConfig.get_asset_path("logo.png")
        #self.setWindowIcon(QIcon(icon_path))
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Painel lateral de navegação
        self._setup_sidebar(main_layout)
        
        # Área de conteúdo principal
        self._setup_content_area(main_layout)
    
    def _setup_sidebar(self, parent_layout: QHBoxLayout):
        """Configura painel lateral de navegação."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame#sidebar {
                background-color: #2d2d30;
                border-right: 1px solid #3e3e42;
            }
        """)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        sidebar_layout.setSpacing(5)
        
        # Título do menu
        menu_title = QLabel("Menu")
        menu_title.setStyleSheet("color: #888; font-size: 11px; font-weight: bold;")
        sidebar_layout.addWidget(menu_title)
        
        # Botões de navegação
        self.btn_inventory = self._create_nav_button("Inventários", "inventory")
        self.btn_export = self._create_nav_button("Exportação", "export")
        self.btn_history = self._create_nav_button("Histórico", "history")
        
        sidebar_layout.addWidget(self.btn_inventory)
        sidebar_layout.addWidget(self.btn_export)
        sidebar_layout.addWidget(self.btn_history)
        
        sidebar_layout.addStretch()
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #3e3e42;")
        sidebar_layout.addWidget(sep)
        
        # Configurações
        self.btn_settings = self._create_nav_button("Configurações", "settings")
        sidebar_layout.addWidget(self.btn_settings)
        
        parent_layout.addWidget(sidebar)
    
    def _create_nav_button(self, text: str, module: str) -> QPushButton:
        """Cria botão de navegação do sidebar."""
        btn = QPushButton(text)
        btn.setMinimumHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 5px;
                text-align: left;
                padding-left: 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3e3e42;
            }
            QPushButton:pressed, QPushButton:checked {
                background-color: #0078d4;
                color: white;
            }
        """)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._navigate_to(module))
        return btn
    
    def _setup_content_area(self, parent_layout: QHBoxLayout):
        """Configura área de conteúdo principal."""
        content_frame = QFrame()
        content_frame.setObjectName("content")
        content_frame.setStyleSheet("""
            QFrame#content {
                background-color: #1e1e1e;
            }
        """)
        
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget para alternar entre views
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        
        # Adiciona views
        self.inventory_view = InventoryView(self._user)
        self.stack.addWidget(self.inventory_view)
        
        # Placeholder para outras views
        self.export_view = self._create_placeholder_view("Exportação")
        self.stack.addWidget(self.export_view)
        
        self.history_view = self._create_placeholder_view("Histórico de Exportações")
        self.stack.addWidget(self.history_view)
        
        self.settings_view = self._create_placeholder_view("Configurações")
        self.stack.addWidget(self.settings_view)
        
        parent_layout.addWidget(content_frame)
    
    def _create_placeholder_view(self, title: str) -> QWidget:
        """Cria view placeholder."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888; font-size: 24px;")
        layout.addWidget(label)
        
        coming_soon = QLabel("Em desenvolvimento...")
        coming_soon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coming_soon.setStyleSheet("color: #555; font-size: 14px;")
        layout.addWidget(coming_soon)
        
        return widget
    
    def _setup_toolbar(self):
        """Configura barra de ferramentas."""
        toolbar = QToolBar("Barra de Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d30;
                border-bottom: 1px solid #3e3e42;
                padding: 5px;
                spacing: 5px;
            }
        """)
        self.addToolBar(toolbar)
        
        # Informações do usuário
        user_info = QLabel(f"  {self._user.display_name} | {self._user.company_name}")
        user_info.setStyleSheet("color: #cccccc; font-size: 12px;")
        toolbar.addWidget(user_info)
        
        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().Policy.Expanding,
            spacer.sizePolicy().Policy.Preferred
        )
        toolbar.addWidget(spacer)
        
        # Ação de logout
        logout_action = QAction("Sair", self)
        logout_action.triggered.connect(self._on_logout)
        toolbar.addAction(logout_action)
    
    def _setup_statusbar(self):
        """Configura barra de status."""
        self.statusbar = QStatusBar()
        self.statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
            }
        """)
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Pronto")
    
    def _connect_signals(self):
        """Conecta sinais."""
        self._controller.module_changed.connect(self._on_module_changed)
        self._controller.status_changed.connect(self.statusbar.showMessage)
        self._controller.user_logged_out.connect(self._on_logged_out)
    
    def _navigate_to(self, module: str):
        """Navega para um módulo."""
        # Atualiza botões
        self.btn_inventory.setChecked(module == "inventory")
        self.btn_export.setChecked(module == "export")
        self.btn_history.setChecked(module == "history")
        self.btn_settings.setChecked(module == "settings")
        
        # Alterna view
        index_map = {
            "inventory": 0,
            "export": 1,
            "history": 2,
            "settings": 3
        }
        
        if module in index_map:
            self.stack.setCurrentIndex(index_map[module])
            self._controller.navigate_to(module)
    
    def _on_module_changed(self, module: str):
        """Callback de mudança de módulo."""
        self.statusbar.showMessage(f"Módulo: {module.title()}")
    
    def _on_logout(self):
        """Handler de logout."""
        reply = QMessageBox.question(
            self,
            "Logout",
            "Deseja realmente sair do sistema?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._controller.logout()
    
    def _on_logged_out(self):
        """Callback de logout."""
        from views.login_view import LoginView
        
        self.login_view = LoginView()
        self.login_view.show()
        self.close()
    
    def closeEvent(self, event):
        """Evento de fechamento da janela."""
        reply = QMessageBox.question(
            self,
            "Sair",
            "Deseja realmente fechar o sistema?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
