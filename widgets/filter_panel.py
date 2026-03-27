"""
filter_panel.py
===============
Painel de filtros para exportação de carga de inventário.
"""

from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QGroupBox, QRadioButton, QCheckBox,
    QPushButton, QButtonGroup, QFrame, QSizePolicy,
    QSpacerItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from widgets.multi_select_combo import MultiSelectCombo
from widgets.product_search_combo import ProductSearchCombo


class CollapsibleSection(QWidget):
    """Seção expansível (expand/collapse) com header clicável."""

    def __init__(self, title: str, content: QWidget, expanded: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._title = title
        self._content = content

        self._btn = QPushButton()
        self._btn.setCheckable(True)
        self._btn.setChecked(expanded)
        self._btn.setText(("\u25BC "+ title) if expanded else ("\u25BA "+ title))
        self._btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                background-color: transparent;
                color: #cccccc;
                border: none;
                padding: 6px 4px;
                font-weight: bold;
            }
            QPushButton:hover { color: #ffffff; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._btn)

        # content wrapper
        self._wrap = QFrame()
        inner = QVBoxLayout(self._wrap)
        inner.setContentsMargins(6, 4, 6, 6)
        inner.addWidget(self._content)
        layout.addWidget(self._wrap)

        self._btn.toggled.connect(self._on_toggled)
        self._on_toggled(expanded)

    def _on_toggled(self, checked: bool):
        self._wrap.setVisible(checked)
        self._btn.setText(("\u25BC "+ self._title) if checked else ("\u25BA "+ self._title))



class FilterPanel(QWidget):
    """
    Painel de filtros para seleção de produtos para exportação.
    
    Signals:
        filters_changed: Emitido quando filtros mudam
        select_clicked: Emitido ao clicar em Selecionar
        clear_clicked: Emitido ao clicar em Limpar
    """
    
    filters_changed = Signal(dict)
    select_clicked = Signal()
    clear_clicked = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Configura interface."""
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Área de scroll para os filtros
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #252526;
            }
            QScrollBar:vertical {
                background-color: #252526;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #3e3e42;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Container dos filtros
        filter_container = QWidget()
        filter_container.setStyleSheet("background-color: #252526;")
        filter_layout = QVBoxLayout(filter_container)
        filter_layout.setContentsMargins(15, 15, 15, 15)
        filter_layout.setSpacing(15)
        
        # Título
        title = QLabel("Filtros de Seleção")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; padding-bottom: 5px;")
        filter_layout.addWidget(title)
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #3e3e42;")
        filter_layout.addWidget(sep)
        
        # ===== FILTROS DE SELEÇÃO MÚLTIPLA =====
        
        # Produto (com busca ao pressionar Enter)
        self.filter_produto = ProductSearchCombo(
            title="Produto",
            placeholder="Buscar produto... (pressione Enter para buscar na base)"
        )
        filter_layout.addWidget(CollapsibleSection("Produto", self.filter_produto, expanded=False))
        
        # Grupo de Estoque
        self.filter_grupo = MultiSelectCombo(
            title="Grupo de Estoque",
            placeholder="Buscar grupo..."
        )
        filter_layout.addWidget(CollapsibleSection("Grupo de Estoque", self.filter_grupo, expanded=False))
        
        # Fornecedor (múltipla seleção)
        self.filter_fornecedor = MultiSelectCombo(
            title="Fornecedor",
            placeholder="Buscar fornecedor..."
        )
        filter_layout.addWidget(CollapsibleSection("Fornecedor", self.filter_fornecedor, expanded=False))
        
        # Fabricante (múltipla seleção)
        self.filter_fabricante = MultiSelectCombo(
            title="Fabricante",
            placeholder="Buscar fabricante..."
        )
        filter_layout.addWidget(CollapsibleSection("Fabricante", self.filter_fabricante, expanded=False))
        
        # Localização
        self.filter_localizacao = MultiSelectCombo(
            title="Localização",
            placeholder="Buscar localização..."
        )
        filter_layout.addWidget(CollapsibleSection("Localização", self.filter_localizacao, expanded=False))
        
        # Tipo de Produto
        self.filter_tipo_produto = MultiSelectCombo(
            title="Tipo de Produto",
            placeholder="Buscar tipo..."
        )
        filter_layout.addWidget(CollapsibleSection("Tipo de Produto", self.filter_tipo_produto, expanded=False))
        
        # ===== GRUPO: LOCAL ESTOQUE =====
        group_local = self._create_group_box("Local Estoque")
        self._group_local_layout = QVBoxLayout(group_local)
        self._group_local_layout.setSpacing(8)

        self.radio_local_group = QButtonGroup(self)
        self._locais_estoque_mode: str = "A"

        # Inicializa com modo padrão "A" (Loja e Depósito) — será reconfigurado
        # após a conexão ao banco via configure_local_estoque()
        self._rebuild_local_estoque_options("A", None)

        filter_layout.addWidget(group_local)
        
        # ===== GRUPO: LOCALIZAÇÃO =====
        group_localizacao = self._create_group_box("Localização")
        group_loc_layout = QVBoxLayout(group_localizacao)
        group_loc_layout.setSpacing(8)
        
        self.radio_loc_group = QButtonGroup(self)
        
        self.radio_com_localizacao = QRadioButton("Somente com localização")
        self.radio_sem_localizacao = QRadioButton("Somente sem localização")
        self.radio_ambas_localizacao = QRadioButton("Ambos")
        self.radio_ambas_localizacao.setChecked(True)
        
        self.radio_loc_group.addButton(self.radio_com_localizacao, 1)
        self.radio_loc_group.addButton(self.radio_sem_localizacao, 2)
        self.radio_loc_group.addButton(self.radio_ambas_localizacao, 3)
        
        for radio in [self.radio_com_localizacao, self.radio_sem_localizacao, 
                      self.radio_ambas_localizacao]:
            self._style_radio(radio)
            group_loc_layout.addWidget(radio)
        
        filter_layout.addWidget(group_localizacao)
        
        # ===== GRUPO: ESTOQUE =====
        group_estoque = self._create_group_box("Estoque")
        group_est_layout = QVBoxLayout(group_estoque)
        group_est_layout.setSpacing(8)
        
        self.radio_estoque_group = QButtonGroup(self)
        
        self.radio_estoque_negativo = QRadioButton("Negativo")
        self.radio_estoque_positivo = QRadioButton("Positivo")
        self.radio_estoque_zerado = QRadioButton("Zerado")
        self.radio_estoque_todos = QRadioButton("Todos")
        self.radio_estoque_todos.setChecked(True)
        
        self.radio_estoque_group.addButton(self.radio_estoque_negativo, 1)
        self.radio_estoque_group.addButton(self.radio_estoque_positivo, 2)
        self.radio_estoque_group.addButton(self.radio_estoque_zerado, 3)
        self.radio_estoque_group.addButton(self.radio_estoque_todos, 4)
        
        for radio in [self.radio_estoque_negativo, self.radio_estoque_positivo,
                      self.radio_estoque_zerado, self.radio_estoque_todos]:
            self._style_radio(radio)
            group_est_layout.addWidget(radio)
        
        filter_layout.addWidget(group_estoque)
        
        # ===== GRUPO: ENCOMENDA =====
        group_encomenda = self._create_group_box("Encomenda")
        group_enc_layout = QVBoxLayout(group_encomenda)
        group_enc_layout.setSpacing(8)
        
        self.radio_encomenda_group = QButtonGroup(self)
        
        self.radio_somente_encomenda = QRadioButton("Somente encomenda")
        self.radio_somente_nao_encomenda = QRadioButton("Somente não encomenda")
        self.radio_ambas_encomenda = QRadioButton("Ambos")
        self.radio_ambas_encomenda.setChecked(True)
        
        self.radio_encomenda_group.addButton(self.radio_somente_encomenda, 1)
        self.radio_encomenda_group.addButton(self.radio_somente_nao_encomenda, 2)
        self.radio_encomenda_group.addButton(self.radio_ambas_encomenda, 3)
        
        for radio in [self.radio_somente_encomenda, self.radio_somente_nao_encomenda,
                      self.radio_ambas_encomenda]:
            self._style_radio(radio)
            group_enc_layout.addWidget(radio)
        
        filter_layout.addWidget(group_encomenda)
        
        # ===== GRUPO: OPÇÕES ADICIONAIS =====
        group_opcoes = self._create_group_box("Opções Adicionais")
        group_opc_layout = QVBoxLayout(group_opcoes)
        group_opc_layout.setSpacing(8)
        
        self.chk_peso_variavel = QCheckBox("Somente peso variável")
        self.chk_produtos_venda = QCheckBox("Somente produtos para venda")

        for chk in [self.chk_peso_variavel, self.chk_produtos_venda]:
            self._style_checkbox(chk)
            group_opc_layout.addWidget(chk)
        
        filter_layout.addWidget(group_opcoes)
        
        # Spacer
        filter_layout.addStretch()
        
        # Adiciona container ao scroll
        scroll.setWidget(filter_container)
        main_layout.addWidget(scroll)
        
        # ===== BOTÕES DE AÇÃO =====
        btn_container = QWidget()
        btn_container.setStyleSheet("background-color: #2d2d30;")
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setContentsMargins(15, 15, 15, 15)
        btn_layout.setSpacing(10)
        
        # Separador
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #3e3e42;")
        btn_layout.addWidget(sep2)
        
        # Botão Selecionar
        self.btn_selecionar = QPushButton("Selecionar")
        self.btn_selecionar.setMinimumHeight(40)
        self.btn_selecionar.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        btn_layout.addWidget(self.btn_selecionar)
        
        # Botão Limpar Seleção
        self.btn_limpar = QPushButton("Limpar Seleção")
        self.btn_limpar.setMinimumHeight(35)
        self.btn_limpar.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                font-size: 12px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        btn_layout.addWidget(self.btn_limpar)
        
        main_layout.addWidget(btn_container)
    
    # ------------------------------------------------------------------
    # Local Estoque — configuração dinâmica
    # ------------------------------------------------------------------

    def _rebuild_local_estoque_options(
        self,
        modo: str,
        locais_list: Optional[List[str]]
    ):
        """
        Reconstrói os radio buttons do grupo Local Estoque.

        Args:
            modo: "L"=Loja, "D"=Depósito, "A"=Loja e Depósito, "T"=lista
            locais_list: Lista de ENDLOCALESTOQUE (usado apenas no modo "T")
        """
        # Remove botões existentes do grupo e do layout
        for btn in list(self.radio_local_group.buttons()):
            self.radio_local_group.removeButton(btn)
            self._group_local_layout.removeWidget(btn)
            btn.deleteLater()

        self._locais_estoque_mode = modo

        # Define as opções conforme o modo
        if modo == "L":
            options: List[tuple] = [("Loja", "loja")]
        elif modo == "D":
            options = [("Depósito", "deposito")]
        elif modo == "T" and locais_list:
            options = [(val, val) for val in locais_list]
        else:  # "A" ou default
            options = [("Loja", "loja"), ("Depósito", "deposito")]

        for i, (label, value) in enumerate(options):
            radio = QRadioButton(label)
            radio.setProperty("local_value", value)
            if i == 0:
                radio.setChecked(True)
            self._style_radio(radio)
            self.radio_local_group.addButton(radio, i + 1)
            self._group_local_layout.addWidget(radio)

    def configure_local_estoque(
        self,
        modo: str,
        locais_list: Optional[List[str]] = None
    ):
        """
        Configura o grupo Local Estoque conforme configuração do sistema.

        Deve ser chamado após a conexão com o banco, passando os dados
        retornados por ProductService.get_all_filter_data().

        Args:
            modo: "L"=somente Loja, "D"=somente Depósito,
                  "A"=Loja e Depósito, "T"=lista ENDLOCALESTOQUE
            locais_list: Lista de valores ENDLOCALESTOQUE (modo "T" apenas)
        """
        self._rebuild_local_estoque_options(modo, locais_list)

    def _get_local_estoque_selected(self) -> str:
        """Retorna o valor do radio de local de estoque selecionado."""
        checked = self.radio_local_group.checkedButton()
        if checked:
            return checked.property("local_value") or "loja"
        return "loja"

    def _create_group_box(self, title: str) -> QGroupBox:
        """Cria um GroupBox estilizado."""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                font-weight: bold;
                font-size: 12px;
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
        return group
    
    def _style_radio(self, radio: QRadioButton):
        """Aplica estilo ao RadioButton."""
        radio.setStyleSheet("""
            QRadioButton {
                color: #cccccc;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QRadioButton::indicator:unchecked {
                border: 2px solid #555;
                border-radius: 8px;
                background-color: #252526;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #0078d4;
                border-radius: 8px;
                background-color: #0078d4;
            }
            QRadioButton::indicator:unchecked:hover {
                border-color: #777;
            }
        """)
    
    def _style_checkbox(self, checkbox: QCheckBox):
        """Aplica estilo ao CheckBox."""
        checkbox.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #252526;
            }
            QCheckBox::indicator:checked {
                border: 1px solid #0078d4;
                border-radius: 3px;
                background-color: #0078d4;
            }
            QCheckBox::indicator:unchecked:hover {
                border-color: #777;
            }
        """)
    
    def _connect_signals(self):
        """Conecta sinais dos widgets."""
        # Botões
        self.btn_selecionar.clicked.connect(self.select_clicked.emit)
        self.btn_limpar.clicked.connect(self._on_clear_clicked)
        
        # Filtros de seleção
        self.filter_produto.selection_changed.connect(self._on_filter_changed)
        self.filter_grupo.selection_changed.connect(self._on_filter_changed)
        self.filter_fornecedor.selection_changed.connect(self._on_filter_changed)
        self.filter_fabricante.selection_changed.connect(self._on_filter_changed)
        self.filter_localizacao.selection_changed.connect(self._on_filter_changed)
        self.filter_tipo_produto.selection_changed.connect(self._on_filter_changed)
        
        # Radio buttons
        self.radio_local_group.buttonClicked.connect(self._on_filter_changed)
        self.radio_loc_group.buttonClicked.connect(self._on_filter_changed)
        self.radio_estoque_group.buttonClicked.connect(self._on_filter_changed)
        self.radio_encomenda_group.buttonClicked.connect(self._on_filter_changed)
        
        # Checkboxes
        self.chk_peso_variavel.stateChanged.connect(self._on_filter_changed)
        self.chk_produtos_venda.stateChanged.connect(self._on_filter_changed)
    
    def _on_filter_changed(self, *args):
        """Callback quando filtro muda."""
        self.filters_changed.emit(self.get_filters())
    
    def _on_clear_clicked(self):
        """Limpa todos os filtros."""
        # Limpa seleções múltiplas
        self.filter_produto.clear_selection()
        self.filter_grupo.clear_selection()
        self.filter_fornecedor.clear_selection()
        self.filter_fabricante.clear_selection()
        self.filter_localizacao.clear_selection()
        self.filter_tipo_produto.clear_selection()
        
        # Reset radio buttons para defaults
        btns = self.radio_local_group.buttons()
        if btns:
            btns[0].setChecked(True)
        self.radio_ambas_localizacao.setChecked(True)
        self.radio_estoque_todos.setChecked(True)
        self.radio_ambas_encomenda.setChecked(True)
        
        # Desmarca checkboxes
        self.chk_peso_variavel.setChecked(False)
        self.chk_produtos_venda.setChecked(False)
        
        self.clear_clicked.emit()
    
    def get_filters(self) -> Dict[str, Any]:
        """
        Retorna dicionário com todos os filtros aplicados.
        
        Returns:
            Dict com filtros
        """
        return {
            # Seleções
            "produtos": self.filter_produto.get_selected_values(),
            "grupos": self.filter_grupo.get_selected_values(),
            "fornecedor": self.filter_fornecedor.get_selected_values(),
            "fabricante": self.filter_fabricante.get_selected_values(),
            "localizacoes": self.filter_localizacao.get_selected_values(),
            "tipos_produto": self.filter_tipo_produto.get_selected_values(),
            
            # Local estoque
            "local_estoque": self._get_local_estoque_selected(),
            
            # Localização
            "filtro_localizacao": (
                "com" if self.radio_com_localizacao.isChecked() else
                "sem" if self.radio_sem_localizacao.isChecked() else
                "ambos"
            ),
            
            # Estoque
            "filtro_estoque": (
                "negativo" if self.radio_estoque_negativo.isChecked() else
                "positivo" if self.radio_estoque_positivo.isChecked() else
                "zerado" if self.radio_estoque_zerado.isChecked() else
                "todos"
            ),
            
            # Encomenda
            "filtro_encomenda": (
                "somente_encomenda" if self.radio_somente_encomenda.isChecked() else
                "somente_nao_encomenda" if self.radio_somente_nao_encomenda.isChecked() else
                "ambos"
            ),
            
            # Opções
            "somente_peso_variavel": self.chk_peso_variavel.isChecked(),
            "somente_venda": self.chk_produtos_venda.isChecked(),
        }
    
    def load_filter_data(
        self,
        produtos: List[tuple] = None,
        grupos: List[tuple] = None,
        fornecedores: List[tuple] = None,
        fabricantes: List[tuple] = None,
        localizacoes: List[tuple] = None,
        tipos_produto: List[tuple] = None
    ):
        """
        Carrega dados nos filtros.
        
        Args:
            produtos: Lista de (cod, descricao)
            grupos: Lista de (cod, descricao)
            fornecedores: Lista de (cod, nome)
            fabricantes: Lista de (cod, nome)
            localizacoes: Lista de (cod, descricao)
            tipos_produto: Lista de (cod, descricao)
        """
        if produtos:
            self.filter_produto.set_items(produtos)
        if grupos:
            self.filter_grupo.set_items(grupos)
        if fornecedores:
            self.filter_fornecedor.set_items(fornecedores)
        if fabricantes:
            self.filter_fabricante.set_items(fabricantes)
        if localizacoes:
            self.filter_localizacao.set_items(localizacoes)
        if tipos_produto:
            self.filter_tipo_produto.set_items(tipos_produto)
