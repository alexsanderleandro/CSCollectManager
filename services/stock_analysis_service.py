"""
stock_analysis_service.py
==========================
Compara a contagem lida dos PDFs (``ContagemPDF``) com o estoque atual do ERP
e monta o payload que vai para a IA. A IA nunca recebe o PDF nem a tabela
inteira — só o resumo agregado e as N maiores divergências.

Regras de negócio (definidas com o usuário):
- Produto sem controle de lote  -> ``csfEstoqueData(@codproduto, @codempresa, @data, @localestoque)``.
- Produto com lote EXISTENTE    -> ``csfEstoqueDataLote(@codproduto, @codempresa, @data, @numlote, @localestoque)``.
- Produto com lote que NÃO existe em ``produtoslote`` -> marcado "lote novo",
  sem chamar função de estoque (a função devolve 0 silenciosamente para lote
  inexistente — não dá pra usar o retorno dela para decidir isso).
- ``controlarlote`` é lido direto de ``produtos`` — nunca deduzido de outra
  consulta (um produto pode controlar lote e ainda não ter nenhum lote batendo
  com um filtro qualquer).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text

from database.connection import get_session
from services.pdf_contagem_parser import ContagemPDF
from utils.logger import get_logger

logger = get_logger(__name__)

_TAMANHO_LOTE_BATCH = 200


@dataclass
class ItemAnalise:
    """Resultado da comparação de um produto (ou produto+lote) contado."""
    codigo: str
    descricao: str
    lote: str
    contado: float
    sistema: Optional[float]   # None quando situacao == "lote_novo" (não consultado)
    diferenca: Optional[float]  # None quando situacao == "lote_novo"
    situacao: str               # "confere" | "falta" | "sobra" | "lote_novo"
    grupo: str = ""


@dataclass
class ResultadoAnalise:
    """Resultado completo da análise: itens + totais agregados.

    ``total_itens`` conta **registros** (uma linha por produto+lote, que é
    como o estoque precisa ser comparado); ``total_produtos`` conta produtos
    distintos. Um produto com N lotes soma N registros e 1 produto — a mesma
    separação que o rodapé do PDF faz entre "Total de registros" e "Total de
    produtos contados".
    """
    itens: List[ItemAnalise] = field(default_factory=list)
    total_itens: int = 0
    total_produtos: int = 0
    total_confere: int = 0
    total_falta: int = 0
    total_sobra: int = 0
    total_lote_novo: int = 0


class StockAnalysisValidationError(ValueError):
    """Erro de validação bloqueante (empresa divergente entre PDFs, etc.)."""
    pass


class StockAnalysisService:
    """Compara contagens de PDF com o estoque do ERP."""

    # ------------------------------------------------------------------
    # Validação de empresa
    # ------------------------------------------------------------------

    def validar_empresa(self, contagens: List[ContagemPDF], codempresa_logada: str) -> None:
        """
        Garante que todos os PDFs são da mesma empresa, e que essa empresa é
        a que está logada no app.

        Raises:
            StockAnalysisValidationError: Com o detalhe de qual arquivo tem
                qual codempresa, se houver divergência.
        """
        if not contagens:
            raise StockAnalysisValidationError("Nenhum PDF anexado.")

        codempresa_logada = str(codempresa_logada or "").strip()
        divergentes = []
        for c in contagens:
            codempresa_pdf = str(c.codempresa or "").strip()
            if codempresa_pdf != codempresa_logada:
                divergentes.append((c.arquivo, codempresa_pdf))

        if divergentes:
            detalhe = "\n".join(f"  • {arq} → empresa {cod!r}" for arq, cod in divergentes)
            raise StockAnalysisValidationError(
                f"Empresa logada: {codempresa_logada!r}\n\n"
                f"PDF(s) de empresa diferente:\n{detalhe}"
            )

    # ------------------------------------------------------------------
    # Análise principal
    # ------------------------------------------------------------------

    def analisar(
        self,
        contagens: List[ContagemPDF],
        data_referencia: date,
        local_estoque: str,
        codempresa: str,
    ) -> ResultadoAnalise:
        """
        Compara os itens contados nos PDFs com o estoque do ERP.

        Args:
            contagens: PDFs já validados (mesma empresa).
            data_referencia: Data para a consulta de estoque histórico.
            local_estoque: 'L' (loja), 'D' (depósito), ou nome de local (modo "T").
            codempresa: Código da empresa (int como string).

        Returns:
            ``ResultadoAnalise`` com os itens comparados e totais.
        """
        itens_agrupados = self._agrupar_itens(contagens)
        codigos = sorted({codigo for codigo, _lote in itens_agrupados})

        with get_session() as session:
            controla_lote = self._buscar_controlarlote(session, codigos)

            sem_lote: List[Tuple[str, str]] = []
            com_lote: List[Tuple[str, str]] = []
            for chave in itens_agrupados:
                codigo, lote = chave
                if controla_lote.get(codigo, False) and lote:
                    com_lote.append(chave)
                else:
                    sem_lote.append(chave)

            lotes_existentes = self._buscar_lotes_existentes(session, codempresa, com_lote)

            com_lote_existente = [c for c in com_lote if c in lotes_existentes]
            lote_novo = [c for c in com_lote if c not in lotes_existentes]

            estoque_sem_lote = self._consultar_estoque_sem_lote(
                session, [c for c, _l in sem_lote], codempresa, data_referencia, local_estoque
            )
            estoque_com_lote = self._consultar_estoque_com_lote(
                session, com_lote_existente, codempresa, data_referencia, local_estoque
            )

        itens: List[ItemAnalise] = []
        totais = {"confere": 0, "falta": 0, "sobra": 0, "lote_novo": 0}

        for chave in sem_lote:
            codigo, lote = chave
            dados = itens_agrupados[chave]
            sistema = estoque_sem_lote.get(codigo, 0.0)
            self._adicionar_item(itens, totais, codigo, dados, lote, sistema)

        for chave in com_lote_existente:
            codigo, lote = chave
            dados = itens_agrupados[chave]
            sistema = estoque_com_lote.get(chave, 0.0)
            self._adicionar_item(itens, totais, codigo, dados, lote, sistema)

        for chave in lote_novo:
            codigo, lote = chave
            dados = itens_agrupados[chave]
            itens.append(ItemAnalise(
                codigo=codigo,
                descricao=dados["descricao"],
                lote=lote,
                contado=dados["contado"],
                sistema=None,
                diferenca=None,
                situacao="lote_novo",
                grupo=dados["grupo"],
            ))
            totais["lote_novo"] += 1

        return ResultadoAnalise(
            itens=itens,
            total_itens=len(itens),
            total_produtos=len({i.codigo for i in itens}),
            total_confere=totais["confere"],
            total_falta=totais["falta"],
            total_sobra=totais["sobra"],
            total_lote_novo=totais["lote_novo"],
        )

    @staticmethod
    def _adicionar_item(itens, totais, codigo, dados, lote, sistema):
        diferenca = dados["contado"] - sistema
        if diferenca == 0:
            situacao = "confere"
        elif diferenca < 0:
            situacao = "falta"
        else:
            situacao = "sobra"
        totais[situacao] += 1
        itens.append(ItemAnalise(
            codigo=codigo,
            descricao=dados["descricao"],
            lote=lote,
            contado=dados["contado"],
            sistema=sistema,
            diferenca=diferenca,
            situacao=situacao,
            grupo=dados["grupo"],
        ))

    # ------------------------------------------------------------------
    # Agrupamento dos itens de todos os PDFs anexados
    # ------------------------------------------------------------------

    @staticmethod
    def _agrupar_itens(contagens: List[ContagemPDF]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """
        Agrupa itens de todos os PDFs por (codigo, lote), somando a
        quantidade contada — vários PDFs podem cobrir partes diferentes da
        mesma contagem.
        """
        agrupados: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for contagem in contagens:
            for item in contagem.itens:
                chave = (item.codigo, item.lote)
                if chave not in agrupados:
                    agrupados[chave] = {
                        "descricao": item.descricao,
                        "grupo": item.grupo,
                        "contado": 0.0,
                    }
                agrupados[chave]["contado"] += item.qtde_contada
        return agrupados

    # ------------------------------------------------------------------
    # Consultas ao banco (SQLAlchemy Session + text(), padrão do projeto)
    # ------------------------------------------------------------------

    @staticmethod
    def _chunks(items: List, tamanho: int = _TAMANHO_LOTE_BATCH):
        for i in range(0, len(items), tamanho):
            yield items[i:i + tamanho]

    def _buscar_controlarlote(self, session, codigos: List[str]) -> Dict[str, bool]:
        """Lê ``produtos.controlarlote`` direto do banco, sem dedução."""
        resultado: Dict[str, bool] = {}
        if not codigos:
            return resultado
        stmt = text(
            "SELECT codproduto, controlarlote FROM produtos WHERE codproduto IN :codigos"
        ).bindparams(bindparam("codigos", expanding=True))
        for lote in self._chunks(codigos):
            for row in session.execute(stmt, {"codigos": lote}):
                resultado[row.codproduto] = bool(row.controlarlote)
        return resultado

    def _buscar_lotes_existentes(
        self, session, codempresa: str, pares: List[Tuple[str, str]]
    ) -> set:
        """Retorna o subconjunto de (codigo, numlote) que existe em ``produtoslote``."""
        existentes = set()
        if not pares:
            return existentes
        for lote_pares in self._chunks(pares):
            values_sql = ", ".join(
                f"(:c{i}, :l{i})" for i in range(len(lote_pares))
            )
            params: Dict[str, Any] = {"empresa": codempresa}
            for i, (codigo, numlote) in enumerate(lote_pares):
                params[f"c{i}"] = codigo
                params[f"l{i}"] = numlote
            sql = f"""
                SELECT v.codigo, v.numlote
                FROM produtoslote pl
                INNER JOIN (VALUES {values_sql}) AS v(codigo, numlote)
                    ON pl.codproduto = v.codigo AND pl.numlote = v.numlote
                WHERE pl.codempresa = :empresa
            """
            for row in session.execute(text(sql), params):
                existentes.add((row.codigo, row.numlote))
        return existentes

    def _consultar_estoque_sem_lote(
        self, session, codigos: List[str], codempresa: str, data_referencia: date, local_estoque: str
    ) -> Dict[str, float]:
        """Estoque de produtos sem controle de lote via ``csfEstoqueData``."""
        resultado: Dict[str, float] = {}
        codigos_unicos = sorted(set(codigos))
        if not codigos_unicos:
            return resultado
        for lote in self._chunks(codigos_unicos):
            values_sql = ", ".join(f"(:c{i})" for i in range(len(lote)))
            params: Dict[str, Any] = {
                "empresa": codempresa,
                "data": data_referencia,
                "local": local_estoque,
            }
            for i, codigo in enumerate(lote):
                params[f"c{i}"] = codigo
            sql = f"""
                SELECT v.codigo,
                       dbo.csfEstoqueData(v.codigo, :empresa, :data, :local) AS estoque
                FROM (VALUES {values_sql}) AS v(codigo)
            """
            for row in session.execute(text(sql), params):
                resultado[row.codigo] = float(row.estoque or 0)
        return resultado

    def _consultar_estoque_com_lote(
        self,
        session,
        pares: List[Tuple[str, str]],
        codempresa: str,
        data_referencia: date,
        local_estoque: str,
    ) -> Dict[Tuple[str, str], float]:
        """Estoque de produtos com lote existente via ``csfEstoqueDataLote``."""
        resultado: Dict[Tuple[str, str], float] = {}
        if not pares:
            return resultado
        for lote_pares in self._chunks(pares):
            values_sql = ", ".join(
                f"(:c{i}, :l{i})" for i in range(len(lote_pares))
            )
            params: Dict[str, Any] = {
                "empresa": codempresa,
                "data": data_referencia,
                "local": local_estoque,
            }
            for i, (codigo, numlote) in enumerate(lote_pares):
                params[f"c{i}"] = codigo
                params[f"l{i}"] = numlote
            sql = f"""
                SELECT v.codigo, v.numlote,
                       dbo.csfEstoqueDataLote(v.codigo, :empresa, :data, v.numlote, :local) AS estoque
                FROM (VALUES {values_sql}) AS v(codigo, numlote)
            """
            for row in session.execute(text(sql), params):
                resultado[(row.codigo, row.numlote)] = float(row.estoque or 0)
        return resultado

    # ------------------------------------------------------------------
    # Payload para a IA
    # ------------------------------------------------------------------

    def montar_payload_ia(
        self,
        resultado: ResultadoAnalise,
        empresa_nome: str,
        data_referencia: date,
        limite: Optional[int] = None,
    ) -> str:
        """
        Monta o texto enviado à IA: resumo agregado (sempre completo) + as N
        maiores divergências (``limite``; ``None`` = todas). Nunca inclui o
        PDF nem a tabela inteira.
        """
        linhas = [
            f"# Contagem — {empresa_nome} — {data_referencia.strftime('%d/%m/%Y')}",
            "",
            f"Produtos contados: {resultado.total_produtos}",
            f"Registros (produto+lote): {resultado.total_itens}",
            f"Conferem: {resultado.total_confere}",
            f"Divergências: {resultado.total_falta + resultado.total_sobra}"
            f"  (falta: {resultado.total_falta} · sobra: {resultado.total_sobra})",
            f"Lotes novos: {resultado.total_lote_novo}",
            "",
        ]

        divergentes = [i for i in resultado.itens if i.situacao in ("falta", "sobra")]
        divergentes.sort(key=lambda i: abs(i.diferenca or 0), reverse=True)
        if limite is not None:
            divergentes = divergentes[:limite]

        if divergentes:
            linhas.append("# Divergências")
            linhas.append("codproduto | descricao | grupo | contado | sistema | dif")
            for i in divergentes:
                linhas.append(
                    f"{i.codigo} | {i.descricao} | {i.grupo} | "
                    f"{i.contado:g} | {i.sistema:g} | {i.diferenca:+g}"
                )
            linhas.append("")

        lotes_novos = [i for i in resultado.itens if i.situacao == "lote_novo"]
        if lotes_novos:
            linhas.append("# Lotes sem cadastro")
            for i in lotes_novos:
                linhas.append(f"{i.codigo} | {i.lote} | {i.contado:g} unidades contadas")

        return "\n".join(linhas).strip()
