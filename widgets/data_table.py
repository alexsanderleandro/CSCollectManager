"""
data_table.py
=============
Widget de tabela de dados aprimorado.
"""

from typing import List, Dict, Any, Optional, Callable
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction


class DataTableWidget(QTableWidget):
    """
    Tabela de dados com funcionalidades aprimoradas.
    
    Features:
    - Configuração simplificada de colunas
    - Binding de dados
    - Menu de contexto
    - Ordenação
    - Seleção com callback
    """
    
    row_double_clicked = Signal(int, object)  # row, data
    row_selected = Signal(int, object)  # row, data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns = []
        self._data = []
        self._row_data = []
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configura interface."""
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        self.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                gridline-color: #3e3e42;
                border: 1px solid #3e3e42;
                border-radius: 5px;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QTableWidget::item:hover {
                background-color: #3e3e42;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 8px;
                border: none;
                border-right: 1px solid #3e3e42;
                border-bottom: 1px solid #3e3e42;
                font-weight: bold;
            }
        """)
    
    def _connect_signals(self):
        """Conecta sinais."""
        self.cellDoubleClicked.connect(self._on_double_click)
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def setup_columns(self, columns: List[Dict[str, Any]]):
        """
        Configura colunas da tabela.
        
        Args:
            columns: Lista de dicts com keys: name, field, width (opcional), 
                     stretch (opcional), align (opcional)
        
        Exemplo:
            [
                {"name": "Código", "field": "code", "width": 100},
                {"name": "Descrição", "field": "description", "stretch": True},
            ]
        """
        self._columns = columns
        self.setColumnCount(len(columns))
        
        headers = [col["name"] for col in columns]
        self.setHorizontalHeaderLabels(headers)
        
        header = self.horizontalHeader()
        for i, col in enumerate(columns):
            if col.get("stretch"):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif "width" in col:
                self.setColumnWidth(i, col["width"])
    
    def set_data(self, data: List[Any]):
        """
        Define dados da tabela.
        
        Args:
            data: Lista de objetos ou dicts
        """
        self._data = data
        self._row_data = []
        self.setRowCount(0)
        
        for row_idx, item in enumerate(data):
            self.insertRow(row_idx)
            self._row_data.append(item)
            
            for col_idx, col in enumerate(self._columns):
                field = col["field"]
                
                # Obtém valor do campo
                if isinstance(item, dict):
                    value = item.get(field, "")
                else:
                    value = getattr(item, field, "")
                
                # Formata se houver formatador
                formatter = col.get("formatter")
                if formatter:
                    value = formatter(value)
                
                cell = QTableWidgetItem(str(value))
                
                # Alinhamento
                align = col.get("align", "left")
                if align == "center":
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif align == "right":
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                self.setItem(row_idx, col_idx, cell)
    
    def get_selected_data(self) -> Optional[Any]:
        """Retorna dados da linha selecionada."""
        row = self.currentRow()
        if row >= 0 and row < len(self._row_data):
            return self._row_data[row]
        return None
    
    def _on_double_click(self, row: int, col: int):
        """Handler de duplo clique."""
        if row < len(self._row_data):
            self.row_double_clicked.emit(row, self._row_data[row])
    
    def _on_selection_changed(self):
        """Handler de mudança de seleção."""
        row = self.currentRow()
        if row >= 0 and row < len(self._row_data):
            self.row_selected.emit(row, self._row_data[row])
