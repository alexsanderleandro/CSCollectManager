"""
product_search_combo.py
=======================
ComboBox de seleção de produtos com busca ao pressionar Enter.
Implementa lazy loading para melhor performance.
"""

from typing import List, Tuple, Optional
from PySide6.QtWidgets import QWidget, QListWidgetItem, QCheckBox
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QKeyEvent

from widgets.multi_select_combo import MultiSelectCombo, _combo_qss
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

                    # Cria item com QCheckBox (igual ao MultiSelectCombo._populate_list)
                    # para que select_all / clear_selection / get_selected_values funcionem
                    item = QListWidgetItem()
                    checkbox = QCheckBox(descricao)
                    checkbox.setProperty("item_value", codigo)
                    checkbox.setStyleSheet(_combo_qss("""
                        QCheckBox {
                            color: {{FG_PRIMARY}};
                            spacing: 5px;
                        }
                        QCheckBox::indicator {
                            width: 14px;
                            height: 14px;
                        }
                        QCheckBox::indicator:unchecked {
                            border: 1px solid {{BORDER}};
                            background-color: {{CHECKBOX_BG}};
                            border-radius: 2px;
                        }
                        QCheckBox::indicator:checked {
                            border: 1px solid {{ACCENT}};
                            background-color: {{ACCENT}};
                            border-radius: 2px;
                        }
                    """))
                    checkbox.setChecked(True)
                    # Mesmo motivo do MultiSelectCombo._populate_list(): evita
                    # que destruir um checkbox focado role o painel de filtros.
                    checkbox.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    checkbox.stateChanged.connect(self._on_item_changed)
                    item.setSizeHint(QSize(0, 24))
                    self.list_widget.addItem(item)
                    self.list_widget.setItemWidget(item, checkbox)
                else:
                    # Se já existe, marca o checkbox como selecionado
                    widget = self.list_widget.itemWidget(self.list_widget.item(item_index))
                    if widget:
                        widget.blockSignals(True)
                        widget.setChecked(True)
                        widget.blockSignals(False)
            
            # Limpa campo de busca
            self.txt_search.clear()
            
            # Atualiza contagem e emite sinal
            self._update_count()
            self.selection_changed.emit(self.get_selected_values())
