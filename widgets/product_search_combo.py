"""
product_search_combo.py
=======================
ComboBox de seleção de produtos com busca ao pressionar Enter.
Implementa lazy loading para melhor performance.
"""

from typing import List, Tuple, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QTimer
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
        """
        Inicializa o combo de busca de produtos.

        Herda de :class:`MultiSelectCombo` e adiciona tratamento especial
        da tecla Enter para abrir o diálogo de busca de produtos.

        Args:
            title: Rótulo exibido acima da lista.
            placeholder: Texto-dica do campo de busca.
            parent: Widget pai (opcional).
        """
        super().__init__(title=title, placeholder=placeholder, parent=parent)
        self._company_code: Optional[str] = None
        
        # Sobrescreve o keyPressEvent do txt_search
        self._setup_search_key_handler()
    
    def set_company_code(self, company_code: str):
        """Define o código da empresa para buscas dinâmicas."""
        self._company_code = company_code

    def clear_selection(self):
        """Remove todos os produtos adicionados dinamicamente e limpa o campo."""
        restore_scroll = self._begin_scroll_guard()
        # Limpa a lista interna de itens
        self._items.clear()
        # Limpa o widget de lista (checkboxes dinâmicos)
        self.list_widget.clear()
        # Limpa o campo de busca
        self.txt_search.blockSignals(True)
        self.txt_search.clear()
        self.txt_search.blockSignals(False)
        self._update_count()

        # Restaura já (rolagem síncrona) e no próximo ciclo do event loop, que
        # é quando uma eventual rolagem disparada por mudança de foco ocorre.
        restore_scroll()
        QTimer.singleShot(0, restore_scroll)

        self.selection_changed.emit([])

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
        
        dialog = ProductSearchDialog(search_text, self._company_code, self)
        
        if dialog.exec() == ProductSearchDialog.Accepted and hasattr(dialog, '_last_selected'):
            # Códigos que devem ficar marcados ao final: os que já estavam
            # selecionados (antes de qualquer filtro local ativo em txt_search)
            # + os recém-escolhidos. Todo item inserido nesta lista deve vir
            # marcado por padrão.
            already_selected = set(self.get_selected_values())
            newly_selected = set()

            existing_codes = {codigo for codigo, _ in self._items}
            for codigo, descricao in dialog._last_selected:
                newly_selected.add(codigo)
                if codigo not in existing_codes:
                    self._items.append((codigo, descricao))
                    existing_codes.add(codigo)

            # Limpa o campo de busca sem disparar _filter_items (evita
            # repopular a lista duas vezes) e repopula a lista completa, sem
            # filtro — necessário caso txt_search tivesse texto residual e
            # list_widget estivesse mostrando um subconjunto filtrado.
            self.txt_search.blockSignals(True)
            self.txt_search.clear()
            self.txt_search.blockSignals(False)
            self._populate_list()

            to_check = already_selected | newly_selected
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                checkbox = self.list_widget.itemWidget(item)
                if checkbox and checkbox.property("item_value") in to_check:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(True)
                    checkbox.blockSignals(False)

            # Atualiza contagem e emite sinal
            self._update_count()
            self.selection_changed.emit(self.get_selected_values())
