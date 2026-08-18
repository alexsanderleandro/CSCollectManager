"""
pdf_contagem_parser.py
=======================
Parser determinístico de PDFs de contagem exportados pelo LOGSCAN (coletor
mobile), formato "LOGSCAN vX.Y.Z rev. N | RELATÓRIO DE CONTAGEM DE ESTOQUE".

Cobre os dois layouts do relatório, que diferem em mais do que a ordem das
linhas — têm **conjuntos de colunas diferentes**:

- Modelo 1 (por produto):
  ``Código EAN Descrição Lote Fabricação Validade Qtde Unid. Localização``
- Modelo 2 (por grupo de estoque):
  ``Código EAN Descrição Qtde Unid. Localização`` (sem lote/datas), com linhas
  ``Grupo: <cod> - <nome>`` intercaladas entre os itens.

Por isso as colunas são mapeadas pelo **cabeçalho da tabela**, nunca por
posição fixa.

Além das linhas de item, a tabela traz linhas "vazadas" (que ocupam a largura
toda) e que **não são itens**:

- ``Grupo: <cod> - <nome>``    — agrupador do Modelo 2.
- ``Produto: <cod> - <desc>``  — agrupador de um produto com controle de lote.
- ``Obs. produto: <texto>``    — observação do produto (vem logo após ``Produto:``).
- ``Obs.: <texto>``            — observação da linha/lote (vem logo após o item).

Extrai apenas dados estruturados, sem nenhuma interpretação de negócio: a
comparação com o estoque do sistema e a análise de divergências ficam a cargo
de outro serviço, que monta a tabela comparativa e aciona a IA.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

import pdfplumber

_HEADER_RE = re.compile(
    r"^LOGSCAN\s+(?P<versao>[^|]+?)\s*\|\s*RELAT[ÓO]RIO DE CONTAGEM DE ESTOQUE\s*\|\s*"
    r"Modelo\s+(?P<modelo_num>\d+)\s*-\s*(?P<modelo_desc>.+)$",
    re.IGNORECASE,
)
_EMPRESA_RE = re.compile(
    r"^Empresa:\s*(?P<codempresa>\S+)\s*\|\s*(?P<nome_empresa>.+?)\s*\|\s*"
    r"Usu[áa]rio:\s*(?P<codvendedor>\S+)\s*-\s*(?P<nome_vendedor>.+?)\s*\|\s*"
    r"Data de exporta[çc][ãa]o:\s*(?P<data>\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})$",
    re.IGNORECASE,
)
_TOTAL_PRODUTOS_RE = re.compile(r"Total de produtos contados:\s*(\d+)")
_TOTAL_REGISTROS_RE = re.compile(r"Total de registros:\s*(\d+)")

# Linhas "vazadas" da tabela, que não são itens. A alternação é ordenada:
# "Obs. produto" precisa vir antes de "Obs." para não ser engolida por ela.
_LINHA_PREFIXO_RE = re.compile(
    r"^(?P<tipo>Grupo|Produto|Obs\.\s*produto|Obs\.)\s*:\s*(?P<valor>.*)$",
    re.IGNORECASE,
)
# "060460 - PLACA MAE H61 K LGA1155 REVENGER" -> "060460"
_PRODUTO_COD_RE = re.compile(r"^(?P<codigo>\S+)\s*-\s*")

_FILENAME_RE = re.compile(
    r"^CONTAGEM_(?P<codempresa>[^_]+)_(?P<codvendedor>[^_]+)_(?P<cnpj>\d+)_(?P<timestamp>\d{12})$",
    re.IGNORECASE,
)

# Cabeçalho normalizado (sem acento, sem ponto final) -> campo do ContagemItem.
_COLUNAS_CONHECIDAS = {
    "codigo": "codigo",
    "ean": "ean",
    "descricao": "descricao",
    "lote": "lote",
    "fabricacao": "fabricacao",
    "validade": "validade",
    "qtde": "qtde",
    "unid": "unidade",
    "localizacao": "localizacao",
}

# Só as tabelas que começam com estas três colunas são tabelas de itens; as
# demais da página (ex.: "Produtos lançados com quantidade zerada
# automaticamente") são ignoradas.
_TABLE_HEADER_PREFIX = ["codigo", "ean", "descricao"]


@dataclass
class ContagemItem:
    """Um item (linha de produto) da tabela de contagem."""
    codigo: str
    ean: str
    descricao: str
    lote: str = ""
    fabricacao: Optional[date] = None
    validade: Optional[date] = None
    qtde_contada: float = 0.0
    unidade: str = ""
    localizacao: str = ""
    grupo: str = ""              # só preenchido no Modelo 2
    observacao: str = ""         # "Obs.:" — observação desta linha/lote
    observacao_produto: str = ""  # "Obs. produto:" — observação do produto


@dataclass
class ContagemPDF:
    """Dados extraídos de um PDF de contagem LOGSCAN."""
    arquivo: str
    modelo: str               # "MOD1" ou "MOD2"
    versao_app: str
    codempresa: str
    nome_empresa: str
    codvendedor: str
    nome_vendedor: str
    data_exportacao: datetime
    total_produtos_contados: int
    total_registros: int
    itens: List[ContagemItem] = field(default_factory=list)
    # Valores lidos do NOME do arquivo, para checagem cruzada pelo chamador
    # (mesmo padrão já usado na validação de download de contagens).
    codempresa_arquivo: str = ""
    codvendedor_arquivo: str = ""
    cnpj_arquivo: str = ""


@dataclass
class _EstadoLeitura:
    """Contexto de leitura que atravessa linhas e páginas.

    Um produto com lote é introduzido por uma linha ``Produto:``, seguida
    opcionalmente de ``Obs. produto:``, e só então vêm as linhas de item — e
    esse bloco pode ser cortado por uma quebra de página.
    """
    grupo: str = ""
    produto_atual: str = ""
    observacao_produto: str = ""
    ultimo_item: Optional[ContagemItem] = None


def _parse_data_hdr(txt: str) -> datetime:
    return datetime.strptime(txt.strip(), "%d/%m/%Y %H:%M")


def _parse_ddmmyyyy(txt: Optional[str]) -> Optional[date]:
    txt = (txt or "").strip()
    if not txt:
        return None
    return datetime.strptime(txt, "%d%m%Y").date()


def _parse_qtde(txt: Optional[str]) -> float:
    txt = (txt or "").strip()
    return float(txt) if txt else 0.0


def _normalizar_cabecalho(txt: Optional[str]) -> str:
    """Normaliza o nome de uma coluna: minúsculo, sem acento e sem ponto final
    (``"Unid."`` -> ``"unid"``, ``"Fabricação"`` -> ``"fabricacao"``)."""
    base = unicodedata.normalize("NFKD", (txt or "").strip().lower())
    return "".join(c for c in base if not unicodedata.combining(c)).rstrip(".")


class PdfContagemParser:
    """Parser de PDFs de contagem no layout LOGSCAN (Modelo 1 e Modelo 2)."""

    def parse(self, caminho: str) -> ContagemPDF:
        """
        Lê e valida um PDF de contagem LOGSCAN.

        Args:
            caminho: Caminho do arquivo PDF.

        Returns:
            ``ContagemPDF`` com cabeçalho e itens extraídos.

        Raises:
            ValueError: Se o cabeçalho não corresponder ao formato LOGSCAN
                conhecido, ou se a quantidade de itens/produtos extraídos não
                bater com os totais declarados no rodapé.
        """
        with pdfplumber.open(caminho) as pdf:
            if not pdf.pages:
                raise ValueError(f"PDF vazio: {caminho}")

            primeira_pagina_texto = pdf.pages[0].extract_text() or ""
            linhas = primeira_pagina_texto.splitlines()
            if not linhas:
                raise ValueError(f"Não foi possível extrair texto do PDF: {caminho}")

            header_match = _HEADER_RE.match(linhas[0].strip())
            if not header_match:
                raise ValueError(
                    f"Cabeçalho não corresponde ao formato LOGSCAN esperado "
                    f"(esperado 'LOGSCAN vX.Y.Z ... | RELATÓRIO DE CONTAGEM DE "
                    f"ESTOQUE | Modelo N - ...'): {linhas[0]!r}"
                )
            modelo = f"MOD{header_match.group('modelo_num')}"
            versao_app = header_match.group("versao")

            empresa_match = None
            for linha in linhas[1:4]:
                empresa_match = _EMPRESA_RE.match(linha.strip())
                if empresa_match:
                    break
            if not empresa_match:
                raise ValueError(
                    f"Linha de empresa/usuário não encontrada ou fora do "
                    f"formato esperado no PDF: {caminho}"
                )

            codempresa = empresa_match.group("codempresa")
            nome_empresa = empresa_match.group("nome_empresa")
            codvendedor = empresa_match.group("codvendedor")
            nome_vendedor = empresa_match.group("nome_vendedor")
            data_exportacao = _parse_data_hdr(empresa_match.group("data"))

            total_produtos_contados: Optional[int] = None
            total_registros: Optional[int] = None
            itens: List[ContagemItem] = []
            estado = _EstadoLeitura()

            for page in pdf.pages:
                itens.extend(self._extrair_itens_pagina(page, estado))

                texto_pagina = page.extract_text() or ""
                if total_produtos_contados is None:
                    m = _TOTAL_PRODUTOS_RE.search(texto_pagina)
                    if m:
                        total_produtos_contados = int(m.group(1))
                if total_registros is None:
                    m = _TOTAL_REGISTROS_RE.search(texto_pagina)
                    if m:
                        total_registros = int(m.group(1))

            if total_produtos_contados is None or total_registros is None:
                raise ValueError(f"Rodapé de totais não encontrado no PDF: {caminho}")

            if len(itens) != total_registros:
                raise ValueError(
                    f"Itens extraídos ({len(itens)}) não batem com 'Total de "
                    f"registros' do rodapé ({total_registros}) — {caminho}"
                )

            # Um produto com N lotes ocupa N linhas (registros), mas continua
            # sendo um só produto — é o que o rodapé separa em dois totais.
            produtos_distintos = len({i.codigo for i in itens})
            if produtos_distintos != total_produtos_contados:
                raise ValueError(
                    f"Produtos distintos extraídos ({produtos_distintos}) não "
                    f"batem com 'Total de produtos contados' do rodapé "
                    f"({total_produtos_contados}) — {caminho}"
                )

            nome_base = os.path.splitext(os.path.basename(caminho))[0]
            fn_match = _FILENAME_RE.match(nome_base)
            codempresa_arquivo = fn_match.group("codempresa") if fn_match else ""
            codvendedor_arquivo = fn_match.group("codvendedor") if fn_match else ""
            cnpj_arquivo = fn_match.group("cnpj") if fn_match else ""

            return ContagemPDF(
                arquivo=caminho,
                modelo=modelo,
                versao_app=versao_app,
                codempresa=codempresa,
                nome_empresa=nome_empresa,
                codvendedor=codvendedor,
                nome_vendedor=nome_vendedor,
                data_exportacao=data_exportacao,
                total_produtos_contados=total_produtos_contados,
                total_registros=total_registros,
                itens=itens,
                codempresa_arquivo=codempresa_arquivo,
                codvendedor_arquivo=codvendedor_arquivo,
                cnpj_arquivo=cnpj_arquivo,
            )

    def _extrair_itens_pagina(self, page, estado: _EstadoLeitura) -> List[ContagemItem]:
        """Extrai os itens da tabela de uma página, já com as observações.

        ``estado`` é lido e atualizado — grupo, produto corrente e observação
        de produto pendente precisam sobreviver à quebra de página.
        """
        itens: List[ContagemItem] = []

        for table in page.find_tables():
            linhas_extraidas = table.extract()
            if not linhas_extraidas:
                continue

            cabecalho = [_normalizar_cabecalho(c) for c in linhas_extraidas[0]]
            if cabecalho[:3] != _TABLE_HEADER_PREFIX:
                continue  # não é a tabela de itens

            # Mapa coluna -> índice, montado a partir do cabeçalho: é o que
            # permite ler Modelo 1 (9 colunas) e Modelo 2 (6) com o mesmo código.
            mapa: Dict[str, int] = {}
            for idx, nome in enumerate(cabecalho):
                campo = _COLUNAS_CONHECIDAS.get(nome)
                if campo and campo not in mapa:
                    mapa[campo] = idx

            for cells in linhas_extraidas[1:]:
                primeira_celula = (cells[0] or "").strip()
                if not primeira_celula:
                    continue

                prefixo = _LINHA_PREFIXO_RE.match(primeira_celula)
                if prefixo:
                    self._tratar_linha_prefixada(prefixo, estado)
                    continue

                def _col(campo: str) -> str:
                    idx = mapa.get(campo)
                    if idx is None or idx >= len(cells):
                        return ""
                    return (cells[idx] or "").strip()

                codigo = _col("codigo")
                if not codigo:
                    continue  # sem código não é item

                item = ContagemItem(
                    codigo=codigo,
                    ean=_col("ean"),
                    descricao=_col("descricao"),
                    lote=_col("lote"),
                    fabricacao=_parse_ddmmyyyy(_col("fabricacao")),
                    validade=_parse_ddmmyyyy(_col("validade")),
                    qtde_contada=_parse_qtde(_col("qtde")),
                    unidade=_col("unidade"),
                    localizacao=_col("localizacao"),
                    grupo=estado.grupo,
                )
                if estado.observacao_produto and estado.produto_atual == codigo:
                    item.observacao_produto = estado.observacao_produto

                itens.append(item)
                estado.ultimo_item = item

        return itens

    @staticmethod
    def _tratar_linha_prefixada(prefixo: re.Match, estado: _EstadoLeitura) -> None:
        """Aplica ao estado uma linha ``Grupo:``/``Produto:``/``Obs...:``."""
        tipo = re.sub(r"\s+", " ", prefixo.group("tipo").strip().lower())
        valor = prefixo.group("valor").strip()

        if tipo == "grupo":
            estado.grupo = valor
            estado.produto_atual = ""
            estado.observacao_produto = ""
        elif tipo == "produto":
            cod_match = _PRODUTO_COD_RE.match(valor)
            estado.produto_atual = cod_match.group("codigo") if cod_match else valor
            estado.observacao_produto = ""
        elif tipo == "obs. produto":
            estado.observacao_produto = valor
        else:  # "obs." — observação da linha/lote imediatamente anterior
            item = estado.ultimo_item
            if item is not None and valor:
                item.observacao = f"{item.observacao} {valor}".strip() if item.observacao else valor
