"""
stock_analysis_widgets.py
=========================
Peças da tela "Análise de Estoque" que não dependem do estado da página:
os diálogos de escolha (contagens baixadas, produto a explicar), os cartões
de aprofundamento da análise da IA, a célula ordenável da grade e a
conversão do texto da IA para HTML (usada na tela e no PDF).
"""
from __future__ import annotations

import html as html_lib
import os
import re
import unicodedata
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.styles import get_active_theme, themed_qss
from services.contagem_zip import ContagemBaixada

# Chave de ordenação guardada em cada célula da grade (ver `ItemOrdenavel`).
CHAVE_ORDEM = Qt.ItemDataRole.UserRole + 1


def sem_acento(texto: str) -> str:
    """Minúsculo e sem acento — para busca que acha "limao" em "LIMÃO"."""
    base = unicodedata.normalize("NFKD", (texto or "").casefold())
    return "".join(c for c in base if not unicodedata.combining(c))


class ItemOrdenavel(QTableWidgetItem):
    """Célula que ordena pela chave em ``CHAVE_ORDEM`` (número de verdade,
    não o texto formatado "1.234,50"), e pelo texto quando não há chave."""

    def __lt__(self, other):
        a, b = self.data(CHAVE_ORDEM), other.data(CHAVE_ORDEM)
        if a is None or b is None:
            return super().__lt__(other)
        try:
            return a < b
        except TypeError:
            return str(a) < str(b)


_QSS_DIALOGO = """
    QDialog { background-color: {{BG_PRIMARY}}; color: {{FG_PRIMARY}}; }
    QLabel { color: {{FG_PRIMARY}}; background: transparent; }
    QLineEdit {
        background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
        border: 1px solid {{BORDER}}; border-radius: 6px; padding: 5px 10px;
    }
    QLineEdit:focus { border-color: {{ACCENT}}; }
    QTableWidget {
        background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
        border: 1px solid {{BORDER}}; gridline-color: {{BORDER}};
    }
    QTableWidget::item:selected { background-color: {{ACCENT}}; color: #ffffff; }
    QTableWidget::item:alternate { background-color: {{BG_TERTIARY}}; }
    QHeaderView::section {
        background-color: {{BG_TERTIARY}}; color: {{FG_SECONDARY}};
        border: none; border-bottom: 1px solid {{BORDER}}; padding: 6px 8px; font-weight: bold;
    }
    QPushButton {
        background-color: {{BG_HOVER}}; color: {{FG_PRIMARY}};
        border: none; border-radius: 8px; padding: 7px 18px;
    }
    QPushButton:hover { background-color: {{BG_SELECTED}}; }
    QPushButton:disabled { color: {{FG_DISABLED}}; }
    QPushButton[primary="true"] {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {{ACCENT}}, stop:1 #1d6bb0);
        color: white; font-weight: bold;
    }
    QPushButton[primary="true"]:disabled { background: {{BG_HOVER}}; color: {{FG_DISABLED}}; }
"""


def _tabela_dialogo(colunas: List[str]) -> QTableWidget:
    tabela = QTableWidget()
    tabela.setColumnCount(len(colunas))
    tabela.setHorizontalHeaderLabels(colunas)
    tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tabela.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tabela.setAlternatingRowColors(True)
    tabela.verticalHeader().setVisible(False)
    tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    return tabela


# ----------------------------------------------------------------------
# Escolha das contagens baixadas
# ----------------------------------------------------------------------

class SelecionarContagensDialog(QDialog):
    """Lista as contagens baixadas da empresa logada para escolher quais
    entram na análise (no máximo ``vagas``)."""

    _COL_MARCA, _COL_CONFERENTE, _COL_DATA, _COL_LOCAL, _COL_PRODUTOS, _COL_REGISTROS, _COL_ARQUIVO = range(7)

    def __init__(self, contagens: List[ContagemBaixada], pasta: str, ja_na_analise: set,
                 vagas: int, parent=None):
        super().__init__(parent)
        self._vagas = vagas
        self.setWindowTitle("Selecionar contagens")
        self.resize(1060, 540)
        self.setStyleSheet(themed_qss(_QSS_DIALOGO))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        ja = len(ja_na_analise)
        topo = QLabel(
            f"Contagens desta empresa baixadas em <b>{html_lib.escape(pasta)}</b>, a pasta da tela "
            f"Download Contagens. Marque até <b>{vagas}</b>"
            + (f" (já há {ja} na análise)." if ja else ".")
        )
        topo.setWordWrap(True)
        layout.addWidget(topo)

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Filtrar por conferente, data ou arquivo")
        self._busca.setClearButtonEnabled(True)
        self._busca.textChanged.connect(self._filtrar)
        layout.addWidget(self._busca)

        self._tabela = _tabela_dialogo(
            ["", "Conferente", "Exportada em", "Local", "Produtos", "Registros", "Arquivo"])
        self._tabela.horizontalHeader().setSectionResizeMode(
            self._COL_ARQUIVO, QHeaderView.ResizeMode.Stretch)
        self._tabela.setRowCount(len(contagens))
        centro = Qt.AlignmentFlag.AlignCenter
        for row, c in enumerate(contagens):
            na_analise = os.path.normcase(os.path.abspath(c.caminho)) in ja_na_analise
            marca = QTableWidgetItem()
            marca.setData(Qt.ItemDataRole.UserRole, c.caminho)
            conferente = f"{c.codvendedor} – {c.nome_vendedor}" if c.nome_vendedor else c.codvendedor
            if na_analise:
                conferente += "  · já na análise"
            data = f"{c.data_exportacao:%d/%m/%Y %H:%M}" if c.data_exportacao else "—"
            local = c.local or "—"
            if c.erro:
                local = "⚠ ilegível"
            textos = [conferente, data, local,
                      "—" if c.total_produtos is None else str(c.total_produtos),
                      "—" if c.total_registros is None else str(c.total_registros),
                      c.nome_arquivo]
            celulas = [marca] + [QTableWidgetItem(t) for t in textos]
            for col in (self._COL_DATA, self._COL_PRODUTOS, self._COL_REGISTROS):
                celulas[col].setTextAlignment(centro)
            if c.erro or na_analise:
                dica = c.erro or "Esta contagem já está na análise."
                apagado = QColor(get_active_theme().FG_DISABLED)
                for cel in celulas:
                    cel.setFlags(Qt.ItemFlag.NoItemFlags)
                    cel.setToolTip(dica)
                    cel.setForeground(apagado)
            else:
                marca.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                               | Qt.ItemFlag.ItemIsSelectable)
                marca.setCheckState(Qt.CheckState.Unchecked)
            for col, cel in enumerate(celulas):
                self._tabela.setItem(row, col, cel)
        self._tabela.itemChanged.connect(self._on_marcado)
        # Clicar em qualquer ponto da linha marca/desmarca, não só na caixinha.
        self._tabela.cellClicked.connect(self._on_celula_clicada)
        layout.addWidget(self._tabela, 1)

        rodape = QHBoxLayout()
        self._lbl_contador = QLabel("")
        self._lbl_contador.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; background: transparent;"))
        rodape.addWidget(self._lbl_contador, 1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        rodape.addWidget(cancelar)
        self._btn_ok = QPushButton("Adicionar à análise")
        self._btn_ok.setProperty("primary", "true")
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self.accept)
        rodape.addWidget(self._btn_ok)
        layout.addLayout(rodape)
        self._atualizar_contador()

    def selecionadas(self) -> List[str]:
        """Caminhos marcados, na ordem da lista (mais nova primeiro)."""
        return [self._tabela.item(r, 0).data(Qt.ItemDataRole.UserRole)
                for r in range(self._tabela.rowCount())
                if self._tabela.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _on_celula_clicada(self, row: int, col: int):
        marca = self._tabela.item(row, 0)
        if col == 0 or not (marca.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return
        marcado = marca.checkState() == Qt.CheckState.Checked
        marca.setCheckState(Qt.CheckState.Unchecked if marcado else Qt.CheckState.Checked)

    def _on_marcado(self, item: QTableWidgetItem):
        if item.column() != 0 or item.checkState() != Qt.CheckState.Checked:
            self._atualizar_contador()
            return
        if len(self.selecionadas()) > self._vagas:
            self._tabela.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._tabela.blockSignals(False)
            self._atualizar_contador(
                f"Cabem só mais {self._vagas} contagem(ns) na análise (máximo de 3, uma por "
                f"coluna). Desmarque outra antes.")
            return
        self._atualizar_contador()

    def _atualizar_contador(self, erro: str = ""):
        n = len(self.selecionadas())
        self._btn_ok.setEnabled(n > 0)
        if erro:
            self._lbl_contador.setStyleSheet(themed_qss("color: {{ERROR}}; background: transparent;"))
            self._lbl_contador.setText(erro)
        else:
            self._lbl_contador.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; background: transparent;"))
            self._lbl_contador.setText(f"{n} de {self._vagas} marcada(s).")

    def _filtrar(self, texto: str):
        busca = sem_acento(texto.strip())
        for r in range(self._tabela.rowCount()):
            linha = " ".join(self._tabela.item(r, c).text() for c in range(1, self._tabela.columnCount()))
            self._tabela.setRowHidden(r, bool(busca) and busca not in sem_acento(linha))


# ----------------------------------------------------------------------
# Escolha do produto a explicar
# ----------------------------------------------------------------------

class EscolherProdutoDialog(QDialog):
    """Lista os produtos com divergência para o aprofundamento "Explicar um
    produto". Produto já explicado aparece bloqueado: a mesma pergunta não
    é feita duas vezes."""

    def __init__(self, produtos: List[dict], aviso: str, parent=None):
        """``produtos``: dicts com codigo, descricao, registros, diferenca
        (texto), valor (texto), chave_valor (float), situacao (texto) e
        explicado (bool)."""
        super().__init__(parent)
        self.codigo_escolhido: Optional[str] = None
        self.setWindowTitle("Explicar um produto")
        self.resize(820, 480)
        self.setStyleSheet(themed_qss(_QSS_DIALOGO))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        topo = QLabel(aviso)
        topo.setWordWrap(True)
        layout.addWidget(topo)

        self._busca = QLineEdit()
        self._busca.setPlaceholderText("Buscar código ou descrição")
        self._busca.setClearButtonEnabled(True)
        self._busca.textChanged.connect(self._filtrar)
        layout.addWidget(self._busca)

        self._tabela = _tabela_dialogo(["Produto", "Descrição", "Registros", "Diferença", "Valor", "Situação"])
        self._tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tabela.setRowCount(len(produtos))
        centro = Qt.AlignmentFlag.AlignCenter
        for row, p in enumerate(produtos):
            situacao = "✓ já explicado" if p["explicado"] else p["situacao"]
            textos = [p["codigo"], p["descricao"], str(p["registros"]), p["diferenca"], p["valor"], situacao]
            for col, texto in enumerate(textos):
                cel = QTableWidgetItem(texto)
                if col in (2, 3, 4):
                    cel.setTextAlignment(centro)
                if col == 0:
                    cel.setData(Qt.ItemDataRole.UserRole, p["codigo"])
                if p["explicado"]:
                    cel.setFlags(Qt.ItemFlag.NoItemFlags)
                    cel.setToolTip("Este produto já foi explicado nesta análise — a explicação está na aba.")
                    cel.setForeground(QColor(get_active_theme().FG_DISABLED))
                self._tabela.setItem(row, col, cel)
        self._tabela.itemSelectionChanged.connect(self._atualizar_botao)
        self._tabela.cellDoubleClicked.connect(lambda *_: self._confirmar())
        layout.addWidget(self._tabela, 1)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        rodape.addWidget(cancelar)
        self._btn_ok = QPushButton("Explicar")
        self._btn_ok.setProperty("primary", "true")
        self._btn_ok.setDefault(True)
        self._btn_ok.clicked.connect(self._confirmar)
        rodape.addWidget(self._btn_ok)
        layout.addLayout(rodape)
        self._atualizar_botao()

    def _selecionado(self) -> Optional[str]:
        linhas = self._tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        cel = self._tabela.item(linhas[0].row(), 0)
        if not (cel.flags() & Qt.ItemFlag.ItemIsEnabled):
            return None
        return cel.data(Qt.ItemDataRole.UserRole)

    def _atualizar_botao(self):
        self._btn_ok.setEnabled(self._selecionado() is not None)

    def _confirmar(self):
        codigo = self._selecionado()
        if codigo:
            self.codigo_escolhido = codigo
            self.accept()

    def _filtrar(self, texto: str):
        busca = sem_acento(texto.strip())
        for r in range(self._tabela.rowCount()):
            linha = f"{self._tabela.item(r, 0).text()} {self._tabela.item(r, 1).text()}"
            self._tabela.setRowHidden(r, bool(busca) and busca not in sem_acento(linha))


# ----------------------------------------------------------------------
# Conta da acurácia, registro a registro
# ----------------------------------------------------------------------

class ContaAcuraciaDialog(QDialog):
    """A conta de uma linha da aba Acurácia (um grupo, uma localização ou o
    geral): o valor de cada registro e as somas que viram "Valor dos
    registros", "Valor dos que conferem" e "% valor"."""

    def __init__(self, titulo: str, explicacao: str, colunas: List[str], linhas: List[dict],
                 alinhar_centro: Tuple[int, ...], conta_html: str, parent=None):
        """``linhas``: dicts com ``celulas`` (textos na ordem de ``colunas``),
        ``cor_situacao`` (QColor da coluna Situação, a 4ª), ``confere`` e
        ``sem_custo``. A última coluna é o valor do registro."""
        super().__init__(parent)
        self.setWindowTitle(f"Conta da acurácia — {titulo}")
        self.resize(1100, 600)
        self.setStyleSheet(themed_qss(_QSS_DIALOGO))
        tema = get_active_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        cabecalho = QLabel(f"<b>{html_lib.escape(titulo)}</b>")
        cabecalho.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-size: 12pt; background: transparent;"))
        layout.addWidget(cabecalho)
        lbl_explicacao = QLabel(explicacao)
        lbl_explicacao.setWordWrap(True)
        lbl_explicacao.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9.5pt; background: transparent;"))
        layout.addWidget(lbl_explicacao)

        tabela = _tabela_dialogo(colunas)
        tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabela.setRowCount(len(linhas))
        centro = Qt.AlignmentFlag.AlignCenter
        ultima = len(colunas) - 1
        for row, linha in enumerate(linhas):
            for col, texto in enumerate(linha["celulas"]):
                cel = QTableWidgetItem(texto)
                if col in alinhar_centro:
                    cel.setTextAlignment(centro)
                if col == 3:
                    cel.setForeground(linha["cor_situacao"])
                if col == ultima:
                    if linha["sem_custo"]:
                        cel.setForeground(QColor(tema.FG_DISABLED))
                        cel.setToolTip("Sem custo cadastrado: fica fora das somas em valor")
                    elif linha["confere"]:
                        # Os valores que somam no "Valor dos que conferem".
                        cel.setForeground(QColor(tema.SUCCESS))
                        fonte = cel.font()
                        fonte.setBold(True)
                        cel.setFont(fonte)
                tabela.setItem(row, col, cel)
        layout.addWidget(tabela, 1)

        conta = QLabel(conta_html)
        conta.setObjectName("contaAcuracia")
        conta.setTextFormat(Qt.TextFormat.RichText)
        conta.setWordWrap(True)
        conta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        conta.setStyleSheet(themed_qss("""
            QLabel#contaAcuracia {
                color: {{FG_PRIMARY}}; font-size: 10pt; background-color: {{BG_SECONDARY}};
                border: 1px solid {{BORDER}}; border-radius: 8px; padding: 10px 12px;
            }
        """))
        layout.addWidget(conta)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        fechar = QPushButton("Fechar")
        fechar.setDefault(True)
        fechar.clicked.connect(self.accept)
        rodape.addWidget(fechar)
        layout.addLayout(rodape)


# ----------------------------------------------------------------------
# Cartões de aprofundamento (aba "Análise da IA")
# ----------------------------------------------------------------------

class CartaoAprofundar(QFrame):
    """Cartão clicável no fim da análise: ícone, nome, o que entrega e um
    rodapé com o custo ("1 pedido à IA") ou o estado ("Gerando…")."""

    clicado = Signal(str)

    def __init__(self, acao: str, icone: str, nome: str, descricao: str, rodape: str, parent=None):
        super().__init__(parent)
        self.acao = acao
        self._icone = icone
        self._rodape_padrao = rodape
        self.setObjectName("cartaoAprofundar")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(112)
        self.setStyleSheet(themed_qss("""
            QFrame#cartaoAprofundar {
                background-color: {{BG_TERTIARY}}; border: 1px solid {{BORDER}}; border-radius: 8px;
            }
            QFrame#cartaoAprofundar:hover, QFrame#cartaoAprofundar:focus { border-color: {{ACCENT}}; background-color: {{BG_HOVER}}; }
            QFrame#cartaoAprofundar[rodando="true"] { border-color: {{ACCENT}}; }
            QFrame#cartaoAprofundar:disabled { background-color: {{BG_SECONDARY}}; }
            QLabel { background: transparent; border: none; }
        """))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(4)
        self._lbl_icone = QLabel(icone)
        self._lbl_icone.setStyleSheet("font-size: 15pt;")
        layout.addWidget(self._lbl_icone)
        self._lbl_nome = QLabel(nome)
        self._lbl_nome.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-weight: bold; font-size: 10pt;"))
        layout.addWidget(self._lbl_nome)
        self._lbl_desc = QLabel(descricao)
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        layout.addWidget(self._lbl_desc, 1)
        self._lbl_rodape = QLabel(rodape)
        layout.addWidget(self._lbl_rodape)
        self.set_estado("normal")

    def set_estado(self, estado: str, rodape: str = ""):
        """``normal`` | ``rodando`` | ``feito``."""
        self.setProperty("rodando", "true" if estado == "rodando" else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self._lbl_icone.setText("⏳" if estado == "rodando" else self._icone)
        if estado == "feito":
            cor = "{{SUCCESS}}; font-weight: bold"
        elif estado == "rodando":
            cor = "{{ACCENT}}; font-weight: bold"
        else:
            cor = "{{FG_SECONDARY}}"
        self._lbl_rodape.setStyleSheet(themed_qss(f"color: {cor}; font-size: 8.5pt;"))
        self._lbl_rodape.setText(rodape or self._rodape_padrao)

    def mouseReleaseEvent(self, event):
        if (self.isEnabled() and event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicado.emit(self.acao)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.isEnabled() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicado.emit(self.acao)
            return
        super().keyPressEvent(event)


# ----------------------------------------------------------------------
# Texto da IA -> HTML
# ----------------------------------------------------------------------

_ITEM_RE = re.compile(r"^(?:[•\-*]\s+|\d+[.)]\s+)")


def linhas_ia(texto: str) -> List[Tuple[str, str]]:
    """Classifica cada linha do texto da IA em ``titulo``, ``item`` ou
    ``paragrafo``. A IA é instruída a escrever texto simples (título numa
    linha sozinho, itens com "• "); marcas de Markdown que escaparem mesmo
    assim são limpas aqui, em vez de aparecerem cruas."""
    resultado = []
    for bruta in (texto or "").splitlines():
        linha = bruta.strip().replace("**", "")
        linha = re.sub(r"^#+\s*", "", linha)
        if not linha:
            continue
        if _ITEM_RE.match(linha):
            if linha[0] in "-*":
                linha = "• " + linha[1:].lstrip()
            resultado.append(("item", linha))
        elif len(linha) <= 80 and not linha.endswith((".", ";", ",", "!", "?")):
            resultado.append(("titulo", linha))
        else:
            resultado.append(("paragrafo", linha))
    return resultado


def texto_ia_em_html(texto: str, espaco_titulo: int = 10, espaco_linha: int = 3) -> str:
    """HTML do texto da IA: títulos em negrito e itens com recuo, para a tela
    (QLabel) e para o PDF (QTextDocument)."""
    partes = []
    primeira = True
    for tipo, linha in linhas_ia(texto):
        seguro = html_lib.escape(linha)
        if tipo == "titulo":
            topo = 0 if primeira else espaco_titulo
            partes.append(f"<p style='margin-top:{topo}px; margin-bottom:{espaco_linha}px;'><b>{seguro}</b></p>")
        elif tipo == "item":
            partes.append(f"<p style='margin-top:0px; margin-bottom:{espaco_linha}px; "
                          f"margin-left:14px; text-indent:-10px;'>{seguro}</p>")
        else:
            partes.append(f"<p style='margin-top:0px; margin-bottom:{espaco_linha + 3}px;'>{seguro}</p>")
        primeira = False
    return "".join(partes)


def criar_secao_ia(titulo: str, detalhe: str, texto: str) -> QWidget:
    """Uma seção da aba da IA: cabeçalho com linha divisória (menos na
    análise principal, que já tem o contexto acima) e o texto selecionável."""
    secao = QWidget()
    secao.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(secao)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    if titulo:
        divisoria = QFrame()
        divisoria.setFixedHeight(1)
        divisoria.setStyleSheet(themed_qss("background-color: {{BORDER}}; border: none;"))
        layout.addSpacing(10)
        layout.addWidget(divisoria)
        cabecalho = QLabel(
            f"<b>{html_lib.escape(titulo)}</b>"
            + (f"&nbsp;&nbsp;<span style='font-size:9pt;'>{html_lib.escape(detalhe)}</span>" if detalhe else "")
        )
        cabecalho.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-size: 11pt; background: transparent;"))
        layout.addWidget(cabecalho)
    corpo = QLabel(texto_ia_em_html(texto))
    corpo.setTextFormat(Qt.TextFormat.RichText)
    corpo.setWordWrap(True)
    corpo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                  | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    corpo.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-size: 10.5pt; background: transparent;"))
    corpo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    layout.addWidget(corpo)
    return secao
