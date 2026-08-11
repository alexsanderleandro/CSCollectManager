"""
pdf_contagem_parser.py
=======================
Parser determinístico de PDFs de contagem exportados pelo LOGSCAN (coletor
mobile), formato "LOGSCAN vX.Y.Z rev. N | RELATÓRIO DE CONTAGEM DE ESTOQUE".

Cobre os dois layouts do relatório — Modelo 1 (por produto) e Modelo 2 (por
grupo de estoque) — que diferem apenas por Modelo 2 intercalar linhas
"Grupo: <cod> - <nome>" entre os itens.

Extrai apenas dados estruturados, sem nenhuma interpretação de negócio: a
comparação com o estoque do sistema e a análise de divergências ficam a cargo
de outro serviço, que monta a tabela comparativa e aciona a IA.
"""
from __future__ import annotations

import os
import re
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
_GRUPO_RE = re.compile(r"^Grupo:\s*(.+)$", re.IGNORECASE)
_PAGINACAO_RE = re.compile(r"^P[áa]gina\s+\d+\s*/\s*\d+$", re.IGNORECASE)

# Distância vertical máxima (pt) entre o fim de uma linha de item e uma linha em
# itálico para que ela seja considerada observação desse item — a altura de
# linha da tabela é ~13pt; qualquer coisa muito além disso (ex.: o rodapé
# "Página N/M", que também usa fonte itálica) não é observação de item.
_MAX_GAP_OBSERVACAO = 20

_TABLE_HEADER_PREFIX = ["código", "ean", "descrição"]

_FILENAME_RE = re.compile(
    r"^CONTAGEM_(?P<codempresa>[^_]+)_(?P<codvendedor>[^_]+)_(?P<cnpj>\d+)_(?P<timestamp>\d{12})$",
    re.IGNORECASE,
)


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
    grupo: str = ""          # só preenchido no Modelo 2
    observacao: str = ""


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


def _is_oblique(fontname: Optional[str]) -> bool:
    f = (fontname or "").lower()
    return "oblique" in f or "italic" in f


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
                conhecido, ou se a quantidade de itens extraídos não bater com
                o "Total de registros" declarado no rodapé.
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
            grupo_atual = ""

            for page in pdf.pages:
                itens.extend(self._extrair_itens_pagina(page, grupo_atual_inicial=grupo_atual))
                if itens:
                    grupo_atual = itens[-1].grupo

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

    def _extrair_itens_pagina(self, page, grupo_atual_inicial: str) -> List[ContagemItem]:
        """Extrai os itens da tabela de uma página, já com observações associadas.

        Usa ``find_tables()`` (em vez de ``extract_tables()``) porque expõe o
        bounding box de cada linha — necessário para casar cada observação em
        itálico com o item correto quando há mais de um item na página.
        """
        itens: List[ContagemItem] = []
        tops: List[float] = []
        grupo_atual = grupo_atual_inicial

        for table in page.find_tables():
            linhas_extraidas = table.extract()
            if not linhas_extraidas:
                continue
            header_row = [(c or "").strip().lower() for c in linhas_extraidas[0]]
            if header_row[:3] != _TABLE_HEADER_PREFIX:
                continue  # não é a tabela de itens (ex.: nenhuma nesta página)

            for row_obj, cells in zip(table.rows[1:], linhas_extraidas[1:]):
                primeira_celula = (cells[0] or "").strip()
                grupo_match = _GRUPO_RE.match(primeira_celula)
                if grupo_match and all(not (c or "").strip() for c in cells[1:]):
                    grupo_atual = grupo_match.group(1).strip()
                    continue
                if not primeira_celula:
                    continue

                codigo, ean, descricao, lote, fabricacao, validade, qtde, unidade, localizacao = (
                    (c or "").strip() for c in cells
                )
                itens.append(ContagemItem(
                    codigo=codigo,
                    ean=ean,
                    descricao=descricao,
                    lote=lote,
                    fabricacao=_parse_ddmmyyyy(fabricacao),
                    validade=_parse_ddmmyyyy(validade),
                    qtde_contada=_parse_qtde(qtde),
                    unidade=unidade,
                    localizacao=localizacao,
                    grupo=grupo_atual,
                ))
                tops.append(row_obj.bbox[1])

        if itens:
            self._associar_observacoes(page, itens, tops)
        return itens

    @staticmethod
    def _associar_observacoes(page, itens: List[ContagemItem], tops: List[float]) -> None:
        """Associa linhas em itálico (observações) ao item mais próximo acima delas.

        A posição vertical (``top``) de cada linha de observação é comparada
        com o ``top`` de cada linha de item já extraída da mesma página; o
        item com o maior ``top`` ainda menor que o da observação é o dono dela.
        """
        words = page.extract_words(extra_attrs=["fontname"])
        linhas_italico: List[List[dict]] = []
        for w in words:
            if not _is_oblique(w.get("fontname")):
                continue
            if linhas_italico and abs(linhas_italico[-1][0]["top"] - w["top"]) < 2:
                linhas_italico[-1].append(w)
            else:
                linhas_italico.append([w])

        for linha in linhas_italico:
            texto = " ".join(w["text"] for w in sorted(linha, key=lambda w: w["x0"])).strip()
            if not texto or _PAGINACAO_RE.match(texto):
                continue
            obs_top = linha[0]["top"]
            melhor_idx = None
            melhor_top = None
            for idx, item_top in enumerate(tops):
                if item_top < obs_top and (melhor_top is None or item_top > melhor_top):
                    melhor_top = item_top
                    melhor_idx = idx
            if melhor_idx is not None and (obs_top - melhor_top) <= _MAX_GAP_OBSERVACAO:
                item = itens[melhor_idx]
                item.observacao = f"{item.observacao} {texto}".strip() if item.observacao else texto
