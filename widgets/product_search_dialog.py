"""
product_search_dialog.py
========================
Diálogo para busca e seleção de produtos ao pressionar Enter no campo de busca.
Implementa lazy loading para melhor performance.
"""

from typing import List, Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QProgressBar, QMessageBox, QAbstractItemView,
    QFrame, QTableWidgetSelectionRange
)
from PySide6.QtCore import Qt, QThread, Signal, QItemSelectionModel, QItemSelection
from PySide6.QtGui import QFont

from services.product_service import ProductService


class ProductSearchWorker(QThread):
    """Worker para buscar produtos em background."""
    
    finished = Signal(list)  # Lista de produtos encontrados
    total_changed = Signal(int)  # Total de registros encontrados
    error = Signal(str)      # Mensagem de erro
    
    def __init__(self, search_text: str, limit: int = 50, offset: int = 0):
        super().__init__()
        self.search_text = search_text.strip()
        self.limit = limit
        self.offset = offset
        self.service = ProductService()
    
    def run(self):
        """Executa a busca."""
        try:
            # Busca produtos (com ou sem filtro de texto)
            results, total = self.service.search_products(
                search_text=self.search_text,
                limit=self.limit,
                offset=self.offset
            )
            
            self.total_changed.emit(total)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ProductSearchDialog(QDialog):
    """
    Diálogo de busca de produtos com lazy loading.
    
    Abre quando o usuário pressiona Enter no campo de busca do filtro.
    Carrega automaticamente os produtos ao abrir (com paginação).
    Permite selecionar um ou múltiplos produtos para o filtro.
    """
    
    # Signal emitido com produtos selecionados (lista de tuplas: codproduto, descricao)
    products_selected = Signal(list)
    
    def __init__(self, search_text: str = "", parent=None):
        super().__init__(parent)
        self.search_text = search_text
        self.worker = None
        self.current_page = 0
        self.page_size = 50
        self.total_products = 0
        self.all_loaded_products = []
        self._setup_ui()
        self._apply_theme()
        self._perform_search()
    
    def _setup_ui(self):
        """Configura interface do diálogo."""
        self.setWindowTitle("Buscar Produtos")
        self.setMinimumSize(900, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Campo de busca (para refinar resultado)
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        search_label = QLabel("Buscar:")
        search_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        search_layout.addWidget(search_label)
        
        self.txt_search = QLineEdit()
        self.txt_search.setText(self.search_text)
        self.txt_search.setPlaceholderText("Digite para refinar resultados...")
        self.txt_search.setMinimumHeight(35)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        search_layout.addWidget(self.txt_search)
        
        layout.addLayout(search_layout)
        
        # Info de resultados
        self.lbl_info = QLabel("Carregando...")
        self.lbl_info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.lbl_info)
        
        # Tabela de resultados
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Código", "Descrição", "Grupo", "EAN", "Unidade"
        ])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                gridline-color: #3e3e42;
                border: 1px solid #3e3e42;
            }
            QTableWidget::item {
                padding: 5px;
                color: #cccccc;
                background-color: #252526;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QTableWidget::item:selected:active {
                background-color: #0078d4;
                color: #ffffff;
            }
            QTableWidget::item:selected:!active {
                background-color: #005a9e;
                color: #ffffff;
            }
            QTableWidget::item:hover {
                background-color: #2d2d30;
                color: #cccccc;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        """)
        
        # Ajusta colunas
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Descrição
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Código
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Grupo
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # EAN
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Unidade
        
        layout.addWidget(self.table)
        
        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
            }
        """)
        layout.addWidget(self.progress)
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #3e3e42;")
        layout.addWidget(sep)
        
        # Botões de ação (Todos, Limpar)
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        
        btn_all = QPushButton("Todos")
        btn_all.setMinimumHeight(32)
        btn_all.setMaximumWidth(80)
        btn_all.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_all.clicked.connect(self._select_all)
        action_layout.addWidget(btn_all)
        
        btn_clear = QPushButton("Limpar")
        btn_clear.setMinimumHeight(32)
        btn_clear.setMaximumWidth(80)
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_clear.clicked.connect(self._clear_selection)
        action_layout.addWidget(btn_clear)
        
        action_layout.addStretch()
        layout.addLayout(action_layout)
        
        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        lbl_count = QLabel("Nenhum produto selecionado")
        lbl_count.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_count = lbl_count
        btn_layout.addWidget(lbl_count)
        
        btn_layout.addStretch()
        
        btn_select = QPushButton("Selecionar")
        btn_select.setMinimumHeight(35)
        btn_select.setMinimumWidth(120)
        btn_select.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        btn_select.clicked.connect(self._on_select)
        btn_layout.addWidget(btn_select)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumHeight(35)
        btn_cancel.setMinimumWidth(120)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # Conecta sinais
        self.txt_search.textChanged.connect(self._on_search_text_changed)
        self.table.itemSelectionChanged.connect(self._update_count)
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def _apply_theme(self):
        """Aplica tema escuro."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #cccccc;
            }
        """)
    
    def _perform_search(self):
        """Executa a busca de produtos (primeira página)."""
        if self.worker:
            self.worker.quit()
            self.worker.wait()
        
        self.current_page = 0
        self.all_loaded_products = []
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate
        self.table.setRowCount(0)
        
        # Busca a primeira página
        self._load_next_page()
    
    def _load_next_page(self):
        """Carrega a próxima página de resultados."""
        if self.worker:
            self.worker.quit()
            self.worker.wait()
        
        offset = self.current_page * self.page_size
        
        self.worker = ProductSearchWorker(
            search_text=self.txt_search.text(),
            limit=self.page_size,
            offset=offset
        )
        self.worker.finished.connect(self._on_search_finished)
        self.worker.total_changed.connect(self._on_total_changed)
        self.worker.error.connect(self._on_search_error)
        self.worker.start()
    
    def _on_total_changed(self, total: int):
        """Callback quando total de resultados é atualizado."""
        self.total_products = total
        self._update_info_label()
    
    def _on_search_finished(self, results: list):
        """Callback quando busca termina."""
        self.progress.setVisible(False)
        
        # Adiciona produtos à lista armazenada
        self.all_loaded_products.extend(results)
        
        # Adiciona à tabela
        start_row = self.table.rowCount() if self.current_page > 0 else 0
        self.table.setRowCount(len(self.all_loaded_products))
        
        for row_idx, product in enumerate(results):
            row = start_row + row_idx
            
            # Código — não usar setForeground; cor controlada pelo CSS
            self.table.setItem(row, 0, QTableWidgetItem(str(product.get("codproduto", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(product.get("descricaoproduto", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(product.get("nomegrupo", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(product.get("codeanunidade", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(product.get("unidade", ""))))
        
        self.current_page += 1
        self._update_info_label()
    
    def _on_search_error(self, error_msg: str):
        """Callback em caso de erro na busca."""
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Erro na Busca", f"Erro ao buscar produtos:\n{error_msg}")
    
    def _on_scroll(self, value: int):
        """Detecta se o usuário scrollou até o fim da tabela para lazy load."""
        scrollbar = self.table.verticalScrollBar()
        
        # Se chegou perto do fim (90%) e ainda há mais produtos a carregar
        if scrollbar.maximum() > 0:
            percentage = (value / scrollbar.maximum()) * 100
            
            if percentage >= 85 and len(self.all_loaded_products) < self.total_products:
                # Carrega próxima página
                self.progress.setVisible(True)
                self.progress.setRange(0, 0)
                self._load_next_page()
    
    def _on_search_text_changed(self):
        """Refina os resultados conforme o usuário digita."""
        # Aqui poderíamos fazer um filtro local sem nova query
        # Por enquanto, apenas filtra a tabela existente
        search_text = self.txt_search.text().lower()
        
        for row in range(self.table.rowCount()):
            # Procura nas colunas Código e Descrição
            codigo = self.table.item(row, 0).text().lower() if self.table.item(row, 0) else ""
            descricao = self.table.item(row, 1).text().lower() if self.table.item(row, 1) else ""
            
            match = search_text in codigo or search_text in descricao
            self.table.setRowHidden(row, not match)
    
    def _update_info_label(self):
        """Atualiza rótulo de informações."""
        total_visible = sum(1 for i in range(self.table.rowCount()) if not self.table.isRowHidden(i))
        
        if self.total_products == 0:
            self.lbl_info.setText("Nenhum produto encontrado")
        elif len(self.all_loaded_products) < self.total_products:
            self.lbl_info.setText(
                f"Exibindo {len(self.all_loaded_products)} de {self.total_products} produtos "
                f"({total_visible} visíveis) - Role para carregar mais"
            )
        else:
            self.lbl_info.setText(
                f"Total: {self.total_products} produtos ({total_visible} visíveis)"
            )
    
    def _update_count(self):
        """Atualiza contagem de selecionados."""
        count = len(self.table.selectedIndexes()) // self.table.columnCount()
        if count == 0:
            self.lbl_count.setText("Nenhum produto selecionado")
        elif count == 1:
            self.lbl_count.setText("1 produto selecionado")
        else:
            self.lbl_count.setText(f"{count} produtos selecionados")
    
    def _select_all(self):
        """Seleciona todos os produtos visíveis."""
        # selectAll() é método nativo Qt — funciona sempre
        self.table.selectAll()
        # Se houver linhas ocultas (filtro ativo), desseleciona elas
        has_hidden = any(self.table.isRowHidden(r) for r in range(self.table.rowCount()))
        if has_hidden:
            model = self.table.model()
            sel_model = self.table.selectionModel()
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    sel_model.select(
                        model.index(row, 0),
                        QItemSelectionModel.SelectionFlag.Deselect
                        | QItemSelectionModel.SelectionFlag.Rows
                    )
        self._update_count()

    def _clear_selection(self):
        """Limpa a seleção de todos os produtos."""
        self.table.clearSelection()
        self._update_count()
    
    def _on_select(self):
        """Retorna produtos selecionados."""
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        
        if not selected_rows:
            QMessageBox.warning(self, "Aviso", "Selecione ao menos um produto.")
            return
        
        # Coleta dados dos produtos selecionados (ignora linhas ocultas pelo filtro)
        selected_products = []
        for row in sorted(selected_rows):
            if self.table.isRowHidden(row):
                continue
            # Mantém código como string para preservar zeros à esquerda
            codigo = self.table.item(row, 0).text().strip()
            descricao = self.table.item(row, 1).text().strip()
            # Formata como "CÓDIGO - DESCRIÇÃO" para melhor legibilidade
            selected_products.append((codigo, f"{codigo} - {descricao}"))
        
        # Armazena para recuperação posterior
        self._last_selected = selected_products
        
        self.products_selected.emit(selected_products)
        self.accept()
