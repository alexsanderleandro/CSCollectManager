"""
main_window_erp.py
==================
Janela principal profissional estilo ERP para CSCollectManager.

Layout completo com:
- Menu bar com todos os módulos
- Toolbar com ícones
- Painel lateral de navegação
- Área central com filtros e tabela
- Status bar avançada
- Atalhos de teclado
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QFrame, QLabel, QPushButton, QToolBar, QDockWidget,
    QStackedWidget, QListWidget, QListWidgetItem, QSizePolicy,
    QMessageBox, QFileDialog, QApplication, QSpacerItem, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QAction, QIcon, QCloseEvent, QKeySequence, QCursor, QPixmap

from utils.constants import APP_INFO, Icons, Messages, Shortcuts, UIConfig
from utils.logger import get_logger
from utils.workers import DataLoaderWorker, ExportWorker
from widgets.status_bar import AppStatusBar
from widgets.filter_panel import FilterPanel
from widgets.lazy_product_table import LazyProductTable
from widgets.progress_dialog import ProgressDialog
from services.product_service import ProductService, ProductFilter
from services.export_service import ExportService, EmpresaInfo, UsuarioInfo

# Caminho do logotipo
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")

logger = get_logger(__name__)


class SidebarButton(QPushButton):
    """Botão estilizado para sidebar."""
    
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(45)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9d9d9d;
                text-align: left;
                padding: 12px 16px;
                border: none;
                border-radius: 0;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #2d2d30;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #094771;
                color: #ffffff;
                border-left: 3px solid #0078d4;
            }
        """)


class ModuleHeader(QFrame):
    """Cabeçalho de módulo com título e ações."""
    
    def __init__(self, icon: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self._setup_ui(icon, title, subtitle)
    
    def _setup_ui(self, icon: str, title: str, subtitle: str):
        self.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-bottom: 1px solid #3e3e42;
            }
        """)
        self.setMinimumHeight(80)
        self.setMaximumHeight(80)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        
        # Ícone do módulo
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 28))
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)
        
        # Título e subtítulo
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff; background: transparent;")
        text_layout.addWidget(title_label)
        
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setStyleSheet("color: #9d9d9d; font-size: 10pt; background: transparent;")
            text_layout.addWidget(subtitle_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        # Container para botões de ação
        self._action_layout = QHBoxLayout()
        self._action_layout.setSpacing(8)
        layout.addLayout(self._action_layout)
    
    def add_action_button(self, text: str, icon: str = "", primary: bool = False) -> QPushButton:
        """Adiciona botão de ação ao header."""
        btn = QPushButton(f"{icon}  {text}" if icon else text)
        btn.setMinimumHeight(36)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        if primary:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1e8ad4;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
            """)
        else:
            btn.setStyleSheet("""
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
            """)
        
        self._action_layout.addWidget(btn)
        return btn


class MainWindowERP(QMainWindow):
    """
    Janela principal profissional estilo ERP.
    
    Signals:
        logout_requested: Usuário solicita logout
        export_requested: Exportação solicitada
    """
    
    logout_requested = Signal()
    export_requested = Signal(dict)
    
    # Módulos do sistema
    MODULE_PRODUCTS = "products"
    MODULE_EXPORT = "export"
    MODULE_HISTORY = "history"
    MODULE_SETTINGS = "settings"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Estado
        self._current_module = self.MODULE_PRODUCTS
        self._empresa_info = {}
        self._usuario_info = {}
        self._local_estoque: str = "loja"  # Valor selecionado no filtro Loja/Depósito
        self._export_vendedor: Dict[str, Any] = {}  # Vendedor selecionado na tela de exportação
        self._connection_info = {}
        
        # Serviços e Workers
        self._product_service = ProductService()
        self._load_worker: Optional[DataLoaderWorker] = None
        self._export_worker: Optional[ExportWorker] = None
        
        # Códigos selecionados para exportação (preenchidos em _on_export_selected)
        self._export_codprodutos: List = []
        
        # Setup
        self._setup_window()
        self._setup_ui()
        self._setup_menus()
        self._setup_shortcuts()
        self._connect_signals()
        
        # Seleciona módulo inicial
        self._switch_module(self.MODULE_PRODUCTS)
        
        logger.info("MainWindow ERP inicializada")
    
    def _setup_window(self):
        """Configura propriedades da janela."""
        self.setWindowTitle(f"{APP_INFO.NAME} - Sistema de Exportação de Carga")
        
        # Define ícone da janela
        if os.path.exists(LOGO_PATH):
            icon = QIcon(LOGO_PATH)
            self.setWindowIcon(icon)
        
        self.setMinimumSize(UIConfig.MIN_WINDOW_WIDTH, UIConfig.MIN_WINDOW_HEIGHT)
        self.resize(UIConfig.DEFAULT_WINDOW_WIDTH, UIConfig.DEFAULT_WINDOW_HEIGHT)
        
        # Maximiza a janela
        self.showMaximized()
    
    def _setup_ui(self):
        """Configura interface principal."""
        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ===== SIDEBAR =====
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # ===== ÁREA DE CONTEÚDO =====
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Stack de módulos
        self._module_stack = QStackedWidget()
        
        # Dicionário de índices das páginas no stack
        self._pages = {}
        
        # Cria páginas dos módulos
        self._create_products_page()
        self._create_export_page()
        self._create_history_page()
        self._create_settings_page()
        
        content_layout.addWidget(self._module_stack)
        
        main_layout.addWidget(content_area, 1)
        
        # ===== STATUS BAR =====
        self._status_bar = AppStatusBar()
        self.setStatusBar(self._status_bar)
    
    def _create_sidebar(self) -> QFrame:
        """Cria barra lateral de navegação."""
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-right: 1px solid #3e3e42;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        

        
        # Botões de navegação
        nav_frame = QFrame()
        nav_frame.setStyleSheet("border: none;")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(8, 16, 8, 8)
        nav_layout.setSpacing(4)
        
        # Label de seção
        section_label = QLabel("  NAVEGAÇÃO")
        section_label.setStyleSheet("color: #666666; font-size: 9pt; font-weight: bold; padding: 8px 0;")
        nav_layout.addWidget(section_label)
        
        # Botões
        self._sidebar_buttons = {}
        
        modules = [
            (self.MODULE_PRODUCTS, "📦", "Produtos"),
            (self.MODULE_EXPORT, "📤", "Exportar Carga"),
            (self.MODULE_HISTORY, "📋", "Histórico"),
        ]
        
        for module_id, icon, text in modules:
            btn = SidebarButton(icon, text)
            btn.clicked.connect(lambda checked, m=module_id: self._switch_module(m))
            nav_layout.addWidget(btn)
            self._sidebar_buttons[module_id] = btn
        
        nav_layout.addStretch()
        
        layout.addWidget(nav_frame)
        
        # Info do usuário na parte inferior
        user_frame = QFrame()
        user_frame.setMinimumHeight(70)
        user_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-top: 1px solid #3e3e42;
                border-right: none;
            }
        """)
        user_layout = QHBoxLayout(user_frame)
        user_layout.setContentsMargins(12, 8, 12, 8)
        
        user_icon = QLabel("👤")
        user_icon.setFont(QFont("Segoe UI", 20))
        user_icon.setStyleSheet("background: transparent;")
        user_layout.addWidget(user_icon)
        
        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        
        self._lbl_user_name = QLabel("Usuário")
        self._lbl_user_name.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 10pt; background: transparent;")
        user_info.addWidget(self._lbl_user_name)
        
        self._lbl_company = QLabel("Empresa")
        self._lbl_company.setStyleSheet("color: #9d9d9d; font-size: 9pt; background: transparent;")
        user_info.addWidget(self._lbl_company)
        
        user_layout.addLayout(user_info)
        user_layout.addStretch()
        
        # Botão de logout
        btn_logout = QPushButton("🚪")
        btn_logout.setToolTip("Sair")
        btn_logout.setFixedSize(32, 32)
        btn_logout.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_logout.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                font-size: 14pt;
            }
            QPushButton:hover {
                background-color: #3e3e42;
            }
        """)
        btn_logout.clicked.connect(self._on_logout)
        user_layout.addWidget(btn_logout)
        
        layout.addWidget(user_frame)
        
        return sidebar
    
    def _create_products_page(self):
        """Cria página de produtos."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = ModuleHeader("📦", "Produtos", "Consulta e seleção de produtos para exportação")
        layout.addWidget(header)
        
        # Área de conteúdo com splitter
        content = QSplitter(Qt.Orientation.Horizontal)
        content.setHandleWidth(2)
        content.setStyleSheet("""
            QSplitter {
                background-color: #1e1e1e;
            }
            QSplitter::handle {
                background-color: #3e3e42;
            }
            QSplitter::handle:hover {
                background-color: #0078d4;
            }
        """)
        
        # Painel de filtros
        filter_container = QFrame()
        filter_container.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-right: 1px solid #3e3e42;
            }
        """)
        filter_layout = QVBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        filter_header = QLabel("  🔍 FILTROS")
        filter_header.setMinimumHeight(40)
        filter_header.setStyleSheet("""
            background-color: #2d2d30;
            color: #9d9d9d;
            font-weight: bold;
            font-size: 10pt;
            padding-left: 8px;
            border-bottom: 1px solid #3e3e42;
        """)
        filter_layout.addWidget(filter_header)
        
        self._filter_panel = FilterPanel()
        filter_layout.addWidget(self._filter_panel)
        
        filter_container.setMinimumWidth(280)
        filter_container.setMaximumWidth(400)
        content.addWidget(filter_container)
        
        # Tabela de produtos
        self._product_table = LazyProductTable()
        content.addWidget(self._product_table)
        
        content.setSizes([320, 900])
        layout.addWidget(content)
        
        self._module_stack.addWidget(page)
        self._pages[self.MODULE_PRODUCTS] = self._module_stack.count() - 1
    
    def _create_export_page(self):
        """Cria página de exportação."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = ModuleHeader("📤", "Exportar Carga", "Configure e execute a exportação para coletores")
        layout.addWidget(header)

        # Conteúdo
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        from PySide6.QtWidgets import QCheckBox, QLineEdit

        # ===== GRUPO: DIRETÓRIO DE SAÍDA =====
        dir_group = QGroupBox("📁 Diretório de Saída  (obrigatório)")
        dir_group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 2px solid #0078d4;
                border-radius: 8px;
                margin-top: 16px;
                padding: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        dir_layout = QHBoxLayout(dir_group)
        dir_layout.setSpacing(10)

        self._txt_export_dir = QLineEdit()
        self._txt_export_dir.setPlaceholderText("Selecione o diretório onde o arquivo será gerado...")
        self._txt_export_dir.setReadOnly(True)
        self._txt_export_dir.setMinimumHeight(36)
        self._txt_export_dir.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11pt;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        dir_layout.addWidget(self._txt_export_dir, 1)

        btn_browse = QPushButton("📂  Procurar...")
        btn_browse.setMinimumSize(130, 36)
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #0078d4; color: white; }
        """)
        btn_browse.clicked.connect(self._on_browse_export_dir)
        dir_layout.addWidget(btn_browse)

        content_layout.addWidget(dir_group)

        # ===== GRUPO: VENDEDOR (obrigatório) =====
        vendedor_group = QGroupBox("👤 Vendedor  (obrigatório)")
        vendedor_group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 2px solid #0078d4;
                border-radius: 8px;
                margin-top: 16px;
                padding: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        vendedor_layout = QHBoxLayout(vendedor_group)
        vendedor_layout.setSpacing(10)

        self._txt_vendedor = QLineEdit()
        self._txt_vendedor.setPlaceholderText("Pressione Enter ou clique em Buscar para selecionar o vendedor...")
        self._txt_vendedor.setReadOnly(True)
        self._txt_vendedor.setMinimumHeight(36)
        self._txt_vendedor.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11pt;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        self._txt_vendedor.installEventFilter(self)
        vendedor_layout.addWidget(self._txt_vendedor, 1)

        btn_buscar_vendedor = QPushButton("🔍  Buscar")
        btn_buscar_vendedor.setMinimumSize(120, 36)
        btn_buscar_vendedor.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_buscar_vendedor.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 11pt;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #0078d4; color: white; }
        """)
        btn_buscar_vendedor.clicked.connect(self._on_search_vendedor)
        vendedor_layout.addWidget(btn_buscar_vendedor)

        content_layout.addWidget(vendedor_group)

        # ===== GRUPO: OPÇÕES =====
        export_options = QGroupBox("📋 Opções de Exportação")
        export_options.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                margin-top: 16px;
                padding: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        options_layout = QGridLayout(export_options)
        options_layout.setSpacing(16)

        chk_style = "color: #cccccc; font-size: 11pt;"

        self._chk_export_txt = QCheckBox("Exportar arquivo TXT de carga")
        self._chk_export_txt.setChecked(True)
        self._chk_export_txt.setEnabled(False)  # Sempre obrigatório
        self._chk_export_txt.setStyleSheet(chk_style)
        options_layout.addWidget(self._chk_export_txt, 0, 0)

        self._chk_export_photos = QCheckBox("Incluir fotos dos produtos (ZIP)")
        self._chk_export_photos.setStyleSheet(chk_style)
        options_layout.addWidget(self._chk_export_photos, 0, 1)

        content_layout.addWidget(export_options)

        # ===== GRUPO: RESUMO =====
        summary_group = QGroupBox("📊 Resumo da Exportação")
        summary_group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                margin-top: 16px;
                padding: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        summary_layout = QVBoxLayout(summary_group)

        self._lbl_export_summary = QLabel("Selecione produtos na aba \u2018Produtos\u2019 e clique em Exportar Selecionados.")
        self._lbl_export_summary.setStyleSheet("color: #9d9d9d; font-size: 11pt; padding: 16px;")
        summary_layout.addWidget(self._lbl_export_summary)

        content_layout.addWidget(summary_group)

        # ===== BOTÕES DE AÇÃO =====
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumSize(120, 40)
        btn_cancel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #505050; }
        """)
        btn_cancel.clicked.connect(lambda: self._switch_module(self.MODULE_PRODUCTS))
        action_layout.addWidget(btn_cancel)

        self._btn_start_export = QPushButton("📤  Iniciar Exportação")
        self._btn_start_export.setMinimumSize(180, 40)
        self._btn_start_export.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_start_export.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11pt;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #1e8ad4; }
            QPushButton:pressed { background-color: #005a9e; }
            QPushButton:disabled {
                background-color: #3e3e42;
                color: #666666;
            }
        """)
        self._btn_start_export.clicked.connect(self._on_start_export)
        action_layout.addWidget(self._btn_start_export)

        content_layout.addLayout(action_layout)
        content_layout.addStretch()

        layout.addWidget(content)

        self._module_stack.addWidget(page)
        self._pages[self.MODULE_EXPORT] = self._module_stack.count() - 1
    
    def _create_history_page(self):
        """Cria página de histórico."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = ModuleHeader("📋", "Histórico de Exportações", "Visualize exportações anteriores")
        layout.addWidget(header)
        
        # Conteúdo
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        
        # Placeholder
        placeholder = QLabel("📋\n\nHistórico de exportações\n\nEm desenvolvimento...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #666666; font-size: 14pt;")
        content_layout.addWidget(placeholder)
        
        layout.addWidget(content)
        
        self._module_stack.addWidget(page)
        self._pages[self.MODULE_HISTORY] = self._module_stack.count() - 1
    
    def _create_settings_page(self):
        """Cria página de configurações."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = ModuleHeader("⚙️", "Configurações", "Configurações do sistema")
        layout.addWidget(header)
        
        # Conteúdo
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        
        # Placeholder
        placeholder = QLabel("⚙️\n\nConfigurações do sistema\n\nEm desenvolvimento...")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #666666; font-size: 14pt;")
        content_layout.addWidget(placeholder)
        
        layout.addWidget(content)
        
        self._module_stack.addWidget(page)
        self._pages[self.MODULE_SETTINGS] = self._module_stack.count() - 1
    
    def _setup_menus(self):
        """Configura menus."""
        menubar = self.menuBar()
        
        # Menu Arquivo
        menu_file = menubar.addMenu("&Arquivo")
        
        action_new = QAction("Nova Exportação", self)
        action_new.setShortcut(Shortcuts.NEW)
        action_new.triggered.connect(lambda: self._switch_module(self.MODULE_EXPORT))
        menu_file.addAction(action_new)
        
        menu_file.addSeparator()
        
        action_logout = QAction("Trocar Usuário", self)
        action_logout.triggered.connect(self._on_logout)
        menu_file.addAction(action_logout)
        
        action_quit = QAction("Sair", self)
        action_quit.setShortcut(Shortcuts.QUIT)
        action_quit.triggered.connect(self.close)
        menu_file.addAction(action_quit)
        
        # Menu Editar
        menu_edit = menubar.addMenu("&Editar")
        
        action_select_all = QAction("Selecionar Todos", self)
        action_select_all.setShortcut(Shortcuts.SELECT_ALL)
        action_select_all.triggered.connect(self._on_select_all)
        menu_edit.addAction(action_select_all)
        
        action_refresh = QAction("Atualizar", self)
        action_refresh.setShortcut(Shortcuts.REFRESH)
        action_refresh.triggered.connect(self._on_refresh)
        menu_edit.addAction(action_refresh)
        
        # Menu Visualizar
        menu_view = menubar.addMenu("&Visualizar")
        
        action_products = QAction("Produtos", self)
        action_products.triggered.connect(lambda: self._switch_module(self.MODULE_PRODUCTS))
        menu_view.addAction(action_products)
        
        action_history = QAction("Histórico", self)
        action_history.triggered.connect(lambda: self._switch_module(self.MODULE_HISTORY))
        menu_view.addAction(action_history)
        
        # Menu Ajuda
        menu_help = menubar.addMenu("&Ajuda")
        
        action_docs = QAction("Documentação", self)
        action_docs.setShortcut(Shortcuts.HELP)
        action_docs.triggered.connect(self._on_docs)
        menu_help.addAction(action_docs)
        
        menu_help.addSeparator()
        
        action_about = QAction("Sobre", self)
        action_about.triggered.connect(self._on_about)
        menu_help.addAction(action_about)
    
    def _setup_shortcuts(self):
        """Configura atalhos de teclado."""
        pass  # Atalhos já definidos nos menus
    
    def _connect_signals(self):
        """Conecta sinais."""
        # Filter panel
        self._filter_panel.select_clicked.connect(self._on_apply_filters)
        self._filter_panel.clear_clicked.connect(self._on_clear_filters)
        
        # Product table — redireciona exportação do menu de contexto para o mesmo fluxo
        self._product_table.export_requested.connect(lambda _: self._on_export_selected())
        self._product_table.export_photos_requested.connect(self._on_export_photos)
    
    # ==========================================
    # NAVIGATION
    # ==========================================
    
    def _switch_module(self, module_id: str):
        """Alterna entre módulos."""
        if module_id not in self._pages:
            return
        
        self._current_module = module_id
        self._module_stack.setCurrentIndex(self._pages[module_id])
        
        # Atualiza sidebar
        for mid, btn in self._sidebar_buttons.items():
            btn.setChecked(mid == module_id)
        
        logger.debug(f"Módulo alterado para: {module_id}")
    
    # ==========================================
    # PUBLIC API
    # ==========================================
    
    def set_connection_info(self, empresa: Dict, usuario: Dict, connection: Dict):
        """Define informações de conexão."""
        self._empresa_info = empresa
        self._usuario_info = usuario
        self._connection_info = connection
        
        # Atualiza UI
        empresa_nome = empresa.get("nome", "Empresa")
        usuario_nome = usuario.get("nome", "Usuário")
        servidor = connection.get("server", "")
        database = connection.get("database", "")
        cnpj = empresa.get("cnpj", "")
        
        # Status bar
        self._status_bar.set_user(usuario_nome, empresa_nome)
        self._status_bar.set_connected(servidor)
        self._status_bar.set_database_info(database, cnpj)
        
        self.setWindowTitle(f"{APP_INFO.NAME} - {empresa_nome}")
        
        logger.info(f"Conexão configurada: {empresa_nome} / {usuario_nome}")
    
    def load_filter_data(self):
        """
        Carrega dados dos filtros a partir do banco e popula os combos do FilterPanel.

        Deve ser chamado após a conexão ser configurada (pós-login).
        """
        try:
            self._status_bar.show_message("Carregando filtros...")
            filter_data = self._product_service.get_all_filter_data()
            self._filter_panel.load_filter_data(
                grupos=filter_data.get("grupos", []),
                fornecedores=filter_data.get("fornecedores", []),
                fabricantes=filter_data.get("fabricantes", []),
                localizacoes=filter_data.get("localizacoes", []),
                tipos_produto=filter_data.get("tipos_produto", []),
            )
            self._status_bar.show_message("Filtros carregados", 3000)
            logger.info("Dados dos filtros carregados com sucesso")
        except Exception as e:
            self._status_bar.show_message("Erro ao carregar filtros")
            logger.error(f"Erro ao carregar dados dos filtros: {e}")

    def load_products(self, filters: Dict[str, Any] = None):
        """
        Carrega produtos na tabela com filtros aplicados.
        
        Args:
            filters: Dicionário de filtros do FilterPanel
        """
        # Cancela worker anterior se existir
        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.cancel()
            self._load_worker.wait()
        
        # Converte filtros do painel para ProductFilter
        product_filter = self._build_product_filter(filters) if filters else None
        
        # Função de busca para o worker
        def fetch_products(page: int, page_size: int):
            return self._product_service.get_products_paginated(
                filters=product_filter,
                page=page,
                page_size=page_size
            )
        
        # Cria worker
        self._load_worker = DataLoaderWorker(fetch_products, page_size=1000)
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.page_ready.connect(self._on_page_ready)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.error.connect(self._on_load_error)
        
        # Limpa tabela e inicia carregamento
        self._product_table.model.clear()
        self._product_table.model.begin_loading()
        self._status_bar.show_progress("Carregando produtos...", cancelable=True)
        
        logger.info("Iniciando carregamento de produtos")
        self._load_worker.start()
    
    def _build_product_filter(self, filters: Dict[str, Any]) -> ProductFilter:
        """
        Converte filtros do painel para ProductFilter.

        Args:
            filters: Dicionário de filtros retornado por FilterPanel.get_filters()

        Returns:
            ProductFilter configurado com todos os campos
        """
        # Produtos: manter como strings para evitar erro de conversão nvarchar→int no SQL Server.
        # p.codproduto é nvarchar no banco (pode conter valores como 'CF1102');
        # passar inteiros faz o SQL Server tentar converter toda a coluna para int e falhar.
        produtos_raw = filters.get("produtos") or []
        produtos: List[str] = [
            str(cod).strip() for cod in produtos_raw
            if cod is not None and str(cod).strip()
        ]

        # Grupos: preservar o tipo retornado pelo banco (int ou str conforme a coluna).
        # Forçar int(g) derrubava silenciosamente códigos alfanuméricos como 'CF1102'.
        grupos_raw = filters.get("grupos") or []
        grupos = [g for g in grupos_raw if g is not None]

        # Tipos de produto: idem — preservar tipo original do banco.
        tipos_raw = filters.get("tipos_produto") or []
        tipos = [t for t in tipos_raw if t is not None]

        # Fornecedor / Fabricante: listas de int (MultiSelectCombo)
        fornecedores_raw = filters.get("fornecedor") or []
        fornecedor_list: List[int] = []
        for v in fornecedores_raw:
            try:
                fornecedor_list.append(int(v))
            except (ValueError, TypeError):
                pass
        fornecedor = fornecedor_list or None

        fabricantes_raw = filters.get("fabricante") or []
        fabricante_list: List[int] = []
        for v in fabricantes_raw:
            try:
                fabricante_list.append(int(v))
            except (ValueError, TypeError):
                pass
        fabricante = fabricante_list or None

        return ProductFilter(
            produtos=produtos or None,
            grupos=grupos or None,
            fornecedor=fornecedor,
            fabricante=fabricante,
            localizacoes=filters.get("localizacoes") or None,
            tipos_produto=tipos or None,
            # Filtros do painel
            local_estoque=filters.get("local_estoque", "loja"),
            filtro_localizacao=filters.get("filtro_localizacao", "ambos"),
            filtro_estoque=filters.get("filtro_estoque", "todos"),
            filtro_encomenda=filters.get("filtro_encomenda", "ambos"),
            somente_peso_variavel=bool(filters.get("somente_peso_variavel", False)),
            somente_venda=bool(filters.get("somente_venda", False)),
        )
    
    def _on_load_progress(self, current: int, total: int, percentage: float, message: str):
        """Callback de progresso do carregamento."""
        self._status_bar.update_progress(current, total, f"Carregando... {current:,}/{total:,} ({percentage:.0f}%)")
    
    def _on_page_ready(self, page_number: int, data):
        """Callback quando uma página de dados está pronta."""
        if data:
            # data é a lista de produtos (não tupla)
            products = data
            if page_number == 1:
                # Primeira página: define dados iniciais
                self._product_table.model.set_data(products, len(products))
            else:
                # Páginas seguintes: adiciona aos dados existentes
                self._product_table.model.append_data(products)
    
    def _on_load_finished(self, total_records: int):
        """Callback quando carregamento termina."""
        self._product_table.model.end_loading()
        self._status_bar.hide_progress()
        self._status_bar.show_message(f"✅ {total_records:,} produtos carregados", 5000)
        logger.info(f"Carregamento finalizado: {total_records} produtos")
    
    def _on_load_error(self, error: Exception):
        """Callback de erro no carregamento."""
        self._product_table.model.end_loading()
        self._status_bar.hide_progress()
        self._status_bar.show_error(f"Erro ao carregar: {str(error)}")
        logger.error(f"Erro ao carregar produtos: {error}")
        
        QMessageBox.critical(
            self,
            "Erro",
            f"Erro ao carregar produtos:\n\n{str(error)}"
        )
    
    # ==========================================
    # HANDLERS
    # ==========================================
    
    def _on_apply_filters(self):
        """Aplica filtros e carrega produtos."""
        filters = self._filter_panel.get_filters()
        self._local_estoque = filters.get("local_estoque", "loja")
        self._status_bar.show_message("Aplicando filtros...")
        logger.debug(f"Aplicando filtros: {filters}")
        self.load_products(filters)
    
    def _on_clear_filters(self):
        """Limpa filtros."""
        self._product_table.model.clear()
        self._status_bar.show_message("Filtros limpos", 3000)
    
    def _on_refresh(self):
        """Atualiza dados com filtros atuais."""
        filters = self._filter_panel.get_filters()
        self._local_estoque = filters.get("local_estoque", "loja")
        logger.info("Atualizando dados")
        self.load_products(filters)
    
    def _on_select_all(self):
        """Seleciona todos os produtos."""
        self._product_table._select_all()
    
    def _on_export_selected(self):
        """Navega para a página de exportação com os produtos selecionados."""
        codprodutos = self._product_table.get_selected_codprodutos()
        if not codprodutos:
            QMessageBox.warning(self, "Aviso", "Selecione produtos para exportar.")
            return
        
        # Armazena códigos selecionados para uso na exportação
        self._export_codprodutos = codprodutos
        
        self._switch_module(self.MODULE_EXPORT)
        self._lbl_export_summary.setText(
            f"✅ {len(codprodutos):,} produto(s) selecionado(s) para exportação."
        )
    
    def eventFilter(self, obj, event):
        """Captura Enter no campo de vendedor para abrir busca."""
        from PySide6.QtCore import QEvent
        if obj is self._txt_vendedor and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._on_search_vendedor()
                return True
        return super().eventFilter(obj, event)

    def _on_search_vendedor(self):
        """Abre diálogo de busca de vendedores."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
            QListWidget, QListWidgetItem, QDialogButtonBox, QLabel
        )
        from database.connection import get_session
        from sqlalchemy import text as sa_text

        # Busca vendedores no banco
        try:
            with get_session() as session:
                result = session.execute(sa_text(
                    "SELECT CodVendedor, NomeVendedor FROM vendedores "
                    "WHERE TipoCadastro IN (0, 2) ORDER BY NomeVendedor"
                ))
                vendedores = [(row[0], row[1]) for row in result]
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível carregar vendedores:\n{e}")
            return

        if not vendedores:
            QMessageBox.information(self, "Aviso", "Nenhum vendedor encontrado.")
            return

        # Monta diálogo
        dlg = QDialog(self)
        dlg.setWindowTitle("Selecionar Vendedor")
        dlg.setMinimumSize(420, 480)
        dlg.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #cccccc; }
            QLabel  { color: #cccccc; font-size: 10pt; }
            QLineEdit {
                background-color: #252526; color: #cccccc;
                border: 1px solid #3e3e42; border-radius: 4px;
                padding: 6px 10px; font-size: 11pt;
            }
            QLineEdit:focus { border-color: #0078d4; }
            QListWidget {
                background-color: #252526; color: #cccccc;
                border: 1px solid #3e3e42; border-radius: 4px;
                font-size: 11pt;
            }
            QListWidget::item:hover     { background-color: #2d2d2d; }
            QListWidget::item:selected  { background-color: #0078d4; color: white; }
            QPushButton {
                background-color: #3e3e42; color: #cccccc;
                border: none; border-radius: 4px;
                padding: 6px 20px; font-size: 10pt;
            }
            QPushButton:hover  { background-color: #505050; }
            QPushButton[primary="true"] { background-color: #0078d4; color: white; font-weight: bold; }
            QPushButton[primary="true"]:hover { background-color: #1e8ad4; }
        """)

        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(16, 16, 16, 16)
        dlg_layout.setSpacing(10)

        dlg_layout.addWidget(QLabel("Digite para filtrar:"))

        txt_filter = QLineEdit()
        txt_filter.setPlaceholderText("Nome ou código...")
        txt_filter.setClearButtonEnabled(True)
        dlg_layout.addWidget(txt_filter)

        list_widget = QListWidget()
        list_widget.setAlternatingRowColors(True)
        dlg_layout.addWidget(list_widget)

        def _populate(text: str = ""):
            list_widget.clear()
            txt = text.strip().lower()
            for cod, nome in vendedores:
                label = f"{cod} – {nome}"
                if txt and txt not in label.lower():
                    continue
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, {"codigo": cod, "nome": nome})
                list_widget.addItem(item)
            if list_widget.count() > 0:
                list_widget.setCurrentRow(0)

        _populate()
        txt_filter.textChanged.connect(_populate)

        # Duplo clique confirma
        def _accept_item(item):
            dlg.accept()
        list_widget.itemDoubleClicked.connect(_accept_item)

        # Botões
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btn_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Selecionar")
        ok_btn.setProperty("primary", "true")
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        dlg_layout.addWidget(btn_box)

        txt_filter.setFocus()

        if dlg.exec() == QDialog.DialogCode.Accepted:
            current = list_widget.currentItem()
            if current:
                self._export_vendedor = current.data(Qt.ItemDataRole.UserRole)
                nome = self._export_vendedor["nome"]
                cod  = self._export_vendedor["codigo"]
                self._txt_vendedor.setText(f"{cod} – {nome}")

    def _on_browse_export_dir(self):
        """Abre diálogo para selecionar diretório de saída."""
        current = self._txt_export_dir.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Selecionar Diretório de Saída",
            current,
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self._txt_export_dir.setText(directory)

    def _on_start_export(self):
        """Valida e inicia a exportação em worker separado."""
        # 1. Valida diretório
        output_dir = self._txt_export_dir.text().strip()
        if not output_dir:
            QMessageBox.warning(
                self,
                "Diretório não informado",
                "Informe o diretório de saída antes de iniciar a exportação."
            )
            self._txt_export_dir.setFocus()
            return
        
        if not os.path.isdir(output_dir):
            QMessageBox.warning(
                self,
                "Diretório inválido",
                f"O diretório informado não existe:\n{output_dir}"
            )
            return

        # 2. Obtém produtos selecionados como dicts completos
        produtos = self._product_table.get_selected_products_as_dicts()
        if not produtos:
            QMessageBox.warning(
                self,
                "Nenhum produto",
                "Nenhum produto selecionado.\n\nVolte para a aba Produtos, marque os produtos desejados e navegue para Exportar Carga."
            )
            return

        # 3. Valida vendedor
        if not self._export_vendedor:
            QMessageBox.warning(
                self,
                "Vendedor não informado",
                "Selecione o vendedor antes de iniciar a exportação."
            )
            self._txt_vendedor.setFocus()
            return

        # 4. Monta objetos de empresa e usuário
        empresa = EmpresaInfo(
            codempresa=int(self._empresa_info.get("codigo", 1) or 1),
            nomeempresa=self._empresa_info.get("nome", ""),
            local="Depósito" if self._local_estoque == "deposito" else "Loja"
        )
        usuario = UsuarioInfo(
            codusuario=int(self._export_vendedor.get("codigo", 0) or 0),
            nomeusuario=self._export_vendedor.get("nome", "")
        )

        compress = False

        # 4. Função de exportação a ser executada no worker
        service = ExportService(output_dir=output_dir)

        def do_export(progress_callback=None):
            return service.export_carga(
                empresa=empresa,
                usuario=usuario,
                produtos=produtos,
                output_path=output_dir,
                compress=compress,
                progress_callback=progress_callback,
            )

        # 5. Cria worker
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.cancel()
            self._export_worker.wait()

        self._export_worker = ExportWorker(do_export)
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.cancelled.connect(
            lambda: self._status_bar.show_message("Exportação cancelada.", 4000)
        )

        # 6. Desabilita botão e inicia
        self._btn_start_export.setEnabled(False)
        self._btn_start_export.setText("⏳  Exportando...")
        self._status_bar.show_progress(
            f"Exportando {len(produtos):,} produto(s)...", cancelable=False
        )
        logger.info(f"Iniciando exportação: {len(produtos)} produtos → {output_dir}")
        self._export_worker.start()

    def _on_export_progress(self, current: int, total: int, percentage: float, message: str):
        """Atualiza progresso da exportação."""
        self._status_bar.update_progress(current, total, message)

    def _on_export_finished(self, filepath: str):
        """Callback quando exportação termina com sucesso."""
        self._btn_start_export.setEnabled(True)
        self._btn_start_export.setText("📤  Iniciar Exportação")
        self._status_bar.hide_progress()
        self._status_bar.show_message(f"✅ Exportação concluída: {os.path.basename(filepath)}", 8000)
        logger.info(f"Exportação concluída: {filepath}")

        # Diálogo de sucesso com opção de abrir pasta
        msg = QMessageBox(self)
        msg.setWindowTitle("Exportação Concluída")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("✅ Arquivo gerado com sucesso!")
        msg.setInformativeText(f"<b>{os.path.basename(filepath)}</b>")
        msg.setDetailedText(f"Caminho completo:\n{filepath}")
        btn_abrir = msg.addButton("Abrir Pasta", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg.exec()

        if msg.clickedButton() == btn_abrir:
            import subprocess
            subprocess.Popen(f'explorer /select,"{filepath}"')

    def _on_export_error(self, error: Exception):
        """Callback de erro na exportação."""
        self._btn_start_export.setEnabled(True)
        self._btn_start_export.setText("📤  Iniciar Exportação")
        self._status_bar.hide_progress()
        error_msg = str(error)
        self._status_bar.show_error(f"Erro na exportação: {error_msg}")
        logger.error(f"Erro na exportação: {error}", exc_info=True)

        QMessageBox.critical(
            self,
            "Erro na Exportação",
            f"Ocorreu um erro durante a exportação:\n\n{error_msg}"
        )

    def _on_export_photos(self, codprodutos: List[int]):
        """Exportação de fotos — a ser implementada."""
        logger.info(f"Exportação de fotos solicitada: {len(codprodutos)} produtos")
        QMessageBox.information(
            self,
            "Fotos",
            "A exportação de fotos será implementada em versão futura."
        )

    def _on_logout(self):
        """Solicita logout."""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "Deseja trocar de usuário?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()
    
    def _on_docs(self):
        """Abre documentação."""
        import webbrowser
        webbrowser.open(APP_INFO.WEBSITE)
    
    def _on_about(self):
        """Exibe diálogo sobre."""
        from views.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()
    
    def closeEvent(self, event: QCloseEvent):
        """Evento de fechamento."""
        reply = QMessageBox.question(
            self,
            "Confirmar Saída",
            "Deseja realmente sair do sistema?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Aplicação encerrada pelo usuário")
            event.accept()
        else:
            event.ignore()


# ===== TESTE =====
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from app.styles import apply_theme
    
    app = QApplication(sys.argv)
    apply_theme(app, "dark")
    
    window = MainWindowERP()
    window.set_connection_info(
        empresa={"nome": "Empresa Demonstração LTDA", "codigo": 1},
        usuario={"nome": "Administrador", "codigo": "001"},
        connection={"server": "SERVIDOR\\SQLEXPRESS", "database": "BANCO"}
    )
    window.show()
    
    sys.exit(app.exec())
