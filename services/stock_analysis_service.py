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

# Máximo de PDFs comparados lado a lado — um por coluna de contado na grade.
MAX_PDFS_ANALISE = 3


@dataclass
class ItemAnalise:
    """Um registro (produto+lote) da grade.

    ``contados`` tem a quantidade de cada PDF, na ordem das colunas de
    contado (``None`` = aquele PDF não contou o registro). ``contado``,
    ``diferenca`` e ``situacao`` são os da coluna usada como base da
    diferença — preenchidos por ``StockAnalysisService.aplicar_base``.
    """
    codigo: str
    descricao: str
    lote: str
    contados: List[Optional[float]]
    sistema: Optional[float]    # None quando o lote não existe no ERP (não consultado)
    lote_novo: bool = False
    grupo: str = ""
    contado: Optional[float] = None
    diferenca: Optional[float] = None
    # "confere" | "falta" | "sobra" | "lote_novo" | "nao_contado"
    situacao: str = ""


@dataclass
class ResultadoAnalise:
    """Resultado completo da análise: itens + totais agregados.

    ``total_itens`` conta **registros** (uma linha por produto+lote, que é
    como o estoque precisa ser comparado); ``total_produtos`` conta produtos
    distintos. Um produto com N lotes soma N registros e 1 produto — a mesma
    separação que o rodapé do PDF faz entre "Total de registros" e "Total de
    produtos contados".

    ``colunas`` tem o rótulo de cada coluna de contado ("Contado 014"), um por
    PDF; ``indice_base`` diz qual delas é a base da diferença. Os totais por
    situação são os da coluna base.
    """
    itens: List[ItemAnalise] = field(default_factory=list)
    colunas: List[str] = field(default_factory=list)
    indice_base: int = 0
    total_itens: int = 0
    total_produtos: int = 0
    total_confere: int = 0
    total_falta: int = 0
    total_sobra: int = 0
    total_lote_novo: int = 0
    total_nao_contado: int = 0


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

        def _novo_item(chave, sistema, eh_lote_novo=False):
            codigo, lote = chave
            dados = itens_agrupados[chave]
            itens.append(ItemAnalise(
                codigo=codigo,
                descricao=dados["descricao"],
                lote=lote,
                contados=dados["contados"],
                sistema=sistema,
                lote_novo=eh_lote_novo,
                grupo=dados["grupo"],
            ))

        for chave in sem_lote:
            _novo_item(chave, estoque_sem_lote.get(chave[0], 0.0))
        for chave in com_lote_existente:
            _novo_item(chave, estoque_com_lote.get(chave, 0.0))
        for chave in lote_novo:
            _novo_item(chave, None, eh_lote_novo=True)

        resultado = ResultadoAnalise(
            itens=itens,
            colunas=self.rotulos_colunas(contagens),
            total_itens=len(itens),
            total_produtos=len({i.codigo for i in itens}),
        )
        self.aplicar_base(resultado, 0)
        return resultado

    @staticmethod
    def aplicar_base(resultado: ResultadoAnalise, indice: int) -> None:
        """Recalcula contado, diferença, situação e totais usando a coluna de
        contado ``indice`` como base. Não consulta o banco: o estoque do
        sistema é o mesmo para qualquer coluna."""
        totais = {"confere": 0, "falta": 0, "sobra": 0, "lote_novo": 0, "nao_contado": 0}
        for item in resultado.itens:
            contado = item.contados[indice] if indice < len(item.contados) else None
            item.contado = contado
            if contado is None:
                # O PDF base não contou este registro (só outro PDF contou):
                # não há o que comparar com o sistema.
                item.diferenca = None
                item.situacao = "nao_contado"
            elif item.lote_novo:
                item.diferenca = None
                item.situacao = "lote_novo"
            else:
                item.diferenca = contado - item.sistema
                if item.diferenca == 0:
                    item.situacao = "confere"
                elif item.diferenca < 0:
                    item.situacao = "falta"
                else:
                    item.situacao = "sobra"
            totais[item.situacao] += 1

        resultado.indice_base = indice
        resultado.total_confere = totais["confere"]
        resultado.total_falta = totais["falta"]
        resultado.total_sobra = totais["sobra"]
        resultado.total_lote_novo = totais["lote_novo"]
        resultado.total_nao_contado = totais["nao_contado"]

    @staticmethod
    def rotulos_colunas(contagens: List[ContagemPDF]) -> List[str]:
        """"Contado <codvendedor>" por PDF. O mesmo vendedor em mais de um PDF
        (uma recontagem, por exemplo) ganha a hora da exportação no rótulo, para
        as colunas não ficarem com o mesmo nome."""
        codigos = [str(c.codvendedor or "").strip() or "?" for c in contagens]
        rotulos = []
        for c, cod in zip(contagens, codigos):
            rotulo = f"Contado {cod}"
            if codigos.count(cod) > 1:
                rotulo += f" · {c.data_exportacao:%H:%M}"
            rotulos.append(rotulo)
        for i, rotulo in enumerate(rotulos):
            if rotulos.count(rotulo) > 1:  # mesmo vendedor e mesma hora
                rotulos[i] = f"{rotulo} ({rotulos[:i + 1].count(rotulo)})"
        return rotulos

    # ------------------------------------------------------------------
    # Agrupamento dos itens de todos os PDFs anexados
    # ------------------------------------------------------------------

    @staticmethod
    def _agrupar_itens(contagens: List[ContagemPDF]) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """
        Agrupa os itens por (codigo, lote), com a quantidade de cada PDF
        separada (``contados``, na ordem dos PDFs; ``None`` = não contado
        naquele PDF). Dentro do mesmo PDF as quantidades são somadas: o mesmo
        produto+lote pode aparecer em mais de uma localização.
        """
        agrupados: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for indice, contagem in enumerate(contagens):
            for item in contagem.itens:
                chave = (item.codigo, item.lote)
                if chave not in agrupados:
                    agrupados[chave] = {
                        "descricao": item.descricao,
                        "grupo": item.grupo,
                        "contados": [None] * len(contagens),
                    }
                contados = agrupados[chave]["contados"]
                contados[indice] = (contados[indice] or 0.0) + item.qtde_contada
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
        colunas: Optional[List[int]] = None,
    ) -> str:
        """
        Monta o texto enviado à IA: resumo agregado (sempre completo) + as N
        maiores divergências (``limite``; ``None`` = todas). Nunca inclui o
        PDF nem a tabela inteira.

        ``colunas`` = índices das colunas de contado a considerar (``None`` =
        todas). A coluna base entra sempre: é ela que define as divergências.
        """
        base = resultado.indice_base
        indices = list(range(len(resultado.colunas))) if colunas is None else list(colunas)
        if base not in indices:
            indices.insert(0, base)
        rotulo_base = resultado.colunas[base] if resultado.colunas else "Contado"

        def _qtd(v):
            return "—" if v is None else f"{v:g}"

        linhas = [
            f"# Contagem — {empresa_nome} — {data_referencia.strftime('%d/%m/%Y')}",
            "",
            f"Contagens consideradas: {', '.join(resultado.colunas[i] for i in indices)}",
            f"Base da diferença: {rotulo_base}",
            f"Produtos contados: {resultado.total_produtos}",
            f"Registros (produto+lote): {resultado.total_itens}",
            f"Conferem: {resultado.total_confere}",
            f"Divergências: {resultado.total_falta + resultado.total_sobra}"
            f"  (falta: {resultado.total_falta} · sobra: {resultado.total_sobra})",
            f"Lotes novos: {resultado.total_lote_novo}",
        ]
        if resultado.total_nao_contado:
            linhas.append(f"Não contados em {rotulo_base} (só em outra contagem): "
                          f"{resultado.total_nao_contado}")
        linhas.append("")

        divergentes = [i for i in resultado.itens if i.situacao in ("falta", "sobra")]
        divergentes.sort(key=lambda i: abs(i.diferenca or 0), reverse=True)
        if limite is not None:
            divergentes = divergentes[:limite]

        cab_contados = " | ".join(resultado.colunas[i].lower() for i in indices)
        if divergentes:
            linhas.append(f"# Divergências (diferença = {rotulo_base} − sistema)")
            linhas.append(f"codproduto | descricao | grupo | {cab_contados} | sistema | dif")
            for i in divergentes:
                contados = " | ".join(_qtd(i.contados[c]) for c in indices)
                linhas.append(
                    f"{i.codigo} | {i.descricao} | {i.grupo} | "
                    f"{contados} | {i.sistema:g} | {i.diferenca:+g}"
                )
            linhas.append("")

        lotes_novos = [i for i in resultado.itens if i.situacao == "lote_novo"]
        if lotes_novos:
            linhas.append("# Lotes sem cadastro")
            linhas.append(f"codproduto | lote | {cab_contados}")
            for i in lotes_novos:
                contados = " | ".join(_qtd(i.contados[c]) for c in indices)
                linhas.append(f"{i.codigo} | {i.lote} | {contados}")

        return "\n".join(linhas).strip()
