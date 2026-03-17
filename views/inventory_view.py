"""
inventory_view.py
=================
View de gerenciamento de inventários.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QLineEdit, QGroupBox,
    QProgressBar, QFileDialog, QFrame, QSpacerItem,
    QSizePolicy, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from controllers.inventory_controller import InventoryController
from models.user import User
from models.inventory import Inventory


class InventoryView(QWidget):
    """
    View para gerenciamento e exportação de inventários.
    
    Funcionalidades:
    - Listar inventários
    - Visualizar itens
    - Exportar para coletor
    """
    
    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self._user = user
        self._controller = InventoryController()
        self._selected_inventory: Inventory = None
        
        self._setup_ui()
        self._connect_signals()
        self._load_initial_data()
    
    def _setup_ui(self):
        """Configura interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Cabeçalho
        header_layout = QHBoxLayout()
        
        title = QLabel("Inventários")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setMinimumHeight(35)
        header_layout.addWidget(self.btn_refresh)
        
        main_layout.addLayout(header_layout)
        
        # Splitter para dividir lista e detalhes
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Painel de inventários
        inv_panel = self._create_inventory_panel()
        splitter.addWidget(inv_panel)
        
        # Painel de itens e exportação
        items_panel = self._create_items_panel()
        splitter.addWidget(items_panel)
        
        splitter.setSizes([300, 400])
        main_layout.addWidget(splitter)
    
    def _create_inventory_panel(self) -> QWidget:
        """Cria painel de listagem de inventários."""
        panel = QGroupBox("Inventários Disponíveis")
        panel.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        # Filtros
        filter_layout = QHBoxLayout()
        
        self.cmb_status = QComboBox()
        self.cmb_status.addItem("Todos", None)
        self.cmb_status.addItem("Abertos", "aberto")
        self.cmb_status.addItem("Fechados", "fechado")
        self.cmb_status.setMinimumWidth(120)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.cmb_status)
        
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar inventário...")
        self.txt_search.setMinimumWidth(200)
        filter_layout.addWidget(self.txt_search)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Tabela de inventários
        self.tbl_inventories = QTableWidget()
        self.tbl_inventories.setColumnCount(5)
        self.tbl_inventories.setHorizontalHeaderLabels([
            "Código", "Número", "Descrição", "Data", "Status"
        ])
        self.tbl_inventories.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.tbl_inventories.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.tbl_inventories.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.tbl_inventories.setAlternatingRowColors(True)
        self.tbl_inventories.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                gridline-color: #3e3e42;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 5px;
                border: 1px solid #3e3e42;
            }
        """)
        layout.addWidget(self.tbl_inventories)
        
        return panel
    
    def _create_items_panel(self) -> QWidget:
        """Cria painel de itens e exportação."""
        panel = QGroupBox("Itens do Inventário")
        panel.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        # Informações do inventário selecionado
        info_layout = QHBoxLayout()
        
        self.lbl_selected = QLabel("Selecione um inventário")
        self.lbl_selected.setStyleSheet("color: #888;")
        info_layout.addWidget(self.lbl_selected)
        
        info_layout.addStretch()
        
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #888;")
        info_layout.addWidget(self.lbl_count)
        
        layout.addLayout(info_layout)
        
        # Tabela de itens
        self.tbl_items = QTableWidget()
        self.tbl_items.setColumnCount(5)
        self.tbl_items.setHorizontalHeaderLabels([
            "Código", "Descrição", "Quantidade", "Unidade", "Código Barras"
        ])
        self.tbl_items.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tbl_items.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.tbl_items.setAlternatingRowColors(True)
        self.tbl_items.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                gridline-color: #3e3e42;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 5px;
                border: 1px solid #3e3e42;
            }
        """)
        layout.addWidget(self.tbl_items)
        
        # Painel de exportação
        export_layout = QHBoxLayout()
        
        export_layout.addWidget(QLabel("Formato:"))
        self.cmb_format = QComboBox()
        self.cmb_format.addItem("Texto Posicional (.txt)", "txt")
        self.cmb_format.addItem("CSV (.csv)", "csv")
        self.cmb_format.addItem("XML (.xml)", "xml")
        export_layout.addWidget(self.cmb_format)
        
        export_layout.addSpacing(20)
        
        self.chk_compress = QPushButton("Compactar ZIP")
        self.chk_compress.setCheckable(True)
        self.chk_compress.setChecked(True)
        export_layout.addWidget(self.chk_compress)
        
        export_layout.addStretch()
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMinimumWidth(200)
        export_layout.addWidget(self.progress)
        
        self.btn_export = QPushButton("Exportar para Coletor")
        self.btn_export.setEnabled(False)
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setMinimumWidth(180)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #0e7a0d;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0c6b0c;
            }
            QPushButton:disabled {
                background-color: #3e3e42;
                color: #888;
            }
        """)
        export_layout.addWidget(self.btn_export)
        
        layout.addLayout(export_layout)
        
        return panel
    
    def _connect_signals(self):
        """Conecta sinais."""
        # Controller
        self._controller.inventories_loaded.connect(self._on_inventories_loaded)
        self._controller.inventory_items_loaded.connect(self._on_items_loaded)
        self._controller.export_completed.connect(self._on_export_completed)
        self._controller.export_failed.connect(self._on_export_failed)
        self._controller.export_progress.connect(self._on_export_progress)
        self._controller.loading_started.connect(self._on_loading_started)
        self._controller.loading_finished.connect(self._on_loading_finished)
        
        # UI
        self.btn_refresh.clicked.connect(self._load_inventories)
        self.tbl_inventories.itemSelectionChanged.connect(self._on_inventory_selected)
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.cmb_status.currentIndexChanged.connect(self._load_inventories)
    
    def _load_initial_data(self):
        """Carrega dados iniciais."""
        self._load_inventories()
    
    def _load_inventories(self):
        """Carrega lista de inventários."""
        self._controller.load_inventories(self._user.company_code)
    
    def _on_inventories_loaded(self, inventories: list):
        """Callback quando inventários são carregados."""
        self.tbl_inventories.setRowCount(0)
        
        for inv in inventories:
            row = self.tbl_inventories.rowCount()
            self.tbl_inventories.insertRow(row)
            
            self.tbl_inventories.setItem(row, 0, QTableWidgetItem(str(inv.id)))
            self.tbl_inventories.setItem(row, 1, QTableWidgetItem(inv.number))
            self.tbl_inventories.setItem(row, 2, QTableWidgetItem(inv.description))
            self.tbl_inventories.setItem(
                row, 3, 
                QTableWidgetItem(
                    inv.open_date.strftime("%d/%m/%Y") if inv.open_date else ""
                )
            )
            self.tbl_inventories.setItem(row, 4, QTableWidgetItem(inv.status))
            
            # Armazena objeto no item
            self.tbl_inventories.item(row, 0).setData(Qt.ItemDataRole.UserRole, inv)
    
    def _on_inventory_selected(self):
        """Callback quando inventário é selecionado."""
        selected = self.tbl_inventories.selectedItems()
        
        if selected:
            item = self.tbl_inventories.item(selected[0].row(), 0)
            inventory = item.data(Qt.ItemDataRole.UserRole)
            
            if inventory:
                self._selected_inventory = inventory
                self.lbl_selected.setText(inventory.display_name)
                self.btn_export.setEnabled(True)
                self._controller.select_inventory(inventory)
        else:
            self._selected_inventory = None
            self.lbl_selected.setText("Selecione um inventário")
            self.btn_export.setEnabled(False)
            self.tbl_items.setRowCount(0)
            self.lbl_count.setText("")
    
    def _on_items_loaded(self, items: list):
        """Callback quando itens são carregados."""
        self.tbl_items.setRowCount(0)
        
        for item in items:
            row = self.tbl_items.rowCount()
            self.tbl_items.insertRow(row)
            
            self.tbl_items.setItem(row, 0, QTableWidgetItem(item.product_code))
            self.tbl_items.setItem(row, 1, QTableWidgetItem(item.description))
            self.tbl_items.setItem(row, 2, QTableWidgetItem(item.quantity_formatted))
            self.tbl_items.setItem(row, 3, QTableWidgetItem(item.unit))
            self.tbl_items.setItem(row, 4, QTableWidgetItem(item.barcode))
        
        self.lbl_count.setText(f"{len(items)} itens")
    
    def _on_export_clicked(self):
        """Handler do botão exportar."""
        if not self._selected_inventory:
            return
        
        # Seleciona pasta de destino
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecione a pasta de destino",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            format_type = self.cmb_format.currentData()
            compress = self.chk_compress.isChecked()
            
            self._controller.export_to_collector(
                inventory=self._selected_inventory,
                output_path=folder,
                format_type=format_type,
                compress=compress
            )
    
    def _on_export_progress(self, percent: int):
        """Callback de progresso da exportação."""
        self.progress.setValue(percent)
    
    def _on_export_completed(self, filepath: str):
        """Callback de exportação concluída."""
        self.progress.setVisible(False)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Exportação Concluída",
            f"Arquivo exportado com sucesso:\n{filepath}"
        )
    
    def _on_export_failed(self, error: str):
        """Callback de falha na exportação."""
        self.progress.setVisible(False)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Erro na Exportação", error)
    
    def _on_loading_started(self, message: str):
        """Callback de início de carregamento."""
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.setEnabled(False)
    
    def _on_loading_finished(self):
        """Callback de fim de carregamento."""
        self.progress.setVisible(False)
        self.setEnabled(True)
