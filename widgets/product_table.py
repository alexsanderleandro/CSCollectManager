"""
product_table.py
================
Tabela de produtos com seleção para exportação.
"""

from typing import Optional, List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QLineEdit,
    QCheckBox, QPushButton, QFrame, QAbstractItemView,
    QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QBrush, QAction


class ProductTable(QWidget):
    """
    Tabela de produtos com funcionalidades de seleção.
    
    Signals:
        selection_changed: Emitido quando seleção muda
        row_double_clicked: Emitido ao dar duplo clique
    """
    
    selection_changed = Signal(list)  # Lista de códigos selecionados
    row_double_clicked = Signal(dict)  # Dados do produto
    
    # Colunas da tabela
    COLUMNS = [
        ("sel", "✓", 40),
        ("codigo", "Código", 80),
        ("referencia", "Referência", 100),
        ("descricao", "Descrição", 300),
        ("grupo", "Grupo", 120),
        ("unidade", "Un.", 50),
        ("estoque", "Estoque", 80),
        ("custo", "Custo", 100),
        ("venda", "Venda", 100),
        ("localizacao", "Localização", 120),
    ]
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._products: List[Dict] = []
        self._selected_codes: set = set()
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configura interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # ===== BARRA DE FERRAMENTAS =====
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #2d2d30;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(15, 10, 15, 10)
        
        # Título e contador
        title = QLabel("Produtos")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        toolbar_layout.addWidget(title)
        
        self.lbl_count = QLabel("0 produtos | 0 selecionados")
        self.lbl_count.setStyleSheet("color: #888;")
        toolbar_layout.addWidget(self.lbl_count)
        
        toolbar_layout.addStretch()
        
        # Busca rápida
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Busca rápida...")
        self.txt_search.setMinimumWidth(250)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        toolbar_layout.addWidget(self.txt_search)
        
        # Botão selecionar todos
        self.btn_select_all = QPushButton("Selecionar Todos")
        self.btn_select_all.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        toolbar_layout.addWidget(self.btn_select_all)
        
        # Botão desmarcar todos
        self.btn_deselect_all = QPushButton("Desmarcar Todos")
        self.btn_deselect_all.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #ccc;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        toolbar_layout.addWidget(self.btn_deselect_all)
        
        layout.addWidget(toolbar)
        
        # ===== TABELA =====
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        
        # Configura cabeçalhos
        headers = [col[1] for col in self.COLUMNS]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Configura larguras
        header = self.table.horizontalHeader()
        for i, col in enumerate(self.COLUMNS):
            if col[0] == "descricao":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                self.table.setColumnWidth(i, col[2])
        
        # Configurações da tabela
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.verticalHeader().setVisible(False)
        
        # Estilo da tabela
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                alternate-background-color: #252526;
                border: none;
                gridline-color: #333;
                color: #cccccc;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #333;
            }
            QTableWidget::item:selected {
                background-color: #094771;
            }
            QTableWidget::item:hover {
                background-color: #2a2d2e;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-right: 1px solid #444;
                border-bottom: 1px solid #444;
            }
            QHeaderView::section:hover {
                background-color: #3e3e42;
            }
        """)
        
        layout.addWidget(self.table)
        
        # ===== STATUS BAR =====
        status_bar = QFrame()
        status_bar.setStyleSheet("background-color: #007acc;")
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(15, 5, 15, 5)
        
        self.lbl_status = QLabel("Pronto")
        self.lbl_status.setStyleSheet("color: white; font-size: 11px;")
        status_layout.addWidget(self.lbl_status)
        
        status_layout.addStretch()
        
        self.lbl_selection_info = QLabel("")
        self.lbl_selection_info.setStyleSheet("color: white; font-size: 11px;")
        status_layout.addWidget(self.lbl_selection_info)
        
        layout.addWidget(status_bar)
    
    def _connect_signals(self):
        """Conecta sinais."""
        self.txt_search.textChanged.connect(self._filter_table)
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_deselect_all.clicked.connect(self.deselect_all)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
    
    def load_products(self, products: List[Dict]):
        """
        Carrega produtos na tabela.
        
        Args:
            products: Lista de dicionários com dados dos produtos
        """
        self._products = products
        self._selected_codes.clear()
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        
        for product in products:
            self._add_row(product)
        
        self.table.setSortingEnabled(True)
        self._update_counts()
        self.lbl_status.setText(f"{len(products)} produtos carregados")
    
    def _add_row(self, product: Dict):
        """Adiciona uma linha à tabela."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Checkbox de seleção
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Unchecked)
        chk_item.setData(Qt.ItemDataRole.UserRole, product.get("codigo"))
        self.table.setItem(row, 0, chk_item)
        
        # Dados do produto
        col_map = {
            1: str(product.get("codigo", "")),
            2: product.get("referencia", ""),
            3: product.get("descricao", ""),
            4: product.get("grupo_nome", ""),
            5: product.get("unidade", ""),
            6: self._format_number(product.get("estoque", 0)),
            7: self._format_currency(product.get("custo", 0)),
            8: self._format_currency(product.get("venda", 0)),
            9: product.get("localizacao", ""),
        }
        
        for col, value in col_map.items():
            item = QTableWidgetItem(value)
            
            # Alinhamento
            if col in [6, 7, 8]:  # Números
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            # Cor do estoque
            if col == 6:
                estoque = product.get("estoque", 0)
                if estoque < 0:
                    item.setForeground(QBrush(QColor("#ff6b6b")))
                elif estoque == 0:
                    item.setForeground(QBrush(QColor("#ffa94d")))
                else:
                    item.setForeground(QBrush(QColor("#69db7c")))
            
            item.setData(Qt.ItemDataRole.UserRole, product.get("codigo"))
            self.table.setItem(row, col, item)
    
    def _on_cell_clicked(self, row: int, col: int):
        """Callback ao clicar em célula."""
        if col == 0:
            item = self.table.item(row, 0)
            if item:
                codigo = item.data(Qt.ItemDataRole.UserRole)
                if item.checkState() == Qt.CheckState.Checked:
                    self._selected_codes.add(codigo)
                else:
                    self._selected_codes.discard(codigo)
                
                self._update_counts()
                self.selection_changed.emit(list(self._selected_codes))
    
    def _on_double_click(self, row: int, col: int):
        """Callback ao dar duplo clique."""
        item = self.table.item(row, 1)
        if item:
            codigo = item.data(Qt.ItemDataRole.UserRole)
            for product in self._products:
                if product.get("codigo") == codigo:
                    self.row_double_clicked.emit(product)
                    break
    
    def _filter_table(self, text: str):
        """Filtra tabela pela busca."""
        text = text.lower()
        
        for row in range(self.table.rowCount()):
            match = False
            for col in range(1, self.table.columnCount()):
                item = self.table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)
        
        # Atualiza contagem de visíveis
        visible = sum(1 for r in range(self.table.rowCount()) 
                     if not self.table.isRowHidden(r))
        self.lbl_status.setText(f"Mostrando {visible} de {len(self._products)} produtos")
    
    def select_all(self):
        """Seleciona todos os produtos visíveis."""
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)
                    codigo = item.data(Qt.ItemDataRole.UserRole)
                    self._selected_codes.add(codigo)
        
        self._update_counts()
        self.selection_changed.emit(list(self._selected_codes))
    
    def deselect_all(self):
        """Desmarca todos os produtos."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)
        
        self._selected_codes.clear()
        self._update_counts()
        self.selection_changed.emit([])
    
    def get_selected_codes(self) -> List[int]:
        """Retorna lista de códigos selecionados."""
        return list(self._selected_codes)
    
    def get_selected_products(self) -> List[Dict]:
        """Retorna lista de produtos selecionados."""
        return [p for p in self._products if p.get("codigo") in self._selected_codes]
    
    def _update_counts(self):
        """Atualiza contadores."""
        total = len(self._products)
        selected = len(self._selected_codes)
        self.lbl_count.setText(f"{total} produtos | {selected} selecionados")
        
        if selected > 0:
            self.lbl_selection_info.setText(f"{selected} produto(s) para exportação")
        else:
            self.lbl_selection_info.setText("")
    
    def _show_context_menu(self, pos):
        """Mostra menu de contexto."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d30;
                color: #cccccc;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #094771;
            }
        """)
        
        action_select = QAction("Selecionar", self)
        action_select.triggered.connect(self._select_current_rows)
        menu.addAction(action_select)
        
        action_deselect = QAction("Desmarcar", self)
        action_deselect.triggered.connect(self._deselect_current_rows)
        menu.addAction(action_deselect)
        
        menu.addSeparator()
        
        action_select_all = QAction("Selecionar Todos", self)
        action_select_all.triggered.connect(self.select_all)
        menu.addAction(action_select_all)
        
        action_deselect_all = QAction("Desmarcar Todos", self)
        action_deselect_all.triggered.connect(self.deselect_all)
        menu.addAction(action_deselect_all)
        
        menu.exec(self.table.mapToGlobal(pos))
    
    def _select_current_rows(self):
        """Seleciona linhas atualmente destacadas."""
        for item in self.table.selectedItems():
            row = item.row()
            chk_item = self.table.item(row, 0)
            if chk_item:
                chk_item.setCheckState(Qt.CheckState.Checked)
                codigo = chk_item.data(Qt.ItemDataRole.UserRole)
                self._selected_codes.add(codigo)
        
        self._update_counts()
        self.selection_changed.emit(list(self._selected_codes))
    
    def _deselect_current_rows(self):
        """Desmarca linhas atualmente destacadas."""
        for item in self.table.selectedItems():
            row = item.row()
            chk_item = self.table.item(row, 0)
            if chk_item:
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                codigo = chk_item.data(Qt.ItemDataRole.UserRole)
                self._selected_codes.discard(codigo)
        
        self._update_counts()
        self.selection_changed.emit(list(self._selected_codes))
    
    @staticmethod
    def _format_number(value) -> str:
        """Formata número."""
        try:
            return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "0,00"
    
    @staticmethod
    def _format_currency(value) -> str:
        """Formata valor monetário."""
        try:
            return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "R$ 0,00"
