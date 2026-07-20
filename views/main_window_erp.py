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
from datetime import datetime, timezone, timedelta
import pytz

def _utc_to_local(dt_str: str) -> str:
    """Converte string de data/hora UTC para horário local (UTC-3 / Brasília)."""
    if not dt_str:
        return dt_str
    try:
        dt_str_clean = dt_str[:19]  # remove microssegundos
        dt = datetime.fromisoformat(dt_str_clean)
        # Se vier sem tzinfo, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_local = dt + timedelta(hours=-3)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str[:19]

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QFrame, QLabel, QPushButton, QToolBar, QDockWidget,
    QStackedWidget, QListWidget, QListWidgetItem, QSizePolicy,
    QMessageBox, QFileDialog, QApplication, QSpacerItem, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QAction, QIcon, QCloseEvent, QKeySequence, QShortcut, QCursor, QPixmap

from utils.constants import APP_INFO, Icons, Messages, Shortcuts, UIConfig
from utils.logger import get_logger
from utils.workers import DataLoaderWorker, ExportWorker
from widgets.status_bar import AppStatusBar
from widgets.filter_panel import FilterPanel
from widgets.lazy_product_table import LazyProductTable
from widgets.progress_dialog import ProgressDialog
from services.product_service import ProductService, ProductFilter
from services.export_service import ExportService, EmpresaInfo, UsuarioInfo
from services.db_export_service import DbExportService

# Caminho do logotipo
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")

logger = get_logger(__name__)


class SidebarButton(QPushButton):
    """Botão estilizado para sidebar."""
    
    def __init__(self, icon: str, text: str, parent=None):
        """
        Inicializa o botão da barra lateral.

        Args:
            icon: Emoji ou carácter unicode usado como ícone.
            text: Texto exibido ao lado do ícone.
            parent: Widget pai (opcional).
        """
        super().__init__(parent)
        self.setText(f"  {icon}  {text}")
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(44)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9d9d9d;
                text-align: left;
                padding: 10px 12px;
                border: none;
                border-radius: 0;
                font-size: 10.5pt;
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
        """
        Inicializa o cabeçalho do módulo.

        Args:
            icon: Emoji ou carácter unicode representando o módulo.
            title: Título principal exibido em negrito.
            subtitle: Subtexto descritivo abaixo do título (opcional).
            parent: Widget pai (opcional).
        """
        super().__init__(parent)
        self._setup_ui(icon, title, subtitle)
    
    def _setup_ui(self, icon: str, title: str, subtitle: str):
        """
        Monta o layout visual do cabeçalho.

        Args:
            icon: Ícone do módulo.
            title: Título principal.
            subtitle: Subtexto descritivo.
        """
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
        from PySide6.QtWidgets import QSizePolicy
        btn = QPushButton(f"{icon}  {text}" if icon else text)
        btn.setMinimumHeight(36)
        btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
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
    MODULE_DOWNLOAD_CONTAGENS = "download_contagens"
    MODULE_SETTINGS = "settings"
    
    def __init__(self, parent=None):
        """
        Inicializa a janela principal ERP.

        Configura estado interno, serviços, workers e monta toda a
        interface gráfica (sidebar, menus, filtros, tabela de produtos
        e barra de status).

        Args:
            parent: Widget pai (opcional).
        """
        super().__init__(parent)
        
        # Estado
        self._current_module = self.MODULE_PRODUCTS
        self._empresa_info = {}
        self._usuario_info = {}
        self._local_estoque: str = "loja"  # Valor selecionado no filtro Loja/Depósito
        self._export_vendedor: Dict[str, Any] = {}  # Vendedor selecionado na tela de exportação
        self._connection_info = {}
        self._last_db_export_path: str = ""  # Caminho do último .db gerado
        self._licenca_payload: Dict = {}  # Payload do arquivo .key (dispositivos liberados)
        
        # Serviços e Workers
        self._product_service = ProductService()
        self._load_worker: Optional[DataLoaderWorker] = None
        self._export_worker: Optional[ExportWorker] = None
        
        # Códigos selecionados para exportação (preenchidos em _on_export_selected)
        self._export_codprodutos: List = []
        self._last_export_filters: Dict = {}  # Filtros ativos na última exportação
        
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
        self._create_download_contagens_page()
        
        content_layout.addWidget(self._module_stack)
        
        main_layout.addWidget(content_area, 1)
        
        # ===== STATUS BAR =====
        self._status_bar = AppStatusBar()
        self.setStatusBar(self._status_bar)
    
    def _create_sidebar(self) -> QFrame:
        """Cria barra lateral de navegação."""
        sidebar = QFrame()
        sidebar.setFixedWidth(245)
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
            (self.MODULE_PRODUCTS,           "📦", "Produtos           F1"),
            (self.MODULE_EXPORT,              "📤", "Exportar Carga     F2"),
            (self.MODULE_HISTORY,             "📋", "Histórico           F3"),
            (self.MODULE_DOWNLOAD_CONTAGENS,  "📥", "Download Contagens F4"),
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
        user_frame.setMinimumHeight(50)
        user_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-top: 1px solid #3e3e42;
                border-right: none;
            }
        """)
        user_layout = QHBoxLayout(user_frame)
        user_layout.setContentsMargins(8, 8, 8, 8)
        user_layout.setSpacing(0)

        # Botão de sair do aplicativo
        btn_exit = QPushButton("  ⏻  Sair  (F10)")
        btn_exit.setToolTip("Sair do aplicativo  [F10]")
        btn_exit.setMinimumHeight(36)
        btn_exit.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9d9d9d;
                border: none;
                border-radius: 4px;
                text-align: left;
                padding: 8px 10px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #5a1a1a;
                color: #ff6b6b;
            }
            QPushButton:pressed {
                background-color: #7a1f1f;
            }
        """)
        btn_exit.clicked.connect(self.close)
        user_layout.addWidget(btn_exit)

        # Atalho F10 para sair
        shortcut_f10 = QShortcut(QKeySequence(Qt.Key.Key_F10), self)
        shortcut_f10.activated.connect(self.close)

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

        from PySide6.QtWidgets import QCheckBox, QLineEdit, QComboBox

        # ===== GRUPO: DIRETÓRIO DE SAÍDA =====
        dir_group = QGroupBox("📁 Diretório de saída  (obrigatório)")
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
        # carrega último diretório salvo (persistência)
        try:
            from utils.config import AppConfig
            last_dir = AppConfig.get_last_export_dir()
        except Exception:
            last_dir = None
        if last_dir:
            self._txt_export_dir.setText(last_dir)
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
        vendedor_group = QGroupBox("👤 Conferente  (obrigatório)")
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

        # ===== GRUPO: DISPOSITIVO (obrigatório — vem da licença .key) =====
        aparelho_group = QGroupBox("📱 Dispositivo móvel (obrigatório)")
        aparelho_group.setStyleSheet("""
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
        aparelho_layout = QVBoxLayout(aparelho_group)
        aparelho_layout.setSpacing(8)

        lbl_disp = QLabel("Selecione o dispositivo habilitado na licença (.key):")
        lbl_disp.setStyleSheet("color: #9d9d9d; font-size: 10pt;")
        aparelho_layout.addWidget(lbl_disp)

        # Linha: combo + botão de renomear
        disp_row = QWidget()
        disp_row_layout = QHBoxLayout(disp_row)
        disp_row_layout.setContentsMargins(0, 0, 0, 0)
        disp_row_layout.setSpacing(8)

        self._cmb_dispositivo = QComboBox()
        self._cmb_dispositivo.setMinimumHeight(36)
        self._cmb_dispositivo.addItem("— Selecione o dispositivo —", None)
        self._cmb_dispositivo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._cmb_dispositivo.setStyleSheet("""
            QComboBox {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 11pt;
            }
            QComboBox:focus { border-color: #0078d4; }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox::down-arrow {
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #252526;
                border: 1px solid #3e3e42;
                selection-background-color: #094771;
                color: #cccccc;
            }
        """)
        disp_row_layout.addWidget(self._cmb_dispositivo, 1)

        btn_rename_disp = QPushButton("✏️")
        btn_rename_disp.setToolTip("Definir nome amigável para este dispositivo")
        btn_rename_disp.setFixedSize(40, 36)
        btn_rename_disp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_rename_disp.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                font-size: 14pt;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton:pressed { background-color: #0078d4; }
        """)
        btn_rename_disp.clicked.connect(self._on_rename_dispositivo)
        disp_row_layout.addWidget(btn_rename_disp)

        aparelho_layout.addWidget(disp_row)

        self._lbl_dispositivo_info = QLabel(
            "ℹ️  Os dispositivos disponíveis são carregados automaticamente da licença (.key)."
        )
        self._lbl_dispositivo_info.setStyleSheet("color: #666666; font-size: 9pt;")
        aparelho_layout.addWidget(self._lbl_dispositivo_info)

        content_layout.addWidget(aparelho_group)

        # ===== GRUPO: OPÇÕES =====
        export_options = QGroupBox("📋 Opções de exportação")
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

        self._chk_export_photos = QCheckBox("Incluir fotos dos produtos")
        self._chk_export_photos.setStyleSheet(chk_style)
        options_layout.addWidget(self._chk_export_photos, 0, 0)

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

        btn_cancel = QPushButton("Cancelar  [ESC]")
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

        self._btn_start_export = QPushButton("📤  Iniciar Exportação  [F11]")
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

        # Controles
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        btn_refresh = QPushButton("🔄 Atualizar  [F5]")
        btn_refresh.setMinimumHeight(36)
        btn_refresh.clicked.connect(self._refresh_history)
        controls_layout.addWidget(btn_refresh)

        btn_open = QPushButton("📂 Abrir Pasta")
        btn_open.setMinimumHeight(36)
        btn_open.clicked.connect(self._on_open_history_item)
        controls_layout.addWidget(btn_open)

        btn_clear = QPushButton("🗑️ Limpar Histórico")
        btn_clear.setMinimumHeight(36)
        btn_clear.setToolTip("Apaga todo o histórico de exportações (arquivo JSON)")
        btn_clear.clicked.connect(self._clear_export_history)
        controls_layout.addWidget(btn_clear)

        controls_layout.addStretch()
        content_layout.addWidget(controls)

        # Lista de histórico
        self._history_list = QListWidget()
        self._history_list.setStyleSheet("color: #cccccc; background-color: #252526;")
        self._history_list.itemDoubleClicked.connect(self._on_history_item_double_clicked)
        self._history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._history_list.customContextMenuRequested.connect(self._on_history_context_menu)
        content_layout.addWidget(self._history_list)

        layout.addWidget(content)

        # Carrega inicialmente
        QTimer.singleShot(100, self._refresh_history)
        
        self._module_stack.addWidget(page)
        self._pages[self.MODULE_HISTORY] = self._module_stack.count() - 1
    
    # -------------------------
    # Histórico helpers
    # -------------------------
    def _refresh_history(self):
        """Carrega e exibe o histórico em ordem decrescente por timestamp."""
        try:
            from utils.config import AppConfig
            history = AppConfig.load_export_history()
        except Exception:
            history = []

        def parse_entry_dt(e):
            # Primeiro tenta usar os campos date + time no formato dd-mm-aaaa e HH:MM
            d = e.get('date')
            t = e.get('time')
            if d and t:
                try:
                    return datetime.strptime(f"{d} {t}", "%d-%m-%Y %H:%M")
                except Exception:
                    pass
            # Fallback: timestamp ISO
            ts = e.get("timestamp")
            try:
                return datetime.fromisoformat(ts)
            except Exception:
                return datetime.min

        # Ordenar decrescente (mais recente primeiro)
        history_sorted = sorted(history, key=parse_entry_dt, reverse=True)

        self._history_list.clear()
        for entry in history_sorted:
            date_str = entry.get('date', '')
            time_str = entry.get('time', '')
            usuario_nome = entry.get('usuario', '')
            vendedor = entry.get('vendedor', '')
            aparelho = entry.get('aparelho', '')
            total = entry.get('product_count', entry.get('total_produtos', 0))

            display = f"{date_str} {time_str}  •  Usuário: {usuario_nome}  •  Conferente: {vendedor}  •  Aparelho: {aparelho}  •  {total} produtos"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._history_list.addItem(item)

    def _on_history_item_double_clicked(self, item: QListWidgetItem):
        """Ao dar duplo-clique: tentar abrir pasta do arquivo ZIP gerado."""
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            return
        zip_file = entry.get("zip_path") or entry.get("txt_path") or ""
        folder = os.path.dirname(zip_file) if zip_file else entry.get("output_dir", "")
        if folder and os.path.isdir(folder):
            try:
                os.startfile(folder)
            except Exception:
                QMessageBox.information(self, "Abrir Pasta", f"Não foi possível abrir: {folder}")
        else:
            QMessageBox.information(self, "Abrir Pasta", "Pasta não encontrada.")

    def _on_open_history_item(self):
        """Abre a pasta do item selecionado na lista de histórico."""
        item = self._history_list.currentItem()
        if not item:
            QMessageBox.information(self, "Abrir Pasta", "Selecione um item do histórico primeiro.")
            return
        self._on_history_item_double_clicked(item)

    def _on_history_context_menu(self, pos):
        """Exibe menu de contexto na lista de histórico."""
        from PySide6.QtWidgets import QMenu
        item = self._history_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #252526; color: #cccccc; border: 1px solid #3e3e42; }
            QMenu::item:selected { background-color: #0078d4; }
        """)
        act_open = menu.addAction("📂  Abrir Pasta")
        act_resend = menu.addAction("📡  Reenviar para API")
        action = menu.exec(self._history_list.viewport().mapToGlobal(pos))
        if action == act_open:
            self._on_history_item_double_clicked(item)
        elif action == act_resend:
            self._on_resend_history_to_api(item)

    def _on_resend_history_to_api(self, item):
        """Reenvia para a API a carga do item de histórico selecionado."""
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            return

        zip_path = entry.get('zip_path') or entry.get('txt_path') or ''
        if not zip_path or not os.path.isfile(zip_path):
            QMessageBox.warning(
                self,
                "Arquivo não encontrado",
                f"O arquivo de carga não foi encontrado:\n{zip_path or '(caminho não salvo)'}\n\n"
                "Não é possível reenviar.",
            )
            return

        # Extrai identificadores do registro de histórico
        empresa = entry.get('empresa') or {}
        cnpj = empresa.get('cnpj', '') or ''
        codvendedor = entry.get('codvendedor', '') or ''
        idcelular = entry.get('aparelho', '') or ''

        if not cnpj and not codvendedor and not idcelular:
            QMessageBox.warning(
                self,
                "Dados insuficientes",
                "O registro de histórico não contém os dados de identificação "
                "(CNPJ, vendedor, aparelho) necessários para o reenvio.",
            )
            return

        self._send_to_api(
            zip_path,
            _override_cnpj=cnpj,
            _override_codvendedor=codvendedor,
            _override_idcelular=idcelular,
        )

    def _clear_export_history(self):
        """Limpa o arquivo de histórico após confirmação do usuário."""
        from utils.config import AppConfig

        resp = QMessageBox.question(
            self,
            "Limpar Histórico",
            "Deseja apagar todo o histórico de exportações? Esta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return

        try:
            AppConfig.clear_export_history()
            self._refresh_history()
            # Feedback na status bar
            try:
                self._status_bar.show_message("Histórico de exportações limpo", 3000)
            except Exception:
                pass
        except Exception:
            QMessageBox.information(self, "Limpar Histórico", "Não foi possível limpar o histórico.")
    
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
        shortcuts = [
            (Qt.Key.Key_F1,  lambda: self._switch_module(self.MODULE_PRODUCTS)),
            (Qt.Key.Key_F2,  lambda: self._switch_module(self.MODULE_EXPORT)),
            (Qt.Key.Key_F3,  lambda: self._switch_module(self.MODULE_HISTORY)),
            (Qt.Key.Key_F4,  lambda: self._switch_module(self.MODULE_DOWNLOAD_CONTAGENS)),
            (Qt.Key.Key_F5,  self._on_refresh_shortcut),
            (Qt.Key.Key_F6,  self._on_clear_selection),
            (Qt.Key.Key_F8,  self._on_contagem_download),
            (Qt.Key.Key_F9,  self._on_select_all),
            (Qt.Key.Key_F11, self._on_start_export_shortcut),
            (Qt.Key.Key_Escape, self._on_cancel_export_shortcut),
        ]
        for key, slot in shortcuts:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(slot)
    
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
        
        # Ao entrar no módulo de download de contagens, recarrega a lista automaticamente
        if module_id == self.MODULE_DOWNLOAD_CONTAGENS:
            self._on_contagens_refresh()

        logger.debug(f"Módulo alterado para: {module_id}")
    
    # ==========================================
    # PUBLIC API
    # ==========================================
    
    def set_connection_info(self, empresa: Dict, usuario: Dict, connection: Dict, licenca: Dict = None):
        """Define informações de conexão."""
        self._empresa_info = empresa
        self._usuario_info = usuario
        self._connection_info = connection

        # Define código da empresa no painel de filtros para buscas dinâmicas
        if hasattr(self, "_filter_panel") and self._filter_panel:
            self._filter_panel.set_company_code(empresa.get("codigo"))

        if licenca:
            self._licenca_payload = licenca
            self._populate_dispositivos_combo()

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
        validade_licenca = (licenca or {}).get("validade", "")
        self._status_bar.set_license_validity(validade_licenca)
        
        self.setWindowTitle(f"{APP_INFO.NAME} - {empresa_nome}")
        
        logger.info(f"Conexão configurada: {empresa_nome} / {usuario_nome}")

    def _get_licensed_ids(self) -> set:
        """Retorna o conjunto de IDs de dispositivos presentes na licença atual."""
        ids: set = set()
        raw = (self._licenca_payload.get('ids')
               or self._licenca_payload.get('ids_celular')
               or [])
        for disp in raw:
            if isinstance(disp, dict):
                id_cel = (disp.get('idcelular') or disp.get('id') or '').strip()
            else:
                id_cel = str(disp).strip()
            if id_cel:
                ids.add(id_cel)
        return ids

    def _populate_dispositivos_combo(self):
        """
        Popula o combo de dispositivos a partir do payload da licença.

        O campo 'ids_celular' no .key é uma lista de strings: ["ID001", "ID002"]
        Suporta também lista de dicts (uso futuro):
          [{"idcelular": "ID001", "nome": "Coletor 1"}, ...]

        Nomes amigáveis opcionais são carregados de nome_device.json.
        Apenas IDs presentes na licença são exibidos.
        """
        if not hasattr(self, '_cmb_dispositivo'):
            return

        self._cmb_dispositivo.clear()
        self._cmb_dispositivo.addItem("— Selecione o dispositivo —", None)

        # IDs autorizados pela licença atual
        licensed_ids = self._get_licensed_ids()

        # Nomes amigáveis salvos localmente — filtrados para IDs da licença atual
        try:
            from utils.config import AppConfig
            all_names = AppConfig.load_device_names()
            device_names = {k: v for k, v in all_names.items() if k in licensed_ids}
        except Exception:
            device_names = {}

        # Campo no arquivo .key é 'ids'; payload do token usa 'ids_celular'
        dispositivos = (self._licenca_payload.get('ids')
                        or self._licenca_payload.get('ids_celular')
                        or [])
        count = 0
        for disp in dispositivos:
            if isinstance(disp, dict):
                id_cel = (disp.get('idcelular') or disp.get('id') or '').strip()
                nome_licenca = (disp.get('nome') or '').strip()
            else:
                id_cel = str(disp).strip()
                nome_licenca = ''

            if not id_cel or id_cel not in licensed_ids:
                continue

            # Nome amigável local tem prioridade sobre o nome da licença
            nome_amigavel = device_names.get(id_cel, nome_licenca)
            if nome_amigavel:
                label = f"{nome_amigavel}  ({id_cel})"
            else:
                label = id_cel

            self._cmb_dispositivo.addItem(label, id_cel)
            count += 1

        if hasattr(self, '_lbl_dispositivo_info'):
            if count > 0:
                self._lbl_dispositivo_info.setText(
                    f"✅  {count} dispositivo(s) liberado(s) nesta licença."
                )
                self._lbl_dispositivo_info.setStyleSheet("color: #4caf50; font-size: 9pt;")
            else:
                self._lbl_dispositivo_info.setText(
                    "⚠️  Nenhum dispositivo encontrado na licença. Verifique o arquivo .key."
                )
                self._lbl_dispositivo_info.setStyleSheet("color: #ff9800; font-size: 9pt;")

        self._cmb_dispositivo.setCurrentIndex(0)
        logger.debug(f"Dispositivos da licença carregados: {count}")

    def _on_rename_dispositivo(self):
        """Abre diálogo para definir/editar o nome amigável do dispositivo selecionado."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDialogButtonBox
        from utils.config import AppConfig

        id_cel = self._cmb_dispositivo.currentData() if hasattr(self, '_cmb_dispositivo') else None
        if not id_cel:
            QMessageBox.information(
                self,
                "Renomear dispositivo",
                "Selecione um dispositivo na lista antes de definir o nome amigável."
            )
            return

        device_names = AppConfig.load_device_names()
        nome_atual = device_names.get(id_cel, "")

        dlg = QDialog(self)
        dlg.setWindowTitle("Nome amigável do dispositivo")
        dlg.setFixedSize(420, 180)
        dlg.setStyleSheet("""
            QDialog { background-color: #1e1e1e; color: #cccccc; }
            QLabel  { color: #cccccc; font-size: 10pt; }
            QLineEdit {
                background-color: #252526; color: #cccccc;
                border: 1px solid #3e3e42; border-radius: 4px;
                padding: 6px 10px; font-size: 11pt;
            }
            QLineEdit:focus { border-color: #0078d4; }
            QPushButton {
                background-color: #3e3e42; color: #cccccc;
                border: none; border-radius: 4px;
                padding: 6px 20px; font-size: 10pt; min-width: 80px;
            }
            QPushButton:hover { background-color: #505050; }
            QPushButton[primary="true"] { background-color: #0078d4; color: white; font-weight: bold; }
            QPushButton[primary="true"]:hover { background-color: #1e8ad4; }
        """)

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        lay.addWidget(QLabel(f"Dispositivo ID: <b>{id_cel}</b>"))

        lbl_nome = QLabel("Nome amigável (deixe vazio para remover):")
        lay.addWidget(lbl_nome)

        txt_nome = QLineEdit(nome_atual)
        txt_nome.setPlaceholderText("Ex.: Coletor 1, Coletor Galpão...")
        txt_nome.setClearButtonEnabled(True)
        lay.addWidget(txt_nome)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = btn_box.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setText("Salvar")
        save_btn.setProperty("primary", "true")
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        lay.addWidget(btn_box)

        txt_nome.setFocus()
        txt_nome.selectAll()

        if dlg.exec() == QDialog.DialogCode.Accepted:
            novo_nome = txt_nome.text().strip()
            # Salva o nome e remove do JSON qualquer ID que não esteja na licença atual
            AppConfig.save_device_name(id_cel, novo_nome)
            AppConfig.purge_device_names(self._get_licensed_ids())
            # Recarrega o combo para refletir o novo nome
            self._populate_dispositivos_combo()
            # Restaura a seleção do mesmo dispositivo
            for i in range(self._cmb_dispositivo.count()):
                if self._cmb_dispositivo.itemData(i) == id_cel:
                    self._cmb_dispositivo.setCurrentIndex(i)
                    break
            if novo_nome:
                self._status_bar.show_message(f"✏️  Dispositivo renomeado para '{novo_nome}'", 3000)
            else:
                self._status_bar.show_message("❌  Nome amigável removido", 3000)
    
    def load_filter_data(self):
        """
        Carrega dados dos filtros a partir do banco e popula os combos do FilterPanel.

        Deve ser chamado após a conexão ser configurada (pós-login).
        """
        try:
            self._status_bar.show_message("Carregando filtros...")
            company_code = self._empresa_info.get("codigo")
            
            # Define o código da empresa no painel de filtros para buscas dinâmicas
            if hasattr(self._filter_panel, "filter_produto"):
                self._filter_panel.filter_produto.set_company_code(company_code)
                
            filter_data = self._product_service.get_all_filter_data(company_code)
            self._filter_panel.load_filter_data(
                grupos=filter_data.get("grupos", []),
                fornecedores=filter_data.get("fornecedores", []),
                fabricantes=filter_data.get("fabricantes", []),
                localizacoes=filter_data.get("localizacoes", []),
                tipos_produto=filter_data.get("tipos_produto", []),
            )

            # Configura o grupo Local Estoque conforme a configuração do banco
            # L=Loja, D=Depósito, A=Loja+Depósito, T=Lista ENDLOCALESTOQUE
            modo_local = (filter_data.get("locais_estoque_config") or "A").upper()
            end_locais = filter_data.get("end_locais_estoque") or []
            self._filter_panel.configure_local_estoque(modo_local, end_locais)

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
            company_code=self._empresa_info.get("codigo"),
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

    def _on_clear_selection(self):
        """Limpa a seleção de produtos."""
        self._product_table._clear_selection()

    def _on_start_export_shortcut(self):
        """Aciona Iniciar Exportação via F11 (apenas quando no módulo de exportação)."""
        if self._current_module == self.MODULE_EXPORT and self._btn_start_export.isEnabled():
            self._btn_start_export.click()

    def _on_refresh_shortcut(self):
        """F5: Atualizar — roteia para o módulo ativo."""
        if self._current_module == self.MODULE_HISTORY:
            self._refresh_history()
        elif self._current_module == self.MODULE_DOWNLOAD_CONTAGENS:
            self._on_contagens_refresh()

    def _on_cancel_export_shortcut(self):
        """Aciona Cancelar via ESC (apenas quando no módulo de exportação)."""
        if self._current_module == self.MODULE_EXPORT:
            self._switch_module(self.MODULE_PRODUCTS)
    
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
                    "SELECT v.CodVendedor, v.NomeVendedor FROM vendedores v "
                    "INNER JOIN Usuarios u ON u.CodUsuario = v.CodUsuario "
                    "WHERE v.TipoCadastro IN (0, 2) AND v.CodUsuario IS NOT NULL "
                    "AND u.InativosN = 0 ORDER BY v.CodVendedor ASC"
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
        try:
            from utils.config import AppConfig
            current = self._txt_export_dir.text() or AppConfig.ensure_export_dir()
        except Exception:
            current = self._txt_export_dir.text() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self,
            "Selecionar Diretório de Saída",
            current,
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self._txt_export_dir.setText(directory)
            try:
                from utils.config import AppConfig
                AppConfig.set_last_export_dir(directory)
            except Exception:
                pass

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

        # Se não há seleção na grid principal, tenta usar o filtro de produto
        # presente no painel de filtros (ProductSearchCombo). O filtro mostrado
        # na UI é o painel lateral — não confundir com o diálogo de busca.
        if not produtos:
            try:
                filtros = self._filter_panel.get_filters()
                selecionados = filtros.get("produtos") or []
                if selecionados:
                    # Busca os produtos completos via ProductService para manter
                    # a mesma projeção usada pela UI (estoque, localizacao, etc.)
                    from services.product_service import ProductService, ProductFilter

                    svc = ProductService()
                    pf = ProductFilter.from_dict({"produtos": selecionados})
                    produtos = svc.get_products(pf)
            except Exception:
                produtos = []

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

        # 3b. Valida dispositivo (deve ser selecionado da licença)
        aparelho_id = ""
        if hasattr(self, '_cmb_dispositivo'):
            aparelho_id = self._cmb_dispositivo.currentData() or ""
        if not aparelho_id:
            QMessageBox.warning(
                self,
                "Dispositivo não selecionado",
                "Selecione o dispositivo que receberá a carga.\n\n"
                "Os dispositivos disponíveis são definidos pela licença (.key)."
            )
            if hasattr(self, '_cmb_dispositivo'):
                self._cmb_dispositivo.setFocus()
            return

        # 4. Monta objetos de empresa e usuário
        # Define CNPJ da empresa logada: prioriza valor vindo do login, se vazio tenta consultar o DB
        empresa_cnpj = (self._empresa_info.get("cnpj") or "").strip()
        if not empresa_cnpj:
            try:
                from database.connection import get_session
                from sqlalchemy import text as sa_text
                cod_empresa = int(self._empresa_info.get("codigo", 1) or 1)
                with get_session() as session:
                    result = session.execute(sa_text(
                        "SELECT CNPJ FROM Empresas WHERE CodEmpresa = :cod_empresa"
                    ), {"cod_empresa": cod_empresa})
                    row = result.first()
                    if row and row[0]:
                        empresa_cnpj = str(row[0])
            except Exception:
                empresa_cnpj = ""

        empresa = EmpresaInfo(
            codempresa=int(self._empresa_info.get("codigo", 1) or 1),
            nomeempresa=self._empresa_info.get("nome", ""),
            local=(
                "Depósito" if self._local_estoque == "deposito"
                else "Loja" if self._local_estoque in ("loja", "")
                else self._local_estoque  # valor ENDLOCALESTOQUE (modo "T")
            ),
            cnpj=empresa_cnpj,
        )
        # Busca nome do vendedor diretamente no banco para garantir consistência
        cod_vendedor = int(self._export_vendedor.get("codigo", 0) or 0)
        nome_vendedor = self._export_vendedor.get("nome", "")
        login_usuario = ""
        senha_criptografada = ""
        try:
            from database.connection import get_session
            from sqlalchemy import text as sa_text
            with get_session() as session:
                result = session.execute(sa_text(
                    "SELECT TOP 1 NomeVendedor FROM vendedores WHERE CodVendedor = :cod"
                ), {"cod": cod_vendedor})
                row = result.first()
                if row and row[0]:
                    nome_vendedor = row[0]

                # Busca o usuário do ERP vinculado ao vendedor (login/senha para o registro V)
                result = session.execute(sa_text(
                    "SELECT TOP 1 u.NomeUsuario, u.NSenha FROM vendedores v "
                    "INNER JOIN Usuarios u ON u.CodUsuario = v.CodUsuario "
                    "WHERE v.CodVendedor = :cod"
                ), {"cod": cod_vendedor})
                row_usuario = result.first()
                if row_usuario:
                    login_usuario = (row_usuario[0] or "").strip()
                    if row_usuario[1]:
                        from encryption import encrypt_field
                        # NSenha é VARBINARY (hash PWDENCRYPT do SQL Server) — converter
                        # os bytes reais para hex antes de criptografar para transporte.
                        nsenha_hex = bytes(row_usuario[1]).hex()
                        senha_criptografada = encrypt_field(nsenha_hex) or ""
                else:
                    print(f"[AVISO] Nenhum usuário do ERP vinculado ao vendedor {cod_vendedor} — "
                          f"login_usuario/senha_criptografada ficarão vazios no registro V.")
        except Exception as e:
            # fallback: usa o nome já armazenado na seleção
            print(f"[AVISO] Falha ao buscar vendedor/usuário do ERP para registro V: {e}")

        usuario = UsuarioInfo(
            codusuario=cod_vendedor,
            nomeusuario=nome_vendedor or "",
            id_celular=aparelho_id,
            login_usuario=login_usuario,
            senha_criptografada=senha_criptografada,
        )

        # 4. Função de exportação a ser executada no worker
        db_service = DbExportService(output_dir=output_dir)
        # Captura filtros ativos no momento da exportação (para log)
        try:
            self._last_export_filters = self._filter_panel.get_filters()
        except Exception:
            self._last_export_filters = {}
        # Guarda metadados temporários para histórico e log
        self._last_export_count = len(produtos)
        self._last_export_empresa = {
            "codigo": str(empresa.codempresa),
            "nome": empresa.nomeempresa,
            "local": empresa.local,
            "cnpj": empresa.cnpj,
        }
        self._last_export_usuario = {
            "codigo": str(usuario.codusuario),
            "nome": usuario.nomeusuario,
            "id_celular": usuario.id_celular,
        }
        self._last_export_output_dir = output_dir

        def do_export(progress_callback=None):
            zip_path = db_service.export_carga(
                empresa=empresa,
                usuario=usuario,
                produtos=produtos,
                output_path=output_dir,
                progress_callback=progress_callback,
                include_photos=self._chk_export_photos.isChecked() if hasattr(self, '_chk_export_photos') else False,
                photos_output_dir=os.path.join(output_dir, 'Fotos') if hasattr(self, '_chk_export_photos') and self._chk_export_photos.isChecked() else None,
            )
            return zip_path

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
        self._btn_start_export.setText("📤  Iniciar Exportação  [F11]")
        self._status_bar.hide_progress()
        self._status_bar.show_message(f"✅ Exportação concluída: {os.path.basename(filepath)}", 8000)
        logger.info(f"Exportação concluída: {filepath}")

        # Diálogo de sucesso com opção de abrir pasta
        msg = QMessageBox(self)
        msg.setWindowTitle("Exportação Concluída")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText("✅ Arquivo gerado com sucesso!")
        msg.setInformativeText(
            f"📦 ZIP: <b>{os.path.basename(filepath)}</b>\n\n"
            "Contém: .db (carga de dados) + .sig (assinatura digital)"
        )
        msg.setDetailedText(f"Caminho completo:\n{filepath}")
        btn_abrir = msg.addButton("Abrir Pasta", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg.exec()

        # Salva último diretório sempre (independente do botão clicado)
        try:
            from utils.config import AppConfig
            out_dir = ""
            if filepath:
                out_dir = os.path.dirname(filepath)
            if not out_dir:
                out_dir = (self._txt_export_dir.text() or "").strip()
            if out_dir:
                AppConfig.set_last_export_dir(out_dir)
        except Exception:
            pass

        if msg.clickedButton() == btn_abrir:
            import subprocess
            try:
                # Determina a pasta a abrir
                folder = ""
                if filepath and os.path.exists(filepath):
                    folder = os.path.dirname(filepath)
                if not folder:
                    try:
                        from utils.config import AppConfig
                        folder = AppConfig.get_last_export_dir()
                    except Exception:
                        pass

                if folder and os.path.isdir(folder):
                    # Usa explorer /select,"filepath" para destacar o arquivo.
                    # Passa como STRING (não lista) para preservar espaços no caminho.
                    if filepath and os.path.exists(filepath):
                        try:
                            subprocess.Popen(f'explorer /select,"{filepath}"')
                        except Exception:
                            os.startfile(folder)
                    else:
                        try:
                            os.startfile(folder)
                        except Exception:
                            pass
                else:
                    QMessageBox.information(self, "Abrir Pasta", "Não foi possível localizar a pasta de exportação.")
            except Exception:
                pass

        # Registra histórico de exportação (não bloqueante)
        try:
            from utils.config import AppConfig
            now = datetime.now(pytz.timezone('America/Sao_Paulo'))
            # Dados para histórico — formato solicitado: data dd-mm-aaaa, hora hh:mm,
            # usuário logado, vendedor selecionado, aparelho (nome + id) e quantidade de produtos
            usuario_logado = (self._usuario_info.get('nome') if hasattr(self, '_usuario_info') else None) or ""
            vendedor = ""
            aparelho = ""
            codvendedor = ""
            if hasattr(self, '_last_export_usuario'):
                lv = self._last_export_usuario
                vendedor = lv.get('nome', '')
                aparelho = lv.get('id_celular', '')
                _cod = lv.get('codigo', '')
                if _cod is not None:
                    codvendedor = str(_cod).zfill(3)

            hist_entry = {
                "date": now.strftime("%d-%m-%Y"),
                "time": now.strftime("%H:%M"),
                "usuario": usuario_logado,
                "vendedor": vendedor,
                "aparelho": aparelho,
                "codvendedor": codvendedor,
                "product_count": getattr(self, '_last_export_count', 0),
                "zip_path": filepath,
                "empresa": self._last_export_empresa if hasattr(self, '_last_export_empresa') else {},
                "output_dir": getattr(self, '_last_export_output_dir', ""),
            }
            AppConfig.append_export_history(hist_entry)
        except Exception:
            pass

        # Grava log de exportação na pasta Logs
        self._write_export_log(filepath)

        # ── Envio para a API CSCollect ──────────────────────────────────
        self._send_to_api(filepath)

    def _send_to_api(self, filepath: str, _force_delete_id=None,
                      _override_cnpj: str = None,
                      _override_codvendedor: str = None,
                      _override_idcelular: str = None):
        """
        Verifica duplicidade e envia o arquivo ZIP para a API CSCollect.

        Fluxo:
        1. Verifica se já existe registro (cnpj + codvendedor + idcelular).
        2. Se sim → exibe diálogo de conflito com opções de substituir ou cancelar.
        3. Se "Apagar e enviar novo" → remove o registro antigo e faz upload.
        4. Se "Manter" → cancela sem enviar.
        5. Se não há conflito → faz upload direto.

        Parâmetros opcionais _override_* permitem forçar os valores de identificação
        (usado no reenvio a partir do histórico).
        """
        from utils.config import AppConfig
        try:
            api_configured = AppConfig.is_api_configured()
        except Exception as e:
            logger.exception(f"[_send_to_api] Falha ao verificar configuração da API: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao ler configuração da API no licenca.key:\n{e}")
            return
        if not api_configured:
            return

        try:
            from utils.config import AppConfig
            from services.api_service import ApiService
            from PySide6.QtCore import QThread
            from PySide6.QtWidgets import (
                QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                QPushButton, QProgressBar, QFrame,
            )
            from PySide6.QtCore import Qt
            import os as _os

            url      = AppConfig.get_api_url()
            token    = AppConfig.get_api_authorization()
            db_url   = AppConfig.get_api_database_url()
            api      = ApiService(base_url=url, authorization=token)

            lexp       = getattr(self, '_last_export_empresa',  {})
            lusr       = getattr(self, '_last_export_usuario',  {})
            cnpj       = _override_cnpj if _override_cnpj is not None else lexp.get('cnpj', '')
            codvendedor = _override_codvendedor if _override_codvendedor is not None else lusr.get('codigo', '')
            idcelular  = _override_idcelular if _override_idcelular is not None else lusr.get('id_celular', '')
            if codvendedor is not None and _override_codvendedor is None:
                codvendedor = str(codvendedor).zfill(3)

            # ── Diálogo base (reutilizado nas duas fases) ─────────────────────
            _DLG_CSS = """
                QDialog  { background-color: #1e1e1e; }
                QLabel   { color: #cccccc; font-size: 10pt; }
                QFrame#separator { background-color: #3e3e42; max-height: 1px; }
                QPushButton {
                    border: none; border-radius: 4px;
                    padding: 8px 20px; font-weight: bold; color: white;
                }
                QPushButton#btnOk     { background-color: #0078d4; }
                QPushButton#btnOk:hover { background-color: #1e8ad4; }
                QPushButton#btnDelete { background-color: #c0392b; }
                QPushButton#btnDelete:hover { background-color: #e74c3c; }
                QPushButton#btnKeep   { background-color: #444; }
                QPushButton#btnKeep:hover { background-color: #555; }
                QPushButton#btnRetry  { background-color: #e65100; }
                QPushButton#btnRetry:hover { background-color: #ff6d00; }
                QPushButton:disabled  { background-color: #3e3e42; color: #666; }
            """

            def _make_progress(parent_layout, *, indeterminate=True):
                bar = QProgressBar()
                bar.setRange(0, 0 if indeterminate else 1)
                if not indeterminate:
                    bar.setValue(1)
                bar.setTextVisible(False)
                bar.setMaximumHeight(4)
                bar.setStyleSheet("""
                    QProgressBar { background-color: #2d2d30; border: none; border-radius: 2px; }
                    QProgressBar::chunk { background-color: #0078d4; border-radius: 2px; }
                """)
                parent_layout.addWidget(bar)
                return bar

            # ── FASE 1: verificar duplicidade ─────────────────────────────────
            class _CheckThread(QThread):
                def __init__(self, api_svc, cnpj_v, codv_v, idcel_v, parent=None):
                    super().__init__(parent)
                    self._api   = api_svc
                    self._cnpj  = cnpj_v
                    self._codv  = codv_v
                    self._idcel = idcel_v
                    self.found  = False
                    self.record = None
                    self.error  = None

                def run(self):
                    _dbu = getattr(self, '_db_url', '')
                    self.found, self.record, self.error = self._api.check_existing(
                        self._cnpj, self._codv, self._idcel, database_url=_dbu
                    )

            chk_thread = _CheckThread(api, cnpj, codvendedor, idcelular, self)
            chk_thread._db_url = db_url

            dlg_check = QDialog(self)
            dlg_check.setWindowTitle("Verificando...")
            dlg_check.setWindowFlags(
                Qt.WindowType.Dialog |
                Qt.WindowType.WindowTitleHint |
                Qt.WindowType.CustomizeWindowHint
            )
            dlg_check.setMinimumWidth(380)
            dlg_check.setStyleSheet(_DLG_CSS)

            lay_check = QVBoxLayout(dlg_check)
            lay_check.setContentsMargins(24, 20, 24, 20)
            lay_check.setSpacing(12)

            lbl_chk = QLabel("🔍  Verificando registros existentes na API...")
            lbl_chk.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_chk.setWordWrap(True)
            lay_check.addWidget(lbl_chk)

            lbl_chk_file = QLabel(f"Arquivo: {_os.path.basename(filepath)}")
            lbl_chk_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_chk_file.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
            lay_check.addWidget(lbl_chk_file)

            _make_progress(lay_check)

            def _on_check_done():
                dlg_check.accept()   # fecha o diálogo de verificação

            chk_thread.finished.connect(_on_check_done)
            chk_thread.start()
            self._api_check_thread = chk_thread
            dlg_check.exec()        # bloqueia até _on_check_done

            # ── Resultado da verificação ──────────────────────────────────────
            if chk_thread.found and chk_thread.record:
                rec = chk_thread.record
                nome_banco  = str(rec.get("nome_arquivo") or rec.get("arquivo") or "(sem nome)")
                data_envio  = _utc_to_local(str(rec.get("data_envio") or rec.get("criado_em") or ""))
                carga_id    = rec.get("id")

                # Diálogo de conflito
                dlg_conf = QDialog(self)
                dlg_conf.setWindowTitle("Carga já existente")
                dlg_conf.setWindowFlags(
                    Qt.WindowType.Dialog |
                    Qt.WindowType.WindowTitleHint |
                    Qt.WindowType.CustomizeWindowHint
                )
                dlg_conf.setMinimumWidth(420)
                dlg_conf.setStyleSheet(_DLG_CSS)

                lay_conf = QVBoxLayout(dlg_conf)
                lay_conf.setContentsMargins(24, 20, 24, 20)
                lay_conf.setSpacing(12)

                lbl_warn = QLabel("⚠️  Já existe uma carga registrada para esta identificação:")
                lbl_warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_warn.setWordWrap(True)
                lbl_warn.setStyleSheet("color: #f39c12; font-size: 10pt; font-weight: bold;")
                lay_conf.addWidget(lbl_warn)

                sep = QFrame()
                sep.setObjectName("separator")
                sep.setFrameShape(QFrame.Shape.HLine)
                lay_conf.addWidget(sep)

                # Detalhes do registro existente
                info_css = "color: #cccccc; font-size: 9pt;"
                for label_txt, value_txt in [
                    ("CNPJ:",        cnpj or "—"),
                    ("Vendedor:",    codvendedor or "—"),
                    ("ID Celular:",  idcelular or "—"),
                    ("Arquivo no banco:", nome_banco),
                    ("Data de envio:",    data_envio or "—"),
                ]:
                    row = QHBoxLayout()
                    lbl_k = QLabel(label_txt)
                    lbl_k.setStyleSheet(info_css + " font-weight: bold;")
                    lbl_k.setFixedWidth(120)
                    lbl_v = QLabel(value_txt)
                    lbl_v.setStyleSheet(info_css)
                    lbl_v.setWordWrap(True)
                    row.addWidget(lbl_k)
                    row.addWidget(lbl_v, 1)
                    lay_conf.addLayout(row)

                sep2 = QFrame()
                sep2.setObjectName("separator")
                sep2.setFrameShape(QFrame.Shape.HLine)
                lay_conf.addWidget(sep2)

                lbl_pergunta = QLabel("O que deseja fazer?")
                lbl_pergunta.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_pergunta.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
                lay_conf.addWidget(lbl_pergunta)

                btn_row = QHBoxLayout()
                btn_row.setSpacing(10)
                btn_delete = QPushButton("🗑  Apagar do banco e enviar novo")
                btn_delete.setObjectName("btnDelete")
                btn_keep   = QPushButton("✔  Manter e não enviar")
                btn_keep.setObjectName("btnKeep")
                btn_row.addWidget(btn_delete)
                btn_row.addWidget(btn_keep)
                lay_conf.addLayout(btn_row)

                _conf_choice = {"value": None}  # "delete" | "keep"

                def _choose_delete():
                    _conf_choice["value"] = "delete"
                    dlg_conf.accept()

                def _choose_keep():
                    _conf_choice["value"] = "keep"
                    dlg_conf.reject()

                btn_delete.clicked.connect(_choose_delete)
                btn_keep.clicked.connect(_choose_keep)
                dlg_conf.exec()

                if _conf_choice["value"] != "delete":
                    # "keep", fechou o diálogo (X / Escape) ou qualquer outra ação → cancela envio
                    try:
                        self._status_bar.show_message(
                            f"ℹ️  Envio cancelado — carga '{nome_banco}' mantida no banco.", 6000
                        )
                    except Exception:
                        pass
                    logger.info("Envio para API cancelado: usuário optou por manter registro existente (choice=%r).", _conf_choice["value"])
                    return

                if _conf_choice["value"] == "delete":
                    # Remove o registro antigo antes de subir o novo
                    if carga_id is not None:
                        ok_del, msg_del = api.delete_carga(carga_id, database_url=db_url)
                        if not ok_del:
                            from PySide6.QtWidgets import QMessageBox
                            QMessageBox.warning(
                                self,
                                "Erro ao remover registro",
                                f"Não foi possível remover o registro anterior:\n\n{msg_del}\n\n"
                                "O novo arquivo não será enviado.",
                            )
                            logger.warning(f"Falha ao remover carga {carga_id}: {msg_del}")
                            return
                        logger.info(f"Carga anterior (id={carga_id}) removida: {msg_del}")
                    # Continua para o upload (abaixo)

            # ── FASE 2: upload ────────────────────────────────────────────────
            class _ApiUploadThread(QThread):
                def __init__(self, api_svc, path, cnpj_val, codvend_val, idcel_val, parent=None):
                    super().__init__(parent)
                    self._api  = api_svc
                    self._path = path
                    self._cnpj = cnpj_val
                    self._codv = codvend_val
                    self._idcel = idcel_val
                    self.success = False
                    self.message = ""

                def run(self):
                    self.success, self.message = self._api.upload_file(
                        self._path,
                        cnpj=self._cnpj,
                        codvendedor=self._codv,
                        idcelular=self._idcel,
                    )

            up_thread = _ApiUploadThread(api, filepath, cnpj, codvendedor, idcelular, self)

            self._status_bar.show_message("📡  Enviando carga para a API...", 0)

            dlg_up = QDialog(self)
            dlg_up.setWindowTitle("Enviando para API")
            dlg_up.setWindowFlags(
                Qt.WindowType.Dialog |
                Qt.WindowType.WindowTitleHint |
                Qt.WindowType.CustomizeWindowHint
            )
            dlg_up.setMinimumWidth(380)
            dlg_up.setStyleSheet(_DLG_CSS)

            lay_up = QVBoxLayout(dlg_up)
            lay_up.setContentsMargins(24, 20, 24, 20)
            lay_up.setSpacing(14)

            lbl_up_status = QLabel("📡  Conectando à API...")
            lbl_up_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_up_status.setWordWrap(True)
            lay_up.addWidget(lbl_up_status)

            lbl_up_file = QLabel(f"Arquivo: {_os.path.basename(filepath)}")
            lbl_up_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_up_file.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
            lay_up.addWidget(lbl_up_file)

            prog_up = _make_progress(lay_up)

            btn_ok_up = QPushButton("OK")
            btn_ok_up.setObjectName("btnOk")
            btn_ok_up.setVisible(False)
            btn_ok_up.clicked.connect(dlg_up.accept)
            btn_row_up = QHBoxLayout()
            btn_row_up.addStretch()
            btn_row_up.addWidget(btn_ok_up)
            btn_row_up.addStretch()
            lay_up.addLayout(btn_row_up)

            def _on_upload_done():
                prog_up.setRange(0, 1)
                prog_up.setValue(1)
                if up_thread.success:
                    logger.info(f"Carga enviada para API: {up_thread.message}")
                    lbl_up_status.setText(f"✅  Carga enviada com sucesso!\n{up_thread.message}")
                    lbl_up_status.setStyleSheet("color: #4caf50; font-size: 10pt; font-weight: bold;")
                    try:
                        self._status_bar.show_message(f"✅ API: {up_thread.message}", 6000)
                    except Exception:
                        pass
                    btn_ok_up.setVisible(True)
                else:
                    logger.warning(f"Falha ao enviar para API: {up_thread.message}")
                    lbl_up_status.setText(f"❌  Falha no envio\n{up_thread.message}")
                    lbl_up_status.setStyleSheet("color: #f44336; font-size: 10pt;")
                    prog_up.setStyleSheet("""
                        QProgressBar { background-color: #2d2d30; border: none; border-radius: 2px; }
                        QProgressBar::chunk { background-color: #f44336; border-radius: 2px; }
                    """)
                    try:
                        self._status_bar.show_message("⚠️ API: falha no envio", 6000)
                    except Exception:
                        pass
                    btn_retry = QPushButton("🔄  Tentar novamente")
                    btn_retry.setObjectName("btnRetry")
                    btn_retry.clicked.connect(lambda: (dlg_up.reject(), self._send_to_api(filepath)))
                    btn_row_up.insertWidget(1, btn_retry)
                    btn_ok_up.setVisible(True)
                    btn_ok_up.setText("Fechar")

            up_thread.finished.connect(_on_upload_done)
            up_thread.start()
            self._api_upload_thread = up_thread  # Guarda referência
            dlg_up.exec() # Bloqueia até o upload ser concluído ou cancelado

        except Exception as exc:
            logger.error(f"Erro inesperado ao iniciar envio para API: {exc}")

    def _write_export_log(self, zip_path: str):
        """Grava arquivo de log na pasta Logs com resumo completo da exportação."""
        try:
            from utils.config import AppConfig
            from pathlib import Path as _Path

            log_dir = _Path(AppConfig.get_export_logs_dir())
            now = datetime.now(pytz.timezone('America/Sao_Paulo'))
            log_filename = f"EXPORTLOG-{now.strftime('%Y%m%d-%H%M%S')}.log"
            log_path = log_dir / log_filename

            # Dados do contexto
            usuario_logado = (self._usuario_info.get('nome') if hasattr(self, '_usuario_info') else None) or ""
            empresa_nome   = (self._empresa_info.get('nome') if hasattr(self, '_empresa_info') else None) or ""
            lexp = getattr(self, '_last_export_empresa', {})
            empresa_local  = lexp.get('local', '')
            empresa_cnpj   = lexp.get('cnpj', '')
            lv = getattr(self, '_last_export_usuario', {})
            vendedor   = lv.get('nome', '')
            aparelho   = lv.get('id_celular', '')
            total_prod = getattr(self, '_last_export_count', 0)
            filtros    = getattr(self, '_last_export_filters', {})

            def _fmt(v):
                if v is None or (isinstance(v, list) and not v):
                    return "(todos / não filtrado)"
                if isinstance(v, list):
                    return ", ".join(str(x) for x in v)
                return str(v)

            map_local    = {"loja": "Loja", "deposito": "Depósito"}
            map_loc      = {"com": "Com localização", "sem": "Sem localização", "ambos": "Ambos"}
            map_estoque  = {"negativo": "Negativo", "positivo": "Positivo", "zerado": "Zerado", "todos": "Todos"}
            map_encomenda = {"somente_encomenda": "Somente encomenda",
                             "somente_nao_encomenda": "Somente não-encomenda",
                             "ambos": "Ambos"}

            lines = [
                "=" * 72,
                "  RELATÓRIO DE EXPORTAÇÃO DE CARGA — LogScan Manager",
                "=" * 72,
                f"  Data/Hora          : {now.strftime('%d/%m/%Y %H:%M:%S')}",
                f"  Usuário logado      : {usuario_logado}",
                f"  Empresa             : {empresa_nome}  (CNPJ: {empresa_cnpj})",
                f"  Local estoque       : {empresa_local}",
                f"  Vendedor            : {vendedor}",
                f"  Dispositivo (ID)    : {aparelho}",
                f"  Total exportado     : {total_prod} produto(s)",
                f"  Arquivo gerado      : {zip_path}",
                "-" * 72,
                "  FILTROS APLICADOS NA CONSULTA",
                "-" * 72,
                f"  Produto(s)          : {_fmt(filtros.get('produtos'))}",
                f"  Grupo(s)            : {_fmt(filtros.get('grupos'))}",
                f"  Fornecedor(es)      : {_fmt(filtros.get('fornecedor'))}",
                f"  Fabricante(s)       : {_fmt(filtros.get('fabricante'))}",
                f"  Localização(ões)    : {_fmt(filtros.get('localizacoes'))}",
                f"  Tipo produto(s)     : {_fmt(filtros.get('tipos_produto'))}",
                f"  Local estoque       : {map_local.get(filtros.get('local_estoque',''), filtros.get('local_estoque',''))}",
                f"  Filtro localização  : {map_loc.get(filtros.get('filtro_localizacao','ambos'), 'Ambos')}",
                f"  Filtro estoque      : {map_estoque.get(filtros.get('filtro_estoque','todos'), 'Todos')}",
                f"  Filtro encomenda    : {map_encomenda.get(filtros.get('filtro_encomenda','ambos'), 'Ambos')}",
                f"  Somente peso variável: {'Sim' if filtros.get('somente_peso_variavel') else 'Não'}",
                f"  Somente venda       : {'Sim' if filtros.get('somente_venda') else 'Não'}",
                "=" * 72,
            ]

            log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            logger.info(f"Log de exportação gravado: {log_path}")
        except Exception as exc:
            logger.warning(f"Falha ao gravar log de exportação: {exc}")

    def _on_export_error(self, error: Exception):
        """Callback de erro na exportação."""
        self._btn_start_export.setEnabled(True)
        self._btn_start_export.setText("📤  Iniciar Exportação  [F11]")
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

    # =========================================================================
    # Módulo: Download Contagens API
    # =========================================================================

    def _create_download_contagens_page(self):
        """Cria a página de download de contagens enviadas pelos coletores."""
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = ModuleHeader(
            "📥",
            "Download Contagens",
            "Baixe e valide os arquivos de contagem enviados pelos coletores",
        )
        btn_refresh = header.add_action_button("Atualizar  [F5]", "🔄")
        btn_download = header.add_action_button("Baixar Selecionado  [F8]", "⬇️", primary=True)
        layout.addWidget(header)

        # Área de conteúdo
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(12)

        # Rótulo informativo
        lbl_info = QLabel(
            "Selecione um registro e clique em  ⬇️ Baixar Selecionado  para salvar o arquivo na pasta Cargas."
        )
        lbl_info.setStyleSheet("color: #9d9d9d; font-size: 10pt; padding: 4px 0;")
        content_layout.addWidget(lbl_info)

        # Tabela
        self._contagens_table = QTableWidget()
        self._contagens_table.setColumnCount(7)
        self._contagens_table.setHorizontalHeaderLabels([
            "ID", "Nome do Arquivo", "Vendedor", "Aparelho", "CNPJ", "Data Envio", "URL",
        ])
        self._contagens_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._contagens_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._contagens_table.setColumnHidden(6, True)   # URL oculta
        self._contagens_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._contagens_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._contagens_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._contagens_table.setAlternatingRowColors(True)
        self._contagens_table.verticalHeader().setVisible(False)
        self._contagens_table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                gridline-color: #3e3e42;
                font-size: 10pt;
            }
            QTableWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #9d9d9d;
                border: none;
                border-bottom: 1px solid #3e3e42;
                padding: 6px 8px;
                font-weight: bold;
            }
            QTableWidget::item:alternate {
                background-color: #2d2d30;
            }
        """)
        content_layout.addWidget(self._contagens_table)

        # Label de status da operação de download
        self._lbl_contagens_status = QLabel("")
        self._lbl_contagens_status.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
        content_layout.addWidget(self._lbl_contagens_status)

        layout.addWidget(content)

        self._module_stack.addWidget(page)
        self._pages[self.MODULE_DOWNLOAD_CONTAGENS] = self._module_stack.count() - 1

        # Conecta botões
        btn_refresh.clicked.connect(self._on_contagens_refresh)
        btn_download.clicked.connect(self._on_contagem_download)

    def _on_contagens_refresh(self):
        """Carrega a lista de contagens da API/banco Neon filtrada pelo CNPJ da empresa logada."""
        from utils.config import AppConfig
        from services.api_service import ApiService
        from PySide6.QtCore import QThread, QObject
        from PySide6.QtCore import Signal as _Signal
        from PySide6.QtWidgets import QTableWidgetItem

        try:
            api_configured = AppConfig.is_api_configured()
        except Exception as e:
            logger.exception(f"[_on_contagens_refresh] Falha ao verificar configuração da API: {e}")
            self._lbl_contagens_status.setText(f"⚠️  Erro ao ler configuração da API: {e}")
            return
        if not api_configured:
            self._lbl_contagens_status.setText(
                "⚠️  API não configurada. Verifique o arquivo licenca.key."
            )
            return

        # CNPJ da empresa logada
        cnpj = (self._empresa_info.get("cnpj") or "").strip()
        if not cnpj:
            self._lbl_contagens_status.setText(
                "⚠️  CNPJ da empresa não disponível. Faça login novamente."
            )
            return

        url   = AppConfig.get_api_url()
        token = AppConfig.get_api_authorization()
        db_url = AppConfig.get_api_database_url()
        api   = ApiService(base_url=url, authorization=token)

        self._lbl_contagens_status.setText("🔄  Consultando contagens...")
        self._contagens_table.setRowCount(0)

        class _Worker(QObject):
            done = _Signal(bool, list, str)

            def __init__(self, svc, cnpj_v, db_url_v):
                super().__init__()
                self._svc    = svc
                self._cnpj   = cnpj_v
                self._db_url = db_url_v

            def run(self):
                ok, rows, err = self._svc.list_contagens(self._cnpj, database_url=self._db_url)
                self.done.emit(ok, rows, err or "")

        thread = QThread(self)
        worker = _Worker(api, cnpj, db_url)
        worker.moveToThread(thread)

        def _on_done(ok, rows, err):
            thread.quit()
            if not ok:
                self._lbl_contagens_status.setText(f"❌  Erro: {err}")
                return
            self._contagens_table.setRowCount(0)
            for rec in rows:
                row_idx = self._contagens_table.rowCount()
                self._contagens_table.insertRow(row_idx)
                self._contagens_table.setItem(row_idx, 0, QTableWidgetItem(str(rec.get("id") or "")))
                self._contagens_table.setItem(row_idx, 1, QTableWidgetItem(str(rec.get("nome_arquivo") or "")))
                self._contagens_table.setItem(row_idx, 2, QTableWidgetItem(str(rec.get("codvendedor") or "")))
                self._contagens_table.setItem(row_idx, 3, QTableWidgetItem(str(rec.get("idcelular") or "")))
                self._contagens_table.setItem(row_idx, 4, QTableWidgetItem(str(rec.get("cnpj") or "")))
                data_envio = _utc_to_local(str(rec.get("data_envio") or ""))  # converte UTC→local (UTC-3)
                self._contagens_table.setItem(row_idx, 5, QTableWidgetItem(data_envio))
                self._contagens_table.setItem(row_idx, 6, QTableWidgetItem(str(rec.get("url_arquivo") or "")))

            total = self._contagens_table.rowCount()
            self._lbl_contagens_status.setText(
                f"✅  {total} contagem(ns) encontrada(s) para o CNPJ {cnpj}."
                if total else
                f"ℹ️  Nenhuma contagem encontrada para o CNPJ {cnpj}."
            )

        worker.done.connect(_on_done)
        thread.started.connect(worker.run)
        self._contagens_refresh_thread = thread
        self._contagens_refresh_worker = worker
        thread.start()

    def _on_contagem_download(self):
        """
        Baixa o arquivo selecionado, valida a assinatura do arquivo .sig contido no ZIP
        e salva na pasta Cargas caso a validação passe.
        """
        from utils.config import AppConfig
        from services.api_service import ApiService
        import os, tempfile

        selected_rows = self._contagens_table.selectedItems()
        if not selected_rows:
            QMessageBox.information(self, "Selecionar", "Selecione um registro na tabela.")
            return

        row_idx = self._contagens_table.currentRow()
        nome_arquivo = self._contagens_table.item(row_idx, 1).text() if self._contagens_table.item(row_idx, 1) else ""
        url_arquivo  = self._contagens_table.item(row_idx, 6).text() if self._contagens_table.item(row_idx, 6) else ""
        cnpj_tabela  = self._contagens_table.item(row_idx, 4).text() if self._contagens_table.item(row_idx, 4) else ""

        # Se url_arquivo for caminho relativo (começa com /), monta URL completa
        if url_arquivo and not url_arquivo.startswith("http"):
            base_url = AppConfig.get_api_url().rstrip("/")
            url_arquivo = base_url + "/" + url_arquivo.lstrip("/")

        if not url_arquivo:
            QMessageBox.warning(self, "URL ausente", "Este registro não possui URL de arquivo para download.")
            return

        # CNPJ e token da empresa logada
        cnpj_empresa = (self._empresa_info.get("cnpj") or "").strip()
        token        = AppConfig.get_api_authorization()

        # Validação prévia: CNPJ da tabela deve corresponder ao da empresa logada
        def _normalizar_cnpj(c: str) -> str:
            """Remove pontuação do CNPJ para comparação."""
            import re
            return re.sub(r"[.\-/]", "", (c or "").strip())

        if cnpj_tabela and cnpj_empresa:
            if _normalizar_cnpj(cnpj_tabela) != _normalizar_cnpj(cnpj_empresa):
                QMessageBox.critical(
                    self,
                    "CNPJ Inválido",
                    f"O CNPJ do registro ({cnpj_tabela}) não corresponde ao "
                    f"CNPJ da empresa logada ({cnpj_empresa}).\n\nDownload cancelado.",
                )
                return

        # ── Validação do nome do arquivo (antes do download) ─────────────
        # Padrão esperado: MODELO_CODEMPRESA_CODVENDEDOR_CNPJ_DDMMYYYYHHMM.ZIP
        # Exemplo:         MOD1_1_043_65381113000120_070520261714.zip
        _filename_to_validate = nome_arquivo if nome_arquivo else os.path.basename(url_arquivo.split("?")[0])
        _basename_no_ext = os.path.splitext(_filename_to_validate)[0]
        _parts = _basename_no_ext.split("_")

        if len(_parts) < 5:
            QMessageBox.critical(
                self,
                "Nome de Arquivo Inválido",
                f"O nome do arquivo não segue o padrão esperado:\n"
                f"  MODELO_CODEMPRESA_CODVENDEDOR_CNPJ_DDMMYYYYHHMM.ZIP\n\n"
                f"Arquivo recebido: {_filename_to_validate}\n\nDownload cancelado.",
            )
            return

        _fn_codempresa  = _parts[1]
        _fn_codvendedor = _parts[2]
        _fn_cnpj        = _parts[3]

        # Valida CODEMPRESA
        _codempresa_empresa = str(self._empresa_info.get("codigo", "") or "").strip()
        if _fn_codempresa != _codempresa_empresa:
            QMessageBox.critical(
                self,
                "CODEMPRESA Inválido",
                f"O código de empresa no nome do arquivo  →  {_fn_codempresa}\n"
                f"Código de empresa logada               →  {_codempresa_empresa}\n\n"
                "Os códigos não coincidem. Download cancelado.",
            )
            return

        # Valida CODVENDEDOR (compara sem zero-fill para maior flexibilidade)
        _codvendedor_tabela = (self._contagens_table.item(row_idx, 2).text()
                               if self._contagens_table.item(row_idx, 2) else "")
        if _fn_codvendedor.lstrip("0") != _codvendedor_tabela.lstrip("0"):
            QMessageBox.critical(
                self,
                "CODVENDEDOR Inválido",
                f"O código de vendedor no nome do arquivo  →  {_fn_codvendedor}\n"
                f"Código de vendedor do registro           →  {_codvendedor_tabela}\n\n"
                "Os códigos não coincidem. Download cancelado.",
            )
            return

        # Valida CNPJ
        if _normalizar_cnpj(_fn_cnpj) != _normalizar_cnpj(cnpj_empresa):
            QMessageBox.critical(
                self,
                "CNPJ Inválido no Nome do Arquivo",
                f"O CNPJ no nome do arquivo  →  {_fn_cnpj}\n"
                f"CNPJ da empresa logada     →  {cnpj_empresa}\n\n"
                "Os CNPJs não coincidem. Download cancelado.",
            )
            return

        # Token mínimo
        if not token:
            QMessageBox.critical(
                self,
                "Token ausente",
                "Token de autorização não configurado. Verifique o arquivo licenca.key.",
            )
            return

        # Pasta de destino
        dest_dir  = AppConfig.get_contagens_path()
        filename  = nome_arquivo if nome_arquivo else os.path.basename(url_arquivo.split("?")[0])
        if not filename.lower().endswith(".zip"):
            filename += ".zip"
        dest_path = os.path.join(dest_dir, filename)

        self._lbl_contagens_status.setText(f"⬇️  Baixando {filename}...")
        QApplication.processEvents()

        api = ApiService(
            base_url=AppConfig.get_api_url(),
            authorization=token,
        )
        ok, msg = api.download_contagem_file(url_arquivo, dest_path)

        if not ok:
            self._lbl_contagens_status.setText(f"❌  Erro no download: {msg}")
            # Se for 404, o arquivo foi perdido no servidor (filesystem efêmero do Render).
            # Oferece remover o registro inválido do banco para não poluir a lista.
            is_404 = "(404)" in msg
            if is_404:
                resp_del = QMessageBox.question(
                    self,
                    "Erro no Download",
                    f"{msg}\n\nDeseja remover este registro inválido do banco de dados?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if resp_del == QMessageBox.StandardButton.Yes:
                    contagem_id = self._contagens_table.item(row_idx, 0).text() if self._contagens_table.item(row_idx, 0) else None
                    if contagem_id:
                        del_ok, del_msg = api.delete_contagem(contagem_id, database_url=AppConfig.get_api_database_url())
                        if del_ok:
                            self._contagens_table.removeRow(row_idx)
                            self._lbl_contagens_status.setText("🗑️  Registro inválido removido do banco.")
                        else:
                            self._lbl_contagens_status.setText(f"⚠️  Não foi possível remover: {del_msg}")
            else:
                QMessageBox.critical(self, "Erro no Download", msg)
            return

        # ── Validação da assinatura .sig dentro do ZIP ────────────────
        self._lbl_contagens_status.setText("🔍  Validando assinatura do arquivo...")
        QApplication.processEvents()

        # O HMAC do .sig é assinado com o token da licença (campo 'token' do .key
        # = campo 'serial' do payload), NÃO com o token da API HTTP.
        license_token = AppConfig.get_license_token()
        sig_result = ApiService.validate_sig(dest_path, license_token)

        if not sig_result["ok"]:
            try:
                os.remove(dest_path)
            except Exception:
                pass
            erros_txt = "\n".join(
                f"  • {e}" for e in sig_result["erros"]
            )
            self._lbl_contagens_status.setText("❌  Validação da assinatura falhou — arquivo descartado.")
            QMessageBox.critical(
                self,
                "Validação de Assinatura Falhou",
                f"O arquivo não passou na validação de integridade/assinatura:\n\n"
                f"{erros_txt}\n\n"
                "O arquivo foi descartado.",
            )
            return

        # CNPJ vem do payload do .sig
        cnpj_no_arquivo = _normalizar_cnpj(sig_result["payload"].get("cnpj", ""))
        if cnpj_no_arquivo and cnpj_no_arquivo != _normalizar_cnpj(cnpj_empresa):
            try:
                os.remove(dest_path)
            except Exception:
                pass
            self._lbl_contagens_status.setText(
                f"❌  Validação falhou — CNPJ do .sig (" + cnpj_no_arquivo + ") ≠ CNPJ da empresa (" + cnpj_empresa + ")."
            )
            QMessageBox.critical(
                self,
                "Validação de CNPJ Falhou",
                "O CNPJ declarado no .sig         →  " + cnpj_no_arquivo + "\n"
                + "CNPJ da empresa logada           →  " + cnpj_empresa + "\n\n"
                + "Os CNPJs não coincidem. O arquivo foi descartado.",
            )
            return

        # ── Tudo certo ────────────────────────────────────────────────
        self._lbl_contagens_status.setText("✅  Arquivo baixado e assinatura validada: " + dest_path)

        # Apaga o registro do banco Neon
        contagem_id = self._contagens_table.item(row_idx, 0).text() if self._contagens_table.item(row_idx, 0) else None
        if contagem_id:
            self._lbl_contagens_status.setText("🗑️  Removendo registro do servidor...")
            QApplication.processEvents()
            del_ok, del_msg = api.delete_contagem(contagem_id, database_url=AppConfig.get_api_database_url())
            if del_ok:
                self._lbl_contagens_status.setText("✅  Arquivo baixado, assinatura validada e registro removido do servidor.")
                # Remove linha da tabela
                self._contagens_table.removeRow(row_idx)
            else:
                self._lbl_contagens_status.setText("⚠️  Download OK, mas falha ao remover registro: " + del_msg)

        versao_app = sig_result["payload"].get("versao", "")
        msg_ok = (
            "Arquivo baixado e assinatura validada com sucesso!\n\n"
            "📄  " + filename + "\n"
            "📁  " + dest_dir + "\n"
            "CNPJ: " + (cnpj_no_arquivo or cnpj_empresa) + "\n"
            + ("Versão app: " + versao_app + "\n" if versao_app else "")
            + "\nDeseja abrir a pasta Contagens?"
        )
        resp = QMessageBox.question(
            self,
            "Download Concluído",
            msg_ok,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if resp == QMessageBox.StandardButton.Yes:
            try:
                os.startfile(dest_dir)
            except Exception:
                pass

    # =========================================================================
    # Fim: Download Contagens API
    # =========================================================================

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
