"""
product_search_dialog.py
========================
Diálogo para busca e seleção de produtos ao pressionar Enter no campo de busca.
Implementa lazy loading para melhor performance.
"""

from typing import List, Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QProgressBar, QMessageBox, QAbstractItemView,
    QFrame, QTableWidgetSelectionRange
)
from PySide6.QtCore import Qt, QThread, Signal, QItemSelectionModel, QItemSelection, QTimer
from PySide6.QtGui import QFont

from services.product_service import ProductService
from app.styles import themed_qss


class ProductSearchWorker(QThread):
    """Worker para buscar produtos em background.

    Os sinais carregam o ``seq`` (token da busca que originou este worker) para
    que o diálogo descarte o resultado de uma busca já superada — sem isso, o
    resultado de uma consulta antiga chega depois que a nova já limpou a tabela
    e acaba sendo *acrescentado*, duplicando linhas.

    Os sinais não podem se chamar ``finished``/``error``: ``finished`` sombrearia
    o sinal nativo de ``QThread``, que é justamente o que o diálogo usa para
    saber quando a thread realmente terminou e pode ser liberada.
    """

    resultados = Signal(int, list, int)  # seq, produtos, total de registros
    erro = Signal(int, str)              # seq, mensagem de erro

    def __init__(
        self,
        seq: int,
        search_text: str,
        company_code: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        super().__init__()
        self.seq = seq
        self.search_text = search_text.strip()
        self.company_code = company_code
        self.limit = limit
        self.offset = offset
        self.service = ProductService()

    def run(self):
        """Executa a busca."""
        try:
            # Busca produtos (com ou sem filtro de texto)
            results, total = self.service.search_products(
                search_text=self.search_text,
                company_code=self.company_code,
                limit=self.limit,
                offset=self.offset
            )

            self.resultados.emit(self.seq, results, total)
        except Exception as e:
            self.erro.emit(self.seq, str(e))


class ProductSearchDialog(QDialog):
    """
    Diálogo de busca de produtos com lazy loading.
    
    Abre quando o usuário pressiona Enter no campo de busca do filtro.
    Carrega automaticamente os produtos ao abrir (com paginação).
    Permite selecionar um ou múltiplos produtos para o filtro.
    """
    
    # Signal emitido com produtos selecionados (lista de tuplas: codproduto, descricao)
    products_selected = Signal(list)
    
    def __init__(self, search_text: str = "", company_code: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.search_text = search_text
        self.company_code = company_code
        self.worker = None
        self.current_page = 0
        self.page_size = 50
        self.total_products = 0
        self.all_loaded_products = []

        # Token da busca corrente: incrementado a cada nova busca, permite
        # descartar o resultado de buscas superadas (ver ProductSearchWorker).
        self._search_seq = 0
        # Impede que dois eventos de scroll seguidos busquem o mesmo offset
        # duas vezes (current_page só é incrementado no callback).
        self._carregando = False
        # Workers já disparados que ainda não terminaram. Mantê-los
        # referenciados evita que sejam coletados enquanto rodam, o que
        # derrubaria o app com "QThread: Destroyed while thread is still running".
        self._workers_vivos = []

        # Timer de debounce: aguarda 350ms após o usuário parar de digitar
        # para disparar nova busca no servidor (evita uma query por tecla).
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(350)
        self._search_timer.timeout.connect(self._perform_search)

        self._setup_ui()
        self._apply_theme()
        self._perform_search()
    
    def _setup_ui(self):
        """Configura interface do diálogo."""
        self.setWindowTitle("Buscar Produtos")
        self.setMinimumSize(900, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Campo de busca (para refinar resultado)
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        
        search_label = QLabel("Buscar:")
        search_label.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-weight: bold;"))
        search_layout.addWidget(search_label)

        self.txt_search = QLineEdit()
        self.txt_search.setText(self.search_text)
        self.txt_search.setPlaceholderText("Digite para refinar resultados...")
        self.txt_search.setMinimumHeight(35)
        self.txt_search.setStyleSheet(themed_qss("""
            QLineEdit {
                background-color: {{BG_TERTIARY}};
                color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}};
                border-radius: 5px;
                padding: 5px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: {{ACCENT}};
            }
        """))
        search_layout.addWidget(self.txt_search)

        layout.addLayout(search_layout)

        # Info de resultados
        self.lbl_info = QLabel("Carregando...")
        self.lbl_info.setStyleSheet(themed_qss("color: {{FG_DISABLED}}; font-size: 11px;"))
        layout.addWidget(self.lbl_info)
        
        # Tabela de resultados
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Código", "Descrição", "Grupo", "EAN", "Unidade"
        ])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(themed_qss("""
            QTableWidget {
                background-color: {{BG_TERTIARY}};
                color: {{FG_PRIMARY}};
                gridline-color: {{BORDER}};
                border: 1px solid {{BORDER}};
            }
            QTableWidget::item {
                padding: 5px;
                color: {{FG_PRIMARY}};
                background-color: {{BG_TERTIARY}};
            }
            QTableWidget::item:selected {
                background-color: {{ACCENT}};
                color: #ffffff;
            }
            QTableWidget::item:selected:active {
                background-color: {{ACCENT}};
                color: #ffffff;
            }
            QTableWidget::item:selected:!active {
                background-color: {{ACCENT_PRESSED}};
                color: #ffffff;
            }
            QTableWidget::item:hover {
                background-color: {{BG_HOVER}};
                color: {{FG_PRIMARY}};
            }
            QHeaderView::section {
                background-color: {{BG_TERTIARY}};
                color: {{FG_PRIMARY}};
                padding: 5px;
                border: none;
                font-weight: bold;
            }
        """))
        
        # Ajusta colunas
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Descrição
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Código
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Grupo
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # EAN
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Unidade
        
        layout.addWidget(self.table)
        
        # Barra de progresso
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(themed_qss("""
            QProgressBar {
                background-color: {{BG_TERTIARY}};
                border: 1px solid {{BORDER}};
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: {{ACCENT}};
            }
        """))
        layout.addWidget(self.progress)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(themed_qss("background-color: {{BORDER}};"))
        layout.addWidget(sep)
        
        # Botões de ação (Todos, Limpar)
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        
        btn_all = QPushButton("Todos")
        btn_all.setMinimumHeight(32)
        btn_all.setMaximumWidth(80)
        btn_all.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{BORDER}};
                color: {{FG_PRIMARY}};
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: {{BG_HOVER}};
            }
        """))
        btn_all.clicked.connect(self._select_all)
        action_layout.addWidget(btn_all)
        
        btn_clear = QPushButton("Limpar")
        btn_clear.setMinimumHeight(32)
        btn_clear.setMaximumWidth(80)
        btn_clear.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{BORDER}};
                color: {{FG_PRIMARY}};
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: {{BG_HOVER}};
            }
        """))
        btn_clear.clicked.connect(self._clear_selection)
        action_layout.addWidget(btn_clear)
        
        action_layout.addStretch()
        layout.addLayout(action_layout)
        
        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        lbl_count = QLabel("Nenhum produto selecionado")
        lbl_count.setStyleSheet(themed_qss("color: {{FG_DISABLED}}; font-size: 11px;"))
        # Mesma largura combinada de "Todos" (80px) + espaçamento (8px) + "Limpar" (80px),
        # para acomodar textos maiores ("N produtos selecionados") sem espremer o layout.
        lbl_count.setMinimumWidth(168)
        lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_count = lbl_count
        btn_layout.addWidget(lbl_count)
        
        btn_layout.addStretch()
        
        btn_select = QPushButton("Selecionar")
        btn_select.setMinimumHeight(35)
        btn_select.setMinimumWidth(120)
        btn_select.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{ACCENT}};
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: {{ACCENT_HOVER}};
            }
            QPushButton:pressed {
                background-color: {{ACCENT_PRESSED}};
            }
        """))
        btn_select.clicked.connect(self._on_select)
        btn_layout.addWidget(btn_select)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumHeight(35)
        btn_cancel.setMinimumWidth(120)
        btn_cancel.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{BORDER}};
                color: {{FG_PRIMARY}};
                border: none;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: {{BG_HOVER}};
            }
        """))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # Conecta sinais
        self.txt_search.textChanged.connect(self._on_search_text_changed)
        # Enter no campo do diálogo dispara busca imediatamente (sem debounce)
        self.txt_search.returnPressed.connect(self._perform_search)
        self.table.itemSelectionChanged.connect(self._update_count)
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)
    
    def _apply_theme(self):
        """Aplica o tema ativo (claro/escuro)."""
        self.setStyleSheet(themed_qss("""
            QDialog {
                background-color: {{BG_PRIMARY}};
            }
            QLabel {
                color: {{FG_PRIMARY}};
            }
        """))
    
    def _perform_search(self):
        """Executa a busca de produtos (primeira página), descartando a anterior."""
        # Um debounce pendente dispararia uma segunda busca logo depois desta.
        self._search_timer.stop()

        # Invalida a busca em andamento: o worker antigo pode já ter emitido o
        # resultado (sinal enfileirado), e sem o token ele seria aplicado por
        # cima do estado recém-limpo, duplicando as linhas.
        self._search_seq += 1
        self._descartar_worker_atual()

        self.current_page = 0
        self.all_loaded_products = []
        self._carregando = False
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate
        self.table.setRowCount(0)

        # Busca a primeira página
        self._load_next_page()

    def _load_next_page(self):
        """Carrega a próxima página de resultados."""
        if self._carregando:
            return  # já há uma página em voo; evita buscar o mesmo offset 2x
        self._carregando = True

        offset = self.current_page * self.page_size

        worker = ProductSearchWorker(
            seq=self._search_seq,
            search_text=self.txt_search.text(),
            company_code=self.company_code,
            limit=self.page_size,
            offset=offset
        )
        worker.resultados.connect(self._on_search_finished)
        worker.erro.connect(self._on_search_error)
        # `finished` aqui é o sinal nativo da QThread (emitido quando run()
        # retorna), não o resultado da busca.
        worker.finished.connect(lambda w=worker: self._esquecer_worker(w))

        self.worker = worker
        self._workers_vivos.append(worker)
        worker.start()

    def _descartar_worker_atual(self):
        """Solta os sinais do worker corrente para que seu resultado seja ignorado.

        A thread em si continua até terminar sozinha (a consulta já está no
        banco e não há como cancelá-la); ela permanece em `_workers_vivos` para
        não ser coletada enquanto roda. Não se usa `wait()` aqui de propósito:
        isso congelaria a janela pelo tempo da consulta anterior.
        """
        if self.worker is None:
            return
        for sinal in (self.worker.resultados, self.worker.erro):
            try:
                sinal.disconnect()
            except (TypeError, RuntimeError):
                pass  # já desconectado ou objeto C++ destruído
        self.worker = None

    def _esquecer_worker(self, worker):
        """Remove da lista um worker que já terminou de rodar."""
        if worker in self._workers_vivos:
            self._workers_vivos.remove(worker)
        if self.worker is worker:
            self.worker = None

    def _on_search_finished(self, seq: int, results: list, total: int):
        """Callback quando busca termina."""
        if seq != self._search_seq:
            return  # resultado de uma busca já superada

        self._carregando = False
        self.progress.setVisible(False)
        self.total_products = total

        # Calculado ANTES do extend: a posição de inserção é sempre o fim do
        # que já foi carregado, independente de página.
        start_row = len(self.all_loaded_products)
        self.all_loaded_products.extend(results)
        self.table.setRowCount(len(self.all_loaded_products))

        for row_idx, product in enumerate(results):
            row = start_row + row_idx

            # Código — não usar setForeground; cor controlada pelo CSS
            self.table.setItem(row, 0, QTableWidgetItem(str(product.get("codproduto", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(product.get("descricaoproduto", ""))))
            self.table.setItem(row, 2, QTableWidgetItem(str(product.get("nomegrupo", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(product.get("codeanunidade", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(product.get("unidade", ""))))

        self.current_page += 1
        self._update_info_label()

    def _on_search_error(self, seq: int, error_msg: str):
        """Callback em caso de erro na busca."""
        if seq != self._search_seq:
            return  # erro de uma busca já superada

        self._carregando = False
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Erro na Busca", f"Erro ao buscar produtos:\n{error_msg}")

    def done(self, result: int):
        """Fecha o diálogo só depois que as threads em voo terminarem.

        Sem isso o diálogo (e com ele os workers) pode ser destruído com uma
        consulta ainda rodando. A espera é pontual, só no fechamento.
        """
        self._search_seq += 1  # invalida qualquer resultado ainda por chegar
        self._descartar_worker_atual()
        for worker in list(self._workers_vivos):
            try:
                worker.wait()
            except RuntimeError:
                pass
        self._workers_vivos.clear()
        super().done(result)
    
    def _on_scroll(self, value: int):
        """Detecta se o usuário scrollou até o fim da tabela para lazy load."""
        scrollbar = self.table.verticalScrollBar()
        
        # Se chegou perto do fim (90%) e ainda há mais produtos a carregar
        if scrollbar.maximum() > 0:
            percentage = (value / scrollbar.maximum()) * 100
            
            if percentage >= 85 and len(self.all_loaded_products) < self.total_products:
                # Carrega próxima página
                self.progress.setVisible(True)
                self.progress.setRange(0, 0)
                self._load_next_page()
    
    def _on_search_text_changed(self):
        """Dispara debounce para busca no servidor ao digitar."""
        # Reinicia o timer a cada tecla; a busca real dispara após 350 ms
        # de inatividade via self._search_timer.timeout → _perform_search.
        self._search_timer.start()
    
    def _update_info_label(self):
        """Atualiza rótulo de informações."""
        total_visible = sum(1 for i in range(self.table.rowCount()) if not self.table.isRowHidden(i))
        
        if self.total_products == 0:
            self.lbl_info.setText("Nenhum produto encontrado")
        elif len(self.all_loaded_products) < self.total_products:
            self.lbl_info.setText(
                f"Exibindo {len(self.all_loaded_products)} de {self.total_products} produtos "
                f"({total_visible} visíveis) - Role para carregar mais"
            )
        else:
            self.lbl_info.setText(
                f"Total: {self.total_products} produtos ({total_visible} visíveis)"
            )
    
    def _update_count(self):
        """Atualiza contagem de selecionados."""
        count = len(self.table.selectedIndexes()) // self.table.columnCount()
        if count == 0:
            self.lbl_count.setText("Nenhum produto selecionado")
        elif count == 1:
            self.lbl_count.setText("1 produto selecionado")
        else:
            self.lbl_count.setText(f"{count} produtos selecionados")
    
    def _select_all(self):
        """Seleciona todos os produtos visíveis."""
        # selectAll() é método nativo Qt — funciona sempre
        self.table.selectAll()
        # Se houver linhas ocultas (filtro ativo), desseleciona elas
        has_hidden = any(self.table.isRowHidden(r) for r in range(self.table.rowCount()))
        if has_hidden:
            model = self.table.model()
            sel_model = self.table.selectionModel()
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    sel_model.select(
                        model.index(row, 0),
                        QItemSelectionModel.SelectionFlag.Deselect
                        | QItemSelectionModel.SelectionFlag.Rows
                    )
        self._update_count()

    def _clear_selection(self):
        """Limpa a seleção de todos os produtos."""
        self.table.clearSelection()
        self._update_count()
    
    def _on_select(self):
        """Retorna produtos selecionados."""
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        
        if not selected_rows:
            QMessageBox.warning(self, "Aviso", "Selecione ao menos um produto.")
            return
        
        # Coleta dados dos produtos selecionados (ignora linhas ocultas pelo filtro)
        selected_products = []
        for row in sorted(selected_rows):
            if self.table.isRowHidden(row):
                continue
            # Mantém código como string para preservar zeros à esquerda
            codigo = self.table.item(row, 0).text().strip()
            descricao = self.table.item(row, 1).text().strip()
            # Formata como "CÓDIGO - DESCRIÇÃO" para melhor legibilidade
            selected_products.append((codigo, f"{codigo} - {descricao}"))
        
        # Armazena para recuperação posterior
        self._last_selected = selected_products
        
        self.products_selected.emit(selected_products)
        self.accept()
