"""
searchable_combo.py
===================
ComboBox com busca integrada.
"""

from PySide6.QtWidgets import QComboBox, QCompleter
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem


class SearchableComboBox(QComboBox):
    """
    ComboBox com funcionalidade de busca/filtro.
    
    Permite ao usuário digitar para filtrar os itens.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_completer()
    
    def _setup_completer(self):
        """Configura auto-complete."""
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # Configura completer
        completer = QCompleter(self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCompleter(completer)
    
    def setItems(self, items: list):
        """
        Define itens do combo.
        
        Args:
            items: Lista de tuplas (texto, data) ou strings
        """
        self.clear()
        
        for item in items:
            if isinstance(item, tuple):
                self.addItem(item[0], item[1])
            else:
                self.addItem(str(item))
        
        # Atualiza modelo do completer
        if self.completer():
            self.completer().setModel(self.model())
    
    def currentData(self, role=Qt.ItemDataRole.UserRole):
        """Retorna dados do item selecionado."""
        return super().currentData(role)
    
    def selectByData(self, data):
        """
        Seleciona item pelo valor de dados.
        
        Args:
            data: Valor a procurar
        """
        for i in range(self.count()):
            if self.itemData(i) == data:
                self.setCurrentIndex(i)
                return
