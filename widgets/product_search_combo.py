"""
product_search_combo.py
=======================
ComboBox de seleção de produtos com busca ao pressionar Enter.
Implementa lazy loading para melhor performance.
"""

from typing import List, Tuple, Optional
from PySide6.QtWidgets import QWidget, QListWidgetItem
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

from widgets.multi_select_combo import MultiSelectCombo
from widgets.product_search_dialog import ProductSearchDialog


class ProductSearchCombo(MultiSelectCombo):
    """
    ComboBox de seleção de produtos com busca dinâmica.
    
    Ao pressionar Enter no campo de busca, abre um diálogo com a lista
    de produtos da base de dados conforme SQL padrão.
    Carrega automaticamente os produtos ao abrir (com lazy loading).
    
    Signals:
        Herda de MultiSelectCombo:
        - selection_changed: Emitido quando seleção muda
    """
    
    def __init__(self, title: str = "", placeholder: str = "Buscar produto...", parent: Optional[QWidget] = None):
        super().__init__(title=title, placeholder=placeholder, parent=parent)
        
        # Sobrescreve o keyPressEvent do txt_search
        self._setup_search_key_handler()
    
    def _setup_search_key_handler(self):
        """Configura handler customizado para teclas no campo de busca."""
        # Salva a referência ao keyPressEvent original
        self._original_key_press = self.txt_search.keyPressEvent
        
        # Define novo handler
        self.txt_search.keyPressEvent = self._on_search_key_press
    
    def _on_search_key_press(self, event: QKeyEvent):
        """
        Captura Enter no campo de busca e abre diálogo.
        """
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._open_product_search()
            event.accept()
        else:
            # Processa normalmente para outras teclas
            self._original_key_press(event)
    
    def _open_product_search(self):
        """Abre diálogo de busca de produtos com lazy loading."""
        search_text = self.txt_search.text().strip()
        
        dialog = ProductSearchDialog(search_text, self)
        
        if dialog.exec() == ProductSearchDialog.Accepted and hasattr(dialog, '_last_selected'):
            # Adiciona produtos selecionados
            for codigo, descricao in dialog._last_selected:
                # Procura se o produto já está na lista
                item_index = -1
                for i in range(len(self._items)):
                    if self._items[i][0] == codigo:
                        item_index = i
                        break
                
                # Se não existe, adiciona
                if item_index == -1:
                    self._items.append((codigo, descricao))
                    
                    # Cria item na lista widget
                    item = QListWidgetItem(descricao)
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked)
                    self.list_widget.addItem(item)
                else:
                    # Se já existe, marca como selecionado
                    for i in range(self.list_widget.count()):
                        if self.list_widget.item(i).text() == descricao:
                            self.list_widget.item(i).setCheckState(Qt.CheckState.Checked)
                            break
            
            # Limpa campo de busca
            self.txt_search.clear()
            
            # Atualiza contagem e emite sinal
            self._update_count()
            self.selection_changed.emit(self.get_selected_values())
