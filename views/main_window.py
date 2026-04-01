"""
main_window.py
==============
Janela principal do sistema CSCollectManager.
Layout profissional estilo ERP com painel de filtros e tabela de produtos.
"""

import sys
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMenuBar, QMenu, QToolBar,
    QLabel, QFrame, QMessageBox, QProgressBar, QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont, QAction, QIcon, QCloseEvent

from widgets.filter_panel import FilterPanel
from widgets.product_table import ProductTable


class MainWindow(QMainWindow):
    """
    Janela principal do sistema CSCollectManager.
    
    Signals:
        logout_requested: Emitido quando usuário solicita logout
        export_requested: Emitido quando inicia exportação
    """
    
    logout_requested = Signal()
    export_requested = Signal(dict)  # Filtros e seleção
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Informações de conexão (serão definidas após login)
        self._empresa_nome: str = ""
        self._usuario_nome: str = ""
        self._database_name: str = ""
        
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        
        # Configurações da janela
        self.setWindowTitle("CSCollectManager - Exportação de Carga")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Aplica tema escuro
        self._apply_theme()
    
    def _setup_ui(self):
        """Configura interface principal."""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter para layout redimensionável
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3e3e42;
            }
            QSplitter::handle:hover {
                background-color: #0078d4;
            }
        """)
        
        # ===== PAINEL DE FILTROS (ESQUERDA) =====
        self.filter_panel = FilterPanel()
        self.filter_panel.setMinimumWidth(280)
        self.filter_panel.setMaximumWidth(450)
        self.splitter.addWidget(self.filter_panel)
        
        # ===== ÁREA PRINCIPAL (DIREITA) =====
        main_area = QWidget()
        main_area_layout = QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(0, 0, 0, 0)
        main_area_layout.setSpacing(0)
        
        # Header da área principal
        header = self._create_header()
        main_area_layout.addWidget(header)
        
        # Tabela de produtos
        self.product_table = ProductTable()
        main_area_layout.addWidget(self.product_table)
        
        self.splitter.addWidget(main_area)
        
        # Define proporções iniciais (filtro: 25%, tabela: 75%)
        self.splitter.setSizes([350, 1050])
        
        main_layout.addWidget(self.splitter)
    
    def _create_header(self) -> QFrame:
        """Cria header da área principal."""
        header = QFrame()
        header.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #333;")
        header.setMinimumHeight(60)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Título
        title = QLabel("Exportação de Carga para Coletores")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; border: none;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Informações da conexão
        info_container = QWidget()
        info_container.setStyleSheet("border: none;")
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        self.lbl_empresa = QLabel("Empresa: -")
        self.lbl_empresa.setStyleSheet("color: #aaa; font-size: 11px;")
        info_layout.addWidget(self.lbl_empresa, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.lbl_usuario = QLabel("Usuário: -")
        self.lbl_usuario.setStyleSheet("color: #aaa; font-size: 11px;")
        info_layout.addWidget(self.lbl_usuario, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(info_container)
        
        return header
    
    def _setup_menus(self):
        """Configura menus."""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 5px;
            }
            QMenuBar::item:selected {
                background-color: #094771;
            }
            QMenu {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
            QMenu::separator {
                height: 1px;
                background-color: #444;
            }
        """)
        
        # Menu Arquivo
        menu_arquivo = menubar.addMenu("&Arquivo")
        
        action_novo = QAction("Nova Exportação", self)
        action_novo.setShortcut("Ctrl+N")
        action_novo.triggered.connect(self._on_new_export)
        menu_arquivo.addAction(action_novo)
        
        menu_arquivo.addSeparator()
        
        action_config = QAction("Configurações...", self)
        action_config.setShortcut("Ctrl+,")
        action_config.triggered.connect(self._on_settings)
        menu_arquivo.addAction(action_config)
        
        menu_arquivo.addSeparator()
        
        action_logout = QAction("Trocar Usuário", self)
        action_logout.triggered.connect(self._on_logout)
        menu_arquivo.addAction(action_logout)
        
        action_sair = QAction("Sair", self)
        action_sair.setShortcut("Ctrl+Q")
        action_sair.triggered.connect(self.close)
        menu_arquivo.addAction(action_sair)
        
        # Menu Editar
        menu_editar = menubar.addMenu("&Editar")
        
        action_select_all = QAction("Selecionar Todos", self)
        action_select_all.setShortcut("Ctrl+A")
        action_select_all.triggered.connect(self.product_table.select_all)
        menu_editar.addAction(action_select_all)
        
        action_deselect = QAction("Desmarcar Todos", self)
        action_deselect.setShortcut("Ctrl+D")
        action_deselect.triggered.connect(self.product_table.deselect_all)
        menu_editar.addAction(action_deselect)
        
        menu_editar.addSeparator()
        
        action_limpar = QAction("Limpar Filtros", self)
        action_limpar.setShortcut("Ctrl+L")
        action_limpar.triggered.connect(self.filter_panel._on_clear_clicked)
        menu_editar.addAction(action_limpar)
        
        # Menu Exportação
        menu_export = menubar.addMenu("E&xportação")
        
        action_exportar = QAction("Exportar Carga", self)
        action_exportar.setShortcut("Ctrl+E")
        action_exportar.triggered.connect(self._on_export)
        menu_export.addAction(action_exportar)
        
        menu_export.addSeparator()
        
        action_historico = QAction("Histórico de Exportações", self)
        action_historico.triggered.connect(self._on_export_history)
        menu_export.addAction(action_historico)
        
        # Menu Ajuda
        menu_ajuda = menubar.addMenu("Aj&uda")
        
        action_docs = QAction("Documentação", self)
        action_docs.setShortcut("F1")
        action_docs.triggered.connect(self._on_docs)
        menu_ajuda.addAction(action_docs)
        
        menu_ajuda.addSeparator()
        
        action_sobre = QAction("Sobre", self)
        action_sobre.triggered.connect(self._on_about)
        menu_ajuda.addAction(action_sobre)
    
    def _setup_toolbar(self):
        """Configura barra de ferramentas."""
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d30;
                border-bottom: 1px solid #444;
                spacing: 5px;
                padding: 5px;
            }
            QToolButton {
                background-color: transparent;
                color: #cccccc;
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #3e3e42;
            }
            QToolButton:pressed {
                background-color: #094771;
            }
        """)
        self.addToolBar(toolbar)
        
        # Ações da toolbar
        action_refresh = QAction("Atualizar", self)
        action_refresh.setStatusTip("Recarregar dados")
        action_refresh.triggered.connect(self._on_refresh)
        toolbar.addAction(action_refresh)
        
        toolbar.addSeparator()
        
        action_filter = QAction("Aplicar Filtros", self)
        action_filter.setStatusTip("Aplicar filtros selecionados")
        action_filter.triggered.connect(self._on_apply_filters)
        toolbar.addAction(action_filter)
        
        action_clear = QAction("Limpar Filtros", self)
        action_clear.setStatusTip("Limpar todos os filtros")
        action_clear.triggered.connect(self.filter_panel._on_clear_clicked)
        toolbar.addAction(action_clear)
        
        toolbar.addSeparator()
        
        action_export = QAction("Exportar", self)
        action_export.setStatusTip("Exportar carga selecionada")
        action_export.triggered.connect(self._on_export)
        toolbar.addAction(action_export)
    
    def _setup_statusbar(self):
        """Configura barra de status."""
        self.statusbar = QStatusBar()
        self.statusbar.setStyleSheet("""
            QStatusBar {
                background-color: #007acc;
                color: white;
            }
            QStatusBar::item {
                border: none;
            }
        """)
        self.setStatusBar(self.statusbar)
        
        # Widgets permanentes
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setMaximumHeight(15)
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e6aa8;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #ffffff;
                border-radius: 3px;
            }
        """)
        self.statusbar.addPermanentWidget(self.progress)
        
        self.lbl_db_info = QLabel("")
        self.lbl_db_info.setStyleSheet("padding-right: 10px;")
        self.statusbar.addPermanentWidget(self.lbl_db_info)
        
        self.statusbar.showMessage("Pronto")
    
    def _connect_signals(self):
        """Conecta sinais."""
        # Filter panel
        self.filter_panel.select_clicked.connect(self._on_apply_filters)
        self.filter_panel.clear_clicked.connect(self._on_filters_cleared)
        
        # Product table
        self.product_table.selection_changed.connect(self._on_selection_changed)
        self.product_table.row_double_clicked.connect(self._on_product_double_click)
    
    def _apply_theme(self):
        """Aplica tema escuro."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                font-family: "Segoe UI", sans-serif;
            }
            QMessageBox {
                background-color: #2d2d30;
            }
            QMessageBox QLabel {
                color: #cccccc;
            }
        """)
    
    # ===== MÉTODOS PÚBLICOS =====
    
    def set_connection_info(self, empresa: str, usuario: str, database: str):
        """Define informações da conexão."""
        self._empresa_nome = empresa
        self._usuario_nome = usuario
        self._database_name = database
        
        self.lbl_empresa.setText(f"Empresa: {empresa}")
        self.lbl_usuario.setText(f"Usuário: {usuario}")
        self.lbl_db_info.setText(f"DB: {database}")
        self.setWindowTitle(f"CSCollectManager - {empresa}")
    
    def load_filter_data(self, **kwargs):
        """Carrega dados nos filtros."""
        self.filter_panel.load_filter_data(**kwargs)
    
    def load_products(self, products: list):
        """Carrega produtos na tabela."""
        self.product_table.load_products(products)
    
    def show_progress(self, visible: bool = True, value: int = 0, maximum: int = 100):
        """Mostra/esconde barra de progresso."""
        self.progress.setVisible(visible)
        self.progress.setMaximum(maximum)
        self.progress.setValue(value)
    
    def set_status(self, message: str):
        """Define mensagem da status bar."""
        self.statusbar.showMessage(message)
    
    # ===== SLOTS =====
    
    @Slot()
    def _on_new_export(self):
        """Nova exportação."""
        self.filter_panel._on_clear_clicked()
        self.product_table.deselect_all()
        self.set_status("Nova exportação iniciada")
    
    @Slot()
    def _on_settings(self):
        """Abre configurações."""
        QMessageBox.information(
            self, "Configurações", 
            "Diálogo de configurações será implementado."
        )
    
    @Slot()
    def _on_logout(self):
        """Solicita logout."""
        reply = QMessageBox.question(
            self, "Trocar Usuário",
            "Deseja trocar de usuário?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()
    
    @Slot()
    def _on_refresh(self):
        """Atualiza dados."""
        self.set_status("Atualizando dados...")
        # Será conectado ao controller
    
    @Slot()
    def _on_apply_filters(self):
        """Aplica filtros selecionados."""
        filters = self.filter_panel.get_filters()
        self.set_status("Aplicando filtros...")
        # Será conectado ao controller
    
    @Slot()
    def _on_filters_cleared(self):
        """Callback quando filtros são limpos."""
        self.set_status("Filtros limpos")
    
    @Slot()
    def _on_export(self):
        """Inicia exportação."""
        selected = self.product_table.get_selected_codes()
        
        if not selected:
            QMessageBox.warning(
                self, "Exportação",
                "Selecione pelo menos um produto para exportar."
            )
            return
        
        reply = QMessageBox.question(
            self, "Exportar Carga",
            f"Confirma exportação de {len(selected)} produto(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            filters = self.filter_panel.get_filters()
            filters["selected_codes"] = selected
            self.export_requested.emit(filters)
    
    @Slot()
    def _on_export_history(self):
        """Mostra histórico de exportações."""
        QMessageBox.information(
            self, "Histórico",
            "Histórico de exportações será implementado."
        )
    
    @Slot()
    def _on_docs(self):
        """Abre documentação."""
        QMessageBox.information(
            self, "Documentação",
            "Documentação online será implementada."
        )
    
    @Slot()
    def _on_about(self):
        """Mostra sobre."""
        QMessageBox.about(
            self, "Sobre CSCollectManager",
            "<h3>CSCollectManager</h3>"
            "<p>Sistema de exportação de carga para CSCollect</p>"
            "<p>Versão 1.0.0</p>"
            "<p>© 2026 CEOsoftware</p>"
        )
    
    @Slot(list)
    def _on_selection_changed(self, selected: list):
        """Callback quando seleção muda."""
        count = len(selected)
        self.set_status(f"{count} produto(s) selecionado(s)")
    
    @Slot(dict)
    def _on_product_double_click(self, product: dict):
        """Callback ao dar duplo clique em produto."""
        # Mostra detalhes do produto
        msg = (
            f"<b>Código:</b> {product.get('codigo')}<br>"
            f"<b>Descrição:</b> {product.get('descricao')}<br>"
            f"<b>Referência:</b> {product.get('referencia', '-')}<br>"
            f"<b>Grupo:</b> {product.get('grupo_nome', '-')}<br>"
            f"<b>Estoque:</b> {product.get('estoque', 0)}"
        )
        QMessageBox.information(self, "Detalhes do Produto", msg)
    
    # ===== EVENTOS =====
    
    def closeEvent(self, event: QCloseEvent):
        """Evento de fechamento."""
        reply = QMessageBox.question(
            self, "Sair",
            "Deseja realmente sair do sistema?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


# ===== PONTO DE ENTRADA PARA TESTE =====
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Dados de teste
    test_products = [
        {
            "codigo": 1,
            "referencia": "REF001",
            "descricao": "Produto Teste 1",
            "grupo_nome": "Bebidas",
            "unidade": "UN",
            "estoque": 150.5,
            "custo": 10.50,
            "venda": 15.90,
            "localizacao": "A1-01"
        },
        {
            "codigo": 2,
            "referencia": "REF002",
            "descricao": "Produto Teste 2",
            "grupo_nome": "Alimentos",
            "unidade": "KG",
            "estoque": -5,
            "custo": 25.00,
            "venda": 45.00,
            "localizacao": "B2-03"
        },
        {
            "codigo": 3,
            "referencia": "REF003",
            "descricao": "Produto Teste 3",
            "grupo_nome": "Limpeza",
            "unidade": "UN",
            "estoque": 0,
            "custo": 8.00,
            "venda": 12.50,
            "localizacao": ""
        },
    ]
    
    window = MainWindow()
    window.set_connection_info("Empresa Demo", "admin", "DBDemo")
    window.load_products(test_products)
    
    # Carrega dados de teste nos filtros
    window.load_filter_data(
        grupos=[(1, "Bebidas"), (2, "Alimentos"), (3, "Limpeza")],
        tipos_produto=[(1, "Revenda"), (2, "Consumo")],
    )
    
    window.show()
    sys.exit(app.exec())
