"""
contagem_zip.py
===============
Lê, para a Análise de Estoque, as contagens baixadas na tela "Download
Contagens": os ZIPs assinados que o coletor exporta.

Cada ZIP traz:

- ``.db`` (SQLite) — a contagem em si: tabela ``Produtos`` (código, lote,
  datas, quantidade, grupo, localização) e ``Empresa`` (empresa, CNPJ e o
  local de estoque da carga);
- ``.sig`` — assinatura HMAC do conjunto, com o hash de cada arquivo;
- ``.pdf`` (opcional) — o relatório impresso. Daqui só saem as observações
  do conferente, que não existem no ``.db``;
- ``_metricas.enc`` (opcional) — métricas de produtividade. Daqui saem os
  produtos com quantidade digitada à mão ou lançados sem GTIN.

O ZIP inteiro é reconferido com o ``.sig`` a cada leitura: ele já foi
validado no download, mas fica numa pasta comum e pode ter sido trocado
depois. Um PDF solto, sem o ``.sig``, não tem como ser conferido — por isso
a análise não aceita mais PDF avulso.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from services.pdf_contagem_parser import ContagemItem, PdfContagemParser
from utils.logger import get_logger

logger = get_logger(__name__)

# MODELO_CODEMPRESA_CODVENDEDOR_CNPJ_DDMMAAAAHHMM.zip — mesmo padrão validado
# no download (um sufixo depois do horário, como "…1100A.zip", é aceito).
_NOME_ZIP_RE = re.compile(
    r"^(?P<modelo>[A-Za-z0-9]+)_(?P<codempresa>[^_]+)_(?P<codvendedor>[^_]+)_"
    r"(?P<cnpj>\d+)_(?P<ts>\d{12})[^.]*\.zip$",
    re.IGNORECASE,
)


class ContagemZipError(ValueError):
    """ZIP recusado: assinatura inválida, outra empresa ou conteúdo ilegível."""


@dataclass
class ContagemBaixada:
    """Resumo de um ZIP da pasta de contagens, para a lista de escolha."""
    caminho: str
    codempresa: str
    codvendedor: str
    cnpj: str
    data_exportacao: Optional[datetime]
    nome_vendedor: str = ""
    local: str = ""
    total_produtos: Optional[int] = None
    total_registros: Optional[int] = None
    erro: str = ""

    @property
    def nome_arquivo(self) -> str:
        return os.path.basename(self.caminho)


@dataclass
class Contagem:
    """Uma contagem lida de um ZIP baixado, pronta para a análise."""
    arquivo: str                 # caminho do ZIP
    codempresa: str
    cnpj: str
    local: str                   # Empresa.local: "Loja", "Depósito" ou ENDLOCALESTOQUE
    codvendedor: str
    nome_vendedor: str
    data_exportacao: datetime
    versao_app: str
    itens: List[ContagemItem] = field(default_factory=list)
    # codproduto -> como a quantidade entrou quando não foi bipada
    # ("sem GTIN", "digitado à mão (2×)", "correção de qtde").
    sinais_entrada: Dict[str, List[str]] = field(default_factory=dict)
    # Leituras complementares que falharam sem impedir a análise
    # (ex.: PDF ausente = sem observações do conferente).
    avisos: List[str] = field(default_factory=list)

    @property
    def total_registros(self) -> int:
        return len(self.itens)

    @property
    def total_produtos_contados(self) -> int:
        return len({i.codigo for i in self.itens})


# ----------------------------------------------------------------------
# Lista das contagens baixadas
# ----------------------------------------------------------------------

def _so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def _data_do_nome(ts: str) -> Optional[datetime]:
    try:
        return datetime.strptime(ts, "%d%m%Y%H%M")
    except ValueError:
        return None


def listar_contagens_baixadas(pasta: str, codempresa: str, cnpj: str = "") -> List[ContagemBaixada]:
    """ZIPs de contagem da ``pasta`` que são da empresa logada, do mais novo
    para o mais antigo.

    Só lê o resumo (local, totais, nome do conferente); a validação completa
    fica para quando a contagem entra na análise (``ler_contagem_zip``).
    Um ZIP ilegível entra na lista com ``erro`` preenchido, em vez de sumir.
    """
    resultado: List[ContagemBaixada] = []
    if not pasta or not os.path.isdir(pasta):
        return resultado
    codempresa = str(codempresa or "").strip()
    cnpj = _so_digitos(cnpj)

    for caminho in glob.glob(os.path.join(pasta, "*.zip")):
        m = _NOME_ZIP_RE.match(os.path.basename(caminho))
        if not m:
            continue
        if m.group("codempresa") != codempresa:
            continue
        if cnpj and _so_digitos(m.group("cnpj")) != cnpj:
            continue
        item = ContagemBaixada(
            caminho=caminho,
            codempresa=m.group("codempresa"),
            codvendedor=m.group("codvendedor"),
            cnpj=m.group("cnpj"),
            data_exportacao=_data_do_nome(m.group("ts")),
        )
        try:
            with zipfile.ZipFile(caminho) as zf:
                nomes = zf.namelist()
                db = _primeiro(nomes, ".db")
                if db:
                    empresa, produtos = _ler_db(zf.read(db))
                    item.local = empresa.get("local") or ""
                    item.total_registros = len(produtos)
                    item.total_produtos = len({p["codproduto"] for p in produtos})
                else:
                    item.erro = "Sem arquivo .db (formato antigo)"
                metricas = _ler_metricas(zf, nomes)
                if metricas:
                    item.nome_vendedor = str(metricas.get("nomeusuario") or "").strip()
        except Exception as exc:
            item.erro = f"Não foi possível ler o ZIP: {exc}"
        resultado.append(item)

    resultado.sort(key=lambda c: c.data_exportacao or datetime.min, reverse=True)
    return resultado


# ----------------------------------------------------------------------
# Leitura completa de uma contagem
# ----------------------------------------------------------------------

def ler_contagem_zip(caminho: str, codempresa: str, cnpj: str, token_licenca: str) -> Contagem:
    """Valida o ZIP com o ``.sig`` e devolve a contagem.

    Raises:
        ContagemZipError: assinatura ou hash inválido, ZIP de outra empresa,
            ou sem dados de contagem legíveis.
    """
    from services.api_service import ApiService

    nome = os.path.basename(caminho)
    validacao = ApiService.validate_sig(caminho, token_licenca)
    if not validacao["ok"]:
        erros = "\n".join(f"  • {e}" for e in validacao["erros"])
        raise ContagemZipError(f"{nome}: a assinatura do arquivo não confere.\n{erros}")
    payload = validacao["payload"] or {}

    codempresa = str(codempresa or "").strip()
    cnpj = _so_digitos(cnpj)
    cod_arquivo = str(payload.get("codempresa") or "").strip()
    if cod_arquivo != codempresa:
        raise ContagemZipError(
            f"{nome}: contagem da empresa {cod_arquivo or '?'}, mas a empresa logada é {codempresa}.")
    if cnpj and _so_digitos(payload.get("cnpj", "")) != cnpj:
        raise ContagemZipError(
            f"{nome}: CNPJ do arquivo ({payload.get('cnpj', '?')}) diferente do CNPJ da empresa logada ({cnpj}).")

    m = _NOME_ZIP_RE.match(nome)
    data_exportacao = None
    try:
        data_exportacao = datetime.fromisoformat(str(payload.get("timestamp") or ""))
    except ValueError:
        pass
    if data_exportacao is None and m:
        data_exportacao = _data_do_nome(m.group("ts"))
    if data_exportacao is None:
        data_exportacao = datetime.fromtimestamp(os.path.getmtime(caminho))

    contagem = Contagem(
        arquivo=caminho,
        codempresa=cod_arquivo,
        cnpj=str(payload.get("cnpj") or ""),
        local="",
        codvendedor=str(payload.get("codvendedor") or (m.group("codvendedor") if m else "")),
        nome_vendedor="",
        data_exportacao=data_exportacao,
        versao_app=str(payload.get("versao") or ""),
    )

    with zipfile.ZipFile(caminho) as zf:
        nomes = zf.namelist()
        nome_pdf = _primeiro(nomes, ".pdf")
        pdf = _ler_pdf(zf, nome_pdf, contagem) if nome_pdf else None
        if not nome_pdf:
            contagem.avisos.append("O ZIP não traz o PDF: sem observações do conferente.")

        nome_db = _primeiro(nomes, ".db")
        if nome_db:
            empresa, produtos = _ler_db(zf.read(nome_db))
            contagem.local = str(empresa.get("local") or "")
            contagem.itens = [_item_do_db(p) for p in produtos]
        elif pdf is not None:
            # ZIP no formato antigo (.txt): o PDF, que o .sig também confere,
            # é a única fonte legível da contagem.
            contagem.itens = pdf.itens
            contagem.avisos.append("ZIP no formato antigo (sem .db): itens lidos do PDF.")
        else:
            raise ContagemZipError(f"{nome}: o ZIP não traz o .db nem o PDF da contagem.")

        if pdf is not None:
            _aplicar_observacoes(contagem.itens, pdf.itens)
            contagem.nome_vendedor = pdf.nome_vendedor

        metricas = _ler_metricas(zf, nomes)
        if metricas:
            contagem.nome_vendedor = str(metricas.get("nomeusuario") or "").strip() or contagem.nome_vendedor
        contagem.sinais_entrada = _sinais_entrada(contagem.itens, metricas or {})

    return contagem


# ----------------------------------------------------------------------
# Auxiliares
# ----------------------------------------------------------------------

def _primeiro(nomes: List[str], extensao: str) -> str:
    return next((n for n in nomes if n.lower().endswith(extensao)), "")


def _ler_db(conteudo: bytes) -> Tuple[dict, List[dict]]:
    """(linha de Empresa, linhas de Produtos) do SQLite exportado pelo coletor,
    lido direto da memória."""
    con = sqlite3.connect(":memory:")
    try:
        con.deserialize(conteudo)
        con.row_factory = sqlite3.Row
        empresa = con.execute("SELECT * FROM Empresa LIMIT 1").fetchone()
        produtos = [dict(r) for r in con.execute("SELECT * FROM Produtos")]
        return (dict(empresa) if empresa else {}), produtos
    finally:
        con.close()


def _data_ddmmaaaa(texto) -> Optional[date]:
    texto = str(texto or "").strip()
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%d%m%Y").date()
    except ValueError:
        return None


def _item_do_db(p: dict) -> ContagemItem:
    grupo = str(p.get("nomegrupo") or "").strip() or str(p.get("codgrupo") or "").strip()
    # numlote só vale para produto com controle de lote; nos demais vem nulo.
    lote = str(p.get("numlote") or "").strip() if p.get("controlalote") else ""
    return ContagemItem(
        codigo=str(p.get("codproduto") or "").strip(),
        ean=str(p.get("codean") or "").strip(),
        descricao=str(p.get("descricaoproduto") or "").strip(),
        lote=lote,
        fabricacao=_data_ddmmaaaa(p.get("datafab")),
        validade=_data_ddmmaaaa(p.get("dataval")),
        qtde_contada=float(p.get("qtdecontada") or 0),
        unidade=str(p.get("unidade") or "").strip(),
        localizacao=str(p.get("localizacao") or "").strip(),
        grupo=grupo,
    )


def _ler_pdf(zf: zipfile.ZipFile, nome_pdf: str, contagem: Contagem):
    """PDF de dentro do ZIP (o hash dele já foi conferido pelo .sig). Uma
    falha aqui só tira as observações — a contagem vem do .db."""
    try:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = zf.extract(nome_pdf, pasta)
            return PdfContagemParser().parse(caminho)
    except Exception as exc:
        logger.warning(f"PDF de {os.path.basename(contagem.arquivo)} não lido: {exc}")
        contagem.avisos.append(f"Observações do conferente não lidas (PDF ilegível): {exc}")
        return None


def _aplicar_observacoes(itens: List[ContagemItem], itens_pdf: List[ContagemItem]) -> None:
    """Copia as observações do PDF para os itens do .db, pelo par código+lote
    (a observação de produto vale para todos os lotes dele)."""
    por_lote: Dict[Tuple[str, str], List[str]] = {}
    por_produto: Dict[str, str] = {}
    for i in itens_pdf:
        if i.observacao:
            textos = por_lote.setdefault((i.codigo, i.lote), [])
            if i.observacao not in textos:
                textos.append(i.observacao)
        if i.observacao_produto:
            por_produto[i.codigo] = i.observacao_produto
    for item in itens:
        textos = por_lote.get((item.codigo, item.lote))
        if textos and not item.observacao:
            item.observacao = " / ".join(textos)
        if not item.observacao_produto:
            item.observacao_produto = por_produto.get(item.codigo, "")


def _ler_metricas(zf: zipfile.ZipFile, nomes: List[str]) -> Optional[dict]:
    nome = next((n for n in nomes if n.endswith("_metricas.enc")), "")
    if not nome:
        return None
    try:
        from utils.metrics_decryption import decifrar_metricas
        return decifrar_metricas(json.loads(zf.read(nome).decode("utf-8")))
    except Exception as exc:
        logger.warning(f"Métricas de {nome} não lidas: {exc}")
        return None


def _sinais_entrada(itens: List[ContagemItem], metricas: dict) -> Dict[str, List[str]]:
    """Produtos cuja quantidade não veio de leitura de código: digitada à
    mão na contagem, lançada sem GTIN ou corrigida depois."""
    sinais: Dict[str, List[str]] = {}
    codigo_por_ean = {i.ean: i.codigo for i in itens if i.ean and i.ean.upper() != "SEM GTIN"}

    def _marcar(codigo: str, rotulo: str):
        codigo = str(codigo or "").strip()
        if codigo and rotulo not in sinais.setdefault(codigo, []):
            sinais[codigo].append(rotulo)

    for item in itens:
        if item.ean.upper() == "SEM GTIN":
            _marcar(item.codigo, "sem GTIN")
    for lanc in (metricas.get("lancamentos_manuais") or {}).get("itens") or []:
        codigo = lanc.get("codproduto") or codigo_por_ean.get(lanc.get("codean"), "")
        if lanc.get("alteracao"):
            _marcar(codigo, "correção de qtde")
        elif lanc.get("origem") == "sem_gtin":
            _marcar(codigo, "sem GTIN")
        else:
            _marcar(codigo, "lançado à mão")
    for ajuste in metricas.get("produtos_ajustados_manualmente") or []:
        codigo = ajuste.get("codproduto") or codigo_por_ean.get(ajuste.get("codean"), "")
        vezes = ajuste.get("total_ajustes") or 0
        _marcar(codigo, f"digitado à mão ({vezes}×)" if vezes else "digitado à mão")
    return {c: s for c, s in sinais.items() if s}
