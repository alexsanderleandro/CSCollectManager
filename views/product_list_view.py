"""
product_list_view.py
====================
Widget de listagem de produtos usando QTableView.
Otimizado para alta performance com milhares de registros.
"""

from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QHeaderView, QLabel, QLineEdit, QPushButton,
    QFrame, QAbstractItemView, QMenu, QComboBox
)
from PySide6.QtCore import Qt, Signal, Slot, QModelIndex, QTimer
from PySide6.QtGui import QFont, QAction, QKeySequence

from models.product_table_model import (
    ProductTableModel, 
    ProductSortFilterProxyModel,
    ProductData
)


class ProductListView(QWidget):
    """
    Widget de listagem de produtos com QTableView.
    
    Features:
    - Ordenação por código do produto e código do grupo
    - Filtro de busca rápida
    - Alta performance com milhares de registros
    - Seleção múltipla
    - Menu de contexto
    
    Signals:
        row_selected: Emitido quando linha é selecionada (ProductData)
        row_double_clicked: Emitido em duplo clique (ProductData)
        selection_changed: Emitido quando seleção muda (lista de códigos)
    """
    
    row_selected = Signal(object)  # ProductData
    row_double_clicked = Signal(object)  # ProductData
    selection_changed = Signal(list)  # Lista de códigos
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Modelo e proxy
        self._model = ProductTableModel(self)
        self._proxy_model = ProductSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._model)
        
        # Timer para debounce do filtro
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter)
        
        self._setup_ui()
        self._connect_signals()
        self._apply_theme()
    
    def _setup_ui(self):
        """Configura interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # ===== TOOLBAR =====
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 10, 15, 10)
        toolbar_layout.setSpacing(15)
        
        # Título e contadores
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        
        title = QLabel("Produtos")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setObjectName("title")
        title_layout.addWidget(title)
        
        self.lbl_count = QLabel("0 produtos")
        self.lbl_count.setObjectName("count_label")
        title_layout.addWidget(self.lbl_count)
        
        toolbar_layout.addWidget(title_container)
        toolbar_layout.addStretch()
        
        # Ordenação
        lbl_order = QLabel("Ordenar por:")
        lbl_order.setObjectName("order_label")
        toolbar_layout.addWidget(lbl_order)
        
        self.cmb_order = QComboBox()
        self.cmb_order.addItem("Cód. produto", "codproduto")
        self.cmb_order.addItem("Cód. grupo", "codgrupo")
        self.cmb_order.addItem("Descrição", "descricaoproduto")
        self.cmb_order.addItem("Grupo", "nomegrupo")
        self.cmb_order.addItem("Data validade", "datavalidade")
        self.cmb_order.setMinimumWidth(150)
        self.cmb_order.setObjectName("order_combo")
        toolbar_layout.addWidget(self.cmb_order)
        
        self.btn_order_asc = QPushButton("↑")
        self.btn_order_asc.setToolTip("Ordem Crescente")
        self.btn_order_asc.setFixedWidth(35)
        self.btn_order_asc.setCheckable(True)
        self.btn_order_asc.setChecked(True)
        self.btn_order_asc.setObjectName("order_btn")
        toolbar_layout.addWidget(self.btn_order_asc)
        
        self.btn_order_desc = QPushButton("↓")
        self.btn_order_desc.setToolTip("Ordem Decrescente")
        self.btn_order_desc.setFixedWidth(35)
        self.btn_order_desc.setCheckable(True)
        self.btn_order_desc.setObjectName("order_btn")
        toolbar_layout.addWidget(self.btn_order_desc)
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("separator")
        toolbar_layout.addWidget(sep)
        
        # Busca
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar produto... (Ctrl+F)")
        self.txt_search.setMinimumWidth(250)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setObjectName("search_input")
        toolbar_layout.addWidget(self.txt_search)
        
        layout.addWidget(toolbar)
        
        # ===== TABELA =====
        self.table_view = QTableView()
        self.table_view.setModel(self._proxy_model)
        self.table_view.setObjectName("product_table")
        
        # Configurações da tabela
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.setShowGrid(False)
        self.table_view.setWordWrap(False)
        
        # Cabeçalho horizontal
        h_header = self.table_view.horizontalHeader()
        h_header.setStretchLastSection(False)
        h_header.setSectionsClickable(True)
        h_header.setSortIndicatorShown(True)
        h_header.setHighlightSections(False)
        h_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Define larguras das colunas
        for i in range(self._model.columnCount()):
            width = self._model.get_column_width(i)
            if self._model.get_column_key(i) == "descricaoproduto":
                h_header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                self.table_view.setColumnWidth(i, width)
        
        # Cabeçalho vertical
        v_header = self.table_view.verticalHeader()
        v_header.setVisible(False)
        v_header.setDefaultSectionSize(28)
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        layout.addWidget(self.table_view)
        
        # ===== STATUS BAR =====
        status_bar = QFrame()
        status_bar.setObjectName("status_bar")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(15, 5, 15, 5)
        
        self.lbl_status = QLabel("Pronto")
        self.lbl_status.setObjectName("status_label")
        status_layout.addWidget(self.lbl_status)
        
        status_layout.addStretch()
        
        self.lbl_selection = QLabel("")
        self.lbl_selection.setObjectName("selection_label")
        status_layout.addWidget(self.lbl_selection)
        
        layout.addWidget(status_bar)
        
        # Ordenação inicial por código
        self._proxy_model.sort(0, Qt.SortOrder.AscendingOrder)
    
    def _connect_signals(self):
        """Conecta sinais."""
        # Busca com debounce
        self.txt_search.textChanged.connect(self._on_search_changed)
        
        # Ordenação
        self.cmb_order.currentIndexChanged.connect(self._on_order_changed)
        self.btn_order_asc.clicked.connect(self._on_order_asc)
        self.btn_order_desc.clicked.connect(self._on_order_desc)
        
        # Tabela
        self.table_view.clicked.connect(self._on_row_clicked)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        
        # Seleção
        selection_model = self.table_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
        
        # Dados
        self._model.data_changed.connect(self._update_counts)
        
        # Atalho de teclado
        self.txt_search.setShortcutEnabled(True)
    
    def _apply_theme(self):
        """Aplica tema escuro."""
        self.setStyleSheet("""
            QWidget {
                font-family: "Segoe UI", sans-serif;
            }
            
            #toolbar {
                background-color: #2d2d30;
                border-bottom: 1px solid #3e3e42;
            }
            
            #title {
                color: #ffffff;
            }
            
            #count_label, #order_label {
                color: #888888;
                font-size: 11px;
            }
            
            #order_combo {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 10px;
                color: #ffffff;
                min-height: 28px;
            }
            
            #order_combo:hover {
                border-color: #0078d4;
            }
            
            #order_combo::drop-down {
                border: none;
                width: 20px;
            }
            
            #order_combo QAbstractItemView {
                background-color: #2d2d30;
                color: #ffffff;
                selection-background-color: #094771;
            }
            
            #order_btn {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 4px;
                color: #cccccc;
                font-weight: bold;
                min-height: 28px;
            }
            
            #order_btn:hover {
                background-color: #505050;
            }
            
            #order_btn:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            
            #separator {
                color: #3e3e42;
            }
            
            #search_input {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            
            #search_input:focus {
                border-color: #0078d4;
            }
            
            #product_table {
                background-color: #1e1e1e;
                alternate-background-color: #252526;
                border: none;
                color: #cccccc;
                font-size: 12px;
            }
            
            #product_table::item {
                padding: 5px;
                border-bottom: 1px solid #2d2d30;
            }
            
            #product_table::item:selected {
                background-color: #094771;
            }
            
            #product_table::item:hover:!selected {
                background-color: #2a2d2e;
            }
            
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-right: 1px solid #3e3e42;
                border-bottom: 1px solid #3e3e42;
            }
            
            QHeaderView::section:hover {
                background-color: #3e3e42;
            }
            
            QHeaderView::section:pressed {
                background-color: #094771;
            }
            
            #status_bar {
                background-color: #007acc;
            }
            
            #status_label, #selection_label {
                color: white;
                font-size: 11px;
            }
            
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border: none;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3e3e42;
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border: none;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #3e3e42;
                border-radius: 6px;
                min-width: 20px;
                margin: 2px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            QMenu {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #444;
            }
            
            QMenu::item:selected {
                background-color: #094771;
            }
        """)
    
    # ===== SLOTS =====
    
    @Slot(str)
    def _on_search_changed(self, text: str):
        """Callback quando texto de busca muda."""
        # Debounce de 300ms para performance
        self._filter_timer.stop()
        self._filter_timer.start(300)
    
    @Slot()
    def _apply_filter(self):
        """Aplica filtro de busca."""
        text = self.txt_search.text()
        self._proxy_model.set_filter_text(text)
        self._update_counts()
        
        if text:
            self.lbl_status.setText(f"Filtro aplicado: '{text}'")
        else:
            self.lbl_status.setText("Pronto")
    
    @Slot(int)
    def _on_order_changed(self, index: int):
        """Callback quando ordenação muda."""
        column_key = self.cmb_order.currentData()
        column_index = self._get_column_index(column_key)
        
        if column_index >= 0:
            order = Qt.SortOrder.AscendingOrder if self.btn_order_asc.isChecked() else Qt.SortOrder.DescendingOrder
            self._proxy_model.sort(column_index, order)
    
    @Slot()
    def _on_order_asc(self):
        """Ordenação crescente."""
        self.btn_order_asc.setChecked(True)
        self.btn_order_desc.setChecked(False)
        self._on_order_changed(self.cmb_order.currentIndex())
    
    @Slot()
    def _on_order_desc(self):
        """Ordenação decrescente."""
        self.btn_order_asc.setChecked(False)
        self.btn_order_desc.setChecked(True)
        self._on_order_changed(self.cmb_order.currentIndex())
    
    @Slot(QModelIndex)
    def _on_row_clicked(self, index: QModelIndex):
        """Callback ao clicar em linha."""
        source_index = self._proxy_model.mapToSource(index)
        product = self._model.get_product(source_index.row())
        if product:
            self.row_selected.emit(product)
    
    @Slot(QModelIndex)
    def _on_row_double_clicked(self, index: QModelIndex):
        """Callback ao dar duplo clique."""
        source_index = self._proxy_model.mapToSource(index)
        product = self._model.get_product(source_index.row())
        if product:
            self.row_double_clicked.emit(product)
    
    @Slot()
    def _on_selection_changed(self):
        """Callback quando seleção muda."""
        selected_codes = self.get_selected_codes()
        count = len(selected_codes)
        
        if count > 0:
            self.lbl_selection.setText(f"{count} selecionado(s)")
        else:
            self.lbl_selection.setText("")
        
        self.selection_changed.emit(selected_codes)
    
    def _show_context_menu(self, pos):
        """Mostra menu de contexto."""
        menu = QMenu(self)
        
        action_select_all = QAction("Selecionar Todos", self)
        action_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        action_select_all.triggered.connect(self.table_view.selectAll)
        menu.addAction(action_select_all)
        
        action_deselect = QAction("Limpar Seleção", self)
        action_deselect.triggered.connect(self.table_view.clearSelection)
        menu.addAction(action_deselect)
        
        menu.addSeparator()
        
        action_copy = QAction("Copiar", self)
        action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        action_copy.triggered.connect(self._copy_selection)
        menu.addAction(action_copy)
        
        menu.exec(self.table_view.mapToGlobal(pos))
    
    @Slot()
    def _update_counts(self):
        """Atualiza contadores."""
        total = self._model.rowCount()
        filtered = self._proxy_model.rowCount()
        
        if filtered < total:
            self.lbl_count.setText(f"{filtered} de {total} produtos")
        else:
            self.lbl_count.setText(f"{total} produtos")
    
    def _get_column_index(self, column_key: str) -> int:
        """Retorna índice da coluna pela chave."""
        for i in range(self._model.columnCount()):
            if self._model.get_column_key(i) == column_key:
                return i
        return -1
    
    def _copy_selection(self):
        """Copia seleção para clipboard."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QMimeData
        
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
        
        lines = []
        for index in indexes:
            source_index = self._proxy_model.mapToSource(index)
            product = self._model.get_product(source_index.row())
            if product:
                lines.append(f"{product.codproduto}\t{product.descricaoproduto}")
        
        text = "\n".join(lines)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
    
    # ===== MÉTODOS PÚBLICOS =====
    
    def set_products(self, products: List[Dict[str, Any]]):
        """
        Define lista de produtos.
        
        Args:
            products: Lista de dicionários com dados dos produtos
        """
        self._model.set_data(products)
        self.lbl_status.setText(f"{len(products)} produtos carregados")
    
    def append_products(self, products: List[Dict[str, Any]]):
        """
        Adiciona produtos (carregamento incremental).
        
        Args:
            products: Lista de dicionários com dados dos produtos
        """
        self._model.append_data(products)
    
    def clear(self):
        """Limpa todos os dados."""
        self._model.clear()
        self.lbl_status.setText("Pronto")
    
    def get_selected_codes(self) -> List[int]:
        """Retorna códigos dos produtos selecionados."""
        indexes = self.table_view.selectionModel().selectedRows()
        codes = []
        
        for index in indexes:
            source_index = self._proxy_model.mapToSource(index)
            product = self._model.get_product(source_index.row())
            if product:
                codes.append(product.codproduto)
        
        return codes
    
    def get_selected_products(self) -> List[ProductData]:
        """Retorna produtos selecionados."""
        indexes = self.table_view.selectionModel().selectedRows()
        products = []
        
        for index in indexes:
            source_index = self._proxy_model.mapToSource(index)
            product = self._model.get_product(source_index.row())
            if product:
                products.append(product)
        
        return products
    
    def select_all(self):
        """Seleciona todos os produtos visíveis."""
        self.table_view.selectAll()
    
    def clear_selection(self):
        """Limpa seleção."""
        self.table_view.clearSelection()
    
    def sort_by_code(self, ascending: bool = True):
        """Ordena por código do produto."""
        order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
        self._proxy_model.sort(0, order)
        self.cmb_order.setCurrentIndex(0)
        self.btn_order_asc.setChecked(ascending)
        self.btn_order_desc.setChecked(not ascending)
    
    def sort_by_group(self, ascending: bool = True):
        """Ordena por código do grupo."""
        order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
        col_index = self._get_column_index("codgrupo")
        if col_index >= 0:
            self._proxy_model.sort(col_index, order)
            self.cmb_order.setCurrentIndex(1)
            self.btn_order_asc.setChecked(ascending)
            self.btn_order_desc.setChecked(not ascending)
    
    def filter(self, text: str):
        """Aplica filtro de texto."""
        self.txt_search.setText(text)
    
    def get_product_count(self) -> int:
        """Retorna total de produtos."""
        return self._model.rowCount()
    
    def get_visible_count(self) -> int:
        """Retorna quantidade de produtos visíveis (após filtro)."""
        return self._proxy_model.rowCount()


# ===== TESTE =====
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from datetime import date, timedelta
    
    app = QApplication(sys.argv)
    
    # Gera dados de teste (milhares de registros)
    test_data = []
    for i in range(5000):
        grupo = (i % 10) + 1
        test_data.append({
            "codproduto": i + 1,
            "descricaoproduto": f"Produto de Teste {i + 1:05d} - Descrição Completa",
            "codeanunidade": f"789{i:010d}",
            "codgrupo": grupo,
            "nomegrupo": f"Grupo {grupo:02d}",
            "nomeLocalEstoque": f"Local {(i % 5) + 1}",
            "numlote": f"LT{i:06d}" if i % 3 == 0 else "",
            "datafabricacao": date.today() - timedelta(days=30 + (i % 60)),
            "datavalidade": date.today() + timedelta(days=(i % 90) - 10),
        })
    
    widget = ProductListView()
    widget.resize(1200, 700)
    widget.setWindowTitle("Listagem de Produtos - Teste de Performance")
    
    # Carrega dados
    widget.set_products(test_data)
    
    # Conecta sinais
    widget.row_double_clicked.connect(
        lambda p: print(f"Duplo clique: {p.codproduto} - {p.descricaoproduto}")
    )
    widget.selection_changed.connect(
        lambda codes: print(f"Selecionados: {len(codes)} produtos")
    )
    
    widget.show()
    sys.exit(app.exec())
