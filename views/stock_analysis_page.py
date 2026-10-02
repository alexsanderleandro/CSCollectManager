"""
stock_analysis_page.py
=======================
Página "Análise de Estoque" — compara até três contagens baixadas (os ZIPs
assinados do coletor) com o estoque do ERP, mostra a acurácia e a validade
dos lotes, e aciona a IA para redigir a análise das divergências.
"""

import html as html_lib
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDateEdit, QSpinBox, QComboBox, QLineEdit,
    QRadioButton, QButtonGroup, QMenu, QScrollArea, QDialog,
    QMessageBox, QGroupBox, QSizePolicy, QCheckBox, QStyledItemDelegate, QStyle,
    QTabWidget, QApplication, QFrame, QStackedWidget, QTabBar, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QDate, QEvent, QThreadPool, QMarginsF, QPointF, QRectF, QSize, QSizeF,
    QTimer, QElapsedTimer, QEasingCurve, QPropertyAnimation, Signal
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter,
    QPainterPath, QPen, QPdfWriter, QPageSize, QPageLayout, QTextDocument
)

from app.styles import themed_qss, get_active_theme
from services.contagem_zip import (
    Contagem, ContagemZipError, ler_contagem_zip, listar_contagens_baixadas
)
from services.stock_analysis_service import (
    StockAnalysisService, StockAnalysisValidationError, ResultadoAnalise, ItemAnalise,
    Acuracia, MAX_CONTAGENS_ANALISE, CAMPOS_CUSTO, formatar_moeda, formatar_pct
)
from services.ai_config_service import AIConfigService, NOMES_PROVEDOR
from services.ai_client import AIClient, AIClientError
from views.stock_analysis_widgets import (
    CHAVE_ORDEM, CartaoAprofundar, ContaAcuraciaDialog, EscolherProdutoDialog, ItemOrdenavel,
    SelecionarContagensDialog, criar_secao_ia, sem_acento, texto_ia_em_html
)
from utils.workers import WorkerSignals, TaskRunnable
from utils.config import AppConfig
from utils.constants import APP_INFO
from utils.logger import get_logger
from utils.xlsx_writer import DATA, MOEDA, NUMERO, TEXTO, gravar_xlsx

logger = get_logger(__name__)

_SITUACAO_LABEL = {
    "confere": "Confere",
    "falta": "Falta",
    "sobra": "Sobra",
    "lote_novo": "Lote novo",
    "sem_cadastro": "Sem cadastro",
    "nao_contado": "Não contado",
}
_SITUACAO_COR = {
    "confere": "{{SUCCESS}}",
    "falta": "{{ERROR}}",
    "sobra": "{{WARNING}}",
    "lote_novo": "{{ACCENT}}",
    "nao_contado": "{{FG_DISABLED}}",
}
# "Sem cadastro" é erro de cadastro, não falta nem sobra: cor própria, fora da
# paleta do tema (que não tem um roxo), com um tom para cada fundo.
_COR_SEM_CADASTRO = {"DarkTheme": "#c792ea", "LightTheme": "#8e44ad"}

# Filtro de situação da grade: rótulo -> situações que ele mostra.
_FILTROS_SITUACAO = [
    ("Todas as situações", None),
    ("Só divergências", ("falta", "sobra")),
    ("Falta", ("falta",)),
    ("Sobra", ("sobra",)),
    ("Confere", ("confere",)),
    ("Lote novo", ("lote_novo",)),
    ("Sem cadastro", ("sem_cadastro",)),
    ("Não contado", ("nao_contado",)),
]
_SEM_GRUPO = "(sem grupo)"
_SEM_LOCAL = "(sem localização)"

# Colunas fixas da grade; as de contado (uma por contagem) começam em
# _COL_CONTADO, e as de _COLUNAS_FINAIS vêm logo depois delas. Valor e
# Situação ficam colados na Diferença: é o que se lê junto, e com as colunas
# de detalhe (custo, grupo, localização, observações) no fim elas continuam
# à vista sem rolar para o lado.
_COL_PRODUTO, _COL_DESCRICAO, _COL_LOTE, _COL_CONTADO = 0, 1, 2, 3
_COLUNAS_FINAIS = ["sistema", "diferenca", "valor", "situacao", "entrada",
                   "custo", "grupo", "localizacao", "observacoes"]
_ROTULOS_FINAIS = {
    "diferenca": "Diferença", "valor": "Valor (R$)", "situacao": "Situação", "entrada": "Entrada",
    "custo": "Custo (R$)", "grupo": "Grupo", "localizacao": "Localização", "observacoes": "Observações",
}
# Colunas numéricas começam a ordenação do maior para o menor.
_COLUNAS_NUMERICAS = {"contado", "sistema", "diferenca", "custo", "valor"}
_MARCA_BASE = "● "  # prefixo no cabeçalho da coluna de contado usada como base
# Observação longa sai encurtada na célula (texto inteiro na dica): sem isso
# a coluna esticaria até a largura do texto — a grade não corta valores.
_LIMITE_TEXTO_CELULA = 60

# Aprofundamentos da análise da IA: ação -> (ícone, nome, o que entrega, custo).
_APROFUNDAMENTOS = {
    "plano": ("📋", "Plano de ação detalhado",
              "Ações em ordem de prazo (hoje, 2 dias, próxima carga), com a área responsável.",
              "1 pedido à IA"),
    "produto": ("🔎", "Explicar um produto",
                "Causas prováveis e o que conferir para um produto da grade, com todos os lotes dele.",
                "1 pedido por produto"),
    "gerencia": ("📝", "Resumo curto para a gerência",
                 "Um parágrafo com o saldo em R$, o principal problema e o próximo passo.",
                 "1 pedido à IA"),
    "conferentes": ("👥", "Onde os conferentes discordam",
                    "Registros em que as contagens não batem entre si e o que isso indica.",
                    "1 pedido à IA"),
}
_PEDIDOS_APROFUNDAR = {
    "plano": (
        "Escreva um plano de ação detalhado a partir da análise já entregue. Agrupe as ações "
        "por prazo, com um título para cada prazo (Hoje, Em até 2 dias, Na próxima carga) e as "
        "ações como itens. Em cada ação, diga a área (estoque, compras, fiscal), o produto e o "
        "lote envolvidos e como saber que ela está resolvida. Não repita o diagnóstico."
    ),
    "produto": (
        "Explique as divergências do produto {codigo} ({descricao}) com base nos registros "
        "detalhados acima. Organize em três títulos: Números (contado, sistema, diferença e valor "
        "de cada lote), Causas prováveis (em ordem de probabilidade, considerando a entrada, as "
        "observações do conferente e a validade) e O que conferir. Se houver mais de um lote, "
        "diga se as diferenças entre os lotes se compensam."
    ),
    "gerencia": (
        "Escreva um resumo para a gerência em um único parágrafo de no máximo 90 palavras, sem "
        "título e sem lista: o saldo das divergências em R$, o principal problema encontrado e o "
        "próximo passo."
    ),
    "conferentes": (
        "Analise onde as contagens discordam entre si, usando a tabela de discordâncias acima: "
        "quais registros, qual contagem ficou mais perto do sistema em cada caso e que padrões "
        "aparecem (grupo, localização, tipo de entrada, observações). Diga o que isso indica "
        "sobre a confiabilidade de cada contagem e termine com as ações recomendadas para "
        "resolver as discordâncias."
    ),
}

# Regras de forma comuns à análise e aos aprofundamentos.
_REGRAS_TEXTO_IA = (
    # Sem isto o modelo fecha oferecendo "se quiser, eu elaboro...", e
    # aqui não há como responder — a frase ia parar até no PDF.
    "O texto é um relatório fechado: aparece numa tela do sistema e é "
    "exportado em PDF, e quem lê não tem como responder. Não faça perguntas "
    "nem ofereça ajuda adicional, outras versões ou próximos passos. Não "
    "indique responsáveis por nome — quando fizer sentido, indique a área "
    "(estoque, compras, fiscal).\n\n"
    # A tela e o PDF mostram o texto como veio: Markdown apareceria cru,
    # com ** e ##.
    "Escreva em texto simples, sem Markdown (nada de **, ## ou tabelas): cada "
    "título numa linha sozinho e os itens de lista começando com \"• \"."
)
_LEITURA_DADOS_IA = (
    "Os valores em R$ são diferença × o custo indicado no resumo. \"Sem "
    "cadastro\" é código contado que não existe no ERP: erro de cadastro, não "
    "sobra física. A coluna \"entrada\" indica quantidade que não foi bipada "
    "(digitada à mão, lançada sem GTIN ou corrigida depois) — considere isso "
    "ao apontar causas, assim como as observações do conferente."
)
_SYSTEM_ANALISE = (
    "Você é um analista de estoque. Recebe um resumo já calculado de uma "
    "contagem física comparada ao sistema e escreve uma análise objetiva das "
    "divergências, em português, destacando padrões relevantes e priorizando "
    "o que tem mais valor. Quando houver mais de uma contagem, compare também "
    "as contagens entre si e aponte onde os conferentes discordam. Nunca "
    "invente números — use apenas os valores do resumo recebido.\n\n"
    + _LEITURA_DADOS_IA + "\n\n" + _REGRAS_TEXTO_IA + "\n\n"
    "Termine com a seção \"Ações recomendadas\", com as ações em ordem de prioridade."
)
_SYSTEM_APROFUNDAR = (
    "Você é um analista de estoque. Já entregou uma análise das divergências "
    "de uma contagem física comparada ao sistema e agora escreve uma seção "
    "complementar, que será acrescentada ao fim dela a pedido do usuário. "
    "Responda só ao pedido, sem repetir a análise já entregue. Nunca invente "
    "números — use apenas os valores recebidos.\n\n"
    + _LEITURA_DADOS_IA + "\n\n" + _REGRAS_TEXTO_IA
)

_QSS_TABELA = """
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
"""
_QSS_CAMPO = """
    QComboBox, QLineEdit {
        background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}};
        border: 1px solid {{BORDER}}; border-radius: 6px; padding: 3px 8px; font-size: 9pt;
    }
    QComboBox:focus, QLineEdit:focus { border-color: {{ACCENT}}; }
"""
_QSS_BOTAO = """
    QPushButton {
        background-color: {{BG_HOVER}}; color: {{FG_PRIMARY}};
        border: none; border-radius: 8px; padding: 8px 16px;
    }
    QPushButton:hover { background-color: {{BG_SELECTED}}; }
    QPushButton:disabled { color: {{FG_DISABLED}}; }
"""


def _num(valor, sinal=False) -> str:
    if valor is None:
        return "—"
    return f"{valor:+g}" if sinal else f"{valor:g}"


def _valor_curto(valor, sinal=False) -> str:
    """Valor em R$ sem o símbolo (o cabeçalho da coluna já diz "R$")."""
    return formatar_moeda(valor, sinal).replace("R$ ", "")


def _encurtar(texto: str) -> str:
    if len(texto) <= _LIMITE_TEXTO_CELULA:
        return texto
    return texto[:_LIMITE_TEXTO_CELULA - 1].rstrip() + "…"


def _cor_situacao(situacao: str) -> QColor:
    if situacao == "sem_cadastro":
        return QColor(_COR_SEM_CADASTRO.get(get_active_theme().__name__, "#8e44ad"))
    return _qcolor_from_token(_SITUACAO_COR.get(situacao, "{{FG_PRIMARY}}"))


def _chave_arquivo(caminho: str) -> str:
    return os.path.normcase(os.path.abspath(caminho))


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


class _FolhaLeituraIA(QWidget):
    """Folha com a linha de leitura da animação da análise com IA.

    Linhas apagadas, como as de um relatório, e uma faixa com brilho que desce
    e sobe, como o leitor de código de barras do coletor. A posição da faixa
    vem de fora (`set_fase`): um único QTimer da página move a faixa e gira o
    indicador da aba juntos. A altura é flexível: numa janela baixa a folha
    encolhe e desenha só as linhas que couberem.
    """

    LARGURA, ALTURA = 380, 176
    ALTURA_MIN = 64
    _MARGEM_X, _MARGEM_Y = 18, 16
    _ALTURA_LINHA, _ENTRE_LINHAS, _ENTRE_BARRAS = 8, 12, 10
    _BARRAS_FIXAS = (72, 30, 30)  # código e duas quantidades; a descrição fica com o resto

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fase = 0.0
        self.setMinimumSize(240, self.ALTURA_MIN)
        self.setMaximumSize(self.LARGURA, self.ALTURA)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

    def sizeHint(self) -> QSize:
        return QSize(self.LARGURA, self.ALTURA)

    def set_fase(self, fase: float):
        """Posição da faixa: 0 = topo, 1 = base (já com a suavização aplicada)."""
        self._fase = fase
        self.update()

    def paintEvent(self, event):
        tema = get_active_theme()
        largura, altura = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        contorno = QPainterPath()
        contorno.addRoundedRect(QRectF(0.5, 0.5, largura - 1, altura - 1), 8, 8)
        p.fillPath(contorno, QColor(tema.BG_PRIMARY))
        p.setPen(QPen(QColor(tema.BORDER), 1))
        p.drawPath(contorno)
        p.setClipPath(contorno)

        barra = QColor(tema.FG_PRIMARY)
        barra.setAlphaF(0.10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(barra)
        codigo, qtd1, qtd2 = self._BARRAS_FIXAS
        descricao = (largura - 2 * self._MARGEM_X - sum(self._BARRAS_FIXAS)
                     - 3 * self._ENTRE_BARRAS)
        passo = self._ALTURA_LINHA + self._ENTRE_LINHAS
        linhas = max(1, (altura - 2 * self._MARGEM_Y + self._ENTRE_LINHAS) // passo)
        y = self._MARGEM_Y
        for _ in range(linhas):
            x = self._MARGEM_X
            for w in (codigo, descricao, qtd1, qtd2):
                p.drawRoundedRect(QRectF(x, y, w, self._ALTURA_LINHA), 4, 4)
                x += w + self._ENTRE_BARRAS
            y += passo

        # Faixa de leitura: brilho suave em volta de uma linha nítida.
        acento = QColor(tema.ACCENT)
        centro = 10 + self._fase * (altura - 20)
        transparente = QColor(acento)
        transparente.setAlphaF(0.0)
        suave = QColor(acento)
        suave.setAlphaF(0.16)
        faixa = QLinearGradient(0, centro - 20, 0, centro + 20)
        faixa.setColorAt(0.0, transparente)
        faixa.setColorAt(0.5, suave)
        faixa.setColorAt(1.0, transparente)
        p.fillRect(QRectF(0, centro - 20, largura, 40), QBrush(faixa))
        for espessura, alfa in ((7, 0.12), (4, 0.25)):
            brilho = QColor(acento)
            brilho.setAlphaF(alfa)
            p.fillRect(QRectF(0, centro - espessura / 2, largura, espessura), brilho)
        p.fillRect(QRectF(0, centro - 1, largura, 2), acento)
        p.end()


class _GiroAbaIA(QWidget):
    """Indicador girando no canto da aba "Análise da IA" enquanto a IA analisa;
    continua visível quando o usuário volta para a grade."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angulo = 0.0
        self.setFixedSize(14, 14)
        # Um clique em cima do indicador tem que selecionar a aba, como no resto dela.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_angulo(self, angulo: float):
        self._angulo = angulo
        self.update()

    def paintEvent(self, event):
        acento = QColor(get_active_theme().ACCENT)
        trilho = QColor(acento)
        trilho.setAlphaF(0.25)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(2, 2, 10, 10)
        p.setPen(QPen(trilho, 2))
        p.drawEllipse(area)
        p.setPen(QPen(acento, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # Arco de 90° girando no sentido horário (ângulos do Qt em 1/16 de grau).
        p.drawArc(area, round((90 - self._angulo) * 16), -90 * 16)
        p.end()


class _AnimacaoLeituraIA(QFrame):
    """Painel que fica no lugar do texto enquanto a IA analisa.

    Folha com a linha de leitura, quantas divergências foram enviadas, o
    modelo e o tempo decorrido. Só informação real: a IA não informa
    progresso, então não há porcentagem nem etapas.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # objectName no seletor: QLabel também é um QFrame, e um seletor
        # `QFrame` genérico poria a borda em volta de cada texto.
        self.setObjectName("animacaoIA")
        self.setStyleSheet(themed_qss("""
            QFrame#animacaoIA {
                background-color: {{BG_SECONDARY}}; border: 1px solid {{BORDER}}; border-radius: 8px;
            }
        """))
        # Não impõe altura mínima à aba (a tela tem que caber em notebook):
        # numa janela baixa a folha encolhe e, no limite, some, ficando só os textos.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        layout.addStretch(1)
        self.folha = _FolhaLeituraIA()
        layout.addWidget(self.folha, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        # Fundo transparente explícito: o fundo da página (QSS sem seletor)
        # desce para os filhos e pintaria uma faixa atrás de cada texto.
        self.lbl_mensagem = QLabel("")
        self.lbl_mensagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_mensagem.setWordWrap(True)
        self.lbl_mensagem.setStyleSheet(themed_qss(
            "background: transparent; color: {{FG_PRIMARY}}; font-size: 12.5pt; font-weight: 600;"))
        layout.addWidget(self.lbl_mensagem)
        self.lbl_info = QLabel("")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(themed_qss(
            "background: transparent; color: {{FG_SECONDARY}}; font-size: 9pt;"))
        layout.addWidget(self.lbl_info)
        layout.addStretch(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margens = self.layout().contentsMargins()
        textos = (self.lbl_mensagem.sizeHint().height() + self.lbl_info.sizeHint().height()
                  + 3 * self.layout().spacing() + 8)
        livre = self.height() - margens.top() - margens.bottom() - textos
        self.folha.setVisible(livre >= _FolhaLeituraIA.ALTURA_MIN)


class StockAnalysisPage(QWidget):
    """Página de análise de estoque (contagens baixadas → comparar → IA)."""

    # Produtos (codproduto) e local de estoque ("L", "D" ou ENDLOCALESTOQUE)
    # de uma carga de recontagem — a MainWindowERP leva para Exportar Carga.
    recontagem_solicitada = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._service = StockAnalysisService()
        self._contagens: List[Contagem] = []
        # Contagem única usada como referência da grade (duplo clique na lista).
        # None = agregado de todas as contagens (comportamento padrão).
        self._contagem_referencia: Optional[Contagem] = None
        self._resultado: Optional[ResultadoAnalise] = None
        self._acuracia: Optional[Acuracia] = None
        # Seções da aba da IA: a análise principal e, depois dela, os
        # aprofundamentos pedidos nos cartões. Cada uma: acao, titulo,
        # detalhe, texto, codigo (produto explicado, quando houver).
        self._secoes_ia: List[dict] = []
        self._widgets_secoes: List[QWidget] = []
        # Dados da análise principal, reaproveitados pelos aprofundamentos
        # ("com os mesmos dados já enviados e a análise anterior").
        self._ia_base: Optional[dict] = None
        self._ia_pendente: Optional[dict] = None
        self._acoes_feitas: set = set()
        self._produtos_explicados: set = set()
        # Análise da IA em andamento (animação na aba) e aprofundamento em
        # andamento (dict com acao/titulo/codigo). A geração descarta a
        # resposta de um pedido que o usuário abandonou limpando a tela.
        self._ia_em_andamento = False
        self._aprofundando: Optional[dict] = None
        self._ia_geracao = 0
        # Contexto da análise anterior, para voltar junto com o texto dela se
        # a nova falhar.
        self._contexto_ia_anterior = ""
        # Incrementada a cada nova comparação disparada (troca de data/local de
        # estoque); descarta resultados de uma comparação anterior que ainda
        # não tinha voltado do worker quando o usuário já mudou o parâmetro de
        # novo — sem isso, uma resposta lenta da consulta anterior podia
        # sobrescrever a grade com dados de uma data que não é mais a atual.
        self._analise_geracao = 0
        # Parâmetros (data, local, contagens) do resultado que está na grade.
        self._contexto_resultado: Optional[dict] = None
        # Contagem (id) da coluna base da diferença — sobrevive a um recálculo
        # por troca de data/local, para a escolha do usuário não se perder.
        self._base_id: Optional[int] = None
        # Contagens (id) que o usuário tirou da exportação e da IA.
        self._fora_export: set = set()
        # Estoque do sistema do cálculo anterior (mesma grade, outra
        # data/local), para destacar o que mudou.
        self._sistema_antes: dict = {}
        self._data_antes: Optional[date] = None
        # Ordenação escolhida no cabeçalho: (chave da coluna, ordem). None =
        # ordem padrão, por valor da divergência.
        self._ordem: Optional[tuple] = None
        self._visiveis = 0
        # Aviso das contagens recém-adicionadas (ex.: locais diferentes),
        # mostrado junto do status da comparação que elas disparam.
        self._aviso_contagens = ""
        self._campo_custo = AppConfig.get_analise_campo_custo()
        if self._campo_custo not in CAMPOS_CUSTO:
            self._campo_custo = next(iter(CAMPOS_CUSTO))
        self._codempresa = ""
        self._cnpj = ""
        self._nome_empresa = ""
        self._nome_usuario = ""
        self._locais_estoque_mode = "A"
        self._setup_ui()

    # ------------------------------------------------------------------
    # Configuração externa (chamada pela MainWindowERP)
    # ------------------------------------------------------------------

    def set_empresa_info(self, codigo, nome: str, cnpj: str = ""):
        """Define a empresa logada, usada para validar as contagens."""
        self._codempresa = str(codigo or "")
        self._nome_empresa = nome or ""
        self._cnpj = str(cnpj or "")

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

    @staticmethod
    def _valor_local(local: str) -> str:
        """Empresa.local da carga ("Loja", "Depósito", ENDLOCALESTOQUE) -> valor do rádio."""
        chave = sem_acento(local.strip())
        if chave == "loja":
            return "L"
        if chave == "deposito":
            return "D"
        return local.strip()

    @staticmethod
    def _nome_local(valor: str) -> str:
        return {"L": "Loja", "D": "Depósito"}.get(valor, valor)

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

        # ----- Toolbar: selecionar / limpar / data -----
        toolrow = QHBoxLayout()
        toolrow.setSpacing(10)

        self._btn_selecionar = QPushButton("📥  Selecionar contagens...")
        self._btn_selecionar.setMinimumHeight(36)
        self._btn_selecionar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_selecionar.setToolTip(
            f"Escolha até {MAX_CONTAGENS_ANALISE} contagens baixadas na tela Download Contagens")
        self._btn_selecionar.setStyleSheet(themed_qss(_QSS_BOTAO))
        self._btn_selecionar.clicked.connect(self._on_selecionar_clicked)
        toolrow.addWidget(self._btn_selecionar)

        self._btn_limpar = QPushButton("Limpar")
        self._btn_limpar.setMinimumHeight(36)
        self._btn_limpar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_limpar.setStyleSheet(themed_qss(_QSS_BOTAO))
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

        # ----- Lista das contagens na análise -----
        self._lbl_contagens_info = QLabel("")
        self._lbl_contagens_info.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        content_layout.addWidget(self._lbl_contagens_info)

        self._lista_contagens = QListWidget()
        self._lista_contagens.setMaximumHeight(96)
        self._lista_contagens.setToolTip(
            "Duplo clique: mostrar só esta contagem na grade · botão direito: mais opções")
        self._lista_contagens.setStyleSheet(themed_qss("""
            QListWidget { background-color: {{BG_SECONDARY}}; border: 1px solid {{BORDER}}; border-radius: 6px; }
        """))
        self._lista_contagens.itemDoubleClicked.connect(self._on_contagem_double_clicked)
        self._lista_contagens.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._lista_contagens.customContextMenuRequested.connect(self._on_menu_lista)
        content_layout.addWidget(self._lista_contagens)
        self._atualizar_lbl_contagens_info()

        # ----- Abas: grade | análise da IA | acurácia | validade -----
        # A análise da IA é texto corrido e longo: numa aba própria ela usa a
        # área inteira da grade, em vez de uma faixa espremida embaixo dela.
        self._abas = QTabWidget()
        self._abas.addTab(self._criar_aba_grade(), "📊  Resultado comparativo")
        self._indice_aba_ia = self._abas.addTab(self._criar_aba_ia(), "🤖  Análise da IA")
        self._indice_aba_acuracia = self._abas.addTab(self._criar_aba_acuracia(), "🎯  Acurácia")
        self._indice_aba_validade = self._abas.addTab(self._criar_aba_validade(), "⏳  Validade")
        self._contexto_ia_pendente = ""

        # Um único QTimer move a linha de leitura, gira o indicador da aba e
        # conta o tempo; só roda enquanto a IA está trabalhando.
        self._giro_aba_ia = _GiroAbaIA(self._abas.tabBar())
        self._giro_aba_ia.hide()
        self._timer_ia = QTimer(self)
        self._timer_ia.setInterval(30)
        self._timer_ia.timeout.connect(self._animar_ia)
        self._relogio_ia = QElapsedTimer()
        self._curva_ia = QEasingCurve(QEasingCurve.Type.InOutSine)
        self._segundos_ia = -1
        self._descricao_modelo_ia = ""

        content_layout.addWidget(self._abas, 1)

        # ----- Toolbar: analisar / limite / recontagem / exportar -----
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

        self._btn_recontagem = QPushButton("🔁  Gerar recontagem")
        self._btn_recontagem.setMinimumHeight(36)
        self._btn_recontagem.setEnabled(False)
        self._btn_recontagem.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_recontagem.setToolTip(
            "Leva para Exportar Carga só os produtos das linhas selecionadas na grade "
            "(sem seleção: todas as divergências visíveis)")
        self._btn_recontagem.setStyleSheet(themed_qss(_QSS_BOTAO))
        self._btn_recontagem.clicked.connect(self._on_recontagem_clicked)
        toolrow2.addWidget(self._btn_recontagem)

        self._btn_exportar = QPushButton("Exportar  ▾")
        self._btn_exportar.setMinimumHeight(36)
        self._btn_exportar.setEnabled(False)
        self._btn_exportar.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_exportar.setStyleSheet(themed_qss(_QSS_BOTAO))
        self._btn_exportar.clicked.connect(self._on_exportar_clicked)
        toolrow2.addWidget(self._btn_exportar)

        content_layout.addLayout(toolrow2)

        self._lbl_status = QLabel("")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        content_layout.addWidget(self._lbl_status)

        layout.addWidget(content)

    def _criar_aba_grade(self) -> QWidget:
        aba = QWidget()
        aba_layout = QVBoxLayout(aba)
        aba_layout.setContentsMargins(0, 8, 0, 0)
        aba_layout.setSpacing(8)

        # ----- Base da diferença + colunas para exportação/IA -----
        # Só aparece com mais de uma contagem na grade: com uma só não há o
        # que escolher.
        self._linha_colunas = QWidget()
        linha_colunas = QHBoxLayout(self._linha_colunas)
        linha_colunas.setContentsMargins(0, 0, 0, 0)
        linha_colunas.setSpacing(8)
        lbl_base = QLabel("Base da diferença:")
        lbl_base.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        linha_colunas.addWidget(lbl_base)
        self._cmb_base = QComboBox()
        self._cmb_base.setStyleSheet(themed_qss(_QSS_CAMPO))
        self._cmb_base.setToolTip("Contagem comparada com o sistema na coluna Diferença")
        self._cmb_base.currentIndexChanged.connect(self._on_base_escolhida)
        linha_colunas.addWidget(self._cmb_base)
        linha_colunas.addStretch()
        _lbl_export = QLabel("Considerar na exportação e na IA:")
        _lbl_export.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        linha_colunas.addWidget(_lbl_export)
        self._layout_checks_export = QHBoxLayout()
        self._layout_checks_export.setSpacing(12)
        linha_colunas.addLayout(self._layout_checks_export)
        self._checks_export: List[QCheckBox] = []
        self._linha_colunas.setVisible(False)
        aba_layout.addWidget(self._linha_colunas)

        # ----- Filtros da grade + campo de custo -----
        self._linha_filtros = QWidget()
        linha_filtros = QHBoxLayout(self._linha_filtros)
        linha_filtros.setContentsMargins(0, 0, 0, 0)
        linha_filtros.setSpacing(8)
        self._cmb_situacao = QComboBox()
        for rotulo, situacoes in _FILTROS_SITUACAO:
            self._cmb_situacao.addItem(rotulo, situacoes)
        self._cmb_grupo = QComboBox()
        self._cmb_local = QComboBox()
        self._txt_busca = QLineEdit()
        self._txt_busca.setPlaceholderText("🔍  Buscar código ou descrição")
        self._txt_busca.setClearButtonEnabled(True)
        self._txt_busca.setMinimumWidth(220)
        for campo in (self._cmb_situacao, self._cmb_grupo, self._cmb_local, self._txt_busca):
            campo.setStyleSheet(themed_qss(_QSS_CAMPO))
            campo.setMinimumHeight(28)
            linha_filtros.addWidget(campo)
        self._cmb_situacao.currentIndexChanged.connect(self._aplicar_filtros)
        self._cmb_grupo.currentIndexChanged.connect(self._aplicar_filtros)
        self._cmb_local.currentIndexChanged.connect(self._aplicar_filtros)
        self._txt_busca.textChanged.connect(self._aplicar_filtros)
        linha_filtros.addStretch()
        lbl_custo = QLabel("Valor pelo:")
        lbl_custo.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        linha_filtros.addWidget(lbl_custo)
        self._cmb_custo = QComboBox()
        for campo, rotulo in CAMPOS_CUSTO.items():
            self._cmb_custo.addItem(rotulo, campo)
        self._cmb_custo.setCurrentIndex(max(0, self._cmb_custo.findData(self._campo_custo)))
        self._cmb_custo.setStyleSheet(themed_qss(_QSS_CAMPO))
        self._cmb_custo.setMinimumHeight(28)
        self._cmb_custo.setToolTip("Campo de custo do produto (produtosestoque, empresa logada) "
                                   "usado no valor da divergência")
        self._cmb_custo.currentIndexChanged.connect(self._on_custo_escolhido)
        linha_filtros.addWidget(self._cmb_custo)
        self._linha_filtros.setVisible(False)
        aba_layout.addWidget(self._linha_filtros)

        self._lbl_totais = QLabel("")
        self._lbl_totais.setWordWrap(True)
        self._lbl_totais.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_totais.setToolTip("A conta da acurácia, registro a registro, está na aba Acurácia.")
        self._lbl_totais.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        aba_layout.addWidget(self._lbl_totais)

        # ----- Tabela de divergências -----
        self._table = QTableWidget()
        self._table.setItemDelegate(_DelegateFundoCelula(self._table))
        self._montar_cabecalho()
        # Clique no cabeçalho ordena pela coluna (a base da diferença fica no
        # seletor acima da grade). Ordenação manual, ver `_ordenar`.
        self._table.horizontalHeader().setSectionsClickable(True)
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
        # Várias linhas: é a seleção que vai para a carga de recontagem.
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(themed_qss(_QSS_TABELA))
        aba_layout.addWidget(self._table, 1)
        return aba

    def _criar_aba_ia(self) -> QWidget:
        aba = QWidget()
        aba_layout = QVBoxLayout(aba)
        aba_layout.setContentsMargins(0, 8, 0, 0)
        aba_layout.setSpacing(8)
        # Com a análise numa aba separada da grade, fica registrado de quais
        # dados ela saiu — a grade pode mudar depois (data, base da diferença).
        self._lbl_contexto_ia = QLabel("")
        self._lbl_contexto_ia.setWordWrap(True)
        self._lbl_contexto_ia.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        aba_layout.addWidget(self._lbl_contexto_ia)

        # Texto e cartões de aprofundamento numa rolagem só: os cartões ficam
        # no fim do texto, depois da última seção (layout B aprovado).
        self._scroll_ia = QScrollArea()
        self._scroll_ia.setObjectName("leituraIA")
        self._scroll_ia.setWidgetResizable(True)
        self._scroll_ia.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_ia.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_ia.setStyleSheet(themed_qss("""
            QScrollArea#leituraIA { background-color: {{BG_SECONDARY}}; border: 1px solid {{BORDER}}; border-radius: 8px; }
        """))
        self._conteudo_ia = QWidget()
        self._conteudo_ia.setObjectName("conteudoIA")
        self._conteudo_ia.setStyleSheet(themed_qss("QWidget#conteudoIA { background-color: {{BG_SECONDARY}}; }"))
        conteudo = QVBoxLayout(self._conteudo_ia)
        conteudo.setContentsMargins(18, 14, 18, 14)
        conteudo.setSpacing(0)

        self._lbl_vazio_ia = QLabel("A análise aparece aqui depois de clicar em \"🤖 Analisar com IA\", abaixo.")
        self._lbl_vazio_ia.setStyleSheet(themed_qss(
            "color: {{FG_DISABLED}}; font-size: 10.5pt; background: transparent;"))
        conteudo.addWidget(self._lbl_vazio_ia)

        self._layout_secoes = QVBoxLayout()
        self._layout_secoes.setContentsMargins(0, 0, 0, 0)
        self._layout_secoes.setSpacing(0)
        conteudo.addLayout(self._layout_secoes)

        # Lugar da próxima seção enquanto a IA responde a um aprofundamento.
        self._placeholder_ia = QFrame()
        self._placeholder_ia.setObjectName("gerandoIA")
        self._placeholder_ia.setStyleSheet(themed_qss("""
            QFrame#gerandoIA { background-color: {{BG_TERTIARY}}; border: 1px dashed {{BORDER}}; border-radius: 8px; }
        """))
        linha_placeholder = QHBoxLayout(self._placeholder_ia)
        linha_placeholder.setContentsMargins(12, 10, 12, 10)
        linha_placeholder.setSpacing(14)
        self._folha_aprofundar = _FolhaLeituraIA()
        self._folha_aprofundar.setFixedSize(260, 64)
        linha_placeholder.addWidget(self._folha_aprofundar)
        self._lbl_aprofundando = QLabel("")
        self._lbl_aprofundando.setWordWrap(True)
        self._lbl_aprofundando.setStyleSheet(themed_qss(
            "color: {{FG_PRIMARY}}; font-size: 10pt; background: transparent; border: none;"))
        linha_placeholder.addWidget(self._lbl_aprofundando, 1)
        self._placeholder_ia.hide()
        conteudo.addSpacing(14)
        conteudo.addWidget(self._placeholder_ia)

        # Cartões de aprofundamento.
        self._bloco_cartoes = QWidget()
        self._bloco_cartoes.setObjectName("blocoCartoes")
        self._bloco_cartoes.setStyleSheet(themed_qss("""
            QWidget#blocoCartoes { background: transparent; border-top: 1px dashed {{BORDER}}; }
            QLabel { background: transparent; }
        """))
        bloco = QVBoxLayout(self._bloco_cartoes)
        bloco.setContentsMargins(0, 14, 0, 0)
        bloco.setSpacing(10)
        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(10)
        titulo = QLabel("Aprofundar esta análise")
        titulo.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-weight: bold; font-size: 10.5pt;"))
        cabecalho.addWidget(titulo)
        dica = QLabel("cada cartão faz 1 pedido à IA com os mesmos dados e esta análise")
        dica.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        cabecalho.addWidget(dica)
        cabecalho.addStretch()
        bloco.addLayout(cabecalho)
        linha_cartoes = QHBoxLayout()
        linha_cartoes.setSpacing(10)
        self._cartoes = {}
        for acao, (icone, nome, descricao, rodape) in _APROFUNDAMENTOS.items():
            cartao = CartaoAprofundar(acao, icone, nome, descricao, rodape)
            cartao.clicado.connect(self._on_cartao_clicado)
            linha_cartoes.addWidget(cartao, 1)
            self._cartoes[acao] = cartao
        bloco.addLayout(linha_cartoes)
        self._bloco_cartoes.hide()
        conteudo.addSpacing(22)
        conteudo.addWidget(self._bloco_cartoes)
        conteudo.addStretch(1)
        self._scroll_ia.setWidget(self._conteudo_ia)

        # Enquanto a IA faz a análise principal, a animação ocupa o lugar do
        # texto; o texto de uma análise anterior fica guardado atrás dela e
        # volta se a nova falhar.
        self._animacao_ia = _AnimacaoLeituraIA()
        self._pilha_ia = QStackedWidget()
        # Largura máxima: numa tela larga, linhas de texto do tamanho da janela
        # inteira ficam cansativas de acompanhar.
        self._pilha_ia.setMaximumWidth(1100)
        self._pilha_ia.addWidget(self._scroll_ia)
        self._pilha_ia.addWidget(self._animacao_ia)
        aba_layout.addWidget(self._pilha_ia, 1)
        return aba

    def _nova_tabela(self, colunas: List[str]) -> QTableWidget:
        tabela = QTableWidget()
        tabela.setColumnCount(len(colunas))
        tabela.setHorizontalHeaderLabels(colunas)
        tabela.setItemDelegate(_DelegateFundoCelula(tabela))
        tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.setAlternatingRowColors(True)
        tabela.verticalHeader().setVisible(False)
        tabela.setWordWrap(False)
        tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tabela.horizontalHeader().setStretchLastSection(True)
        tabela.setStyleSheet(themed_qss(_QSS_TABELA))
        return tabela

    def _criar_aba_acuracia(self) -> QWidget:
        aba = QWidget()
        aba_layout = QVBoxLayout(aba)
        aba_layout.setContentsMargins(0, 8, 0, 0)
        aba_layout.setSpacing(8)
        self._lbl_acuracia = QLabel("A acurácia aparece depois que a grade é calculada.")
        self._lbl_acuracia.setWordWrap(True)
        self._lbl_acuracia.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_acuracia.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._lbl_acuracia.linkActivated.connect(self._on_link_acuracia)
        self._lbl_acuracia.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-size: 10.5pt;"))
        aba_layout.addWidget(self._lbl_acuracia)
        nota = QLabel(
            "Entram só os registros comparados com o sistema: conferem, falta e sobra. O valor de cada "
            "registro é custo × quantidade; quando contado e sistema são diferentes, vale a maior das "
            "duas. Um registro contado em duas localizações entra nas duas. Dê um duplo clique numa "
            "linha para ver a conta registro a registro."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        aba_layout.addWidget(nota)

        # Nomes que não se confundem com o "Valor (R$)" da grade (que é
        # diferença × custo) e a fórmula de cada coluna na dica do cabeçalho.
        colunas_acc = [
            ("Registros", "Registros comparados com o sistema: conferem, falta e sobra. "
                          "Lote novo, sem cadastro e não contado ficam fora."),
            ("Conferem", "Registros em que o contado é igual ao estoque do sistema."),
            ("% registros", "Conferem ÷ Registros."),
            ("Valor dos\nregistros (R$)", "Soma do valor de cada registro: custo × quantidade. Quando "
                                          "contado e sistema são diferentes, vale a maior das duas. "
                                          "Registro sem custo cadastrado fica fora desta soma."),
            ("Valor dos que\nconferem (R$)", "A mesma soma, só com os registros que conferem."),
            ("% valor", "Valor dos que conferem ÷ Valor dos registros."),
        ]
        lado_a_lado = QHBoxLayout()
        lado_a_lado.setSpacing(12)
        self._tab_acc_grupo = self._nova_tabela(["Grupo"] + [nome for nome, _dica in colunas_acc])
        self._tab_acc_local = self._nova_tabela(["Localização"] + [nome for nome, _dica in colunas_acc])
        for tabela in (self._tab_acc_grupo, self._tab_acc_local):
            tabela.horizontalHeaderItem(0).setToolTip("Duplo clique numa linha: ver a conta registro a registro.")
            for col, (_nome, dica) in enumerate(colunas_acc, start=1):
                tabela.horizontalHeaderItem(col).setToolTip(dica)
            # Com as duas tabelas lado a lado, quem cede espaço é o nome (com
            # reticências e o nome inteiro na dica): os números, "% valor"
            # incluído, ficam sempre à vista sem rolar para o lado.
            cabecalho = tabela.horizontalHeader()
            cabecalho.setStretchLastSection(False)
            cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tab_acc_grupo.cellDoubleClicked.connect(self._on_acc_grupo_duplo_clique)
        self._tab_acc_local.cellDoubleClicked.connect(self._on_acc_local_duplo_clique)
        for titulo, tabela in (("Por grupo", self._tab_acc_grupo), ("Por localização", self._tab_acc_local)):
            coluna = QVBoxLayout()
            coluna.setSpacing(4)
            lbl = QLabel(titulo)
            lbl.setStyleSheet(themed_qss("color: {{FG_PRIMARY}}; font-weight: bold; font-size: 10pt;"))
            coluna.addWidget(lbl)
            coluna.addWidget(tabela, 1)
            lado_a_lado.addLayout(coluna, 1)
        aba_layout.addLayout(lado_a_lado, 1)
        return aba

    def _criar_aba_validade(self) -> QWidget:
        aba = QWidget()
        aba_layout = QVBoxLayout(aba)
        aba_layout.setContentsMargins(0, 8, 0, 0)
        aba_layout.setSpacing(8)
        linha = QHBoxLayout()
        linha.setSpacing(8)
        self._lbl_validade_ref = QLabel("Lotes vencidos até a data de referência ou que vencem em até")
        linha.addWidget(self._lbl_validade_ref)
        self._spin_validade = QSpinBox()
        self._spin_validade.setRange(0, 3650)
        self._spin_validade.setValue(AppConfig.get_analise_validade_dias())
        self._spin_validade.setMinimumHeight(28)
        self._spin_validade.setStyleSheet(themed_qss("""
            QSpinBox { background-color: {{BG_SECONDARY}}; color: {{FG_PRIMARY}}; border: 1px solid {{BORDER}}; border-radius: 6px; padding: 2px 4px; }
        """))
        self._spin_validade.valueChanged.connect(self._on_validade_dias_alterado)
        linha.addWidget(self._spin_validade)
        linha.addWidget(QLabel("dias depois dela"))
        linha.addStretch()
        aba_layout.addLayout(linha)
        self._tab_validade = self._nova_tabela(
            ["Produto", "Descrição", "Lote", "Validade", "Prazo", "Contado", "Localização"])
        aba_layout.addWidget(self._tab_validade, 1)
        self._lbl_validade_vazio = QLabel("")
        self._lbl_validade_vazio.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        aba_layout.addWidget(self._lbl_validade_vazio)
        return aba

    # ------------------------------------------------------------------
    # Selecionar / remover / limpar contagens
    # ------------------------------------------------------------------

    def _on_selecionar_clicked(self):
        vagas = MAX_CONTAGENS_ANALISE - len(self._contagens)
        if vagas <= 0:
            QMessageBox.information(
                self, "Limite de contagens",
                f"A análise compara no máximo {MAX_CONTAGENS_ANALISE} contagens, uma por coluna "
                f"de contado.\n\nRemova uma delas (botão direito na lista) ou use \"Limpar\"."
            )
            return
        pasta = AppConfig.get_last_contagens_dir()
        self._btn_selecionar.setEnabled(False)
        self._lbl_status.setText("🔄 Procurando as contagens baixadas...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))

        signals = WorkerSignals()
        signals.finished.connect(self._on_lista_contagens_pronta)
        signals.error.connect(self._on_leitura_erro)
        runnable = TaskRunnable(self._listar_em_background, args=(pasta,), signals=signals)
        QThreadPool.globalInstance().start(runnable)

    def _listar_em_background(self, pasta: str):
        return pasta, listar_contagens_baixadas(pasta, self._codempresa, self._cnpj)

    def _on_lista_contagens_pronta(self, payload):
        pasta, lista = payload
        self._btn_selecionar.setEnabled(True)
        self._lbl_status.setText("")
        if not lista:
            QMessageBox.information(
                self, "Nenhuma contagem baixada",
                f"Não há contagens desta empresa na pasta:\n{pasta}\n\n"
                "Baixe as contagens na tela Download Contagens — a pasta é a configurada lá."
            )
            return
        vagas = MAX_CONTAGENS_ANALISE - len(self._contagens)
        ja = {_chave_arquivo(c.arquivo) for c in self._contagens}
        dialogo = SelecionarContagensDialog(lista, pasta, ja, vagas, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        caminhos = dialogo.selecionadas()[:vagas]
        if not caminhos:
            return

        self._btn_selecionar.setEnabled(False)
        self._lbl_status.setText(f"🔄 Conferindo a assinatura e lendo {len(caminhos)} contagem(ns)...")
        signals = WorkerSignals()
        signals.finished.connect(self._on_contagens_lidas)
        signals.error.connect(self._on_leitura_erro)
        runnable = TaskRunnable(self._ler_em_background, args=(caminhos,), signals=signals)
        QThreadPool.globalInstance().start(runnable)

    def _ler_em_background(self, caminhos: List[str]):
        """Roda no worker: valida cada ZIP com o .sig e lê a contagem. Um ZIP
        recusado não impede os outros de entrarem."""
        token = AppConfig.get_license_token()
        lidas, erros = [], []
        for caminho in caminhos:
            try:
                lidas.append(ler_contagem_zip(caminho, self._codempresa, self._cnpj, token))
            except ContagemZipError as exc:
                erros.append(str(exc))
            except Exception as exc:
                logger.exception(f"Erro ao ler a contagem {caminho}")
                erros.append(f"{os.path.basename(caminho)}: {exc}")
        return lidas, erros

    def _on_contagens_lidas(self, payload):
        lidas, erros = payload
        self._btn_selecionar.setEnabled(True)
        if erros:
            QMessageBox.warning(
                self, "Contagem recusada",
                "Estas contagens não entraram na análise:\n\n" + "\n\n".join(erros)
            )
        if not lidas:
            self._lbl_status.setText("❌ Nenhuma contagem entrou na análise.")
            self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))
            return

        candidatas = self._contagens + lidas
        try:
            self._service.validar_empresa(candidatas, self._codempresa)
        except StockAnalysisValidationError as e:
            QMessageBox.critical(self, "Empresa Inválida", str(e))
            self._lbl_status.setText("❌ Contagem(ns) recusada(s) — empresa não confere.")
            self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))
            return

        self._contagens = candidatas
        # Adicionar contagens volta ao agregado por padrão — a referência
        # anterior pode nem fazer mais sentido junto do que acabou de entrar.
        self._contagem_referencia = None
        for c in lidas:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, c)
            item.setToolTip(self._dica_contagem(c))
            self._lista_contagens.addItem(item)
        self._atualizar_marcadores_lista()
        self._atualizar_lbl_contagens_info()

        maior_data = max(c.data_exportacao for c in lidas).date()
        # Sem sinal: a comparação roda uma vez só, logo abaixo — senão a
        # troca de data dispararia uma segunda consulta idêntica.
        self._date_referencia.blockSignals(True)
        self._date_referencia.setDate(QDate(maior_data.year, maior_data.month, maior_data.day))
        self._date_referencia.blockSignals(False)
        self._aviso_contagens = self._aplicar_local_das_contagens()
        self._rodar_comparacao()

    def _on_leitura_erro(self, exc: Exception):
        self._btn_selecionar.setEnabled(True)
        QMessageBox.critical(self, "Erro ao Ler Contagens", str(exc))
        self._lbl_status.setText(f"❌ Erro ao ler as contagens: {exc}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    def _aplicar_local_das_contagens(self) -> str:
        """Marca o local de estoque da carga (Empresa.local do .db), que antes
        o usuário escolhia à mão. Devolve um aviso quando não dá para decidir
        sozinho."""
        locais = []
        for c in self._contagens:
            if c.local and c.local not in locais:
                locais.append(c.local)
        if not locais:
            return ""
        valor = self._valor_local(locais[0])
        botao = next((b for b in self._radio_local_group.buttons()
                      if sem_acento(str(b.property("local_value"))) == sem_acento(valor)), None)
        if botao is None:
            return (f"a carga foi gerada para o local \"{locais[0]}\", que não está entre as opções "
                    f"— confira o local de estoque")
        botao.setChecked(True)
        if len(locais) > 1:
            return (f"as contagens são de locais diferentes ({', '.join(locais)}); a comparação "
                    f"usa {locais[0]}")
        return ""

    @staticmethod
    def _dica_contagem(c: Contagem) -> str:
        linhas = [os.path.basename(c.arquivo)]
        if c.versao_app:
            linhas.append(f"Coletor versão {c.versao_app}")
        linhas += [f"⚠ {a}" for a in c.avisos]
        linhas.append("Duplo clique: mostrar só esta contagem na grade · botão direito: mais opções")
        return "\n".join(linhas)

    def _texto_item_contagem(self, c: Contagem, ativo: bool) -> str:
        marcador = "📌" if ativo else "✓"
        conferente = f"Conferente {c.codvendedor}" + (f" – {c.nome_vendedor}" if c.nome_vendedor else "")
        partes = [f"{marcador} {conferente}", f"exportada em {c.data_exportacao:%d/%m/%Y %H:%M}"]
        if c.local:
            partes.append(c.local)
        partes.append(f"{c.total_produtos_contados} produtos · {c.total_registros} registros")
        if c.avisos:
            partes.append("⚠ ver dica")
        return " · ".join(partes)

    def _atualizar_lbl_contagens_info(self):
        if not self._contagens:
            self._lbl_contagens_info.setText(
                f"Nenhuma contagem na análise (máximo {MAX_CONTAGENS_ANALISE}). Clique em "
                f"\"Selecionar contagens\" para escolher entre as baixadas na tela Download Contagens.")
            return
        texto = f"{len(self._contagens)} de {MAX_CONTAGENS_ANALISE} contagens na análise"
        if self._contagem_referencia is not None:
            c = self._contagem_referencia
            texto += f" · Mostrando apenas: Conferente {c.codvendedor}, {c.data_exportacao:%d/%m/%Y %H:%M}"
        self._lbl_contagens_info.setText(texto + ".")

    def _atualizar_marcadores_lista(self):
        """Redesenha o marcador (📌/✓) de cada item conforme a referência ativa."""
        for i in range(self._lista_contagens.count()):
            item = self._lista_contagens.item(i)
            c = item.data(Qt.ItemDataRole.UserRole)
            item.setText(self._texto_item_contagem(c, ativo=(c is self._contagem_referencia)))

    def _on_contagem_double_clicked(self, item: QListWidgetItem):
        """Define (ou desmarca, se já ativa) a contagem clicada como referência da grade."""
        c = item.data(Qt.ItemDataRole.UserRole)
        if c is None:
            return
        self._contagem_referencia = None if self._contagem_referencia is c else c
        self._atualizar_marcadores_lista()
        self._atualizar_lbl_contagens_info()
        self._rodar_comparacao()

    def _on_menu_lista(self, pos):
        item = self._lista_contagens.itemAt(pos)
        if item is None:
            return
        c = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        if self._contagem_referencia is c:
            acao_ref = menu.addAction("Mostrar todas as contagens na grade")
        else:
            acao_ref = menu.addAction("📌  Mostrar só esta contagem na grade")
        acao_remover = menu.addAction("✖  Remover da análise")
        escolha = menu.exec(self._lista_contagens.viewport().mapToGlobal(pos))
        if escolha is acao_ref:
            self._on_contagem_double_clicked(item)
        elif escolha is acao_remover:
            self._remover_contagem(item)

    def _remover_contagem(self, item: QListWidgetItem):
        """Tira uma contagem da análise — abre vaga para uma recontagem, por
        exemplo, sem precisar limpar tudo."""
        c = item.data(Qt.ItemDataRole.UserRole)
        if len(self._contagens) <= 1:
            self._on_limpar_clicked()
            return
        self._contagens = [x for x in self._contagens if x is not c]
        self._fora_export.discard(id(c))
        if self._contagem_referencia is c:
            self._contagem_referencia = None
        self._lista_contagens.takeItem(self._lista_contagens.row(item))
        self._atualizar_marcadores_lista()
        self._atualizar_lbl_contagens_info()
        self._rodar_comparacao()

    def _on_limpar_clicked(self):
        self._analise_geracao += 1  # descarta uma consulta ainda em andamento
        self._ia_geracao += 1  # e um pedido à IA também
        self._aprofundando = None
        self._parar_animacao_ia()
        self._parar_animacao_aprofundar()
        self._contagens = []
        self._contagem_referencia = None
        self._resultado = None
        self._acuracia = None
        self._contexto_resultado = None
        self._base_id = None
        self._fora_export = set()
        self._sistema_antes = {}
        self._data_antes = None
        self._ordem = None
        self._aviso_contagens = ""
        self._ia_base = None
        self._limpar_secoes_ia()
        self._lista_contagens.clear()
        self._table.setRowCount(0)
        self._table.setEnabled(True)
        self._table.horizontalHeader().setSortIndicatorShown(False)
        self._montar_cabecalho()
        self._ajustar_colunas()
        self._montar_opcoes_colunas()
        for combo in (self._cmb_situacao, self._cmb_grupo, self._cmb_local):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._txt_busca.blockSignals(True)
        self._txt_busca.clear()
        self._txt_busca.blockSignals(False)
        self._linha_filtros.setVisible(False)
        self._lbl_totais.setText("")
        self._atualizar_lbl_contagens_info()
        self._lbl_contexto_ia.setText("")
        self._popular_acuracia()
        self._popular_validade()
        self._abas.setCurrentIndex(0)
        self._spin_limite.setMaximum(0)
        self._atualizar_botoes_resultado()
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

        # Com referência ativa, roda a mesma análise só para aquela contagem —
        # não dá para filtrar o resultado agregado depois de pronto, porque
        # _agrupar_itens soma quantidades quando duas contagens têm o mesmo
        # (codigo, lote); uma linha do agregado pode não ter contrapartida
        # em nenhuma contagem isolada.
        contagens = [self._contagem_referencia] if self._contagem_referencia else self._contagens

        self._analise_geracao += 1
        contexto = {
            "geracao": self._analise_geracao,
            "data": data_referencia,
            "local": local_estoque,
            "codempresa": self._codempresa,
            "campo_custo": self._campo_custo,
            # Mesma grade (mesmas contagens) é o que permite comparar "antes x
            # depois" quando só a data ou o local de estoque mudou. A ordem é
            # a das colunas de contado.
            "ids": tuple(id(c) for c in contagens),
            "arquivos": [os.path.basename(c.arquivo) for c in contagens],
        }

        # Grade esmaecida e ações travadas enquanto o estoque é recalculado:
        # o que está na tela ainda é da data anterior.
        self._table.setEnabled(False)
        self._btn_analisar_ia.setEnabled(False)
        self._btn_exportar.setEnabled(False)
        self._btn_recontagem.setEnabled(False)
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

    def _analisar_em_background(self, contexto: dict, contagens: List[Contagem]):
        """Roda no worker. Devolve o contexto junto do resultado para o slot
        saber a qual pedido a resposta pertence."""
        try:
            resultado = self._service.analisar(
                contagens, contexto["data"], contexto["local"], contexto["codempresa"],
                contexto["campo_custo"],
            )
        except Exception as exc:
            exc.contexto_analise = contexto
            raise
        return contexto, resultado

    def _on_comparacao_pronta(self, payload):
        contexto, resultado = payload
        if contexto["geracao"] != self._analise_geracao:
            return  # data/local já mudou de novo antes desta resposta voltar

        # O campo de custo pode ter mudado enquanto a consulta rodava.
        if resultado.campo_custo != self._campo_custo:
            self._service.aplicar_custo(resultado, self._campo_custo)

        # Mesma grade (mesmas contagens) com outra data/local: guarda o
        # estoque do cálculo anterior para destacar o que mudou.
        contexto_anterior = self._contexto_resultado
        if (contexto_anterior is not None and self._resultado is not None
                and contexto_anterior["ids"] == contexto["ids"]):
            self._sistema_antes = {(i.codigo, i.lote): i.sistema for i in self._resultado.itens}
            self._data_antes = contexto_anterior["data"]
        else:
            self._sistema_antes = {}
            self._data_antes = None

        # Mantém a coluna base escolhida pelo usuário enquanto a contagem dela
        # estiver na grade; senão, a base é a primeira coluna de contado.
        ids = contexto["ids"]
        indice_base = ids.index(self._base_id) if self._base_id in ids else 0
        self._base_id = ids[indice_base] if ids else None
        if indice_base != resultado.indice_base:
            self._service.aplicar_base(resultado, indice_base)

        self._resultado = resultado
        self._contexto_resultado = contexto
        self._table.setEnabled(True)
        self._atualizar_grade()

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
        if self._aviso_contagens:
            texto += f" · ⚠ {self._aviso_contagens}"
            self._aviso_contagens = ""
        self._mostrar_status_ok(texto)

    def _on_base_escolhida(self, indice: int):
        """Troca da base da diferença no seletor. Recalcula na hora — o
        estoque do sistema não muda com a coluna, então não há consulta ao ERP."""
        resultado = self._resultado
        if resultado is None or not self._table.isEnabled():
            return
        if not (0 <= indice < len(resultado.colunas)) or indice == resultado.indice_base:
            return
        self._service.aplicar_base(resultado, indice)
        self._base_id = self._contexto_resultado["ids"][indice]
        self._atualizar_grade()
        self._mostrar_status_ok(
            f"✅ Diferença recalculada com base em {resultado.colunas[indice]} · "
            f"{self._texto_totais(incluir_base=False)}"
        )

    def _on_custo_escolhido(self, _indice: int):
        campo = self._cmb_custo.currentData()
        if not campo or campo == self._campo_custo:
            return
        self._campo_custo = campo
        AppConfig.set_analise_campo_custo(campo)
        if self._resultado is not None and self._table.isEnabled():
            self._service.aplicar_custo(self._resultado, campo)
            self._atualizar_grade()
            self._mostrar_status_ok(f"✅ Valores recalculados pelo {CAMPOS_CUSTO[campo].lower()}.")

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
        if r.total_sem_cadastro:
            partes.append(f"{r.total_sem_cadastro} sem cadastro")
        if r.total_nao_contado:
            partes.append(f"{r.total_nao_contado} não contado(s) em {r.colunas[r.indice_base]}")
        return " · ".join(partes)

    def _atualizar_grade(self):
        """Cabeçalho, linhas, ordem, filtros, larguras, totais, acurácia,
        validade e opções de coluna para o resultado atual (depois de um
        cálculo, de uma troca de base ou de custo)."""
        self._acuracia = self._service.calcular_acuracia(self._resultado)
        self._montar_cabecalho()
        self._popular_tabela()
        self._atualizar_opcoes_filtro()
        self._linha_filtros.setVisible(True)
        # Ordenar antes de filtrar: as linhas escondidas ficam marcadas pela
        # posição, e a ordenação troca as linhas de posição.
        self._ordenar()
        self._aplicar_filtros()
        self._ajustar_colunas()
        self._montar_opcoes_colunas()
        self._popular_acuracia()
        self._popular_validade()

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
        ocupado = self._ia_em_andamento or self._aprofundando is not None
        # Uma troca de data ou de base no meio da análise refaz a grade, mas
        # não pode liberar um segundo pedido à IA ao mesmo tempo.
        self._btn_analisar_ia.setEnabled(
            tem_divergencia and not ocupado and AIConfigService().is_configured()
        )
        self._btn_exportar.setEnabled(resultado is not None)
        self._btn_recontagem.setEnabled(resultado is not None and self._table.isEnabled())
        self._atualizar_cartoes()

    # ----- colunas -----

    def _col(self, chave: str) -> int:
        """Índice da coluna ``chave`` de ``_COLUNAS_FINAIS`` na grade atual."""
        n = len(self._resultado.colunas) if self._resultado else 1
        return _COL_CONTADO + n + _COLUNAS_FINAIS.index(chave)

    def _chave_coluna(self, col: int) -> Optional[tuple]:
        n = len(self._resultado.colunas) if self._resultado else 1
        if col < _COL_CONTADO:
            return (("produto", "descricao", "lote")[col],)
        if col < _COL_CONTADO + n:
            return ("contado", col - _COL_CONTADO)
        k = col - _COL_CONTADO - n
        return (_COLUNAS_FINAIS[k],) if k < len(_COLUNAS_FINAIS) else None

    def _coluna_da_chave(self, chave: tuple) -> Optional[int]:
        n = len(self._resultado.colunas) if self._resultado else 1
        if chave[0] in ("produto", "descricao", "lote"):
            return ("produto", "descricao", "lote").index(chave[0])
        if chave[0] == "contado":
            return _COL_CONTADO + chave[1] if chave[1] < n else None
        return self._col(chave[0])

    def _montar_cabecalho(self):
        """Colunas da grade: Produto, Descrição, Lote, um Contado por
        contagem, Sistema (com a data), Diferença, Custo, Valor, Situação,
        Entrada, Grupo, Localização e Observações. Sem resultado, uma coluna
        Contado genérica."""
        r = self._resultado
        colunas = r.colunas if r else ["Contado"]
        varias = len(colunas) > 1
        base = r.indice_base if r else 0
        data_ref = self._contexto_resultado["data"] if (r and self._contexto_resultado) else None
        nome_custo = CAMPOS_CUSTO.get(r.campo_custo if r else self._campo_custo, "Custo")

        n = len(colunas)
        rotulos = ["Produto", "Descrição", "Lote"]
        rotulos += [(_MARCA_BASE + c) if (varias and i == base) else c for i, c in enumerate(colunas)]
        rotulos += [(f"Sistema em {data_ref:%d/%m/%Y}" if data_ref else "Sistema") if chave == "sistema"
                    else _ROTULOS_FINAIS[chave] for chave in _COLUNAS_FINAIS]
        self._table.setColumnCount(len(rotulos))
        self._table.setHorizontalHeaderLabels(rotulos)

        def _cabecalho(chave):
            return self._table.horizontalHeaderItem(_COL_CONTADO + n + _COLUNAS_FINAIS.index(chave))

        esquerda = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        for col in (_COL_PRODUTO, _COL_DESCRICAO, _COL_LOTE):
            self._table.horizontalHeaderItem(col).setTextAlignment(esquerda)
        for chave in ("situacao", "entrada", "grupo", "localizacao", "observacoes"):
            _cabecalho(chave).setTextAlignment(esquerda)

        _cabecalho("custo").setToolTip(
            f"{nome_custo} do produto (produtosestoque, empresa logada). Troque no seletor \"Valor pelo\".")
        _cabecalho("valor").setToolTip(
            f"Diferença × {nome_custo.lower()}. Ordena pelo tamanho da divergência em R$, "
            f"seja falta ou sobra.")
        _cabecalho("entrada").setToolTip(
            "Quantidade que não foi bipada: digitada à mão, lançada sem GTIN ou corrigida "
            "(métricas do coletor). ⚠ = divergência com entrada manual.")
        if r and self._contexto_resultado:
            arquivos = self._contexto_resultado.get("arquivos", [])
            for i in range(len(colunas)):
                arquivo = arquivos[i] if i < len(arquivos) else ""
                if not varias:
                    dica = arquivo
                elif i == base:
                    dica = f"{arquivo}\nBase da diferença."
                else:
                    dica = f"{arquivo}\nPara usar como base, escolha no seletor acima da grade."
                self._table.horizontalHeaderItem(_COL_CONTADO + i).setToolTip(dica)
            _cabecalho("diferenca").setToolTip(f"{colunas[base]} − Sistema")

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

        self._cmb_base.blockSignals(True)
        self._cmb_base.clear()
        self._cmb_base.addItems(r.colunas)
        self._cmb_base.setCurrentIndex(r.indice_base)
        self._cmb_base.blockSignals(False)

        ids = self._contexto_resultado["ids"]
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
                chk.setChecked(ids[i] not in self._fora_export)
                chk.toggled.connect(self._on_check_export_alterado)
            self._layout_checks_export.addWidget(chk)
            self._checks_export.append(chk)
        self._linha_colunas.setVisible(True)

    def _on_check_export_alterado(self, _marcado: bool):
        ids = self._contexto_resultado["ids"]
        for chk in self._checks_export:
            if not chk.isEnabled():
                continue  # a base, sempre incluída
            contagem_id = ids[chk.property("indice_coluna")]
            if chk.isChecked():
                self._fora_export.discard(contagem_id)
            else:
                self._fora_export.add(contagem_id)

    def _colunas_export(self) -> List[int]:
        """Índices das colunas de contado que entram na exportação e na IA."""
        r = self._resultado
        ids = self._contexto_resultado["ids"]
        return [i for i in range(len(r.colunas))
                if i == r.indice_base or ids[i] not in self._fora_export]

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

    # ----- linhas -----

    def _popular_tabela(self):
        """Preenche as linhas do resultado atual, na ordem padrão (maior
        valor de divergência primeiro). Destaca a coluna de contado base
        (quando há mais de uma) e, depois de uma troca de data/local, as
        células de Sistema/Diferença cujo estoque mudou."""
        r = self._resultado
        n = len(r.colunas)
        col_base = _COL_CONTADO + r.indice_base
        todas = list(range(n))
        nome_custo = CAMPOS_CUSTO.get(r.campo_custo, "Custo")

        tema = get_active_theme()
        cor_mudou = QColor(tema.ACCENT)
        cor_mudou.setAlpha(70)
        cor_base = QColor(tema.ACCENT)
        cor_base.setAlpha(30)
        cor_alerta = QColor(tema.WARNING)
        cor_suave = QColor(tema.FG_SECONDARY)
        data_antes = f"{self._data_antes:%d/%m/%Y}" if self._data_antes else ""
        centro = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        menos_infinito = float("-inf")

        def _celula(texto, chave=None, alinhado=False, dica=""):
            cel = ItemOrdenavel(texto)
            cel.setData(CHAVE_ORDEM, chave if chave is not None else sem_acento(texto))
            if alinhado:
                cel.setTextAlignment(centro)
            if dica:
                cel.setToolTip(dica)
            return cel

        def _chave_num(valor):
            return menos_infinito if valor is None else valor

        ordem = sorted(range(len(r.itens)), key=lambda k: self._service.chave_valor(r.itens[k]), reverse=True)
        self._table.setRowCount(len(r.itens))
        for row, k in enumerate(ordem):
            item = r.itens[k]
            chave = (item.codigo, item.lote)
            mudou = chave in self._sistema_antes and self._sistema_antes[chave] != item.sistema

            cel_produto = _celula(item.codigo)
            cel_produto.setData(Qt.ItemDataRole.UserRole, k)  # linha -> índice em r.itens
            self._table.setItem(row, _COL_PRODUTO, cel_produto)
            self._table.setItem(row, _COL_DESCRICAO, _celula(item.descricao))
            self._table.setItem(row, _COL_LOTE, _celula(item.lote or "—", chave=sem_acento(item.lote)))

            for i, qtd in enumerate(item.contados):
                cel = _celula(_num(qtd), _chave_num(qtd), alinhado=True)
                if n > 1 and _COL_CONTADO + i == col_base:
                    cel.setBackground(cor_base)
                self._table.setItem(row, _COL_CONTADO + i, cel)

            for chave_col, valor, texto in (("sistema", item.sistema, _num(item.sistema)),
                                            ("diferenca", item.diferenca, _num(item.diferenca, sinal=True))):
                cel = _celula(texto, _chave_num(valor), alinhado=True)
                if mudou:
                    cel.setBackground(cor_mudou)
                    fonte = cel.font()
                    fonte.setBold(True)
                    cel.setFont(fonte)
                    cel.setToolTip(f"Estoque do sistema em {data_antes}: "
                                   f"{_num(self._sistema_antes[chave])}")
                self._table.setItem(row, self._col(chave_col), cel)

            self._table.setItem(row, self._col("custo"), _celula(
                _valor_curto(item.custo), _chave_num(item.custo), alinhado=True,
                dica="" if item.custo is not None else f"Produto sem {nome_custo.lower()} cadastrado"))
            dica_valor = ""
            if item.valor_diferenca is not None and item.diferenca:
                dica_valor = f"{_num(item.diferenca, sinal=True)} × {formatar_moeda(item.custo)} ({nome_custo.lower()})"
            self._table.setItem(row, self._col("valor"), _celula(
                _valor_curto(item.valor_diferenca, sinal=True),
                menos_infinito if item.valor_diferenca is None else abs(item.valor_diferenca),
                alinhado=True, dica=dica_valor))

            situacao_item = _celula(_SITUACAO_LABEL.get(item.situacao, item.situacao))
            situacao_item.setForeground(_cor_situacao(item.situacao))
            if item.situacao == "sem_cadastro":
                situacao_item.setToolTip("Código contado que não existe no cadastro de produtos do ERP")
            self._table.setItem(row, self._col("situacao"), situacao_item)

            entrada = self._service.texto_por_coluna(item.sinais, r.colunas, todas)
            cel_entrada = _celula(entrada)
            if entrada and item.situacao in ("falta", "sobra"):
                # Divergência com quantidade que não foi bipada: sinalizada.
                cel_entrada.setText(f"⚠ {entrada}")
                cel_entrada.setForeground(cor_alerta)
                fonte = cel_entrada.font()
                fonte.setBold(True)
                cel_entrada.setFont(fonte)
            elif entrada:
                cel_entrada.setForeground(cor_suave)
            self._table.setItem(row, self._col("entrada"), cel_entrada)

            self._table.setItem(row, self._col("grupo"), _celula(item.grupo))
            self._table.setItem(row, self._col("localizacao"), _celula(", ".join(item.localizacoes)))
            observacoes = self._service.texto_por_coluna(item.observacoes, r.colunas, todas)
            self._table.setItem(row, self._col("observacoes"), _celula(
                _encurtar(observacoes), chave=sem_acento(observacoes),
                dica=observacoes if len(observacoes) > _LIMITE_TEXTO_CELULA else ""))

    def _itens_das_linhas(self, linhas) -> List[ItemAnalise]:
        r = self._resultado
        return [r.itens[self._table.item(row, _COL_PRODUTO).data(Qt.ItemDataRole.UserRole)] for row in linhas]

    def _itens_visiveis(self) -> List[ItemAnalise]:
        """Registros visíveis, na ordem da grade — o que a exportação leva."""
        return self._itens_das_linhas(
            row for row in range(self._table.rowCount()) if not self._table.isRowHidden(row))

    def _itens_selecionados(self) -> List[ItemAnalise]:
        linhas = sorted({i.row() for i in self._table.selectionModel().selectedRows()})
        return self._itens_das_linhas(row for row in linhas if not self._table.isRowHidden(row))

    # ----- ordenação e filtros -----

    def _on_cabecalho_clicado(self, col: int):
        """Clique no cabeçalho: ordena pela coluna; um segundo clique inverte.
        Colunas numéricas começam do maior para o menor."""
        if self._resultado is None or not self._table.isEnabled():
            return
        chave = self._chave_coluna(col)
        if chave is None:
            return
        if self._ordem and self._ordem[0] == chave:
            ordem = (Qt.SortOrder.AscendingOrder if self._ordem[1] == Qt.SortOrder.DescendingOrder
                     else Qt.SortOrder.DescendingOrder)
        else:
            ordem = (Qt.SortOrder.DescendingOrder if chave[0] in _COLUNAS_NUMERICAS
                     else Qt.SortOrder.AscendingOrder)
        self._ordem = (chave, ordem)
        self._ordenar()
        self._aplicar_filtros()

    def _ordenar(self):
        header = self._table.horizontalHeader()
        col = self._coluna_da_chave(self._ordem[0]) if self._ordem else None
        if col is None:
            self._ordem = None
            header.setSortIndicatorShown(False)
            return
        self._table.sortItems(col, self._ordem[1])
        header.setSortIndicatorShown(True)
        header.setSortIndicator(col, self._ordem[1])

    def _atualizar_opcoes_filtro(self):
        """Grupos e localizações do resultado atual nos filtros, mantendo a
        escolha anterior quando ela ainda existe."""
        r = self._resultado
        grupos = sorted({i.grupo or _SEM_GRUPO for i in r.itens}, key=str.casefold)
        locais = sorted({loc for i in r.itens for loc in (i.localizacoes or [_SEM_LOCAL])}, key=str.casefold)
        for combo, valores, todos in ((self._cmb_grupo, grupos, "Todos os grupos"),
                                      (self._cmb_local, locais, "Todas as localizações")):
            atual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(todos, None)
            for valor in valores:
                combo.addItem(valor, valor)
            indice = combo.findData(atual) if atual is not None else 0
            combo.setCurrentIndex(indice if indice >= 0 else 0)
            combo.blockSignals(False)

    def _aplicar_filtros(self, *_args):
        r = self._resultado
        if r is None:
            return
        situacoes = self._cmb_situacao.currentData()
        grupo = self._cmb_grupo.currentData()
        local = self._cmb_local.currentData()
        busca = sem_acento(self._txt_busca.text().strip())
        visiveis = 0
        for row in range(self._table.rowCount()):
            item = r.itens[self._table.item(row, _COL_PRODUTO).data(Qt.ItemDataRole.UserRole)]
            mostra = ((situacoes is None or item.situacao in situacoes)
                      and (grupo is None or (item.grupo or _SEM_GRUPO) == grupo)
                      and (local is None or local in (item.localizacoes or [_SEM_LOCAL]))
                      and (not busca or busca in sem_acento(f"{item.codigo} {item.descricao}")))
            self._table.setRowHidden(row, not mostra)
            visiveis += 1 if mostra else 0
        self._visiveis = visiveis
        self._atualizar_totais()

    def _texto_filtro(self) -> str:
        """Filtro ativo, em texto ("Só divergências · grupo X"); vazio sem filtro."""
        partes = []
        if self._cmb_situacao.currentData() is not None:
            partes.append(self._cmb_situacao.currentText())
        if self._cmb_grupo.currentData() is not None:
            partes.append(f"grupo {self._cmb_grupo.currentText()}")
        if self._cmb_local.currentData() is not None:
            partes.append(f"localização {self._cmb_local.currentText()}")
        if self._txt_busca.text().strip():
            partes.append(f"busca \"{self._txt_busca.text().strip()}\"")
        return " · ".join(partes)

    def _atualizar_totais(self):
        r = self._resultado
        if r is None:
            self._lbl_totais.setText("")
            return
        tema = get_active_theme()
        nome_custo = CAMPOS_CUSTO.get(r.campo_custo, "custo").lower()
        partes = []
        if r.tem_valores:
            partes.append(f"Falta: <b style='color:{tema.ERROR};'>{formatar_moeda(r.valor_falta)}</b>")
            partes.append(f"Sobra: <b style='color:{tema.WARNING};'>{formatar_moeda(r.valor_sobra)}</b>")
            partes.append(f"Saldo líquido: <b style='color:{tema.FG_PRIMARY};'>"
                          f"{formatar_moeda(r.valor_liquido, sinal=True)}</b> ({nome_custo})")
            if r.divergencias_sem_custo:
                partes.append(f"{r.divergencias_sem_custo} divergência(s) sem custo, fora dos valores")
        else:
            partes.append(f"Sem valores em R$: nenhum produto da grade tem {nome_custo} cadastrado")
        if self._acuracia is not None:
            geral = self._acuracia.geral
            texto = f"Acurácia: <b style='color:{tema.FG_PRIMARY};'>{formatar_pct(geral.pct_registros)}</b> dos registros"
            if geral.pct_valor is not None:
                texto += f", <b style='color:{tema.FG_PRIMARY};'>{formatar_pct(geral.pct_valor)}</b> do valor"
            partes.append(texto)
        if self._visiveis < r.total_itens:
            partes.append(f"mostrando {self._visiveis} de {r.total_itens} registros")
        self._lbl_totais.setText(" &nbsp;·&nbsp; ".join(partes))

    # ------------------------------------------------------------------
    # Acurácia e validade
    # ------------------------------------------------------------------

    def _popular_acuracia(self):
        acc = self._acuracia
        for tabela in (self._tab_acc_grupo, self._tab_acc_local):
            tabela.setRowCount(0)
        if acc is None:
            self._lbl_acuracia.setText("A acurácia aparece depois que a grade é calculada.")
            return
        nome_custo = CAMPOS_CUSTO.get(self._resultado.campo_custo, "custo").lower()
        g = acc.geral
        texto = (f"Acurácia geral: <b>{formatar_pct(g.pct_registros)}</b> dos registros "
                 f"({g.conferem} de {g.registros} conferem)")
        if g.pct_valor is not None:
            texto += f" &nbsp;·&nbsp; <b>{formatar_pct(g.pct_valor)}</b> do valor ({nome_custo})"
            if g.sem_custo:
                texto += f" &nbsp;·&nbsp; {g.sem_custo} registro(s) sem custo fora do cálculo em valor"
        else:
            texto += f" &nbsp;·&nbsp; sem acurácia em valor: nenhum registro comparado tem {nome_custo}"
        if g.registros:
            texto += (f" &nbsp;·&nbsp; <a href='geral' style='color:{get_active_theme().ACCENT};'>"
                      f"ver a conta</a>")
        self._lbl_acuracia.setText(texto)

        centro = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        for tabela, linhas in ((self._tab_acc_grupo, acc.por_grupo), (self._tab_acc_local, acc.por_localizacao)):
            tabela.setRowCount(len(linhas))
            for row, linha in enumerate(linhas):
                valores = [linha.nome, str(linha.registros), str(linha.conferem),
                           formatar_pct(linha.pct_registros),
                           _valor_curto(linha.valor_total) if linha.valor_total else "—",
                           _valor_curto(linha.valor_confere) if linha.valor_total else "—",
                           formatar_pct(linha.pct_valor)]
                for col, texto_celula in enumerate(valores):
                    cel = QTableWidgetItem(texto_celula)
                    if col:
                        cel.setTextAlignment(centro)
                        cel.setToolTip("Duplo clique: ver a conta registro a registro")
                    else:
                        cel.setToolTip(f"{linha.nome}\nDuplo clique: ver a conta registro a registro")
                    tabela.setItem(row, col, cel)

    def _on_acc_grupo_duplo_clique(self, row: int, _col: int):
        if self._acuracia and 0 <= row < len(self._acuracia.por_grupo):
            linha = self._acuracia.por_grupo[row]
            self._mostrar_conta_acuracia(linha, f"Grupo {linha.nome}")

    def _on_acc_local_duplo_clique(self, row: int, _col: int):
        if self._acuracia and 0 <= row < len(self._acuracia.por_localizacao):
            linha = self._acuracia.por_localizacao[row]
            self._mostrar_conta_acuracia(
                linha, f"Localização {linha.nome}",
                "Um registro contado em duas localizações entra nas duas.")

    def _on_link_acuracia(self, _link: str):
        if self._acuracia:
            self._mostrar_conta_acuracia(self._acuracia.geral, "Geral (todos os registros comparados)")

    def _mostrar_conta_acuracia(self, linha, titulo: str, observacao: str = ""):
        """Abre a conta de uma linha da acurácia registro a registro: o valor
        de cada um (custo × quantidade) e as somas que viram as colunas."""
        r = self._resultado
        if r is None:
            return
        nome_custo = CAMPOS_CUSTO.get(r.campo_custo, "Custo")
        base = r.colunas[r.indice_base] if r.colunas else "Contado"
        colunas = ["Produto", "Descrição", "Lote", "Situação", base, "Sistema",
                   f"{nome_custo} (R$)", "Quantidade usada", "Valor do registro (R$)"]

        def _ordem(item):
            # Primeiro os que conferem (são eles que somam no "Valor dos que
            # conferem"), depois os demais; sem custo no fim de cada bloco.
            valor = self._service.valor_acuracia(item)
            return (item.situacao != "confere", valor is None, -(valor or 0.0), item.codigo, item.lote)

        linhas = []
        for item in sorted(linha.itens, key=_ordem):
            valor = self._service.valor_acuracia(item)
            if valor is None:
                texto_qtd, texto_valor = "—", "sem custo"
            else:
                qtd, origem = self._service.quantidade_valor(item)
                texto_qtd = _num(qtd)
                if origem:
                    sem_sinal = origem == "sistema" and (item.sistema or 0) < 0
                    texto_qtd += f" ({origem}{', sem sinal' if sem_sinal else ''})"
                texto_valor = _valor_curto(valor)
            linhas.append({
                "celulas": [item.codigo, item.descricao, item.lote or "—",
                            _SITUACAO_LABEL.get(item.situacao, item.situacao),
                            _num(item.contado), _num(item.sistema), _valor_curto(item.custo),
                            texto_qtd, texto_valor],
                "cor_situacao": _cor_situacao(item.situacao),
                "confere": item.situacao == "confere",
                "sem_custo": valor is None,
            })

        explicacao = (
            f"Valor de cada registro = {nome_custo.lower()} × quantidade. Quando o contado ({base}) e "
            f"o sistema são diferentes, vale a maior das duas quantidades. Entram só os registros "
            f"comparados com o sistema: conferem, falta e sobra."
            + (f" {observacao}" if observacao else "")
        )
        partes = [f"<b>% registros</b> = Conferem ÷ Registros = {linha.conferem} ÷ {linha.registros}"
                  f" = <b>{formatar_pct(linha.pct_registros)}</b>"]
        if linha.valor_total:
            partes += [
                f"<b>Valor dos que conferem</b> = soma da última coluna nas linhas que conferem "
                f"= <b>{formatar_moeda(linha.valor_confere)}</b>",
                f"<b>Valor dos registros</b> = soma da última coluna em todas as linhas com custo "
                f"= <b>{formatar_moeda(linha.valor_total)}</b>",
                f"<b>% valor</b> = Valor dos que conferem ÷ Valor dos registros = "
                f"{_valor_curto(linha.valor_confere)} ÷ {_valor_curto(linha.valor_total)} "
                f"= <b>{formatar_pct(linha.pct_valor)}</b>",
            ]
            if linha.sem_custo:
                partes.append(f"{linha.sem_custo} registro(s) sem {nome_custo.lower()} cadastrado "
                              f"ficaram fora das somas em valor; eles contam só em % registros.")
        else:
            partes.append(f"<b>% valor</b>: sem valor, porque nenhum destes registros tem "
                          f"{nome_custo.lower()} cadastrado.")
        ContaAcuraciaDialog(titulo, explicacao, colunas, linhas, (4, 5, 6, 7, 8),
                            "<br>".join(partes), self).exec()

    def _itens_validade(self) -> List[tuple]:
        """(registro, dias até vencer) dos lotes vencidos até a data de
        referência ou que vencem no prazo da aba, do que vence antes."""
        r = self._resultado
        if r is None:
            return []
        referencia = self._data_do_resultado()
        limite = referencia + timedelta(days=self._spin_validade.value())
        lista = [(i, (i.validade - referencia).days) for i in r.itens if i.validade and i.validade <= limite]
        lista.sort(key=lambda t: (t[0].validade, t[0].codigo, t[0].lote))
        return lista

    @staticmethod
    def _texto_prazo(dias: int) -> str:
        if dias < 0:
            return f"vencido há {-dias} dia(s)"
        if dias == 0:
            return "vence na data de referência"
        return f"vence em {dias} dia(s)"

    def _popular_validade(self):
        tabela = self._tab_validade
        referencia = self._data_do_resultado()
        self._lbl_validade_ref.setText(
            f"Lotes vencidos até {referencia:%d/%m/%Y} (data de referência) ou que vencem em até")
        lista = self._itens_validade()
        tabela.setRowCount(len(lista))
        tema = get_active_theme()
        centro = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        for row, (item, dias) in enumerate(lista):
            contado = item.contado if item.contado is not None else next(
                (q for q in item.contados if q is not None), None)
            valores = [item.codigo, item.descricao, item.lote or "—", f"{item.validade:%d/%m/%Y}",
                       self._texto_prazo(dias), _num(contado), ", ".join(item.localizacoes)]
            for col, texto in enumerate(valores):
                cel = QTableWidgetItem(texto)
                if col in (3, 5):
                    cel.setTextAlignment(centro)
                if col == 4:
                    cel.setForeground(QColor(tema.ERROR if dias < 0 else tema.WARNING))
                tabela.setItem(row, col, cel)
        self._abas.setTabText(self._indice_aba_validade,
                              f"⏳  Validade ({len(lista)})" if lista else "⏳  Validade")
        if self._resultado is None:
            self._lbl_validade_vazio.setText("A lista aparece depois que a grade é calculada.")
        elif not lista:
            com_validade = sum(1 for i in self._resultado.itens if i.validade)
            self._lbl_validade_vazio.setText(
                "Nenhum lote vencido ou vencendo no prazo." if com_validade
                else "Nenhum registro da contagem tem validade informada.")
        else:
            vencidos = sum(1 for _i, d in lista if d < 0)
            self._lbl_validade_vazio.setText(
                f"{vencidos} lote(s) vencido(s) e {len(lista) - vencidos} vencendo no prazo.")

    def _on_validade_dias_alterado(self, dias: int):
        AppConfig.set_analise_validade_dias(dias)
        self._popular_validade()

    # ------------------------------------------------------------------
    # Recontagem
    # ------------------------------------------------------------------

    def _on_recontagem_clicked(self):
        """Leva para Exportar Carga só os produtos das linhas selecionadas
        (sem seleção: as divergências visíveis). A recontagem volta como uma
        contagem nova e entra como mais uma coluna na análise."""
        if self._resultado is None:
            return
        selecionados = self._itens_selecionados()
        if selecionados:
            candidatos = selecionados
            origem = "selecionados na grade"
        else:
            candidatos = [i for i in self._itens_visiveis() if i.situacao in ("falta", "sobra")]
            origem = "com divergência visíveis na grade"
        sem_cadastro = {i.codigo for i in candidatos if i.sem_cadastro}
        produtos = {}
        for i in candidatos:
            if not i.sem_cadastro:
                produtos.setdefault(i.codigo, i.descricao)
        if not produtos:
            QMessageBox.information(
                self, "Gerar recontagem",
                "Nenhum produto para recontar. Selecione linhas na grade ou deixe divergências "
                "visíveis (produtos sem cadastro no ERP não entram numa carga)."
            )
            return

        local = self._get_local_estoque_value()
        lista = "\n".join(f"  • {cod} – {desc}" for cod, desc in list(produtos.items())[:15])
        if len(produtos) > 15:
            lista += f"\n  … e mais {len(produtos) - 15}"
        detalhe = (f"\n\n{len(sem_cadastro)} produto(s) sem cadastro no ERP ficaram de fora."
                   if sem_cadastro else "")
        pergunta = QMessageBox(self)
        pergunta.setWindowTitle("Gerar recontagem")
        pergunta.setIcon(QMessageBox.Icon.Question)
        pergunta.setText(f"Gerar uma carga de recontagem com {len(produtos)} produto(s) {origem}?")
        pergunta.setInformativeText(
            f"Local de estoque: {self._nome_local(local)}.\n\n{lista}{detalhe}\n\n"
            "Na tela Exportar Carga, escolha o conferente e o dispositivo. Quando a recontagem "
            "voltar, selecione-a aqui como mais uma contagem da análise."
        )
        btn_sim = pergunta.addButton("Ir para Exportar Carga", QMessageBox.ButtonRole.YesRole)
        pergunta.addButton("Cancelar", QMessageBox.ButtonRole.NoRole)
        pergunta.setDefaultButton(btn_sim)
        pergunta.exec()
        if pergunta.clickedButton() is btn_sim:
            self.recontagem_solicitada.emit(list(produtos), local)

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

        colunas = self._colunas_export()
        payload = self._service.montar_payload_ia(
            self._resultado, self._nome_empresa,
            self._data_do_resultado(),
            limite=self._spin_limite.value(),
            colunas=colunas,
        )

        r = self._resultado
        partes = [f"estoque de {self._data_do_resultado():%d/%m/%Y}"]
        if len(r.colunas) > 1:
            partes.append(f"base da diferença: {r.colunas[r.indice_base]}")
            partes.append("contagens: " + ", ".join(r.colunas[i] for i in colunas))
        if r.tem_valores:
            partes.append(f"valores pelo {CAMPOS_CUSTO.get(r.campo_custo, '').lower()}")
        partes.append(f"{self._spin_limite.value()} de {r.total_falta + r.total_sobra} "
                      f"divergências enviadas")
        self._contexto_ia_pendente = " · ".join(partes)
        self._ia_pendente = {"payload": payload, "colunas": colunas}

        self._btn_analisar_ia.setEnabled(False)
        self._lbl_status.setText("🔄 Analisando com IA...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
        self._iniciar_animacao_ia(self._spin_limite.value())

        self._ia_geracao += 1
        signals = WorkerSignals()
        # Métodos da página, nunca lambda (ver `_rodar_comparacao`).
        signals.finished.connect(self._on_ia_finished)
        signals.error.connect(self._on_ia_error)
        runnable = TaskRunnable(
            self._analisar_ia_em_background, args=(self._ia_geracao, _SYSTEM_ANALISE, payload),
            signals=signals,
        )
        QThreadPool.globalInstance().start(runnable)

    def _analisar_ia_em_background(self, geracao: int, system: str, payload: str):
        """Roda no worker. Devolve a geração junto do texto para o slot saber
        se a resposta ainda vale (o usuário pode ter limpado a tela)."""
        try:
            texto = AIClient().analisar(system, payload)
        except Exception as exc:
            exc.geracao_ia = geracao
            raise
        return geracao, texto

    def _on_ia_finished(self, payload):
        geracao, texto = payload
        if geracao != self._ia_geracao:
            return  # a tela foi limpa enquanto a IA analisava
        self._parar_animacao_ia()
        # Análise nova: os aprofundamentos da anterior não valem mais.
        self._ia_base = dict(self._ia_pendente or {}, texto=texto)
        self._limpar_secoes_ia()
        self._adicionar_secao({"acao": "analise", "titulo": "Análise da IA", "detalhe": "",
                               "texto": texto, "codigo": None})
        self._mostrar_texto_ia_com_fade()
        self._lbl_contexto_ia.setText(
            f"Análise gerada às {datetime.now():%H:%M} · {self._contexto_ia_pendente}"
        )
        self._abas.setCurrentIndex(self._indice_aba_ia)
        self._atualizar_botoes_resultado()
        self._lbl_status.setText("✅ Análise concluída — veja a aba \"Análise da IA\".")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))

    def _on_ia_error(self, exc: Exception):
        if getattr(exc, "geracao_ia", self._ia_geracao) != self._ia_geracao:
            return  # erro de uma análise que o usuário abandonou limpando a tela
        self._parar_animacao_ia()
        # O texto da análise anterior (se houver) volta, com o contexto dele.
        self._lbl_contexto_ia.setText(self._contexto_ia_anterior)
        self._atualizar_botoes_resultado()
        mensagem = str(exc) if isinstance(exc, AIClientError) else f"Erro inesperado: {exc}"
        QMessageBox.critical(self, "Erro na Análise", mensagem)
        self._lbl_status.setText(f"❌ {mensagem}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    # ------------------------------------------------------------------
    # Seções da aba da IA e aprofundamentos
    # ------------------------------------------------------------------

    def _limpar_secoes_ia(self):
        for widget in self._widgets_secoes:
            self._layout_secoes.removeWidget(widget)
            widget.deleteLater()
        self._widgets_secoes = []
        self._secoes_ia = []
        self._acoes_feitas = set()
        self._produtos_explicados = set()
        self._atualizar_cartoes()

    def _adicionar_secao(self, secao: dict) -> QWidget:
        principal = not self._secoes_ia
        secao["hora"] = datetime.now()
        if not principal:
            secao["detalhe"] = f"gerado às {secao['hora']:%H:%M}"
        icone = _APROFUNDAMENTOS.get(secao["acao"], ("",))[0]
        titulo_tela = "" if principal else f"{icone}  {secao['titulo']}".strip()
        widget = criar_secao_ia(titulo_tela, secao["detalhe"], secao["texto"])
        self._layout_secoes.addWidget(widget)
        self._secoes_ia.append(secao)
        self._widgets_secoes.append(widget)
        if secao["codigo"]:
            self._produtos_explicados.add(secao["codigo"])
        elif not principal:
            self._acoes_feitas.add(secao["acao"])
        self._atualizar_cartoes()
        return widget

    def _atualizar_cartoes(self):
        """Mostra os cartões depois da análise e acerta o estado de cada um."""
        tem_analise = bool(self._secoes_ia)
        self._bloco_cartoes.setVisible(tem_analise)
        self._lbl_vazio_ia.setVisible(not tem_analise)
        if not tem_analise:
            return
        rodando = self._aprofundando["acao"] if self._aprofundando else None
        ocupado = self._ia_em_andamento or rodando is not None
        colunas = (self._ia_base or {}).get("colunas") or []
        for acao, cartao in self._cartoes.items():
            if acao == "conferentes":
                # Só faz sentido com duas contagens ou mais na análise enviada.
                cartao.setVisible(len(colunas) >= 2)
            cartao.setEnabled(not ocupado or acao == rodando)
            if acao == rodando:
                cartao.set_estado("rodando", "Gerando…")
            elif acao == "produto" and self._produtos_explicados:
                n = len(self._produtos_explicados)
                cartao.set_estado("feito", f"✓ {n} explicado(s) · escolher outro")
            elif acao in self._acoes_feitas:
                cartao.set_estado("feito", "✓ Adicionado acima · clique para ver")
            else:
                cartao.set_estado("normal")

    def _rolar_para(self, widget: QWidget):
        try:
            self._scroll_ia.verticalScrollBar().setValue(max(0, widget.y() - 6))
        except RuntimeError:
            pass  # a seção foi apagada (Limpar) antes da rolagem agendada

    def _rolar_para_secao(self, acao: str = "", codigo: str = ""):
        for secao, widget in zip(self._secoes_ia, self._widgets_secoes):
            if (codigo and secao["codigo"] == codigo) or (not codigo and secao["acao"] == acao):
                self._abas.setCurrentIndex(self._indice_aba_ia)
                self._rolar_para(widget)
                return

    def _on_cartao_clicado(self, acao: str):
        if not self._secoes_ia or self._ia_em_andamento or self._aprofundando:
            return
        base = self._ia_base or {}
        colunas = base.get("colunas")
        codigo = None
        extra = ""
        if acao == "produto":
            codigo = self._produto_para_explicar()
            if not codigo:
                return
            descricao = next((i.descricao for i in self._resultado.itens if i.codigo == codigo), "")
            titulo = f"Explicação: {codigo} · {descricao}"
            pedido = _PEDIDOS_APROFUNDAR["produto"].format(codigo=codigo, descricao=descricao)
            extra = self._service.montar_payload_produto(
                self._resultado, codigo, self._data_do_resultado(), colunas)
        else:
            if acao in self._acoes_feitas:
                self._rolar_para_secao(acao)
                return
            titulo = _APROFUNDAMENTOS[acao][1]
            pedido = _PEDIDOS_APROFUNDAR[acao]
            if acao == "conferentes":
                extra = self._service.montar_payload_discordancias(self._resultado, colunas)
        self._iniciar_aprofundamento(acao, titulo, pedido, extra, codigo)

    def _produto_para_explicar(self) -> Optional[str]:
        """Produto da linha selecionada na grade; sem seleção (ou com uma
        linha que confere), a lista das divergências para escolher. O mesmo
        produto não é explicado duas vezes."""
        r = self._resultado
        if r is None:
            return None
        selecionados = self._itens_selecionados()
        codigos = {i.codigo for i in selecionados if i.situacao != "confere"}
        if len(codigos) == 1:
            codigo = codigos.pop()
            if codigo in self._produtos_explicados:
                self._rolar_para_secao(codigo=codigo)
                self._lbl_status.setText(
                    f"ℹ️ O produto {codigo} já foi explicado nesta análise — a explicação está na aba.")
                self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))
                return None
            return codigo

        produtos = {}
        for i in r.itens:
            if i.situacao == "confere":
                continue
            p = produtos.setdefault(i.codigo, {
                "codigo": i.codigo, "descricao": i.descricao, "registros": 0, "dif": 0.0,
                "tem_dif": False, "valor": 0.0, "tem_valor": False, "situacoes": [],
                "explicado": i.codigo in self._produtos_explicados,
            })
            p["registros"] += 1
            if i.diferenca is not None:
                p["dif"] += i.diferenca
                p["tem_dif"] = True
            if i.valor_diferenca is not None:
                p["valor"] += i.valor_diferenca
                p["tem_valor"] = True
            rotulo = _SITUACAO_LABEL.get(i.situacao, i.situacao)
            if rotulo not in p["situacoes"]:
                p["situacoes"].append(rotulo)
        if not produtos:
            QMessageBox.information(self, "Explicar um produto", "Não há divergência para explicar nesta grade.")
            return None
        if all(p["explicado"] for p in produtos.values()):
            QMessageBox.information(self, "Explicar um produto",
                                    "Todos os produtos com divergência já foram explicados nesta análise.")
            return None
        lista = sorted(produtos.values(), key=lambda p: (abs(p["valor"]), abs(p["dif"])), reverse=True)
        linhas = [{
            "codigo": p["codigo"], "descricao": p["descricao"], "registros": p["registros"],
            "diferenca": _num(p["dif"], sinal=True) if p["tem_dif"] else "—",
            "valor": _valor_curto(p["valor"], sinal=True) if p["tem_valor"] else "—",
            "situacao": ", ".join(p["situacoes"]), "explicado": p["explicado"],
        } for p in lista]
        if selecionados and not codigos:
            aviso = "A linha selecionada na grade confere com o sistema. Escolha um produto com divergência:"
        elif len(codigos) > 1:
            aviso = "Há linhas de mais de um produto selecionadas na grade. Escolha qual explicar:"
        else:
            aviso = "Nenhuma linha selecionada na grade. Escolha um produto com divergência:"
        dialogo = EscolherProdutoDialog(linhas, aviso, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialogo.codigo_escolhido

    def _iniciar_aprofundamento(self, acao: str, titulo: str, pedido: str, extra: str,
                                codigo: Optional[str]):
        base = self._ia_base or {}
        prompt = "\n\n".join(parte for parte in (
            base.get("payload", ""),
            "# Análise já entregue\n" + base.get("texto", ""),
            extra,
            "# Pedido\n" + pedido,
        ) if parte)
        self._aprofundando = {"acao": acao, "titulo": titulo, "codigo": codigo}
        self._iniciar_animacao_aprofundar()
        self._atualizar_botoes_resultado()
        self._lbl_status.setText(f"🔄 Aprofundando com a IA: {titulo}...")
        self._lbl_status.setStyleSheet(themed_qss("color: {{FG_SECONDARY}}; font-size: 9pt;"))

        self._ia_geracao += 1
        signals = WorkerSignals()
        signals.finished.connect(self._on_aprofundar_pronto)
        signals.error.connect(self._on_aprofundar_erro)
        runnable = TaskRunnable(
            self._analisar_ia_em_background, args=(self._ia_geracao, _SYSTEM_APROFUNDAR, prompt),
            signals=signals,
        )
        QThreadPool.globalInstance().start(runnable)

    def _on_aprofundar_pronto(self, payload):
        geracao, texto = payload
        if geracao != self._ia_geracao or self._aprofundando is None:
            return  # a tela foi limpa enquanto a IA respondia
        info = self._aprofundando
        self._aprofundando = None
        self._parar_animacao_aprofundar()
        widget = self._adicionar_secao({"acao": info["acao"], "titulo": info["titulo"], "detalhe": "",
                                        "texto": texto, "codigo": info["codigo"]})
        self._atualizar_botoes_resultado()
        # A seção nova só tem posição depois que o layout se ajusta.
        QTimer.singleShot(60, lambda w=widget: self._rolar_para(w))
        self._lbl_status.setText(f"✅ Seção \"{info['titulo']}\" acrescentada à análise e ao PDF dela.")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))

    def _on_aprofundar_erro(self, exc: Exception):
        if getattr(exc, "geracao_ia", self._ia_geracao) != self._ia_geracao:
            return
        self._aprofundando = None
        self._parar_animacao_aprofundar()
        self._atualizar_botoes_resultado()
        mensagem = str(exc) if isinstance(exc, AIClientError) else f"Erro inesperado: {exc}"
        QMessageBox.critical(self, "Erro ao Aprofundar", mensagem)
        self._lbl_status.setText(f"❌ {mensagem}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{ERROR}}; font-size: 9pt;"))

    # ------------------------------------------------------------------
    # Animação da IA ("linha de leitura")
    # ------------------------------------------------------------------

    def _iniciar_animacao_ia(self, qtd_divergencias: int):
        """Leva a tela para a aba da IA e põe a animação no lugar do texto."""
        self._ia_em_andamento = True
        self._atualizar_cartoes()
        palavra = "divergência" if qtd_divergencias == 1 else "divergências"
        self._animacao_ia.lbl_mensagem.setText(f"Analisando {qtd_divergencias} {palavra} com a IA")
        self._descricao_modelo_ia = self._texto_modelo_ia()
        self._segundos_ia = -1
        # O contexto na linha de cima é da análise anterior: some enquanto a
        # nova roda, para não parecer que descreve o que está sendo analisado.
        self._contexto_ia_anterior = self._lbl_contexto_ia.text()
        self._lbl_contexto_ia.setText("")
        self._pilha_ia.setCurrentWidget(self._animacao_ia)
        self._abas.setCurrentIndex(self._indice_aba_ia)
        self._ligar_relogio_ia()

    def _parar_animacao_ia(self):
        """Volta a aba da IA para o texto e tira o indicador da aba."""
        self._ia_em_andamento = False
        self._pilha_ia.setCurrentWidget(self._scroll_ia)
        self._desligar_relogio_ia()

    def _iniciar_animacao_aprofundar(self):
        """Mostra a linha de leitura no lugar da próxima seção, acima dos cartões."""
        self._descricao_modelo_ia = self._texto_modelo_ia()
        self._segundos_ia = -1
        self._placeholder_ia.show()
        self._abas.setCurrentIndex(self._indice_aba_ia)
        self._ligar_relogio_ia()
        QTimer.singleShot(60, lambda: self._rolar_para(self._placeholder_ia))

    def _parar_animacao_aprofundar(self):
        self._placeholder_ia.hide()
        self._desligar_relogio_ia()

    def _ligar_relogio_ia(self):
        self._abas.tabBar().setTabButton(
            self._indice_aba_ia, QTabBar.ButtonPosition.RightSide, self._giro_aba_ia
        )
        self._relogio_ia.start()
        self._animar_ia()  # primeiro quadro já com "0:00"
        self._timer_ia.start()

    def _desligar_relogio_ia(self):
        if self._ia_em_andamento or self._aprofundando:
            return
        self._timer_ia.stop()
        self._abas.tabBar().setTabButton(self._indice_aba_ia, QTabBar.ButtonPosition.RightSide, None)

    def _animar_ia(self):
        """Um quadro: move a linha de leitura, gira o indicador da aba e, a
        cada segundo, atualiza o tempo decorrido."""
        ms = self._relogio_ia.elapsed()
        ida = (ms % 5200) / 2600  # a linha vai e volta a cada 2,6 s
        if ida > 1:
            ida = 2 - ida
        fase = self._curva_ia.valueForProgress(ida)
        if self._ia_em_andamento:
            self._animacao_ia.folha.set_fase(fase)
        else:
            self._folha_aprofundar.set_fase(fase)
        self._giro_aba_ia.set_angulo((ms % 800) / 800 * 360)
        segundos = ms // 1000
        if segundos != self._segundos_ia:
            self._segundos_ia = segundos
            tempo = f"tempo decorrido {segundos // 60}:{segundos % 60:02d}"
            if self._ia_em_andamento:
                self._animacao_ia.lbl_info.setText(f"{self._descricao_modelo_ia} · {tempo}")
            elif self._aprofundando:
                cor = get_active_theme().FG_SECONDARY
                self._lbl_aprofundando.setText(
                    f"Gerando “{html_lib.escape(self._aprofundando['titulo'])}” com a IA<br>"
                    f"<span style='color:{cor}; font-size:9pt;'>"
                    f"{html_lib.escape(self._descricao_modelo_ia)} · {tempo}</span>"
                )

    def _texto_modelo_ia(self) -> str:
        """Provedor e modelo configurados, como o usuário os vê nas
        Configurações (ex.: "Anthropic · Claude Sonnet 5")."""
        config = AIConfigService()
        provedor = config.get_provider()
        modelo = config.get_model(provedor)
        nome_modelo = next(
            (m.nome for m in config.list_models(provedor) if m.id == modelo), modelo
        )
        return f"{NOMES_PROVEDOR.get(provedor, provedor)} · {nome_modelo}"

    def _mostrar_texto_ia_com_fade(self):
        """O texto novo entra num fade curto no lugar da animação."""
        efeito = QGraphicsOpacityEffect(self._scroll_ia)
        efeito.setOpacity(0.0)
        self._scroll_ia.setGraphicsEffect(efeito)
        fade = QPropertyAnimation(efeito, b"opacity", self)
        fade.setDuration(250)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.finished.connect(self._remover_fade_texto_ia)
        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _remover_fade_texto_ia(self):
        # Sem o efeito depois do fade: enquanto aplicado, ele deixa o desenho
        # do texto (e a rolagem) mais lento.
        self._scroll_ia.setGraphicsEffect(None)

    # ------------------------------------------------------------------
    # Exportar
    # ------------------------------------------------------------------

    def _on_exportar_clicked(self):
        if not self._resultado:
            return
        filtrada = "  · só o que está visível" if self._texto_filtro() else ""
        menu = QMenu(self)
        acao_comparativo = menu.addAction(f"📊  Resultado comparativo (PDF){filtrada}")
        acao_ia = menu.addAction("🤖  Análise da IA (PDF)")
        acao_ambos = menu.addAction("📊+🤖  Os dois juntos (PDF)")
        menu.addSeparator()
        acao_validade = menu.addAction("⏳  Validade dos lotes (PDF)")
        menu.addSeparator()
        acao_excel = menu.addAction(f"📗  Grade em Excel (.xlsx){filtrada}")
        if not self._secoes_ia:
            acao_ia.setEnabled(False)
            acao_ambos.setEnabled(False)
        if not self._itens_validade():
            acao_validade.setEnabled(False)

        escolha = menu.exec(QCursor.pos())
        if escolha is None:
            return
        if escolha is acao_comparativo:
            self._exportar("comparativo", [self._secao_comparativo()], com_filtro=True)
        elif escolha is acao_ia:
            self._exportar("analise_ia", [self._secao_analise_ia()])
        elif escolha is acao_ambos:
            self._exportar("completo", [self._secao_comparativo(), self._secao_analise_ia()], com_filtro=True)
        elif escolha is acao_validade:
            self._exportar("validade", [self._secao_validade()])
        elif escolha is acao_excel:
            self._exportar_excel()

    def _sugestao_nome(self, sufixo: str, extensao: str = "pdf") -> str:
        data_str = f"{self._data_do_resultado():%d%m%Y}"
        return f"analise_estoque_{self._codempresa}_{data_str}_{sufixo}.{extensao}"

    def _pasta_exportados(self) -> Optional[str]:
        try:
            return AppConfig.get_exportados_path()
        except OSError as exc:
            QMessageBox.critical(
                self, "Erro ao Exportar",
                f"Não foi possível criar a pasta de exportação:\n{exc}")
            return None

    def _exportar(self, sufixo: str, secoes: list, com_filtro: bool = False):
        """Grava o PDF direto em <pasta do app>/Exportados (criada se não
        existir) e oferece abrir a pasta ao final."""
        pasta = self._pasta_exportados()
        if not pasta:
            return
        caminho = _caminho_livre(os.path.join(pasta, self._sugestao_nome(sufixo)))
        if not self._salvar_pdf(secoes, caminho, com_filtro):
            return
        self._perguntar_abrir_pasta(caminho, pasta)

    def _perguntar_abrir_pasta(self, caminho: str, pasta: str):
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

    def _exportar_excel(self):
        """A grade como está na tela (filtro e ordem) numa planilha Excel,
        com todas as colunas e os números como números."""
        pasta = self._pasta_exportados()
        if not pasta:
            return
        caminho = _caminho_livre(os.path.join(pasta, self._sugestao_nome("grade", "xlsx")))
        r = self._resultado
        indices = self._colunas_export()
        varias = len(r.colunas) > 1
        nome_custo = CAMPOS_CUSTO.get(r.campo_custo, "Custo")

        cabecalho = ["Produto", "Descrição", "Lote"]
        cabecalho += [r.colunas[i] + (" (base)" if varias and i == r.indice_base else "") for i in indices]
        # Mesma ordem da grade, com a validade junto das colunas de detalhe.
        cabecalho += [f"Sistema em {self._data_do_resultado():%d/%m/%Y}", "Diferença",
                      "Valor da diferença (R$)", "Situação", "Entrada", f"{nome_custo} (R$)",
                      "Grupo", "Localização", "Validade", "Observações"]
        formatos = [TEXTO] * 3 + [NUMERO] * len(indices)
        formatos += [NUMERO, NUMERO, MOEDA, TEXTO, TEXTO, MOEDA, TEXTO, TEXTO, DATA, TEXTO]
        larguras = [10, 44, 16] + [13] * len(indices) + [15, 11, 20, 13, 24, 16, 20, 20, 11, 60]

        linhas = []
        for item in self._itens_visiveis():
            linhas.append(
                [item.codigo, item.descricao, item.lote]
                + [item.contados[i] for i in indices]
                + [item.sistema, item.diferenca, item.valor_diferenca,
                   _SITUACAO_LABEL.get(item.situacao, item.situacao),
                   self._service.texto_por_coluna(item.sinais, r.colunas, indices),
                   item.custo, item.grupo, ", ".join(item.localizacoes), item.validade,
                   self._service.texto_por_coluna(item.observacoes, r.colunas, indices)]
            )

        agora = datetime.now()
        titulos = [f"Análise de Estoque — {self._nome_empresa or self._codempresa}"]
        detalhes = [f"estoque do sistema em {self._data_do_resultado():%d/%m/%Y}"]
        if varias:
            detalhes.append(f"base da diferença: {r.colunas[r.indice_base]}")
        detalhes.append(f"valores pelo {nome_custo.lower()}")
        texto_detalhes = " · ".join(detalhes)
        titulos.append(texto_detalhes[:1].upper() + texto_detalhes[1:])
        filtro = self._texto_filtro()
        if filtro:
            titulos.append(f"Filtro da grade: {filtro} · {len(linhas)} de {r.total_itens} registros")
        titulos.append(f"Gerado em {agora:%d/%m/%Y} às {agora:%H:%M}"
                       + (f" por {self._nome_usuario}" if self._nome_usuario else ""))
        try:
            gravar_xlsx(caminho, "Análise de Estoque", titulos, cabecalho, linhas, formatos, larguras)
        except Exception as exc:
            logger.error(f"Erro ao exportar Excel: {exc}")
            QMessageBox.critical(self, "Erro ao Exportar", f"Não foi possível gerar a planilha:\n{exc}")
            return
        self._lbl_status.setText(f"✅ Exportado: {caminho}")
        self._lbl_status.setStyleSheet(themed_qss("color: {{SUCCESS}}; font-size: 9pt;"))
        self._perguntar_abrir_pasta(caminho, pasta)

    # ------------------------------------------------------------------
    # Geração de PDF (QTextDocument + QPdfWriter — sem dependência nova)
    # ------------------------------------------------------------------

    def _cabecalho_html(self, com_filtro: bool = False) -> str:
        data_str = f"{self._data_do_resultado():%d/%m/%Y}"
        empresa = html_lib.escape(self._nome_empresa or self._codempresa)
        r = self._resultado
        total_div = r.total_falta + r.total_sobra if r else 0
        total_produtos = r.total_produtos if r else 0
        total_registros = r.total_itens if r else 0
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
        if r:
            partes = []
            if r.tem_valores:
                nome_custo = CAMPOS_CUSTO.get(r.campo_custo, "custo").lower()
                partes.append(f"<b>Falta:</b> {formatar_moeda(r.valor_falta)}{separador}"
                              f"<b>Sobra:</b> {formatar_moeda(r.valor_sobra)}{separador}"
                              f"<b>Saldo líquido:</b> {formatar_moeda(r.valor_liquido, sinal=True)} ({nome_custo})")
            if self._acuracia is not None:
                geral = self._acuracia.geral
                texto = f"<b>Acurácia:</b> {formatar_pct(geral.pct_registros)} dos registros"
                if geral.pct_valor is not None:
                    texto += f", {formatar_pct(geral.pct_valor)} do valor"
                partes.append(texto)
            if partes:
                linhas.append(f"<p style='{linha}'>{separador.join(partes)}</p>")
        if self._contagem_referencia is not None:
            c = self._contagem_referencia
            linhas.append(f"<p style='{linha}'><b>Referência:</b> apenas a contagem do conferente "
                          f"{html_lib.escape(c.codvendedor)} de {c.data_exportacao:%d/%m/%Y %H:%M}</p>")
        if r and len(r.colunas) > 1:
            consideradas = ", ".join(html_lib.escape(r.colunas[i]) for i in self._colunas_export())
            linhas.append(
                f"<p style='{linha}'><b>Contagens consideradas:</b> {consideradas}{separador}"
                f"<b>Base da diferença:</b> {html_lib.escape(r.colunas[r.indice_base])}</p>"
            )
        filtro = self._texto_filtro() if com_filtro else ""
        if filtro and r:
            linhas.append(f"<p style='{linha}'><b>Filtro da grade:</b> {html_lib.escape(filtro)}"
                          f"{separador}{self._visiveis} de {r.total_itens} registros</p>")
        return "".join(linhas)

    def _secao_comparativo(self) -> "_SecaoTabela":
        """A grade como está na tela (filtro e ordem). Observações e entrada
        manual vão em letra menor dentro da Descrição e da Situação, para a
        tabela caber na página."""
        r = self._resultado
        indices = self._colunas_export()
        varias = len(r.colunas) > 1
        miudo = f"font-size:7pt; color:{_PDF_SUAVE};"

        # (título, alinhamento do título) de cada coluna. Larguras: calculadas
        # na geração do PDF — cada coluna do tamanho do seu conteúdo, e a
        # Descrição (coluna_flexivel) com o resto.
        colunas = [("Produto", "center"), ("Descrição", "left"), ("Lote", "center")]
        colunas += [(html_lib.escape(r.colunas[i])
                     + (" (base)" if varias and i == r.indice_base else ""), "center")
                    for i in indices]
        colunas += [("Sistema", "center"), ("Diferença", "center"), ("Valor (R$)", "center"),
                    ("Situação", "left")]
        linhas = []
        for n, item in enumerate(self._itens_visiveis()):
            fundo = f" bgcolor='{_PDF_ZEBRA}'" if n % 2 else ""
            cor = _PDF_COR_SITUACAO.get(item.situacao, _PDF_TEXTO)
            situacao = _SITUACAO_LABEL.get(item.situacao, item.situacao)
            contados = "".join(
                f"<td align='center'{fundo}>{_num(item.contados[i])}</td>" for i in indices
            )
            descricao = html_lib.escape(item.descricao)
            observacoes = self._service.texto_por_coluna(item.observacoes, r.colunas, indices)
            if observacoes:
                descricao += f"<br><span style='{miudo}'><i>Obs.: {html_lib.escape(observacoes)}</i></span>"
            celula_situacao = f"<span style='color:{cor}; font-weight:bold;'>{situacao}</span>"
            sinais = self._service.texto_por_coluna(item.sinais, r.colunas, indices)
            if sinais:
                celula_situacao += f"<br><span style='{miudo}'>{html_lib.escape(sinais)}</span>"
            linhas.append(
                "<tr>"
                f"<td{fundo}>{html_lib.escape(item.codigo)}</td>"
                f"<td{fundo}>{descricao}</td>"
                f"<td align='center'{fundo}>{html_lib.escape(item.lote or '—')}</td>"
                f"{contados}"
                f"<td align='center'{fundo}>{_num(item.sistema)}</td>"
                f"<td align='center'{fundo}>{_num(item.diferenca, sinal=True)}</td>"
                f"<td align='center'{fundo}>{_valor_curto(item.valor_diferenca, sinal=True)}</td>"
                f"<td{fundo}>{celula_situacao}</td>"
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

    def _secao_validade(self) -> "_SecaoTabela":
        referencia = self._data_do_resultado()
        dias = self._spin_validade.value()
        linhas = []
        for n, (item, prazo) in enumerate(self._itens_validade()):
            fundo = f" bgcolor='{_PDF_ZEBRA}'" if n % 2 else ""
            cor = _PDF_COR_SITUACAO["falta"] if prazo < 0 else _PDF_COR_SITUACAO["sobra"]
            contado = item.contado if item.contado is not None else next(
                (q for q in item.contados if q is not None), None)
            linhas.append(
                "<tr>"
                f"<td{fundo}>{html_lib.escape(item.codigo)}</td>"
                f"<td{fundo}>{html_lib.escape(item.descricao)}</td>"
                f"<td align='center'{fundo}>{html_lib.escape(item.lote or '—')}</td>"
                f"<td align='center'{fundo}>{item.validade:%d/%m/%Y}</td>"
                f"<td{fundo}><span style='color:{cor}; font-weight:bold;'>{self._texto_prazo(prazo)}</span></td>"
                f"<td align='center'{fundo}>{_num(contado)}</td>"
                f"<td{fundo}>{html_lib.escape(', '.join(item.localizacoes))}</td>"
                "</tr>"
            )
        return _SecaoTabela(
            titulo_html=(
                f"<p style='font-size:9pt; font-weight:bold; color:{_PDF_MARCA}; "
                f"margin-top:0px; margin-bottom:4px;'>Validade dos lotes — vencidos até "
                f"{referencia:%d/%m/%Y} ou vencendo em até {dias} dia(s)</p>"
            ),
            atributos_tabela=(
                f"border='1' cellspacing='0' cellpadding='3' "
                f"style='border-collapse:collapse; border-style:solid; border-color:{_PDF_BORDA};'"
            ),
            colunas=[("Produto", "center"), ("Descrição", "left"), ("Lote", "center"),
                     ("Validade", "center"), ("Prazo", "left"), ("Contado", "center"),
                     ("Localização", "left")],
            coluna_flexivel=1,
            linhas_html=linhas,
        )

    def _secao_analise_ia(self) -> "_SecaoTexto":
        # Fonte 8 e parágrafos quase colados: o texto da IA é longo, e o
        # espaçamento padrão do HTML (uma linha em branco entre parágrafos)
        # espalhava a análise por várias páginas.
        partes = []
        for k, secao in enumerate(self._secoes_ia):
            titulo = "Análise da IA" if k == 0 else secao["titulo"]
            detalhe = (f" <span style='color:{_PDF_SUAVE}; font-weight:normal;'>· {secao['detalhe']}</span>"
                       if k and secao["detalhe"] else "")
            topo = 0 if k == 0 else 12
            partes.append(
                f"<p style='font-size:9pt; font-weight:bold; color:{_PDF_MARCA}; "
                f"margin-top:{topo}px; margin-bottom:4px;'>{html_lib.escape(titulo)}{detalhe}</p>"
            )
            partes.append(texto_ia_em_html(secao["texto"], espaco_titulo=6, espaco_linha=2))
        return _SecaoTexto("".join(partes))

    def _salvar_pdf(self, secoes: list, caminho: str, com_filtro: bool = False) -> bool:
        agora = datetime.now()
        rodape = f"Gerado em {agora:%d/%m/%Y} às {agora:%H:%M}"
        if self._nome_usuario:
            rodape += f" por {self._nome_usuario}"
        try:
            _gerar_pdf_relatorio(
                caminho, self._cabecalho_html(com_filtro), secoes, rodape, "Análise de Estoque"
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
    "sem_cadastro": "#8e44ad",
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
