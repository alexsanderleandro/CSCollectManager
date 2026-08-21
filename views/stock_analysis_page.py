"""
stock_analysis_page.py
=======================
Página "Análise de Estoque" — anexa PDFs de contagem do coletor, confere o
estoque atual no ERP e aciona a IA para redigir a análise das divergências.
"""

import html as html_lib
import os
from datetime import date
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDateEdit, QSpinBox,
    QRadioButton, QButtonGroup, QTextEdit, QFileDialog, QMenu,
    QMessageBox, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Qt, QDate, QThreadPool
from PySide6.QtGui import QCursor, QPdfWriter, QPageSize, QTextDocument

from app.styles import themed_qss, get_active_theme
from services.pdf_contagem_parser import PdfContagemParser, ContagemPDF
from services.stock_analysis_service import (
    StockAnalysisService, StockAnalysisValidationError, ResultadoAnalise
)
from services.ai_config_service import AIConfigService
from services.ai_client import AIClient, AIClientError
from utils.workers import WorkerSignals, TaskRunnable
from utils.config import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)

_SITUACAO_LABEL = {
    "confere": "Confere",
    "falta": "Falta",
    "sobra": "Sobra",
    "lote_novo": "Lote novo",
}
_SITUACAO_COR = {
    "confere": "{{SUCCESS}}",
    "falta": "{{ERROR}}",
    "sobra": "{{WARNING}}",
    "lote_novo": "{{ACCENT}}",
}


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
        self._codempresa = ""
        self._nome_empresa = ""
        self._locais_estoque_mode = "A"
        self._setup_ui()

    # ------------------------------------------------------------------
    # Configuração externa (chamada pela MainWindowERP)
    # ------------------------------------------------------------------

    def set_empresa_info(self, codigo, nome: str):
        """Define a empresa logada, usada para validar os PDFs anexados."""
        self._codempresa = str(codigo or "")
        self._nome_empresa = nome or ""

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
        self._lbl_pdf_info = QLabel("Nenhum PDF anexado.")
        self._lbl_pdf_info.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        content_layout.addWidget(self._lbl_pdf_info)

        self._pdf_list = QListWidget()
        self._pdf_list.setMaximumHeight(110)
        self._pdf_list.setToolTip("Duplo clique para usar este arquivo como referência da grade")
        self._pdf_list.setStyleSheet(themed_qss("""
            QListWidget { background-color: {{BG_SECONDARY}}; border: 1px solid {{BORDER}}; border-radius: 6px; }
        """))
        self._pdf_list.itemDoubleClicked.connect(self._on_pdf_double_clicked)
        content_layout.addWidget(self._pdf_list)

        # ----- Tabela de divergências -----
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Produto", "Descrição", "Lote", "Contado", "Sistema", "Dif.", "Situação"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
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
        content_layout.addWidget(self._table, 1)

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

        # ----- Texto da análise da IA -----
        self._txt_analise = QTextEdit()
        self._txt_analise.setReadOnly(True)
        self._txt_analise.setMaximumHeight(160)
        self._txt_analise.setVisible(False)
        self._txt_analise.setStyleSheet(themed_qss("""
            QTextEdit {
                background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
                border: 1px solid {{BORDER}}; border-radius: 8px; padding: 10px; font-size: 10pt;
            }
        """))
        content_layout.addWidget(self._txt_analise)

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
            self._date_referencia.setDate(QDate(maior_data.year, maior_data.month, maior_data.day))

        self._lbl_status.setText("✅ PDF(s) validado(s). Consultando estoque no sistema...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))
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
        if self._contagem_referencia is not None:
            self._lbl_pdf_info.setText(
                f"{len(self._contagens)} PDF(s) anexado(s) · "
                f"Mostrando apenas: {os.path.basename(self._contagem_referencia.arquivo)}"
            )
        else:
            self._lbl_pdf_info.setText(f"{len(self._contagens)} PDF(s) anexado(s).")

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
        self._contagens = []
        self._contagem_referencia = None
        self._resultado = None
        self._analise_ia_texto = ""
        self._pdf_list.clear()
        self._table.setRowCount(0)
        self._lbl_pdf_info.setText("Nenhum PDF anexado.")
        self._txt_analise.clear()
        self._txt_analise.setVisible(False)
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

        signals = WorkerSignals()
        signals.finished.connect(self._on_comparacao_pronta)
        signals.error.connect(self._on_comparacao_erro)
        runnable = TaskRunnable(
            self._service.analisar,
            args=(contagens, data_referencia, local_estoque, self._codempresa),
            signals=signals,
        )
        QThreadPool.globalInstance().start(runnable)

    def _on_comparacao_pronta(self, resultado: ResultadoAnalise):
        self._resultado = resultado
        self._popular_tabela(resultado)

        total_divergencias = resultado.total_falta + resultado.total_sobra
        self._spin_limite.setMaximum(max(total_divergencias, 0))
        self._spin_limite.setValue(total_divergencias)
        self._lbl_limite.setText(f"de {total_divergencias} divergências")

        self._btn_analisar_ia.setEnabled(total_divergencias > 0 and AIConfigService().is_configured())
        self._btn_exportar.setEnabled(True)

        self._lbl_status.setText(
            f"✅ {resultado.total_produtos} produtos · {resultado.total_itens} registros · "
            f"{total_divergencias} divergências · {resultado.total_lote_novo} lotes novos"
        )
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))

    def _on_comparacao_erro(self, exc: Exception):
        QMessageBox.critical(self, "Erro na Consulta ao ERP", str(exc))
        self._lbl_status.setText(f"❌ Erro ao consultar estoque: {exc}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    def _popular_tabela(self, resultado: ResultadoAnalise):
        self._table.setRowCount(len(resultado.itens))
        for row, item in enumerate(resultado.itens):
            self._table.setItem(row, 0, QTableWidgetItem(item.codigo))
            self._table.setItem(row, 1, QTableWidgetItem(item.descricao))
            self._table.setItem(row, 2, QTableWidgetItem(item.lote or "—"))
            self._table.setItem(row, 3, QTableWidgetItem(f"{item.contado:g}"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{item.sistema:g}" if item.sistema is not None else "—"))
            self._table.setItem(row, 5, QTableWidgetItem(f"{item.diferenca:+g}" if item.diferenca is not None else "—"))

            situacao_item = QTableWidgetItem(_SITUACAO_LABEL.get(item.situacao, item.situacao))
            cor = _SITUACAO_COR.get(item.situacao, "{{FG_PRIMARY}}")
            situacao_item.setForeground(_qcolor_from_token(cor))
            self._table.setItem(row, 6, situacao_item)

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
            self._date_referencia.date().toPython(),
            limite=self._spin_limite.value(),
        )

        self._btn_analisar_ia.setEnabled(False)
        self._lbl_status.setText("🔄 Analisando com IA...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))

        system = (
            "Você é um analista de estoque. Recebe um resumo já calculado de uma "
            "contagem física comparada ao sistema e escreve uma análise objetiva das "
            "divergências, em português, destacando padrões relevantes. Nunca invente "
            "números — use apenas os valores do resumo recebido."
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
        self._txt_analise.setVisible(True)
        self._lbl_status.setText("✅ Análise concluída.")
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
        data_str = self._date_referencia.date().toString("ddMMyyyy")
        return f"analise_estoque_{self._codempresa}_{data_str}_{sufixo}.pdf"

    def _exportar_comparativo(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar resultado comparativo",
            self._sugestao_nome("comparativo"), "PDF (*.pdf)"
        )
        if not caminho:
            return
        html = self._cabecalho_html() + self._tabela_comparativo_html()
        self._salvar_pdf(html, caminho)

    def _exportar_ia(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar análise da IA",
            self._sugestao_nome("analise_ia"), "PDF (*.pdf)"
        )
        if not caminho:
            return
        html = self._cabecalho_html() + self._analise_ia_html()
        self._salvar_pdf(html, caminho)

    def _exportar_ambos(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar resultado comparativo + análise da IA",
            self._sugestao_nome("completo"), "PDF (*.pdf)"
        )
        if not caminho:
            return
        html = (
            self._cabecalho_html()
            + self._tabela_comparativo_html()
            + self._analise_ia_html()
        )
        self._salvar_pdf(html, caminho)

    # ------------------------------------------------------------------
    # Geração de PDF (QTextDocument + QPdfWriter — sem dependência nova)
    # ------------------------------------------------------------------

    def _cabecalho_html(self) -> str:
        data_str = self._date_referencia.date().toString("dd/MM/yyyy")
        empresa = html_lib.escape(self._nome_empresa or self._codempresa)
        total_div = 0
        total_produtos = 0
        total_registros = 0
        if self._resultado:
            total_div = self._resultado.total_falta + self._resultado.total_sobra
            total_produtos = self._resultado.total_produtos
            total_registros = self._resultado.total_itens
        referencia_html = ""
        if self._contagem_referencia is not None:
            nome_arquivo = html_lib.escape(os.path.basename(self._contagem_referencia.arquivo))
            referencia_html = f"<p><b>Referência:</b> apenas o arquivo {nome_arquivo}</p>"

        return (
            f"<h2>Análise de Estoque</h2>"
            f"<p><b>Empresa:</b> {empresa} &nbsp;·&nbsp; "
            f"<b>Data de referência:</b> {data_str} &nbsp;·&nbsp; "
            f"<b>Produtos:</b> {total_produtos} &nbsp;·&nbsp; "
            f"<b>Registros:</b> {total_registros} &nbsp;·&nbsp; "
            f"<b>Divergências:</b> {total_div}</p>"
            f"{referencia_html}"
        )

    def _tabela_comparativo_html(self) -> str:
        theme = get_active_theme()
        cores = {
            "confere": theme.SUCCESS, "falta": theme.ERROR,
            "sobra": theme.WARNING, "lote_novo": theme.ACCENT,
        }
        linhas = ["<h3>Resultado comparativo</h3>",
                  '<table border="1" cellspacing="0" cellpadding="5" width="100%">',
                  "<tr><th>Produto</th><th>Descrição</th><th>Lote</th>"
                  "<th>Contado</th><th>Sistema</th><th>Dif.</th><th>Situação</th></tr>"]
        for item in self._resultado.itens:
            sistema = f"{item.sistema:g}" if item.sistema is not None else "—"
            diferenca = f"{item.diferenca:+g}" if item.diferenca is not None else "—"
            cor = cores.get(item.situacao, "#000000")
            situacao = _SITUACAO_LABEL.get(item.situacao, item.situacao)
            linhas.append(
                "<tr>"
                f"<td>{html_lib.escape(item.codigo)}</td>"
                f"<td>{html_lib.escape(item.descricao)}</td>"
                f"<td>{html_lib.escape(item.lote or '—')}</td>"
                f"<td align='right'>{item.contado:g}</td>"
                f"<td align='right'>{sistema}</td>"
                f"<td align='right'>{diferenca}</td>"
                f"<td><span style='color:{cor}; font-weight:bold;'>{situacao}</span></td>"
                "</tr>"
            )
        linhas.append("</table>")
        return "".join(linhas)

    def _analise_ia_html(self) -> str:
        paragrafos = "".join(
            f"<p>{html_lib.escape(p)}</p>"
            for p in self._analise_ia_texto.splitlines() if p.strip()
        )
        return f"<h3>Análise da IA</h3>{paragrafos}"

    def _salvar_pdf(self, html: str, caminho: str):
        try:
            writer = QPdfWriter(caminho)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setResolution(150)

            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(writer)

            self._lbl_status.setText(f"✅ Exportado: {caminho}")
            self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))
        except Exception as exc:
            logger.error(f"Erro ao exportar PDF: {exc}")
            QMessageBox.critical(self, "Erro ao Exportar", f"Não foi possível gerar o PDF:\n{exc}")


def _qcolor_from_token(token: str):
    """Resolve um token ``{{NOME}}`` de app/styles.py para QColor."""
    from PySide6.QtGui import QColor
    hex_str = themed_qss(token).strip()
    return QColor(hex_str)
