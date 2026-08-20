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
        self._checked_values.clear()
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

        # Recebe tanto os duplos cliques (um produto por vez, com o diálogo
        # ainda aberto) quanto o clique em "Selecionar", que emite o mesmo sinal.
        houve_mudanca = {"valor": False}

        def _receber(produtos):
            if self._adicionar_produtos(produtos):
                houve_mudanca["valor"] = True

        dialog.products_selected.connect(_receber)
        dialog.exec()

        # O refresh da interface acontece uma única vez, depois de fechado: o
        # combo fica atrás de um diálogo modal, então repopular a lista a cada
        # duplo clique seria trabalho invisível e desperdiçado.
        if houve_mudanca["valor"]:
            # Limpa o campo de busca sem disparar _filter_items (evita
            # repopular a lista duas vezes) e repopula a lista completa, sem
            # filtro. O estado marcado vem de _checked_values, então é
            # preservado independentemente de qualquer filtro local ativo.
            self.txt_search.blockSignals(True)
            self.txt_search.clear()
            self.txt_search.blockSignals(False)
            self._populate_list()

            # Atualiza contagem e emite sinal
            self._update_count()
            self.selection_changed.emit(self.get_selected_values())

    def _adicionar_produtos(self, produtos) -> bool:
        """Inclui produtos na lista do filtro, sem duplicar. Retorna se mudou algo."""
        existing_codes = {codigo for codigo, _ in self._items}
        mudou = False
        for codigo, descricao in produtos or []:
            if codigo not in existing_codes:
                self._items.append((codigo, descricao))
                existing_codes.add(codigo)
                mudou = True
            # Todo item inserido nesta lista deve vir marcado por padrão.
            # Usa _checked_values (fonte da verdade persistente, ver
            # MultiSelectCombo) em vez de get_selected_values(), que só
            # enxerga o que está renderizado — se txt_search tiver texto
            # residual de uma busca anterior, list_widget pode estar
            # mostrando um subconjunto filtrado no momento do Enter.
            if codigo not in self._checked_values:
                self._checked_values.add(codigo)
                mudou = True
        return mudou
