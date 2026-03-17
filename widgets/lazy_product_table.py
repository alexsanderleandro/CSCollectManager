"""
lazy_product_table.py
=====================
Tabela de produtos com lazy loading para alta performance.

Suporta:
- 50.000+ produtos
- Carregamento sob demanda
- Barra de status com progresso
- Exportação com thread separada
"""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QProgressBar, QFrame, QHeaderView, QMenu,
    QApplication, QMessageBox, QToolBar, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QModelIndex
from PySide6.QtGui import QAction, QIcon, QKeySequence

from models.lazy_table_model import LazyTableModel, LazySortFilterProxyModel
from widgets.progress_dialog import ProgressOverlay


class LazyProductTable(QWidget):
    """
    Widget de tabela de produtos com lazy loading.
    
    Signals:
        row_selected: Linha selecionada (row)
        row_double_clicked: Duplo clique na linha (row)
        selection_changed: Seleção alterada (selected_rows)
        export_requested: Exportação solicitada (codprodutos)
        export_photos_requested: Exportação de fotos solicitada (codprodutos)
    """
    
    row_selected = Signal(int)
    row_double_clicked = Signal(int)
    selection_changed = Signal(list)
    export_requested = Signal(list)
    export_photos_requested = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Model
        self._model = LazyTableModel()
        self._proxy_model = LazySortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        
        # State
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)
        
        self._setup_ui()
        self._connect_signals()
    
    @property
    def model(self) -> LazyTableModel:
        """Retorna modelo de dados."""
        return self._model
    
    @property
    def proxy_model(self) -> LazySortFilterProxyModel:
        """Retorna proxy model."""
        return self._proxy_model
    
    @property
    def table_view(self) -> QTableView:
        """Retorna a QTableView."""
        return self._table
    
    def _setup_ui(self):
        """Configura a interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Container para tabela e overlay
        self._table_container = QFrame()
        container_layout = QVBoxLayout(self._table_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tabela
        self._table = QTableView()
        self._table.setModel(self._proxy_model)
        self._configure_table()
        container_layout.addWidget(self._table)
        
        # Overlay de progresso
        self._progress_overlay = ProgressOverlay(self._table_container)
        
        layout.addWidget(self._table_container)
        
        # Status bar
        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)
    
    def _create_toolbar(self) -> QToolBar:
        """Cria toolbar."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(Qt.QSize(20, 20))
        
        # Pesquisa
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Pesquisar...")
        self._search_input.setMinimumWidth(200)
        self._search_input.setMaximumWidth(300)
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_input)
        
        toolbar.addSeparator()
        
        # Ordenação
        toolbar.addWidget(QLabel(" Ordenar: "))
        
        self._sort_combo = QComboBox()
        self._sort_combo.setMinimumWidth(150)
        for key, header, _ in self._model.COLUMNS:
            self._sort_combo.addItem(header, key)
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self._sort_combo)
        
        self._sort_order_btn = QPushButton("↑")
        self._sort_order_btn.setMaximumWidth(30)
        self._sort_order_btn.setCheckable(True)
        self._sort_order_btn.setToolTip("Alternar ordem")
        self._sort_order_btn.clicked.connect(self._on_sort_order_changed)
        toolbar.addWidget(self._sort_order_btn)
        
        toolbar.addSeparator()
        
        # Botões de exportação
        self._btn_export = QPushButton("Exportar Carga")
        self._btn_export.clicked.connect(self._on_export_clicked)
        toolbar.addWidget(self._btn_export)
        
        self._btn_export_photos = QPushButton("Exportar Fotos")
        self._btn_export_photos.clicked.connect(self._on_export_photos_clicked)
        toolbar.addWidget(self._btn_export_photos)
        
        toolbar.addSeparator()
        
        # Seleção
        self._btn_select_all = QPushButton("Selecionar Todos")
        self._btn_select_all.clicked.connect(self._select_all)
        toolbar.addWidget(self._btn_select_all)
        
        self._btn_clear_selection = QPushButton("Limpar Seleção")
        self._btn_clear_selection.clicked.connect(self._clear_selection)
        toolbar.addWidget(self._btn_clear_selection)
        
        return toolbar
    
    def _create_status_bar(self) -> QFrame:
        """Cria barra de status."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMaximumHeight(30)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Label de status
        self._status_label = QLabel("Pronto")
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
        # Progresso de carregamento
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setMaximumHeight(18)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        
        # Contadores
        self._lbl_loaded = QLabel("Carregados: 0")
        layout.addWidget(self._lbl_loaded)
        
        self._lbl_total = QLabel("Total: 0")
        layout.addWidget(self._lbl_total)
        
        self._lbl_selected = QLabel("Selecionados: 0")
        layout.addWidget(self._lbl_selected)
        
        return frame
    
    def _configure_table(self):
        """Configura a tabela."""
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setShowGrid(True)
        self._table.setWordWrap(False)
        
        # Header
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSortIndicatorShown(True)
        
        # Larguras das colunas
        for i, (_, _, width) in enumerate(self._model.COLUMNS):
            self._table.setColumnWidth(i, width)
        
        # Vertical header
        self._table.verticalHeader().setDefaultSectionSize(25)
        self._table.verticalHeader().setVisible(False)
        
        # Context menu
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
    
    def _connect_signals(self):
        """Conecta sinais."""
        # Seleção
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._table.clicked.connect(self._on_row_clicked)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        
        # Modelo
        self._model.loading_started.connect(self._on_loading_started)
        self._model.loading_progress.connect(self._on_loading_progress)
        self._model.loading_finished.connect(self._on_loading_finished)
        self._model.data_changed.connect(self._update_counters)
    
    # ==========================================
    # PUBLIC API
    # ==========================================
    
    def set_model(self, model: LazyTableModel):
        """Define modelo externo."""
        self._model = model
        self._proxy_model.setSourceModel(model)
        
        # Reconecta sinais
        self._model.loading_started.connect(self._on_loading_started)
        self._model.loading_progress.connect(self._on_loading_progress)
        self._model.loading_finished.connect(self._on_loading_finished)
        self._model.data_changed.connect(self._update_counters)
    
    def set_proxy_model(self, proxy: LazySortFilterProxyModel):
        """Define proxy model externo."""
        self._proxy_model = proxy
        self._table.setModel(proxy)
    
    def show_loading(self, message: str = "Carregando..."):
        """Exibe overlay de carregamento."""
        self._progress_overlay.show_progress(message, cancelable=False)
    
    def hide_loading(self):
        """Oculta overlay de carregamento."""
        self._progress_overlay.hide_progress()
    
    def set_status(self, message: str):
        """Define mensagem de status."""
        self._status_label.setText(message)
    
    def get_selected_rows(self) -> List[int]:
        """Retorna linhas selecionadas (índices do proxy)."""
        selection = self._table.selectionModel().selectedRows()
        return [idx.row() for idx in selection]
    
    def get_selected_source_rows(self) -> List[int]:
        """Retorna linhas selecionadas (índices do modelo fonte)."""
        proxy_rows = self.get_selected_rows()
        return self._proxy_model.get_source_rows(proxy_rows)
    
    def get_selected_codprodutos(self) -> List[int]:
        """Retorna códigos dos produtos selecionados."""
        source_rows = self.get_selected_source_rows()
        products = self._model.get_selected_products(source_rows)
        return [p.codproduto for p in products]
    
    # ==========================================
    # HANDLERS
    # ==========================================
    
    def _on_search_changed(self, text: str):
        """Handler de mudança no campo de pesquisa."""
        self._search_timer.start(300)  # Debounce 300ms
    
    def _apply_search(self):
        """Aplica filtro de pesquisa."""
        text = self._search_input.text()
        self._proxy_model.set_filter_text_immediate(text)
        self._update_counters()
    
    def _on_sort_changed(self, index: int):
        """Handler de mudança na ordenação."""
        self._proxy_model.sort(index, self._get_sort_order())
    
    def _on_sort_order_changed(self):
        """Handler de mudança na ordem."""
        ascending = not self._sort_order_btn.isChecked()
        self._sort_order_btn.setText("↑" if ascending else "↓")
        self._proxy_model.sort(self._sort_combo.currentIndex(), self._get_sort_order())
    
    def _get_sort_order(self) -> Qt.SortOrder:
        """Retorna ordem de ordenação atual."""
        if self._sort_order_btn.isChecked():
            return Qt.SortOrder.DescendingOrder
        return Qt.SortOrder.AscendingOrder
    
    def _on_row_clicked(self, index: QModelIndex):
        """Handler de clique na linha."""
        self.row_selected.emit(index.row())
    
    def _on_row_double_clicked(self, index: QModelIndex):
        """Handler de duplo clique."""
        self.row_double_clicked.emit(index.row())
    
    def _on_selection_changed(self):
        """Handler de mudança na seleção."""
        rows = self.get_selected_rows()
        self._lbl_selected.setText(f"Selecionados: {len(rows):,}")
        self.selection_changed.emit(rows)
    
    def _on_loading_started(self):
        """Handler de início de carregamento."""
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(0)  # Indeterminado
        self.set_status("Carregando...")
    
    @Slot(int, int)
    def _on_loading_progress(self, loaded: int, total: int):
        """Handler de progresso."""
        self._progress_bar.setMaximum(100)
        percentage = int((loaded / total * 100)) if total > 0 else 0
        self._progress_bar.setValue(percentage)
        self._lbl_loaded.setText(f"Carregados: {loaded:,}")
        self._lbl_total.setText(f"Total: {total:,}")
    
    @Slot(int)
    def _on_loading_finished(self, total: int):
        """Handler de fim de carregamento."""
        self._progress_bar.setVisible(False)
        self.set_status(f"Carregados {total:,} produtos")
        self._update_counters()
    
    def _update_counters(self):
        """Atualiza contadores."""
        self._lbl_loaded.setText(f"Carregados: {self._model.loaded_records:,}")
        self._lbl_total.setText(f"Total: {self._model.total_records:,}")
        filtered = self._proxy_model.rowCount()
        if filtered != self._model.loaded_records:
            self._lbl_loaded.setText(f"Exibindo: {filtered:,}")
    
    def _select_all(self):
        """Seleciona todas as linhas visíveis."""
        self._table.selectAll()
    
    def _clear_selection(self):
        """Limpa seleção."""
        self._table.clearSelection()
    
    def _on_export_clicked(self):
        """Handler de exportação."""
        codprodutos = self.get_selected_codprodutos()
        if not codprodutos:
            # Se não há seleção, usa todos
            codprodutos = self._model.get_all_codprodutos()
        self.export_requested.emit(codprodutos)
    
    def _on_export_photos_clicked(self):
        """Handler de exportação de fotos."""
        codprodutos = self.get_selected_codprodutos()
        if not codprodutos:
            codprodutos = self._model.get_all_codprodutos()
        self.export_photos_requested.emit(codprodutos)
    
    def _show_context_menu(self, position):
        """Exibe menu de contexto."""
        menu = QMenu(self)
        
        # Copiar
        action_copy = QAction("Copiar", self)
        action_copy.setShortcut(QKeySequence.StandardKey.Copy)
        action_copy.triggered.connect(self._copy_selection)
        menu.addAction(action_copy)
        
        menu.addSeparator()
        
        # Seleção
        action_select_all = QAction("Selecionar Todos", self)
        action_select_all.triggered.connect(self._select_all)
        menu.addAction(action_select_all)
        
        menu.addSeparator()
        
        # Exportar
        action_export = QAction("Exportar Selecionados", self)
        action_export.triggered.connect(self._on_export_clicked)
        menu.addAction(action_export)
        
        action_export_photos = QAction("Exportar Fotos Selecionadas", self)
        action_export_photos.triggered.connect(self._on_export_photos_clicked)
        menu.addAction(action_export_photos)
        
        menu.exec_(self._table.viewport().mapToGlobal(position))
    
    def _copy_selection(self):
        """Copia seleção para clipboard."""
        selection = self._table.selectionModel().selectedIndexes()
        if not selection:
            return
        
        # Organiza por linha
        rows = {}
        for idx in selection:
            row = idx.row()
            if row not in rows:
                rows[row] = []
            rows[row].append(idx.data())
        
        # Monta texto
        lines = []
        for row in sorted(rows.keys()):
            line = "\t".join(str(v) if v else "" for v in rows[row])
            lines.append(line)
        
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
