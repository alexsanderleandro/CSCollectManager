"""
stock_analysis_page.py
=======================
Página "Análise de Estoque" — anexa PDFs de contagem do coletor, confere o
estoque atual no ERP e aciona a IA para redigir a análise das divergências.
"""

import html as html_lib
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDateEdit, QSpinBox,
    QRadioButton, QButtonGroup, QTextEdit, QFileDialog, QMenu,
    QMessageBox, QGroupBox, QSizePolicy, QCheckBox, QStyledItemDelegate, QStyle,
    QTabWidget, QApplication
)
from PySide6.QtCore import Qt, QDate, QEvent, QThreadPool, QMarginsF, QPointF, QRectF, QSizeF
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetricsF, QImage, QPainter, QPen,
    QPdfWriter, QPageSize, QPageLayout, QTextDocument
)

from app.styles import themed_qss, get_active_theme
from services.pdf_contagem_parser import PdfContagemParser, ContagemPDF
from services.stock_analysis_service import (
    StockAnalysisService, StockAnalysisValidationError, ResultadoAnalise, MAX_PDFS_ANALISE
)
from services.ai_config_service import AIConfigService
from services.ai_client import AIClient, AIClientError
from utils.workers import WorkerSignals, TaskRunnable
from utils.config import AppConfig
from utils.constants import APP_INFO
from utils.logger import get_logger

logger = get_logger(__name__)

_SITUACAO_LABEL = {
    "confere": "Confere",
    "falta": "Falta",
    "sobra": "Sobra",
    "lote_novo": "Lote novo",
    "nao_contado": "Não contado",
}
_SITUACAO_COR = {
    "confere": "{{SUCCESS}}",
    "falta": "{{ERROR}}",
    "sobra": "{{WARNING}}",
    "lote_novo": "{{ACCENT}}",
    "nao_contado": "{{FG_DISABLED}}",
}

# Colunas fixas da grade; as de contado (uma por PDF) começam em _COL_CONTADO.
_COL_PRODUTO, _COL_DESCRICAO, _COL_LOTE, _COL_CONTADO = 0, 1, 2, 3
_MARCA_BASE = "● "  # prefixo no cabeçalho da coluna de contado usada como base


class _DelegateFundoCelula(QStyledItemDelegate):
    """Pinta a cor de fundo definida na célula (``setBackground``).

    Com folha de estilo (QSS) no app, o Qt ignora o fundo da célula e usa o
    do QSS — o destaque simplesmente não aparecia. Aqui a cor (translúcida) é
    aplicada por cima, depois do desenho normal; linha selecionada fica só
    com a cor da seleção.
    """

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        fundo = index.data(Qt.ItemDataRole.BackgroundRole)
        if isinstance(fundo, (QBrush, QColor)) and not (option.state & QStyle.StateFlag.State_Selected):
            painter.fillRect(option.rect, fundo)


class StockAnalysisPage(QWidget):
    """Página de análise de estoque (anexar PDFs → comparar → IA)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parser = PdfContagemParser()
        self._service = StockAnalysisService()
        self._contagens: List[ContagemPDF] = []
        # PDF único usado como referência da grade (duplo clique na lista).
        # None = agregado de todos os PDFs anexados (comportamento padrão).
        self._contagem_referencia: Optional[ContagemPDF] = None
        self._resultado: Optional[ResultadoAnalise] = None
        self._analise_ia_texto: str = ""
        # Incrementada a cada nova comparação disparada (troca de data/local de
        # estoque); descarta resultados de uma comparação anterior que ainda
        # não tinha voltado do worker quando o usuário já mudou o parâmetro de
        # novo — sem isso, uma resposta lenta da consulta anterior podia
        # sobrescrever a grade com dados de uma data que não é mais a atual.
        self._analise_geracao = 0
        # Parâmetros (data, local, PDFs) do resultado que está na grade.
        self._contexto_resultado: Optional[dict] = None
        # PDF (id) da coluna base da diferença — sobrevive a um recálculo por
        # troca de data/local, para a escolha do usuário não se perder.
        self._pdf_base_id: Optional[int] = None
        # PDFs (id) que o usuário tirou da exportação e da IA.
        self._pdfs_fora_export: set = set()
        # Estoque do sistema do cálculo anterior (mesma grade, outra
        # data/local), para destacar o que mudou.
        self._sistema_antes: dict = {}
        self._data_antes: Optional[date] = None
        self._codempresa = ""
        self._nome_empresa = ""
        self._nome_usuario = ""
        self._locais_estoque_mode = "A"
        self._setup_ui()

    # ------------------------------------------------------------------
    # Configuração externa (chamada pela MainWindowERP)
    # ------------------------------------------------------------------

    def set_empresa_info(self, codigo, nome: str):
        """Define a empresa logada, usada para validar os PDFs anexados."""
        self._codempresa = str(codigo or "")
        self._nome_empresa = nome or ""

    def set_usuario_info(self, nome: str):
        """Usuário logado — vai no rodapé dos PDFs exportados ("Gerado por")."""
        self._nome_usuario = nome or ""

    def configure_local_estoque(self, modo: str, locais_list: Optional[List[str]] = None):
        """
        Configura as opções de local de estoque conforme a configuração do
        sistema (mesmo padrão de ``widgets/filter_panel.py``).

        Args:
            modo: "L"=Loja, "D"=Depósito, "A"=Loja e Depósito, "T"=lista.
            locais_list: Lista de ENDLOCALESTOQUE (usado apenas no modo "T").
        """
        for btn in list(self._radio_local_group.buttons()):
            self._radio_local_group.removeButton(btn)
            self._local_layout.removeWidget(btn)
            btn.deleteLater()

        self._locais_estoque_mode = modo
        if modo == "L":
            options = [("Loja", "L")]
        elif modo == "D":
            options = [("Depósito", "D")]
        elif modo == "T" and locais_list:
            options = [(val, val) for val in locais_list]
        else:
            options = [("Loja", "L"), ("Depósito", "D")]

        for i, (label, value) in enumerate(options):
            radio = QRadioButton(label)
            radio.setProperty("local_value", value)
            radio.setStyleSheet(themed_qss("QRadioButton { color: {{FG_PRIMARY}}; }"))
            if i == 0:
                radio.setChecked(True)
            self._radio_local_group.addButton(radio, i + 1)
            self._local_layout.addWidget(radio)

    def _get_local_estoque_value(self) -> str:
        btn = self._radio_local_group.checkedButton()
        return btn.property("local_value") if btn else "L"

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        from views.main_window_erp import ModuleHeader

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = ModuleHeader(
            "🔎",
            "Análise de Estoque",
            "Compare a contagem do coletor com o estoque do sistema",
        )
        layout.addWidget(header)

        content = QWidget()
        content.setStyleSheet(themed_qss("background-color: {{BG_PRIMARY}};"))
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(12)

        # ----- Toolbar: anexar / limpar / data -----
        toolrow = QHBoxLayout()
        toolrow.setSpacing(10)

        self._btn_anexar = QPushButton("📎  Anexar PDFs...")
        self._btn_anexar.setMinimumHeight(36)
        self._btn_anexar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_anexar.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{BG_HOVER}}; color: {{FG_PRIMARY}};
                border: none; border-radius: 8px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: {{BG_SELECTED}}; }
        """))
        self._btn_anexar.clicked.connect(self._on_anexar_clicked)
        toolrow.addWidget(self._btn_anexar)

        self._btn_limpar = QPushButton("Limpar")
        self._btn_limpar.setMinimumHeight(36)
        self._btn_limpar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_limpar.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{BG_HOVER}}; color: {{FG_PRIMARY}};
                border: none; border-radius: 8px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: {{BG_SELECTED}}; }
        """))
        self._btn_limpar.clicked.connect(self._on_limpar_clicked)
        toolrow.addWidget(self._btn_limpar)

        toolrow.addStretch()

        toolrow.addWidget(QLabel("Data de referência:"))
        self._date_referencia = QDateEdit()
        self._date_referencia.setCalendarPopup(True)
        self._date_referencia.setDate(QDate.currentDate())
        self._date_referencia.setMinimumHeight(36)
        self._date_referencia.setMinimumWidth(140)
        self._date_referencia.setStyleSheet(themed_qss("""
            QDateEdit {
                background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}}; border-radius: 6px; padding: 4px 8px;
            }
        """))
        self._date_referencia.dateChanged.connect(self._on_parametros_alterados)
        toolrow.addWidget(self._date_referencia)
        content_layout.addLayout(toolrow)

        # ----- Local de estoque -----
        group_local = QGroupBox("Local de Estoque")
        group_local.setStyleSheet(themed_qss("""
            QGroupBox { color: {{FG_PRIMARY}}; border: 1px solid {{BORDER}}; border-radius: 8px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
        """))
        self._local_layout = QHBoxLayout(group_local)
        self._local_layout.setSpacing(16)
        self._radio_local_group = QButtonGroup(self)
        self._radio_local_group.buttonClicked.connect(self._on_parametros_alterados)
        content_layout.addWidget(group_local)
        self.configure_local_estoque("A", None)

        # ----- Lista de PDFs anexados -----
        self._lbl_pdf_info = QLabel(f"Nenhum PDF anexado (máximo {MAX_PDFS_ANALISE}).")
        self._lbl_pdf_info.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        content_layout.addWidget(self._lbl_pdf_info)

        self._pdf_list = QListWidget()
        self._pdf_list.setMaximumHeight(110)
        self._pdf_list.setToolTip("Duplo clique para mostrar só este arquivo na grade")
        self._pdf_list.setStyleSheet(themed_qss("""
            QListWidget { background-color: {{BG_SECONDARY}}; border: 1px solid {{BORDER}}; border-radius: 6px; }
        """))
        self._pdf_list.itemDoubleClicked.connect(self._on_pdf_double_clicked)
        content_layout.addWidget(self._pdf_list)

        # ----- Abas: grade comparativa | análise da IA -----
        # A análise da IA é texto corrido e longo: numa aba própria ela usa a
        # área inteira da grade, em vez de uma faixa espremida embaixo dela.
        self._abas = QTabWidget()
        aba_grade = QWidget()
        aba_grade_layout = QVBoxLayout(aba_grade)
        aba_grade_layout.setContentsMargins(0, 8, 0, 0)
        aba_grade_layout.setSpacing(8)

        # ----- Base da diferença + colunas para exportação/IA -----
        # Só aparece com mais de um PDF na grade: com um só não há o que escolher.
        self._linha_colunas = QWidget()
        linha_colunas = QHBoxLayout(self._linha_colunas)
        linha_colunas.setContentsMargins(0, 0, 0, 0)
        linha_colunas.setSpacing(12)
        self._lbl_base = QLabel("")
        self._lbl_base.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        linha_colunas.addWidget(self._lbl_base)
        linha_colunas.addStretch()
        _lbl_export = QLabel("Considerar na exportação e na IA:")
        _lbl_export.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        linha_colunas.addWidget(_lbl_export)
        self._layout_checks_export = QHBoxLayout()
        self._layout_checks_export.setSpacing(12)
        linha_colunas.addLayout(self._layout_checks_export)
        self._checks_export: List[QCheckBox] = []
        self._linha_colunas.setVisible(False)
        aba_grade_layout.addWidget(self._linha_colunas)

        # ----- Tabela de divergências -----
        self._table = QTableWidget()
        self._table.setItemDelegate(_DelegateFundoCelula(self._table))
        self._montar_cabecalho()
        # Clique no cabeçalho de uma coluna de contado = usar como base da diferença.
        self._table.horizontalHeader().sectionClicked.connect(self._on_cabecalho_clicado)
        # Larguras calculadas em `_ajustar_colunas` (não Stretch): numa coluna
        # esticada o texto que não cabe é cortado com "...", e aqui nenhum
        # valor pode sair cortado. Sem quebra de linha nem reticências — se a
        # janela for estreita demais, aparece a rolagem horizontal.
        self._table.setWordWrap(False)
        self._table.setTextElideMode(Qt.TextElideMode.ElideNone)
        _fonte_cab = self._table.horizontalHeader().font()
        _fonte_cab.setBold(True)  # o QSS também põe negrito; aqui é para a medida da largura contar com ele
        self._table.horizontalHeader().setFont(_fonte_cab)
        # Mede todas as linhas (o padrão do Qt amostra só ~1000): um valor
        # longo lá embaixo também não pode sair cortado.
        self._table.horizontalHeader().setResizeContentsPrecision(-1)
        self._table.viewport().installEventFilter(self)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(themed_qss("""
            QTableWidget {
                background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}}; gridline-color: {{BORDER}}; font-size: 10pt;
            }
            QTableWidget::item:selected { background-color: {{ACCENT}}; color: #ffffff; }
            QHeaderView::section {
                background-color: {{BG_TERTIARY}}; color: {{FG_SECONDARY}};
                border: none; border-bottom: 1px solid {{BORDER}}; padding: 6px 8px; font-weight: bold;
            }
            QTableWidget::item:alternate { background-color: {{BG_TERTIARY}}; }
        """))
        aba_grade_layout.addWidget(self._table, 1)
        self._abas.addTab(aba_grade, "📊  Resultado comparativo")

        # ----- Aba da análise da IA -----
        aba_ia = QWidget()
        aba_ia_layout = QVBoxLayout(aba_ia)
        aba_ia_layout.setContentsMargins(0, 8, 0, 0)
        aba_ia_layout.setSpacing(8)
        # Com a análise numa aba separada da grade, fica registrado de quais
        # dados ela saiu — a grade pode mudar depois (data, base da diferença).
        self._lbl_contexto_ia = QLabel("")
        self._lbl_contexto_ia.setWordWrap(True)
        self._lbl_contexto_ia.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        aba_ia_layout.addWidget(self._lbl_contexto_ia)
        self._txt_analise = QTextEdit()
        self._txt_analise.setReadOnly(True)
        self._txt_analise.setPlaceholderText(
            "A análise aparece aqui depois de clicar em \"🤖 Analisar com IA\", abaixo."
        )
        # Largura máxima: numa tela larga, linhas de texto do tamanho da janela
        # inteira ficam cansativas de acompanhar.
        self._txt_analise.setMaximumWidth(1100)
        self._txt_analise.setStyleSheet(themed_qss("""
            QTextEdit {
                background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}}; border-radius: 8px; padding: 14px; font-size: 10.5pt;
            }
        """))
        aba_ia_layout.addWidget(self._txt_analise, 1)
        self._abas.addTab(aba_ia, "🤖  Análise da IA")
        self._contexto_ia_pendente = ""

        content_layout.addWidget(self._abas, 1)

        # ----- Toolbar: analisar / limite / exportar -----
        toolrow2 = QHBoxLayout()
        toolrow2.setSpacing(10)

        self._btn_analisar_ia = QPushButton("🤖  Analisar com IA")
        self._btn_analisar_ia.setMinimumHeight(36)
        self._btn_analisar_ia.setEnabled(False)
        self._btn_analisar_ia.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_analisar_ia.setStyleSheet(themed_qss("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {{ACCENT}}, stop:1 #1d6bb0);
                color: white; border: none; border-radius: 8px; padding: 8px 20px; font-weight: bold;
            }
            QPushButton:disabled { background: {{BG_HOVER}}; color: {{FG_DISABLED}}; }
        """))
        self._btn_analisar_ia.clicked.connect(self._on_analisar_ia_clicked)
        toolrow2.addWidget(self._btn_analisar_ia)

        toolrow2.addWidget(QLabel("Enviar"))
        self._spin_limite = QSpinBox()
        self._spin_limite.setMinimum(0)
        self._spin_limite.setMaximum(0)
        self._spin_limite.setMinimumHeight(36)
        self._spin_limite.setStyleSheet(themed_qss("""
            QSpinBox { background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}}; border: 1px solid {{BORDER}}; border-radius: 6px; padding: 4px; }
        """))
        toolrow2.addWidget(self._spin_limite)
        self._lbl_limite = QLabel("divergências")
        self._lbl_limite.setStyleSheet(themed_qss("color: {{FG_SECONDARY}};"))
        toolrow2.addWidget(self._lbl_limite)

        toolrow2.addStretch()

        self._btn_exportar = QPushButton("Exportar  ▾")
        self._btn_exportar.setMinimumHeight(36)
        self._btn_exportar.setEnabled(False)
        self._btn_exportar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_exportar.setStyleSheet(themed_qss("""
            QPushButton {
                background-color: {{BG_HOVER}}; color: {{FG_PRIMARY}};
                border: none; border-radius: 8px; padding: 8px 16px;
            }
            QPushButton:hover { background-color: {{BG_SELECTED}}; }
            QPushButton:disabled { color: {{FG_DISABLED}}; }
        """))
        self._btn_exportar.clicked.connect(self._on_exportar_clicked)
        toolrow2.addWidget(self._btn_exportar)

        content_layout.addLayout(toolrow2)

        self._lbl_status = QLabel("")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        content_layout.addWidget(self._lbl_status)

        layout.addWidget(content)

    # ------------------------------------------------------------------
    # Anexar / limpar PDFs
    # ------------------------------------------------------------------

    def _on_anexar_clicked(self):
        arquivos, _ = QFileDialog.getOpenFileNames(
            self, "Anexar PDFs de contagem", AppConfig.get_last_pdf_dir(), "PDF (*.pdf)"
        )
        if not arquivos:
            return
        AppConfig.set_last_pdf_dir(os.path.dirname(arquivos[0]))

        def _chave(caminho):
            return os.path.normcase(os.path.abspath(caminho))

        # O mesmo arquivo duas vezes viraria duas colunas idênticas.
        ja_anexados = {_chave(c.arquivo) for c in self._contagens}
        novos, repetidos = [], []
        for a in arquivos:
            if _chave(a) in ja_anexados:
                repetidos.append(os.path.basename(a))
            else:
                ja_anexados.add(_chave(a))
                novos.append(a)
        if repetidos:
            QMessageBox.information(
                self, "PDF já anexado",
                "Estes arquivos já estão na análise e foram ignorados:\n\n"
                + "\n".join(f"  • {r}" for r in repetidos)
            )
        if not novos:
            return

        vagas = MAX_PDFS_ANALISE - len(self._contagens)
        if len(novos) > vagas:
            if vagas <= 0:
                detalhe = (f"Já há {MAX_PDFS_ANALISE} PDFs anexados. Use \"Limpar\" "
                           f"para começar outra análise.")
            else:
                detalhe = (f"Já há {len(self._contagens)} anexado(s); selecione no "
                           f"máximo {vagas} arquivo(s).")
            QMessageBox.warning(
                self, "Limite de PDFs",
                f"A análise compara no máximo {MAX_PDFS_ANALISE} PDFs, um por coluna "
                f"de contado.\n\n{detalhe}"
            )
            return
        arquivos = novos

        self._btn_anexar.setEnabled(False)
        self._lbl_status.setText("🔄 Lendo PDF(s)...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))

        signals = WorkerSignals()
        signals.finished.connect(self._on_pdfs_lidos)
        signals.error.connect(self._on_pdfs_erro)
        runnable = TaskRunnable(self._ler_pdfs, args=(arquivos,), signals=signals)
        QThreadPool.globalInstance().start(runnable)

    def _ler_pdfs(self, arquivos: List[str]) -> List[ContagemPDF]:
        return [self._parser.parse(a) for a in arquivos]

    def _on_pdfs_lidos(self, novas_contagens: List[ContagemPDF]):
        self._btn_anexar.setEnabled(True)

        candidatas = self._contagens + novas_contagens
        try:
            self._service.validar_empresa(candidatas, self._codempresa)
        except StockAnalysisValidationError as e:
            QMessageBox.critical(self, "Empresa Inválida", str(e))
            self._lbl_status.setText("❌ PDF(s) rejeitado(s) — empresa não confere.")
            self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))
            return

        self._contagens = candidatas
        # Anexar mais arquivos volta ao agregado por padrão — a referência
        # anterior pode nem fazer mais sentido junto do que acabou de entrar.
        self._contagem_referencia = None
        for c in novas_contagens:
            item = QListWidgetItem(self._texto_item_pdf(c, ativo=False))
            item.setData(Qt.ItemDataRole.UserRole, c)
            self._pdf_list.addItem(item)

        self._atualizar_lbl_pdf_info()

        if novas_contagens:
            maior_data = max(c.data_exportacao for c in novas_contagens).date()
            # Sem sinal: a comparação roda uma vez só, logo abaixo — senão a
            # troca de data dispararia uma segunda consulta idêntica.
            self._date_referencia.blockSignals(True)
            self._date_referencia.setDate(QDate(maior_data.year, maior_data.month, maior_data.day))
            self._date_referencia.blockSignals(False)

        self._rodar_comparacao()

    def _on_pdfs_erro(self, exc: Exception):
        self._btn_anexar.setEnabled(True)
        QMessageBox.critical(self, "Erro ao Ler PDF", str(exc))
        self._lbl_status.setText(f"❌ Erro ao ler PDF: {exc}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    def _texto_item_pdf(self, c: ContagemPDF, ativo: bool) -> str:
        marcador = "📌" if ativo else "✓"
        return (
            f"{marcador} {os.path.basename(c.arquivo)} · "
            f"{c.total_produtos_contados} produtos · {c.total_registros} registros"
        )

    def _atualizar_lbl_pdf_info(self):
        anexados = f"{len(self._contagens)} de {MAX_PDFS_ANALISE} PDF(s) anexado(s)"
        if self._contagem_referencia is not None:
            self._lbl_pdf_info.setText(
                f"{anexados} · "
                f"Mostrando apenas: {os.path.basename(self._contagem_referencia.arquivo)}"
            )
        else:
            self._lbl_pdf_info.setText(f"{anexados}.")

    def _atualizar_marcadores_lista(self):
        """Redesenha o marcador (📌/✓) de cada item conforme a referência ativa."""
        for i in range(self._pdf_list.count()):
            item = self._pdf_list.item(i)
            c = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self._texto_item_pdf(c, ativo=(c is self._contagem_referencia)))

    def _on_pdf_double_clicked(self, item: QListWidgetItem):
        """Define (ou desmarca, se já ativo) o PDF clicado como referência da grade."""
        c = item.data(Qt.ItemDataRole.UserRole)
        if c is None:
            return
        self._contagem_referencia = None if self._contagem_referencia is c else c
        self._atualizar_marcadores_lista()
        self._atualizar_lbl_pdf_info()
        self._rodar_comparacao()

    def _on_limpar_clicked(self):
        self._analise_geracao += 1  # descarta uma consulta ainda em andamento
        self._contagens = []
        self._contagem_referencia = None
        self._resultado = None
        self._contexto_resultado = None
        self._pdf_base_id = None
        self._pdfs_fora_export = set()
        self._sistema_antes = {}
        self._data_antes = None
        self._analise_ia_texto = ""
        self._pdf_list.clear()
        self._table.setRowCount(0)
        self._table.setEnabled(True)
        self._montar_cabecalho()
        self._ajustar_colunas()
        self._montar_opcoes_colunas()
        self._lbl_pdf_info.setText(f"Nenhum PDF anexado (máximo {MAX_PDFS_ANALISE}).")
        self._txt_analise.clear()
        self._lbl_contexto_ia.setText("")
        self._abas.setCurrentIndex(0)
        self._btn_analisar_ia.setEnabled(False)
        self._btn_exportar.setEnabled(False)
        self._spin_limite.setMaximum(0)
        self._lbl_status.setText("")

    def _on_parametros_alterados(self, *_args):
        """Refaz a comparação quando a data ou o local de estoque mudam."""
        if self._contagens:
            self._rodar_comparacao()

    # ------------------------------------------------------------------
    # Comparação com o ERP
    # ------------------------------------------------------------------

    def _rodar_comparacao(self):
        data_referencia = self._date_referencia.date().toPython()
        local_estoque = self._get_local_estoque_value()

        # Com referência ativa, roda a mesma análise só para aquele PDF —
        # não dá para filtrar o resultado agregado depois de pronto, porque
        # _agrupar_itens soma quantidades quando dois PDFs têm o mesmo
        # (codigo, lote); uma linha do agregado pode não ter contrapartida
        # em nenhum arquivo isolado.
        contagens = [self._contagem_referencia] if self._contagem_referencia else self._contagens

        self._analise_geracao += 1
        contexto = {
            "geracao": self._analise_geracao,
            "data": data_referencia,
            "local": local_estoque,
            "codempresa": self._codempresa,
            # Mesma grade (mesmos PDFs) é o que permite comparar "antes x
            # depois" quando só a data ou o local de estoque mudou. A ordem é
            # a das colunas de contado.
            "pdfs": tuple(id(c) for c in contagens),
            "arquivos": [os.path.basename(c.arquivo) for c in contagens],
        }

        # Grade esmaecida e ações travadas enquanto o estoque é recalculado:
        # o que está na tela ainda é da data anterior.
        self._table.setEnabled(False)
        self._btn_analisar_ia.setEnabled(False)
        self._btn_exportar.setEnabled(False)
        self._lbl_status.setText(
            f"⏳ Consultando o estoque do sistema em {data_referencia:%d/%m/%Y}..."
        )
        self._lbl_status.setStyleSheet(themed_qss("color: {{WARNING}}; font-size: 9pt; font-weight: bold;"))

        signals = WorkerSignals()
        # Métodos da página, nunca lambda: com lambda o Qt entrega a resposta
        # no contexto do próprio `signals`, que é destruído assim que o worker
        # termina — a resposta era descartada antes de chegar na tela.
        signals.finished.connect(self._on_comparacao_pronta)
        signals.error.connect(self._on_comparacao_erro)
        runnable = TaskRunnable(
            self._analisar_em_background, args=(contexto, contagens), signals=signals,
        )
        QThreadPool.globalInstance().start(runnable)

    def _analisar_em_background(self, contexto: dict, contagens: List[ContagemPDF]):
        """Roda no worker. Devolve o contexto junto do resultado para o slot
        saber a qual pedido a resposta pertence."""
        try:
            resultado = self._service.analisar(
                contagens, contexto["data"], contexto["local"], contexto["codempresa"]
            )
        except Exception as exc:
            exc.contexto_analise = contexto
            raise
        return contexto, resultado

    def _on_comparacao_pronta(self, payload):
        contexto, resultado = payload
        if contexto["geracao"] != self._analise_geracao:
            return  # data/local já mudou de novo antes desta resposta voltar

        # Mesma grade (mesmos PDFs) com outra data/local: guarda o estoque do
        # cálculo anterior para destacar o que mudou.
        contexto_anterior = self._contexto_resultado
        if (contexto_anterior is not None and self._resultado is not None
                and contexto_anterior["pdfs"] == contexto["pdfs"]):
            self._sistema_antes = {(i.codigo, i.lote): i.sistema for i in self._resultado.itens}
            self._data_antes = contexto_anterior["data"]
        else:
            self._sistema_antes = {}
            self._data_antes = None

        # Mantém a coluna base escolhida pelo usuário enquanto o PDF dela
        # estiver na grade; senão, a base é a primeira coluna de contado.
        pdfs = contexto["pdfs"]
        indice_base = pdfs.index(self._pdf_base_id) if self._pdf_base_id in pdfs else 0
        self._pdf_base_id = pdfs[indice_base] if pdfs else None
        if indice_base != resultado.indice_base:
            self._service.aplicar_base(resultado, indice_base)

        self._resultado = resultado
        self._contexto_resultado = contexto
        self._atualizar_grade()
        self._table.setEnabled(True)

        alterados = sum(
            1 for i in resultado.itens
            if (i.codigo, i.lote) in self._sistema_antes
            and self._sistema_antes[(i.codigo, i.lote)] != i.sistema
        )
        texto = (
            f"✅ Grade calculada com o estoque de {contexto['data']:%d/%m/%Y} "
            f"(às {datetime.now():%H:%M:%S}) · {resultado.total_produtos} produtos · "
            f"{resultado.total_itens} registros · {self._texto_totais()}"
        )
        if self._data_antes is not None:
            referencia = f"{self._data_antes:%d/%m/%Y}"
            if alterados:
                texto += (f" · {alterados} registro(s) com estoque diferente de "
                          f"{referencia} (destacados na grade)")
            else:
                texto += f" · nenhum estoque do sistema mudou em relação a {referencia}"
        self._mostrar_status_ok(texto)

    def _on_cabecalho_clicado(self, coluna: int):
        """Clique no cabeçalho de uma coluna de contado: ela vira a base da
        diferença. Recalcula na hora — o estoque do sistema não muda com a
        coluna, então não há consulta ao ERP."""
        resultado = self._resultado
        if resultado is None or not self._table.isEnabled():
            return
        indice = coluna - _COL_CONTADO
        if not (0 <= indice < len(resultado.colunas)) or indice == resultado.indice_base:
            return
        self._service.aplicar_base(resultado, indice)
        self._pdf_base_id = self._contexto_resultado["pdfs"][indice]
        self._atualizar_grade()
        self._mostrar_status_ok(
            f"✅ Diferença recalculada com base em {resultado.colunas[indice]} · "
            f"{self._texto_totais(incluir_base=False)}"
        )

    def _mostrar_status_ok(self, texto: str):
        self._lbl_status.setText(texto)
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt; font-weight: bold;"))

    def _texto_totais(self, incluir_base: bool = True) -> str:
        r = self._resultado
        partes = []
        if incluir_base and len(r.colunas) > 1:
            partes.append(f"base: {r.colunas[r.indice_base]}")
        partes.append(f"{r.total_falta + r.total_sobra} divergências")
        partes.append(f"{r.total_lote_novo} lotes novos")
        if r.total_nao_contado:
            partes.append(f"{r.total_nao_contado} não contado(s) em {r.colunas[r.indice_base]}")
        return " · ".join(partes)

    def _atualizar_grade(self):
        """Cabeçalho, linhas, larguras, totais e opções de coluna para o
        resultado atual (depois de um cálculo ou de uma troca de base)."""
        self._montar_cabecalho()
        self._popular_tabela()
        self._ajustar_colunas()
        self._montar_opcoes_colunas()

        total_divergencias = self._resultado.total_falta + self._resultado.total_sobra
        self._spin_limite.setMaximum(max(total_divergencias, 0))
        self._spin_limite.setValue(total_divergencias)
        self._lbl_limite.setText(f"de {total_divergencias} divergências")
        self._atualizar_botoes_resultado()

    def _on_comparacao_erro(self, exc: Exception):
        contexto = getattr(exc, "contexto_analise", None)
        if contexto is not None and contexto["geracao"] != self._analise_geracao:
            return  # erro de uma comparação anterior, já substituída
        # A grade continua com o último resultado válido (e o cabeçalho
        # "Sistema em ..." com a data dele) — só volta a ficar utilizável.
        self._table.setEnabled(True)
        self._atualizar_botoes_resultado()
        QMessageBox.critical(self, "Erro na Consulta ao ERP", str(exc))
        self._lbl_status.setText(f"❌ Erro ao consultar estoque: {exc}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    def _atualizar_botoes_resultado(self):
        resultado = self._resultado
        tem_divergencia = bool(resultado) and (resultado.total_falta + resultado.total_sobra) > 0
        self._btn_analisar_ia.setEnabled(tem_divergencia and AIConfigService().is_configured())
        self._btn_exportar.setEnabled(resultado is not None)

    def _montar_cabecalho(self):
        """Colunas da grade: Produto, Descrição, Lote, um Contado por PDF,
        Sistema (com a data), Diferença, Situação. Sem resultado, uma coluna
        Contado genérica."""
        r = self._resultado
        colunas = r.colunas if r else ["Contado"]
        varias = len(colunas) > 1
        base = r.indice_base if r else 0
        data_ref = self._contexto_resultado["data"] if (r and self._contexto_resultado) else None

        rotulos = ["Produto", "Descrição", "Lote"]
        rotulos += [(_MARCA_BASE + c) if (varias and i == base) else c for i, c in enumerate(colunas)]
        rotulos += [f"Sistema em {data_ref:%d/%m/%Y}" if data_ref else "Sistema", "Diferença", "Situação"]
        self._table.setColumnCount(len(rotulos))
        self._table.setHorizontalHeaderLabels(rotulos)

        esquerda = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        for col in (_COL_PRODUTO, _COL_DESCRICAO, _COL_LOTE, len(rotulos) - 1):
            self._table.horizontalHeaderItem(col).setTextAlignment(esquerda)

        if r and self._contexto_resultado:
            arquivos = self._contexto_resultado.get("arquivos", [])
            for i in range(len(colunas)):
                arquivo = arquivos[i] if i < len(arquivos) else ""
                if not varias:
                    dica = arquivo
                elif i == base:
                    dica = f"{arquivo}\nBase da diferença."
                else:
                    dica = f"{arquivo}\nClique para calcular a diferença com base nesta contagem."
                self._table.horizontalHeaderItem(_COL_CONTADO + i).setToolTip(dica)
            self._table.horizontalHeaderItem(len(rotulos) - 2).setToolTip(
                f"{colunas[base]} − Sistema")

    def _montar_opcoes_colunas(self):
        """Linha acima da grade: qual coluna é a base da diferença e quais
        colunas de contado entram na exportação e na IA."""
        for chk in self._checks_export:
            self._layout_checks_export.removeWidget(chk)
            chk.deleteLater()
        self._checks_export = []

        r = self._resultado
        if r is None or len(r.colunas) < 2:
            self._linha_colunas.setVisible(False)
            return

        pdfs = self._contexto_resultado["pdfs"]
        for i, rotulo in enumerate(r.colunas):
            chk = QCheckBox(rotulo)
            chk.setProperty("indice_coluna", i)
            chk.setStyleSheet(themed_qss("QCheckBox { color: {{FG_PRIMARY}}; font-size: 9pt; }"))
            if i == r.indice_base:
                # A diferença é calculada sobre ela: não dá para deixá-la de fora.
                chk.setChecked(True)
                chk.setEnabled(False)
                chk.setToolTip("Base da diferença — sempre incluída")
            else:
                chk.setChecked(pdfs[i] not in self._pdfs_fora_export)
                chk.toggled.connect(self._on_check_export_alterado)
            self._layout_checks_export.addWidget(chk)
            self._checks_export.append(chk)

        self._lbl_base.setText(
            f"Base da diferença: <b>{html_lib.escape(r.colunas[r.indice_base])}</b> — "
            f"clique no cabeçalho de outra coluna de contado para trocar."
        )
        self._linha_colunas.setVisible(True)

    def _on_check_export_alterado(self, _marcado: bool):
        pdfs = self._contexto_resultado["pdfs"]
        for chk in self._checks_export:
            if not chk.isEnabled():
                continue  # a base, sempre incluída
            pdf_id = pdfs[chk.property("indice_coluna")]
            if chk.isChecked():
                self._pdfs_fora_export.discard(pdf_id)
            else:
                self._pdfs_fora_export.add(pdf_id)

    def _colunas_export(self) -> List[int]:
        """Índices das colunas de contado que entram na exportação e na IA."""
        r = self._resultado
        pdfs = self._contexto_resultado["pdfs"]
        return [i for i in range(len(r.colunas))
                if i == r.indice_base or pdfs[i] not in self._pdfs_fora_export]

    # Folga além da medida do Qt: a medida do cabeçalho nem sempre inclui o
    # padding do QSS, e o que sobra por conta dela é o que causava "Situaç...".
    _FOLGA_COLUNA = 16

    def _ajustar_colunas(self):
        """Cada coluna com a largura do seu maior conteúdo, cabeçalho incluso;
        a sobra de espaço da tela vai para a Descrição."""
        tabela = self._table
        header = tabela.horizontalHeader()
        tabela.resizeColumnsToContents()
        for col in range(tabela.columnCount()):
            header.resizeSection(col, header.sectionSize(col) + self._FOLGA_COLUNA)
        ocupado = sum(header.sectionSize(c) for c in range(tabela.columnCount()))
        livre = tabela.viewport().width() - ocupado
        if livre > 0:
            header.resizeSection(1, header.sectionSize(1) + livre)

    def eventFilter(self, obj, event):
        # A sobra de espaço muda com a janela e com a barra de rolagem vertical
        # (que aparece depois de a grade ser preenchida); recalcula para a
        # Descrição continuar ocupando exatamente a largura da tela.
        if obj is self._table.viewport() and event.type() == QEvent.Type.Resize:
            self._ajustar_colunas()
        return super().eventFilter(obj, event)

    def _data_do_resultado(self) -> date:
        """Data do estoque que está na grade — pode diferir do campo de data
        enquanto um recálculo não termina (ou se ele falhou)."""
        if self._contexto_resultado is not None:
            return self._contexto_resultado["data"]
        return self._date_referencia.date().toPython()

    def _popular_tabela(self):
        """Preenche as linhas do resultado atual. Destaca a coluna de contado
        base (quando há mais de uma) e, depois de uma troca de data/local, as
        células de Sistema/Diferença cujo estoque mudou."""
        r = self._resultado
        n = len(r.colunas)
        col_sistema = _COL_CONTADO + n
        col_diferenca = col_sistema + 1
        col_situacao = col_sistema + 2
        col_base = _COL_CONTADO + r.indice_base

        tema = get_active_theme()
        cor_mudou = QColor(tema.ACCENT)
        cor_mudou.setAlpha(70)
        cor_base = QColor(tema.ACCENT)
        cor_base.setAlpha(30)
        data_antes = f"{self._data_antes:%d/%m/%Y}" if self._data_antes else ""
        centro = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

        def _num(valor, sinal=False):
            if valor is None:
                return "—"
            return f"{valor:+g}" if sinal else f"{valor:g}"

        def _celula_num(texto):
            cel = QTableWidgetItem(texto)
            cel.setTextAlignment(centro)
            return cel

        self._table.setRowCount(len(r.itens))
        for row, item in enumerate(r.itens):
            chave = (item.codigo, item.lote)
            mudou = chave in self._sistema_antes and self._sistema_antes[chave] != item.sistema

            self._table.setItem(row, _COL_PRODUTO, QTableWidgetItem(item.codigo))
            self._table.setItem(row, _COL_DESCRICAO, QTableWidgetItem(item.descricao))
            self._table.setItem(row, _COL_LOTE, QTableWidgetItem(item.lote or "—"))

            for i, qtd in enumerate(item.contados):
                cel = _celula_num(_num(qtd))
                if n > 1 and _COL_CONTADO + i == col_base:
                    cel.setBackground(cor_base)
                self._table.setItem(row, _COL_CONTADO + i, cel)

            for col, texto in ((col_sistema, _num(item.sistema)),
                               (col_diferenca, _num(item.diferenca, sinal=True))):
                cel = _celula_num(texto)
                if mudou:
                    cel.setBackground(cor_mudou)
                    fonte = cel.font()
                    fonte.setBold(True)
                    cel.setFont(fonte)
                    cel.setToolTip(f"Estoque do sistema em {data_antes}: "
                                   f"{_num(self._sistema_antes[chave])}")
                self._table.setItem(row, col, cel)

            situacao_item = QTableWidgetItem(_SITUACAO_LABEL.get(item.situacao, item.situacao))
            cor = _SITUACAO_COR.get(item.situacao, "{{FG_PRIMARY}}")
            situacao_item.setForeground(_qcolor_from_token(cor))
            self._table.setItem(row, col_situacao, situacao_item)

    # ------------------------------------------------------------------
    # Analisar com IA
    # ------------------------------------------------------------------

    def _on_analisar_ia_clicked(self):
        if not self._resultado:
            return
        if not AIConfigService().is_configured():
            QMessageBox.warning(
                self, "IA não configurada",
                "Configure um provedor de IA em Configurações (F12) antes de analisar."
            )
            return

        payload = self._service.montar_payload_ia(
            self._resultado, self._nome_empresa,
            self._data_do_resultado(),
            limite=self._spin_limite.value(),
            colunas=self._colunas_export(),
        )

        r = self._resultado
        partes = [f"estoque de {self._data_do_resultado():%d/%m/%Y}"]
        if len(r.colunas) > 1:
            partes.append(f"base da diferença: {r.colunas[r.indice_base]}")
            partes.append("contagens: " + ", ".join(r.colunas[i] for i in self._colunas_export()))
        partes.append(f"{self._spin_limite.value()} de {r.total_falta + r.total_sobra} "
                      f"divergências enviadas")
        self._contexto_ia_pendente = " · ".join(partes)

        self._btn_analisar_ia.setEnabled(False)
        self._lbl_status.setText("🔄 Analisando com IA...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))

        system = (
            "Você é um analista de estoque. Recebe um resumo já calculado de uma "
            "contagem física comparada ao sistema e escreve uma análise objetiva das "
            "divergências, em português, destacando padrões relevantes. Quando houver "
            "mais de uma contagem, compare também as contagens entre si e aponte onde "
            "os conferentes discordam. Nunca invente números — use apenas os valores "
            "do resumo recebido."
        )
        signals = WorkerSignals()
        signals.finished.connect(self._on_ia_finished)
        signals.error.connect(self._on_ia_error)
        runnable = TaskRunnable(AIClient().analisar, args=(system, payload), signals=signals)
        QThreadPool.globalInstance().start(runnable)

    def _on_ia_finished(self, texto: str):
        self._btn_analisar_ia.setEnabled(True)
        self._analise_ia_texto = texto
        self._txt_analise.setPlainText(texto)
        self._lbl_contexto_ia.setText(
            f"Análise gerada às {datetime.now():%H:%M} · {self._contexto_ia_pendente}"
        )
        self._abas.setCurrentIndex(1)
        self._lbl_status.setText("✅ Análise concluída — veja a aba \"Análise da IA\".")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))

    def _on_ia_error(self, exc: Exception):
        self._btn_analisar_ia.setEnabled(True)
        mensagem = str(exc) if isinstance(exc, AIClientError) else f"Erro inesperado: {exc}"
        QMessageBox.critical(self, "Erro na Análise", mensagem)
        self._lbl_status.setText(f"❌ {mensagem}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    # ------------------------------------------------------------------
    # Exportar
    # ------------------------------------------------------------------

    def _on_exportar_clicked(self):
        if not self._resultado:
            return
        menu = QMenu(self)
        acao_comparativo = menu.addAction("📊  Resultado comparativo")
        acao_ia = menu.addAction("🤖  Análise da IA")
        acao_ambos = menu.addAction("📊+🤖  Os dois juntos")
        if not self._analise_ia_texto:
            acao_ia.setEnabled(False)
            acao_ambos.setEnabled(False)

        escolha = menu.exec(QCursor.pos())
        if escolha is None:
            return
        if escolha is acao_comparativo:
            self._exportar_comparativo()
        elif escolha is acao_ia:
            self._exportar_ia()
        elif escolha is acao_ambos:
            self._exportar_ambos()

    def _sugestao_nome(self, sufixo: str) -> str:
        data_str = f"{self._data_do_resultado():%d%m%Y}"
        return f"analise_estoque_{self._codempresa}_{data_str}_{sufixo}.pdf"

    def _exportar_comparativo(self):
        self._exportar("comparativo", [self._secao_comparativo()])

    def _exportar_ia(self):
        self._exportar("analise_ia", [self._secao_analise_ia()])

    def _exportar_ambos(self):
        self._exportar("completo", [self._secao_comparativo(), self._secao_analise_ia()])

    def _exportar(self, sufixo: str, secoes: list):
        """Grava o PDF direto em <pasta do app>/Exportados (criada se não
        existir) e oferece abrir a pasta ao final."""
        try:
            pasta = AppConfig.get_exportados_path()
        except OSError as exc:
            QMessageBox.critical(
                self, "Erro ao Exportar",
                f"Não foi possível criar a pasta de exportação:\n{exc}")
            return
        caminho = _caminho_livre(os.path.join(pasta, self._sugestao_nome(sufixo)))
        if not self._salvar_pdf(secoes, caminho):
            return

        pergunta = QMessageBox(self)
        pergunta.setWindowTitle("Exportação concluída")
        pergunta.setIcon(QMessageBox.Icon.Question)
        pergunta.setText(f"Arquivo gerado: <b>{html_lib.escape(os.path.basename(caminho))}</b>")
        pergunta.setInformativeText(f"Pasta: {pasta}\n\nDeseja abrir a pasta de exportação?")
        btn_sim = pergunta.addButton("Sim", QMessageBox.ButtonRole.YesRole)
        pergunta.addButton("Não", QMessageBox.ButtonRole.NoRole)
        pergunta.setDefaultButton(btn_sim)
        pergunta.exec()

        if pergunta.clickedButton() is btn_sim:
            _abrir_pasta_com_arquivo(caminho)
        else:
            janela = self.window()
            janela.raise_()
            janela.activateWindow()

    # ------------------------------------------------------------------
    # Geração de PDF (QTextDocument + QPdfWriter — sem dependência nova)
    # ------------------------------------------------------------------

    def _cabecalho_html(self) -> str:
        data_str = f"{self._data_do_resultado():%d/%m/%Y}"
        empresa = html_lib.escape(self._nome_empresa or self._codempresa)
        total_div = 0
        total_produtos = 0
        total_registros = 0
        if self._resultado:
            total_div = self._resultado.total_falta + self._resultado.total_sobra
            total_produtos = self._resultado.total_produtos
            total_registros = self._resultado.total_itens
        # Fonte 9 e linhas coladas: o cabeçalho se repete em toda página e
        # não pode roubar espaço da grade.
        linha = "font-size:9pt; margin-top:1px; margin-bottom:0px;"
        separador = f"&nbsp;<span style='color:{_PDF_BORDA};'>|</span>&nbsp;"
        linhas = [
            f"<p style='{linha} margin-top:0px; font-weight:bold; color:{_PDF_MARCA};'>"
            f"Análise de Estoque</p>",
            f"<p style='{linha}'><b>Empresa:</b> {empresa}{separador}"
            f"<b>Data de referência:</b> {data_str}{separador}"
            f"<b>Produtos:</b> {total_produtos}{separador}"
            f"<b>Registros:</b> {total_registros}{separador}"
            f"<b>Divergências:</b> {total_div}</p>",
        ]
        if self._contagem_referencia is not None:
            nome_arquivo = html_lib.escape(os.path.basename(self._contagem_referencia.arquivo))
            linhas.append(f"<p style='{linha}'><b>Referência:</b> apenas o arquivo {nome_arquivo}</p>")
        if self._resultado and len(self._resultado.colunas) > 1:
            r = self._resultado
            consideradas = ", ".join(html_lib.escape(r.colunas[i]) for i in self._colunas_export())
            linhas.append(
                f"<p style='{linha}'><b>Contagens consideradas:</b> {consideradas}{separador}"
                f"<b>Base da diferença:</b> {html_lib.escape(r.colunas[r.indice_base])}</p>"
            )
        return "".join(linhas)

    def _secao_comparativo(self) -> "_SecaoTabela":
        r = self._resultado
        indices = self._colunas_export()
        varias = len(r.colunas) > 1

        def _num(valor, sinal=False):
            if valor is None:
                return "—"
            return f"{valor:+g}" if sinal else f"{valor:g}"

        # (título, alinhamento do título) de cada coluna. Larguras: calculadas
        # na geração do PDF — cada coluna do tamanho do seu conteúdo, e a
        # Descrição (coluna_flexivel) com o resto.
        colunas = [("Produto", "center"), ("Descrição", "left"), ("Lote", "center")]
        colunas += [(html_lib.escape(r.colunas[i])
                     + (" (base)" if varias and i == r.indice_base else ""), "center")
                    for i in indices]
        colunas += [("Sistema", "center"), ("Diferença", "center"), ("Situação", "left")]
        linhas = []
        for n, item in enumerate(r.itens):
            fundo = f" bgcolor='{_PDF_ZEBRA}'" if n % 2 else ""
            cor = _PDF_COR_SITUACAO.get(item.situacao, _PDF_TEXTO)
            situacao = _SITUACAO_LABEL.get(item.situacao, item.situacao)
            contados = "".join(
                f"<td align='center'{fundo}>{_num(item.contados[i])}</td>" for i in indices
            )
            linhas.append(
                "<tr>"
                f"<td{fundo}>{html_lib.escape(item.codigo)}</td>"
                f"<td{fundo}>{html_lib.escape(item.descricao)}</td>"
                f"<td align='center'{fundo}>{html_lib.escape(item.lote or '—')}</td>"
                f"{contados}"
                f"<td align='center'{fundo}>{_num(item.sistema)}</td>"
                f"<td align='center'{fundo}>{_num(item.diferenca, sinal=True)}</td>"
                f"<td{fundo}><span style='color:{cor}; font-weight:bold;'>{situacao}</span></td>"
                "</tr>"
            )
        return _SecaoTabela(
            titulo_html=(
                f"<p style='font-size:9pt; font-weight:bold; color:{_PDF_MARCA}; "
                f"margin-top:0px; margin-bottom:4px;'>Resultado comparativo</p>"
            ),
            atributos_tabela=(
                f"border='1' cellspacing='0' cellpadding='3' "
                f"style='border-collapse:collapse; border-style:solid; border-color:{_PDF_BORDA};'"
            ),
            colunas=colunas,
            coluna_flexivel=1,
            linhas_html=linhas,
        )

    def _secao_analise_ia(self) -> "_SecaoTexto":
        # Fonte 8 e parágrafos quase colados: o texto da IA é longo, e o
        # espaçamento padrão do HTML (uma linha em branco entre parágrafos)
        # espalhava a análise por várias páginas.
        paragrafos = "".join(
            f"<p style='margin-top:0px; margin-bottom:3px;'>{html_lib.escape(p)}</p>"
            for p in self._analise_ia_texto.splitlines() if p.strip()
        )
        return _SecaoTexto(
            f"<p style='font-size:9pt; font-weight:bold; color:{_PDF_MARCA}; "
            f"margin-top:0px; margin-bottom:4px;'>Análise da IA</p>{paragrafos}"
        )

    def _salvar_pdf(self, secoes: list, caminho: str) -> bool:
        agora = datetime.now()
        rodape = f"Gerado em {agora:%d/%m/%Y} às {agora:%H:%M}"
        if self._nome_usuario:
            rodape += f" por {self._nome_usuario}"
        try:
            _gerar_pdf_relatorio(
                caminho, self._cabecalho_html(), secoes, rodape, "Análise de Estoque"
            )
        except Exception as exc:
            logger.error(f"Erro ao exportar PDF: {exc}")
            QMessageBox.critical(self, "Erro ao Exportar", f"Não foi possível gerar o PDF:\n{exc}")
            return False
        self._lbl_status.setText(f"✅ Exportado: {caminho}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))
        return True


# ----------------------------------------------------------------------
# PDF de relatório: A4 paisagem, cabeçalho e rodapé em todas as páginas
# ----------------------------------------------------------------------

def _caminho_livre(caminho: str) -> str:
    """O próprio caminho, se ainda não existe; senão "nome (2).pdf",
    "nome (3).pdf"... — uma exportação nunca sobrescreve a anterior."""
    if not os.path.exists(caminho):
        return caminho
    base, extensao = os.path.splitext(caminho)
    n = 2
    while os.path.exists(f"{base} ({n}){extensao}"):
        n += 1
    return f"{base} ({n}){extensao}"


def _abrir_pasta_com_arquivo(caminho: str) -> None:
    """Abre a pasta no Explorer com o arquivo já selecionado (mesmo jeito da
    exportação de carga); se não der, abre só a pasta."""
    import subprocess
    try:
        # Caminho como STRING (não lista), para preservar espaços.
        subprocess.Popen(f'explorer /select,"{os.path.normpath(caminho)}"')
    except Exception:
        try:
            os.startfile(os.path.dirname(caminho))
        except Exception as exc:
            logger.warning(f"Não foi possível abrir a pasta de exportação: {exc}")


_LOGO_PATH = AppConfig.get_asset_path("logo.png")

# Cores de impressão: fixas, sem depender do tema da tela — o papel é sempre
# branco, e as cores do tema escuro (claras) somem nele.
_PDF_TEXTO = "#1b2433"
_PDF_SUAVE = "#5b6577"
_PDF_MARCA = "#1d6bb0"
_PDF_BORDA = "#cfd6e0"
_PDF_ZEBRA = "#f2f5f9"
_PDF_COR_SITUACAO = {
    "confere": "#2e7d32",
    "falta": "#c62828",
    "sobra": "#b26a00",
    "lote_novo": "#1d6bb0",
    "nao_contado": "#7a8494",
}

@dataclass
class _SecaoTabela:
    """Grade do PDF. Paginada à mão (ver `_paginar_tabela`): cada página
    recebe uma tabela completa, com a linha de títulos repetida."""
    titulo_html: str
    atributos_tabela: str       # atributos do <table> (borda, espaçamento)
    colunas: list               # (título HTML, alinhamento) de cada coluna
    coluna_flexivel: int        # a que fica com a sobra da largura (Descrição)
    linhas_html: List[str]      # um <tr> por registro


@dataclass
class _SecaoTexto:
    """Texto corrido (análise da IA), paginado pelo próprio Qt."""
    html: str


_logo_pdf_cache: Optional[QImage] = None


def _logo_pdf() -> Optional[QImage]:
    """Logotipo recortado nas bordas transparentes e reduzido: o PNG tem
    1024 px com margem vazia em volta do ícone — sem o recorte, o ícone fica
    menor e desalinhado com a margem da página."""
    global _logo_pdf_cache
    if _logo_pdf_cache is None:
        img = QImage(_LOGO_PATH)
        if img.isNull():
            _logo_pdf_cache = QImage()
        else:
            _logo_pdf_cache = _recortar_transparencia(img).scaledToHeight(
                240, Qt.TransformationMode.SmoothTransformation)
    return None if _logo_pdf_cache.isNull() else _logo_pdf_cache


def _recortar_transparencia(img: QImage) -> QImage:
    alfa = img.convertToFormat(QImage.Format.Format_Alpha8)
    largura, altura, por_linha = alfa.width(), alfa.height(), alfa.bytesPerLine()
    dados = bytes(alfa.constBits())[:por_linha * altura]
    # Brilho quase invisível (alfa < 16) conta como transparente.
    limiar = bytes(0 if v < 16 else 255 for v in range(256))
    topo, base, esquerda, direita = altura, -1, largura, -1
    for y in range(altura):
        linha = dados[y * por_linha:y * por_linha + largura].translate(limiar)
        miolo = linha.strip(b"\x00")
        if miolo:
            topo, base = min(topo, y), y
            inicio = len(linha) - len(linha.lstrip(b"\x00"))
            esquerda = min(esquerda, inicio)
            direita = max(direita, inicio + len(miolo) - 1)
    if base < 0:
        return img
    return img.copy(esquerda, topo, direita - esquerda + 1, base - topo + 1)


def _linha_titulos(secao: _SecaoTabela, larguras: Optional[List[float]] = None) -> str:
    """<tr> com os títulos das colunas (larguras em %, quando informadas)."""
    estilo = f"background-color:{_PDF_MARCA}; color:#ffffff; font-weight:bold;"
    celulas = []
    for c, (texto, alinhamento) in enumerate(secao.colunas):
        largura = f" width='{larguras[c]:.3f}%'" if larguras else ""
        celulas.append(f"<th align='{alinhamento}'{largura} style='{estilo}'>{texto}</th>")
    return "<tr>" + "".join(celulas) + "</tr>"


def _tabela_de_celulas(doc: QTextDocument):
    return next((f for f in doc.rootFrame().childFrames() if hasattr(f, "rows")), None)


def _larguras_colunas(secao: _SecaoTabela, documento, largura: float,
                      folga: float) -> Optional[List[float]]:
    """Largura de cada coluna, em % da página: a do seu maior conteúdo (título
    incluso), medida na grade inteira; a coluna flexível (Descrição) fica com
    o que sobrar.

    Medir uma vez e aplicar a mesma largura em todas as páginas mantém as
    colunas alinhadas entre uma página e outra — cada página é uma tabela
    própria, e sozinha cada uma se dimensionaria pelo próprio conteúdo."""
    # Sem largura na tabela e com espaço de sobra, o Qt deixa cada coluna com
    # a largura natural do conteúdo, sem quebrar linha.
    medida = documento(f"<table {secao.atributos_tabela}>" + _linha_titulos(secao)
                       + "".join(secao.linhas_html) + "</table>", 8, 100000)
    tabela = _tabela_de_celulas(medida)
    if tabela is None:
        return None
    layout = medida.documentLayout()
    n = len(secao.colunas)
    esquerdas = [layout.blockBoundingRect(tabela.cellAt(0, c).firstCursorPosition().block()).left()
                 for c in range(n)]
    moldura = layout.frameBoundingRect(tabela)
    esquerdas.append(moldura.right() + (esquerdas[0] - moldura.left()))
    # `folga`: o Qt aplica a % sobre uma largura útil um pouco menor que a da
    # página (bordas, espaçamento) — sem ela, texto que cabia exato quebrava
    # no meio da palavra ("Produt|o").
    naturais = [(esquerdas[c + 1] - esquerdas[c] + folga) / largura * 100 for c in range(n)]

    flex = secao.coluna_flexivel
    fixas = sum(p for c, p in enumerate(naturais) if c != flex)
    limite_fixas = 80.0   # a Descrição fica sempre com pelo menos 20% da página
    if fixas > limite_fixas:
        naturais = [p if c == flex else p * limite_fixas / fixas for c, p in enumerate(naturais)]
        fixas = limite_fixas
    naturais[flex] = 100 - fixas
    return naturais


def _paginar_tabela(secao: _SecaoTabela, documento, largura: float,
                    alt_corpo: float, folga: float, folga_coluna: float) -> List[str]:
    """Divide a grade em páginas e devolve o HTML de cada uma: uma tabela
    completa por página, com a linha de títulos repetida.

    Deixar o Qt quebrar uma tabela única entre páginas esticava a última
    linha de cada página até o fim da área, parecendo uma linha vazia. Aqui a
    altura de cada linha é medida numa tabela inteira e as linhas são
    distribuídas de modo que cada página só receba as que cabem."""
    larguras = _larguras_colunas(secao, documento, largura, folga_coluna)
    abertura = f"<table width='100%' {secao.atributos_tabela}>" + _linha_titulos(secao, larguras)

    medida = documento(abertura + "".join(secao.linhas_html) + "</table>", 8, largura)
    tabela = _tabela_de_celulas(medida)
    alt_titulo = documento(secao.titulo_html, 8, largura).size().height()
    if tabela is None or not secao.linhas_html:
        return [secao.titulo_html + abertura + "".join(secao.linhas_html) + "</table>"]

    layout = medida.documentLayout()
    topos = [layout.blockBoundingRect(tabela.cellAt(r, 0).firstCursorPosition().block()).top()
             for r in range(tabela.rows())]
    topos.append(layout.frameBoundingRect(tabela).bottom())
    alt_titulos_colunas = topos[1] - topos[0]
    alturas = [topos[r + 1] - topos[r] for r in range(1, tabela.rows())]

    paginas: List[List[int]] = [[]]
    disponivel = alt_corpo - alt_titulo - alt_titulos_colunas - folga
    for indice, altura_linha in enumerate(alturas):
        if paginas[-1] and altura_linha > disponivel:
            paginas.append([])
            disponivel = alt_corpo - alt_titulos_colunas - folga
        paginas[-1].append(indice)
        disponivel -= altura_linha

    return [
        (secao.titulo_html if n == 0 else "") + abertura
        + "".join(secao.linhas_html[i] for i in indices) + "</table>"
        for n, indices in enumerate(paginas)
    ]


def _gerar_pdf_relatorio(caminho: str, cabecalho_html: str, secoes: list,
                         rodape_esquerda: str, titulo: str) -> None:
    """Gera o PDF paginado à mão (o `QTextDocument.print_` não aceita
    cabeçalho/rodapé próprios): em cada página, marca + dados da análise no
    topo, o conteúdo da página no meio, e "gerado em/por" + numeração no
    rodapé. Cada seção (grade, análise da IA) começa numa página nova."""
    writer = QPdfWriter(caminho)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setPageMargins(QMarginsF(12, 10, 12, 9), QPageLayout.Unit.Millimeter)
    writer.setResolution(300)
    writer.setTitle(titulo)
    writer.setCreator(f"{APP_INFO.NAME} {APP_INFO.VERSION} — {APP_INFO.COMPANY}")

    dpi = writer.resolution()

    def mm(valor: float) -> float:
        return valor * dpi / 25.4

    largura, altura = writer.width(), writer.height()   # área útil, dentro das margens
    familia = QApplication.font().family()

    def _documento(html: str, tamanho_pt: int, largura_texto: float) -> QTextDocument:
        doc = QTextDocument()
        doc.documentLayout().setPaintDevice(writer)   # pt medidos na resolução do PDF
        doc.setDocumentMargin(0)
        doc.setDefaultFont(QFont(familia, tamanho_pt))
        doc.setHtml(f"<div style='color:{_PDF_TEXTO};'>{html}</div>")
        doc.setTextWidth(largura_texto)
        return doc

    # --- Marca: logotipo + "LogScan Manager" / "by CEOsoftware" ---
    logo = _logo_pdf()
    alt_logo = mm(11)
    larg_logo = logo.width() * alt_logo / logo.height() if logo else 0.0
    fonte_marca = QFont(familia, 12, QFont.Weight.Bold)
    fonte_by = QFont(familia, 7)
    fm_marca = QFontMetricsF(fonte_marca, writer)
    fm_by = QFontMetricsF(fonte_by, writer)
    x_nome = larg_logo + mm(2.5) if logo else 0.0
    larg_marca = x_nome + max(fm_marca.horizontalAdvance(APP_INFO.NAME),
                              fm_by.horizontalAdvance("by CEOsoftware"))
    x_divisor = larg_marca + mm(4)
    x_info = x_divisor + mm(4)

    doc_cab = _documento(cabecalho_html, 9, largura - x_info)
    alt_cab = max(alt_logo, doc_cab.size().height())
    y_regua = alt_cab + mm(2)
    y_corpo = y_regua + mm(4)

    alt_rodape = mm(6)
    alt_corpo = altura - y_corpo - alt_rodape - mm(2)

    # Conteúdo de cada página: (documento, deslocamento vertical dentro dele).
    paginas_corpo = []
    for secao in secoes:
        if isinstance(secao, _SecaoTabela):
            for html in _paginar_tabela(secao, _documento, largura, alt_corpo, mm(1), mm(1.5)):
                paginas_corpo.append((_documento(html, 8, largura), 0.0))
        else:
            doc_texto = _documento(secao.html, 8, largura)
            doc_texto.setPageSize(QSizeF(largura, alt_corpo))
            for k in range(doc_texto.pageCount()):
                paginas_corpo.append((doc_texto, k * alt_corpo))
    if not paginas_corpo:
        paginas_corpo.append((_documento("", 8, largura), 0.0))
    total_paginas = len(paginas_corpo)

    fonte_rodape = QFont(familia, 7)
    fm_rodape = QFontMetricsF(fonte_rodape, writer)

    painter = QPainter(writer)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for pagina in range(total_paginas):
            if pagina:
                writer.newPage()

            # Cabeçalho
            if logo:
                painter.drawImage(QRectF(0, (alt_cab - alt_logo) / 2, larg_logo, alt_logo), logo)
            bloco = fm_marca.height() + fm_by.height()
            y_bloco = (alt_cab - bloco) / 2
            painter.setFont(fonte_marca)
            painter.setPen(QColor(_PDF_TEXTO))
            painter.drawText(QPointF(x_nome, y_bloco + fm_marca.ascent()), APP_INFO.NAME)
            painter.setFont(fonte_by)
            painter.setPen(QColor(_PDF_SUAVE))
            painter.drawText(QPointF(x_nome, y_bloco + fm_marca.height() + fm_by.ascent()),
                             "by CEOsoftware")
            painter.setPen(QPen(QColor(_PDF_BORDA), mm(0.25)))
            painter.drawLine(QPointF(x_divisor, 0), QPointF(x_divisor, alt_cab))
            painter.save()
            painter.translate(x_info, (alt_cab - doc_cab.size().height()) / 2)
            doc_cab.drawContents(painter)
            painter.restore()
            painter.setPen(QPen(QColor(_PDF_MARCA), mm(0.45)))
            painter.drawLine(QPointF(0, y_regua), QPointF(largura, y_regua))

            # Conteúdo desta página
            doc_pagina, deslocamento = paginas_corpo[pagina]
            painter.save()
            painter.translate(0, y_corpo - deslocamento)
            doc_pagina.drawContents(painter, QRectF(0, deslocamento, largura, alt_corpo))
            painter.restore()

            # Rodapé
            y_rodape = altura - alt_rodape
            painter.setPen(QPen(QColor(_PDF_BORDA), mm(0.25)))
            painter.drawLine(QPointF(0, y_rodape), QPointF(largura, y_rodape))
            painter.setFont(fonte_rodape)
            painter.setPen(QColor(_PDF_SUAVE))
            y_texto = y_rodape + (alt_rodape + fm_rodape.ascent() - fm_rodape.descent()) / 2
            painter.drawText(QPointF(0, y_texto), rodape_esquerda)
            numero = f"Página {pagina + 1}/{total_paginas}"
            painter.drawText(QPointF(largura - fm_rodape.horizontalAdvance(numero), y_texto), numero)
    finally:
        painter.end()


def _qcolor_from_token(token: str):
    """Resolve um token ``{{NOME}}`` de app/styles.py para QColor."""
    from PySide6.QtGui import QColor
    hex_str = themed_qss(token).strip()
    return QColor(hex_str)
