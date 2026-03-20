"""
multi_select_combo.py
=====================
ComboBox com seleção múltipla e busca integrada.
"""

from typing import List, Tuple, Optional, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QFrame, QCheckBox, QAbstractItemView, QMenu
)
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QIcon, QAction


class _ScrollGuardList(QListWidget):
    """QListWidget que só rola quando o usuário clicou explicitamente nela."""

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()  # propaga ao pai sem rolar


    """
    Widget de seleção múltipla com busca.
    
    Features:
    - Busca/filtro de itens
    - Seleção múltipla com checkboxes
    - Botões selecionar todos / limpar
    - Exibe contagem de selecionados
    
    Signals:
        selection_changed: Emitido quando seleção muda
    """
    
    selection_changed = Signal(list)  # Lista de itens selecionados
    
    def __init__(
        self,
        title: str = "",
        placeholder: str = "Buscar...",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._title = title
        self._placeholder = placeholder
        self._items: List[Tuple[Any, str]] = []  # (value, display_text)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configura interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Título
        if self._title:
            title_label = QLabel(self._title)
            title_label.setStyleSheet("font-weight: bold; color: #cccccc;")
            layout.addWidget(title_label)
        
        # Campo de busca
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(self._placeholder)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        layout.addWidget(self.txt_search)
        
        # Lista de itens
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:hover {
                background-color: #3e3e42;
            }
        """)
        self.list_widget.setMinimumHeight(120)
        self.list_widget.setMaximumHeight(200)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        layout.addWidget(self.list_widget)
        
        # Botões de ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.btn_select_all = QPushButton("Todos")
        self.btn_select_all.setMaximumWidth(60)
        self.btn_select_all.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_layout.addWidget(self.btn_select_all)
        
        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.setMaximumWidth(60)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_layout.addWidget(self.btn_clear)
        
        btn_layout.addStretch()
        
        # Label de contagem
        self.lbl_count = QLabel("0 selecionado(s)")
        self.lbl_count.setStyleSheet("color: #888; font-size: 11px;")
        btn_layout.addWidget(self.lbl_count)
        
        layout.addLayout(btn_layout)
    
    def _connect_signals(self):
        """Conecta sinais."""
        self.txt_search.textChanged.connect(self._filter_items)
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_clear.clicked.connect(self.clear_selection)
    
    def set_items(self, items: List[Tuple[Any, str]]):
        """
        Define itens da lista.
        
        Args:
            items: Lista de tuplas (value, display_text)
        """
        self._items = items
        self._populate_list()
    
    def add_items_from_list(self, items: List[str]):
        """
        Adiciona itens a partir de lista de strings.
        
        Args:
            items: Lista de strings
        """
        self._items = [(item, item) for item in items]
        self._populate_list()
    
    def _populate_list(self, filter_text: str = ""):
        """Popula lista com itens."""
        self.list_widget.clear()
        
        filter_lower = filter_text.lower()
        
        for value, display in self._items:
            if filter_lower and filter_lower not in display.lower():
                continue
            
            item = QListWidgetItem()
            checkbox = QCheckBox(display)
            checkbox.setProperty("item_value", value)
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #cccccc;
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                }
                QCheckBox::indicator:unchecked {
                    border: 1px solid #555;
                    background-color: #252526;
                    border-radius: 2px;
                }
                QCheckBox::indicator:checked {
                    border: 1px solid #0078d4;
                    background-color: #0078d4;
                    border-radius: 2px;
                }
            """)
            checkbox.stateChanged.connect(self._on_item_changed)
            
            item.setSizeHint(QSize(0, 24))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, checkbox)
    
    def _filter_items(self, text: str):
        """Filtra itens pelo texto."""
        # Salva seleção atual
        selected = self.get_selected_values()
        
        # Repopula com filtro
        self._populate_list(text)
        
        # Restaura seleção
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            checkbox = self.list_widget.itemWidget(item)
            if checkbox:
                value = checkbox.property("item_value")
                if value in selected:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(True)
                    checkbox.blockSignals(False)
        
        self._update_count()
    
    def _on_item_changed(self, state: int):
        """Callback quando item é marcado/desmarcado."""
        self._update_count()
        self.selection_changed.emit(self.get_selected_values())
    
    def _update_count(self):
        """Atualiza label de contagem."""
        count = len(self.get_selected_values())
        self.lbl_count.setText(f"{count} selecionado(s)")
    
    def get_selected_values(self) -> List[Any]:
        """Retorna lista de valores selecionados."""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            checkbox = self.list_widget.itemWidget(item)
            if checkbox and checkbox.isChecked():
                selected.append(checkbox.property("item_value"))
        return selected
    
    def get_selected_texts(self) -> List[str]:
        """Retorna lista de textos selecionados."""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            checkbox = self.list_widget.itemWidget(item)
            if checkbox and checkbox.isChecked():
                selected.append(checkbox.text())
        return selected
    
    def select_all(self):
        """Seleciona todos os itens visíveis."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            checkbox = self.list_widget.itemWidget(item)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(True)
                checkbox.blockSignals(False)
        
        self._update_count()
        self.selection_changed.emit(self.get_selected_values())
    
    def clear_selection(self):
        """Limpa seleção."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            checkbox = self.list_widget.itemWidget(item)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
        
        self._update_count()
        self.selection_changed.emit([])
    
    def set_selected_values(self, values: List[Any]):
        """
        Define itens selecionados por valor.
        
        Args:
            values: Lista de valores a selecionar
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            checkbox = self.list_widget.itemWidget(item)
            if checkbox:
                value = checkbox.property("item_value")
                checkbox.blockSignals(True)
                checkbox.setChecked(value in values)
                checkbox.blockSignals(False)
        
        self._update_count()


class SingleSelectCombo(QWidget):
    """
    Widget de seleção única com busca.
    
    Signals:
        selection_changed: Emitido quando seleção muda
    """
    
    selection_changed = Signal(object)  # Valor selecionado
    
    def __init__(
        self,
        title: str = "",
        placeholder: str = "Buscar...",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._title = title
        self._placeholder = placeholder
        self._items: List[Tuple[Any, str]] = []
        self._selected_value = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configura interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Título
        if self._title:
            title_label = QLabel(self._title)
            title_label.setStyleSheet("font-weight: bold; color: #cccccc;")
            layout.addWidget(title_label)
        
        # Campo de busca
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(self._placeholder)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        layout.addWidget(self.txt_search)
        
        # Lista de itens
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3e3e42;
                border-radius: 3px;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:hover {
                background-color: #3e3e42;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """)
        self.list_widget.setMinimumHeight(100)
        self.list_widget.setMaximumHeight(150)
        layout.addWidget(self.list_widget)
        
        # Botão limpar
        btn_layout = QHBoxLayout()
        
        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.setMaximumWidth(60)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def _connect_signals(self):
        """Conecta sinais."""
        self.txt_search.textChanged.connect(self._filter_items)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.btn_clear.clicked.connect(self.clear_selection)
    
    def set_items(self, items: List[Tuple[Any, str]]):
        """Define itens da lista."""
        self._items = items
        self._populate_list()
    
    def _populate_list(self, filter_text: str = ""):
        """Popula lista com itens."""
        self.list_widget.clear()
        
        filter_lower = filter_text.lower()
        
        for value, display in self._items:
            if filter_lower and filter_lower not in display.lower():
                continue
            
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, value)
            self.list_widget.addItem(item)
            
            if value == self._selected_value:
                item.setSelected(True)
    
    def _filter_items(self, text: str):
        """Filtra itens."""
        self._populate_list(text)
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Callback de clique em item."""
        self._selected_value = item.data(Qt.ItemDataRole.UserRole)
        self.selection_changed.emit(self._selected_value)
    
    def get_selected_value(self) -> Any:
        """Retorna valor selecionado."""
        return self._selected_value
    
    def clear_selection(self):
        """Limpa seleção."""
        self._selected_value = None
        self.list_widget.clearSelection()
        self.selection_changed.emit(None)
    
    def set_selected_value(self, value: Any):
        """Define valor selecionado."""
        self._selected_value = value
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == value:
                item.setSelected(True)
                break
