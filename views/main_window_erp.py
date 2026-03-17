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
from utils.workers import DataLoaderWorker
from widgets.status_bar import AppStatusBar
from widgets.filter_panel import FilterPanel
from widgets.lazy_product_table import LazyProductTable
from widgets.progress_dialog import ProgressDialog
from services.product_service import ProductService, ProductFilter

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
        
        # Logotipo da aplicação (menor, à esquerda)
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    36, 36,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                logo_label.setPixmap(scaled)
            else:
                logo_label.setText("📦")
                logo_label.setFont(QFont("Segoe UI", 20))
        else:
            logo_label.setText("📦")
            logo_label.setFont(QFont("Segoe UI", 20))
        
        logo_label.setStyleSheet("background: transparent;")
        layout.addWidget(logo_label)
        
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


class QuickStatsCard(QFrame):
    """Card de estatísticas rápidas."""
    
    def __init__(self, icon: str, title: str, value: str, color: str = "#0078d4", parent=None):
        super().__init__(parent)
        self._setup_ui(icon, title, value, color)
    
    def _setup_ui(self, icon: str, title: str, value: str, color: str):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                border-left: 4px solid {color};
            }}
        """)
        self.setMinimumSize(200, 90)
        self.setMaximumHeight(90)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Ícone
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 24))
        icon_label.setStyleSheet(f"color: {color}; background: transparent;")
        layout.addWidget(icon_label)
        
        # Textos
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #9d9d9d; font-size: 10pt; background: transparent;")
        text_layout.addWidget(title_label)
        
        self._value_label = QLabel(value)
        self._value_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self._value_label.setStyleSheet(f"color: {color}; background: transparent;")
        text_layout.addWidget(self._value_label)
        
        layout.addLayout(text_layout)
        layout.addStretch()
    
    def set_value(self, value: str):
        """Atualiza valor."""
        self._value_label.setText(value)


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
    MODULE_DASHBOARD = "dashboard"
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
        self._connection_info = {}
        
        # Serviços e Workers
        self._product_service = ProductService()
        self._load_worker: Optional[DataLoaderWorker] = None
        
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
        
        # Cria páginas dos módulos
        self._create_dashboard_page()
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
        
        # Logo/Header
        header = QFrame()
        header.setMinimumHeight(70)
        header.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-bottom: 1px solid #3e3e42;
                border-right: none;
            }
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.setContentsMargins(0, 4, 0, 4)
        header_layout.setSpacing(4)
        
        # Logotipo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    48, 48,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                logo_label.setPixmap(scaled)
            else:
                logo_label.setText("📦")
                logo_label.setFont(QFont("Segoe UI", 24))
        else:
            logo_label.setText("📦")
            logo_label.setFont(QFont("Segoe UI", 24))
        
        logo_label.setStyleSheet("background: transparent;")
        header_layout.addWidget(logo_label)
        
        # Nome da aplicação
        name_label = QLabel(APP_INFO.NAME)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #0078d4; background: transparent;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(name_label)
        
        version_label = QLabel(f"v{APP_INFO.VERSION}")
        version_label.setStyleSheet("color: #666666; font-size: 8pt; background: transparent;")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(version_label)
        
        layout.addWidget(header)
        
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
            (self.MODULE_DASHBOARD, "🏠", "Dashboard"),
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
        
        # Seção inferior
        section_label2 = QLabel("  SISTEMA")
        section_label2.setStyleSheet("color: #666666; font-size: 9pt; font-weight: bold; padding: 8px 0;")
        nav_layout.addWidget(section_label2)
        
        btn_settings = SidebarButton("⚙️", "Configurações")
        btn_settings.clicked.connect(lambda: self._switch_module(self.MODULE_SETTINGS))
        nav_layout.addWidget(btn_settings)
        self._sidebar_buttons[self.MODULE_SETTINGS] = btn_settings
        
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
    
    def _create_dashboard_page(self):
        """Cria página do dashboard."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = ModuleHeader("🏠", "Dashboard", "Visão geral do sistema")
        layout.addWidget(header)
        
        # Conteúdo
        content = QWidget()
        content.setStyleSheet("background-color: #1e1e1e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)
        
        # Cards de estatísticas
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self._card_products = QuickStatsCard("📦", "Produtos Ativos", "0", "#4caf50")
        stats_layout.addWidget(self._card_products)
        
        self._card_exports = QuickStatsCard("📤", "Exportações Hoje", "0", "#2196f3")
        stats_layout.addWidget(self._card_exports)
        
        self._card_photos = QuickStatsCard("📷", "Fotos Cadastradas", "0", "#ff9800")
        stats_layout.addWidget(self._card_photos)
        
        self._card_pending = QuickStatsCard("⏳", "Pendentes", "0", "#f44336")
        stats_layout.addWidget(self._card_pending)
        
        stats_layout.addStretch()
        content_layout.addLayout(stats_layout)
        
        # Ações rápidas
        actions_group = QGroupBox("⚡ Ações Rápidas")
        actions_group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
            }
        """)
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setContentsMargins(16, 24, 16, 16)
        actions_layout.setSpacing(12)
        
        btn_new_export = self._create_action_card("📤", "Nova Exportação", "Exportar carga para coletores")
        btn_new_export.clicked.connect(lambda: self._switch_module(self.MODULE_EXPORT))
        actions_layout.addWidget(btn_new_export)
        
        btn_view_products = self._create_action_card("📦", "Ver Produtos", "Consultar produtos cadastrados")
        btn_view_products.clicked.connect(lambda: self._switch_module(self.MODULE_PRODUCTS))
        actions_layout.addWidget(btn_view_products)
        
        btn_history = self._create_action_card("📋", "Histórico", "Ver exportações anteriores")
        btn_history.clicked.connect(lambda: self._switch_module(self.MODULE_HISTORY))
        actions_layout.addWidget(btn_history)
        
        actions_layout.addStretch()
        content_layout.addWidget(actions_group)
        
        content_layout.addStretch()
        layout.addWidget(content)
        
        self._module_stack.addWidget(page)
        self._pages = {self.MODULE_DASHBOARD: self._module_stack.count() - 1}
    
    def _create_action_card(self, icon: str, title: str, description: str) -> QPushButton:
        """Cria card de ação clicável."""
        btn = QPushButton()
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setMinimumSize(200, 100)
        btn.setMaximumSize(250, 120)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                text-align: left;
                padding: 16px;
            }
            QPushButton:hover {
                background-color: #2d2d30;
                border-color: #0078d4;
            }
        """)
        
        btn_layout = QVBoxLayout(btn)
        btn_layout.setSpacing(8)
        
        icon_label = QLabel(f"{icon} {title}")
        icon_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        icon_label.setStyleSheet("color: #ffffff;")
        btn_layout.addWidget(icon_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #9d9d9d; font-size: 9pt;")
        desc_label.setWordWrap(True)
        btn_layout.addWidget(desc_label)
        
        return btn
    
    def _create_products_page(self):
        """Cria página de produtos."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = ModuleHeader("📦", "Produtos", "Consulta e seleção de produtos para exportação")
        self._btn_refresh = header.add_action_button("Atualizar", "🔄")
        self._btn_export_selected = header.add_action_button("Exportar Selecionados", "📤", primary=True)
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
        
        # Opções de exportação
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
        
        # Checkboxes de opções
        from PySide6.QtWidgets import QCheckBox, QRadioButton, QButtonGroup
        
        self._chk_export_txt = QCheckBox("Exportar arquivo TXT de carga")
        self._chk_export_txt.setChecked(True)
        self._chk_export_txt.setStyleSheet("color: #cccccc;")
        options_layout.addWidget(self._chk_export_txt, 0, 0)
        
        self._chk_export_photos = QCheckBox("Incluir fotos dos produtos (ZIP)")
        self._chk_export_photos.setStyleSheet("color: #cccccc;")
        options_layout.addWidget(self._chk_export_photos, 0, 1)
        
        self._chk_compress = QCheckBox("Compactar arquivo final")
        self._chk_compress.setStyleSheet("color: #cccccc;")
        options_layout.addWidget(self._chk_compress, 1, 0)
        
        content_layout.addWidget(export_options)
        
        # Resumo
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
        
        self._lbl_export_summary = QLabel("Selecione produtos na aba 'Produtos' para exportar.")
        self._lbl_export_summary.setStyleSheet("color: #9d9d9d; font-size: 11pt; padding: 16px;")
        summary_layout.addWidget(self._lbl_export_summary)
        
        content_layout.addWidget(summary_group)
        
        # Botões de ação
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumSize(120, 40)
        btn_cancel.clicked.connect(lambda: self._switch_module(self.MODULE_PRODUCTS))
        action_layout.addWidget(btn_cancel)
        
        self._btn_start_export = QPushButton("📤  Iniciar Exportação")
        self._btn_start_export.setMinimumSize(180, 40)
        self._btn_start_export.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
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
        
        action_export = QAction("Exportar Selecionados", self)
        action_export.setShortcut(Shortcuts.EXPORT)
        action_export.triggered.connect(self._on_export_selected)
        menu_file.addAction(action_export)
        
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
        
        action_dashboard = QAction("Dashboard", self)
        action_dashboard.triggered.connect(lambda: self._switch_module(self.MODULE_DASHBOARD))
        menu_view.addAction(action_dashboard)
        
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
        # Botões do header de produtos
        self._btn_refresh.clicked.connect(self._on_refresh)
        self._btn_export_selected.clicked.connect(self._on_export_selected)
        
        # Filter panel
        self._filter_panel.select_clicked.connect(self._on_apply_filters)
        self._filter_panel.clear_clicked.connect(self._on_clear_filters)
        self._filter_panel.export_clicked.connect(self._on_export_selected)
        
        # Product table
        self._product_table.export_requested.connect(self._on_export_products)
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
        
        self._lbl_user_name.setText(usuario_nome)
        self._lbl_company.setText(empresa_nome)
        
        # Status bar
        self._status_bar.set_user(usuario_nome, empresa_nome)
        self._status_bar.set_connected(servidor)
        self._status_bar.set_database_info(database, cnpj)
        
        self.setWindowTitle(f"{APP_INFO.NAME} - {empresa_nome}")
        
        logger.info(f"Conexão configurada: {empresa_nome} / {usuario_nome}")
    
    def update_statistics(self, products: int, exports: int, photos: int, pending: int):
        """Atualiza estatísticas do dashboard."""
        self._card_products.set_value(f"{products:,}")
        self._card_exports.set_value(f"{exports:,}")
        self._card_photos.set_value(f"{photos:,}")
        self._card_pending.set_value(f"{pending:,}")
    
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
            filters: Dicionário de filtros
            
        Returns:
            ProductFilter configurado
        """
        return ProductFilter(
            produtos=filters.get("produtos") or None,
            grupos=filters.get("grupos") or None,
            fornecedor=filters.get("fornecedor") or None,
            fabricante=filters.get("fabricante") or None,
            localizacoes=filters.get("localizacoes") or None,
            tipos_produto=filters.get("tipos_produto") or None,
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
        logger.info("Atualizando dados")
        self.load_products(filters)
    
    def _on_select_all(self):
        """Seleciona todos os produtos."""
        self._product_table._select_all()
    
    def _on_export_selected(self):
        """Exporta produtos selecionados."""
        codprodutos = self._product_table.get_selected_codprodutos()
        if not codprodutos:
            QMessageBox.warning(self, "Aviso", "Selecione produtos para exportar.")
            return
        self._switch_module(self.MODULE_EXPORT)
        self._lbl_export_summary.setText(
            f"✅ {len(codprodutos):,} produtos selecionados para exportação."
        )
    
    def _on_export_products(self, codprodutos: List[int]):
        """Exporta lista de produtos."""
        logger.info(f"Exportando {len(codprodutos)} produtos")
        self.export_requested.emit({"codprodutos": codprodutos})
    
    def _on_export_photos(self, codprodutos: List[int]):
        """Exporta fotos."""
        logger.info(f"Exportando fotos de {len(codprodutos)} produtos")
    
    def _on_start_export(self):
        """Inicia exportação."""
        if self._chk_export_txt.isChecked():
            self._status_bar.show_progress("Exportando carga...", cancelable=True)
        
        if self._chk_export_photos.isChecked():
            self._status_bar.show_info("Exportação de fotos incluída")
    
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
    window.update_statistics(
        products=45230,
        exports=12,
        photos=8450,
        pending=3
    )
    window.show()
    
    sys.exit(app.exec())
