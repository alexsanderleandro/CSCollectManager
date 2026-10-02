"""
stock_analysis_service.py
==========================
Compara as contagens lidas dos ZIPs baixados (``Contagem``) com o estoque do
ERP e monta o texto que vai para a IA. A IA nunca recebe os arquivos nem a
tabela inteira — só o resumo agregado e as N maiores divergências.

Regras de negócio (definidas com o usuário):
- Código que não existe em ``produtos`` -> "sem cadastro", sem consultar
  estoque. Antes ele caía como produto sem lote, o estoque voltava 0 e o
  registro aparecia como sobra, misturando erro de cadastro com sobra física.
- Produto sem controle de lote  -> ``csfEstoqueData(@codproduto, @codempresa, @data, @localestoque)``.
- Produto com lote EXISTENTE    -> ``csfEstoqueDataLote(@codproduto, @codempresa, @data, @numlote, @localestoque)``.
- Produto com lote que NÃO existe em ``produtoslote`` -> marcado "lote novo",
  sem chamar função de estoque (a função devolve 0 silenciosamente para lote
  inexistente — não dá pra usar o retorno dela para decidir isso).
- ``controlarlote`` é lido direto de ``produtos`` — nunca deduzido de outra
  consulta (um produto pode controlar lote e ainda não ter nenhum lote batendo
  com um filtro qualquer).
- Valor da divergência = diferença × custo de ``produtosestoque`` (da empresa
  logada). O campo de custo é escolhido na tela; os cinco são lidos de uma vez,
  então trocar de campo não consulta o banco de novo.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text

from database.connection import get_session
from utils.logger import get_logger

logger = get_logger(__name__)

_TAMANHO_LOTE_BATCH = 200

# Máximo de contagens comparadas lado a lado — uma por coluna de contado na grade.
MAX_CONTAGENS_ANALISE = 3

# Campos de custo de ``produtosestoque`` que podem valorizar a divergência,
# na ordem em que aparecem no seletor da tela. O primeiro é o padrão.
CAMPOS_CUSTO = {
    "customedio": "Custo médio",
    "custoatual": "Custo atual",
    "customediocontabil": "Custo médio contábil",
    "custocontabil": "Custo contábil",
    "custoreposicao": "Custo de reposição",
}
CAMPO_CUSTO_PADRAO = "customedio"

# Situações comparadas com o sistema — as únicas que entram na acurácia.
SITUACOES_COMPARADAS = ("confere", "falta", "sobra")


@dataclass
class ItemAnalise:
    """Um registro (produto+lote) da grade.

    ``contados`` tem a quantidade de cada contagem, na ordem das colunas de
    contado (``None`` = aquela contagem não contou o registro). ``contado``,
    ``diferenca`` e ``situacao`` são os da coluna usada como base da
    diferença — preenchidos por ``StockAnalysisService.aplicar_base``.
    ``observacoes`` e ``sinais`` guardam o índice da coluna de origem.
    """
    codigo: str
    descricao: str
    lote: str
    contados: List[Optional[float]]
    sistema: Optional[float]    # None quando não consultado (lote novo ou sem cadastro)
    lote_novo: bool = False
    sem_cadastro: bool = False
    grupo: str = ""
    unidade: str = ""
    localizacoes: List[str] = field(default_factory=list)
    validade: Optional[date] = None
    observacoes: List[Tuple[int, str]] = field(default_factory=list)
    sinais: List[Tuple[int, str]] = field(default_factory=list)
    custos: Dict[str, Optional[float]] = field(default_factory=dict)
    contado: Optional[float] = None
    diferenca: Optional[float] = None
    # "confere" | "falta" | "sobra" | "lote_novo" | "sem_cadastro" | "nao_contado"
    situacao: str = ""
    custo: Optional[float] = None
    valor_diferenca: Optional[float] = None


@dataclass
class ResultadoAnalise:
    """Resultado completo da análise: itens + totais agregados.

    ``total_itens`` conta **registros** (uma linha por produto+lote, que é
    como o estoque precisa ser comparado); ``total_produtos`` conta produtos
    distintos.

    ``colunas`` tem o rótulo de cada coluna de contado ("Contado 014"), uma por
    contagem; ``indice_base`` diz qual delas é a base da diferença. Os totais
    por situação e em R$ são os da coluna base.
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
    total_sem_cadastro: int = 0
    total_nao_contado: int = 0
    campo_custo: str = CAMPO_CUSTO_PADRAO
    valor_falta: float = 0.0       # soma (negativa) do valor das faltas
    valor_sobra: float = 0.0       # soma (positiva) do valor das sobras
    divergencias_sem_custo: int = 0

    @property
    def valor_liquido(self) -> float:
        return self.valor_falta + self.valor_sobra

    @property
    def tem_valores(self) -> bool:
        """Algum registro tem custo no campo escolhido."""
        return any(i.custo is not None for i in self.itens)


@dataclass
class LinhaAcuracia:
    """Acurácia de um recorte (geral, um grupo ou uma localização).

    ``valor_total`` é o "Valor dos registros" da tela e ``valor_confere`` o
    "Valor dos que conferem"; ``itens`` guarda os registros somados, para a
    tela mostrar a conta registro a registro.
    """
    nome: str
    registros: int = 0          # comparados com o sistema
    conferem: int = 0
    valor_total: float = 0.0
    valor_confere: float = 0.0
    sem_custo: int = 0
    itens: List[ItemAnalise] = field(default_factory=list, repr=False)

    @property
    def pct_registros(self) -> Optional[float]:
        return 100.0 * self.conferem / self.registros if self.registros else None

    @property
    def pct_valor(self) -> Optional[float]:
        return 100.0 * self.valor_confere / self.valor_total if self.valor_total else None


@dataclass
class Acuracia:
    geral: LinhaAcuracia
    por_grupo: List[LinhaAcuracia]
    por_localizacao: List[LinhaAcuracia]


class StockAnalysisValidationError(ValueError):
    """Erro de validação bloqueante (contagem de outra empresa, etc.)."""
    pass


def formatar_moeda(valor: Optional[float], sinal: bool = False) -> str:
    """"R$ 1.234,56" (com "+"/"−" quando ``sinal``); "—" sem valor."""
    if valor is None:
        return "—"
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if valor < 0 and round(valor, 2) != 0:
        return f"−R$ {texto}"
    if sinal and round(valor, 2) != 0:
        return f"+R$ {texto}"
    return f"R$ {texto}"


def formatar_pct(valor: Optional[float]) -> str:
    return "—" if valor is None else f"{valor:.1f}%".replace(".", ",")


class StockAnalysisService:
    """Compara contagens com o estoque do ERP."""

    # ------------------------------------------------------------------
    # Validação de empresa
    # ------------------------------------------------------------------

    def validar_empresa(self, contagens: list, codempresa_logada: str) -> None:
        """
        Garante que todas as contagens são da empresa logada.

        Raises:
            StockAnalysisValidationError: Com o detalhe de qual arquivo tem
                qual codempresa, se houver divergência.
        """
        if not contagens:
            raise StockAnalysisValidationError("Nenhuma contagem selecionada.")

        codempresa_logada = str(codempresa_logada or "").strip()
        divergentes = []
        for c in contagens:
            codempresa_arquivo = str(c.codempresa or "").strip()
            if codempresa_arquivo != codempresa_logada:
                divergentes.append((c.arquivo, codempresa_arquivo))

        if divergentes:
            detalhe = "\n".join(f"  • {arq} → empresa {cod!r}" for arq, cod in divergentes)
            raise StockAnalysisValidationError(
                f"Empresa logada: {codempresa_logada!r}\n\n"
                f"Contagem(ns) de empresa diferente:\n{detalhe}"
            )

    # ------------------------------------------------------------------
    # Análise principal
    # ------------------------------------------------------------------

    def analisar(
        self,
        contagens: list,
        data_referencia: date,
        local_estoque: str,
        codempresa: str,
        campo_custo: str = CAMPO_CUSTO_PADRAO,
    ) -> ResultadoAnalise:
        """
        Compara os itens das contagens com o estoque do ERP.

        Args:
            contagens: Contagens já validadas (mesma empresa).
            data_referencia: Data para a consulta de estoque histórico.
            local_estoque: 'L' (loja), 'D' (depósito), ou nome de local (modo "T").
            codempresa: Código da empresa (int como string).
            campo_custo: Campo de ``CAMPOS_CUSTO`` usado no valor da divergência.

        Returns:
            ``ResultadoAnalise`` com os itens comparados e totais.
        """
        itens_agrupados = self._agrupar_itens(contagens)
        codigos = sorted({codigo for codigo, _lote in itens_agrupados})

        with get_session() as session:
            controla_lote = self._buscar_controlarlote(session, codigos)
            # `_buscar_controlarlote` só devolve os códigos que existem em `produtos`.
            cadastrados = set(controla_lote)

            sem_lote: List[Tuple[str, str]] = []
            com_lote: List[Tuple[str, str]] = []
            sem_cadastro: List[Tuple[str, str]] = []
            for chave in itens_agrupados:
                codigo, lote = chave
                if codigo not in cadastrados:
                    sem_cadastro.append(chave)
                elif controla_lote[codigo] and lote:
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
            custos = self._buscar_custos(session, codempresa, sorted(cadastrados))

        itens: List[ItemAnalise] = []

        def _novo_item(chave, sistema, eh_lote_novo=False, eh_sem_cadastro=False):
            codigo, lote = chave
            dados = itens_agrupados[chave]
            itens.append(ItemAnalise(
                codigo=codigo,
                descricao=dados["descricao"],
                lote=lote,
                contados=dados["contados"],
                sistema=sistema,
                lote_novo=eh_lote_novo,
                sem_cadastro=eh_sem_cadastro,
                grupo=dados["grupo"],
                unidade=dados["unidade"],
                localizacoes=sorted(dados["localizacoes"]),
                validade=dados["validade"],
                observacoes=dados["observacoes"],
                sinais=dados["sinais"],
                custos=custos.get(codigo, {}),
            ))

        for chave in sem_lote:
            _novo_item(chave, estoque_sem_lote.get(chave[0], 0.0))
        for chave in com_lote_existente:
            _novo_item(chave, estoque_com_lote.get(chave, 0.0))
        for chave in lote_novo:
            _novo_item(chave, None, eh_lote_novo=True)
        for chave in sem_cadastro:
            _novo_item(chave, None, eh_sem_cadastro=True)

        resultado = ResultadoAnalise(
            itens=itens,
            colunas=self.rotulos_colunas(contagens),
            total_itens=len(itens),
            total_produtos=len({i.codigo for i in itens}),
            campo_custo=campo_custo if campo_custo in CAMPOS_CUSTO else CAMPO_CUSTO_PADRAO,
        )
        self.aplicar_base(resultado, 0)
        return resultado

    @classmethod
    def aplicar_base(cls, resultado: ResultadoAnalise, indice: int) -> None:
        """Recalcula contado, diferença, situação, valores e totais usando a
        coluna de contado ``indice`` como base. Não consulta o banco: o
        estoque do sistema é o mesmo para qualquer coluna."""
        totais = {s: 0 for s in ("confere", "falta", "sobra", "lote_novo", "sem_cadastro", "nao_contado")}
        for item in resultado.itens:
            contado = item.contados[indice] if indice < len(item.contados) else None
            item.contado = contado
            if contado is None:
                # A contagem base não contou este registro (só outra contou):
                # não há o que comparar com o sistema.
                item.diferenca = None
                item.situacao = "nao_contado"
            elif item.sem_cadastro:
                item.diferenca = None
                item.situacao = "sem_cadastro"
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
        resultado.total_sem_cadastro = totais["sem_cadastro"]
        resultado.total_nao_contado = totais["nao_contado"]
        cls._recalcular_valores(resultado)

    @classmethod
    def aplicar_custo(cls, resultado: ResultadoAnalise, campo: str) -> None:
        """Troca o campo de custo e recalcula os valores (sem ir ao banco)."""
        resultado.campo_custo = campo if campo in CAMPOS_CUSTO else CAMPO_CUSTO_PADRAO
        cls._recalcular_valores(resultado)

    @staticmethod
    def _recalcular_valores(resultado: ResultadoAnalise) -> None:
        falta = sobra = 0.0
        sem_custo = 0
        for item in resultado.itens:
            item.custo = item.custos.get(resultado.campo_custo)
            if item.diferenca is None or item.custo is None:
                item.valor_diferenca = None
            else:
                item.valor_diferenca = item.diferenca * item.custo
            if item.situacao in ("falta", "sobra"):
                if item.valor_diferenca is None:
                    sem_custo += 1
                elif item.valor_diferenca < 0:
                    falta += item.valor_diferenca
                else:
                    sobra += item.valor_diferenca
        resultado.valor_falta = falta
        resultado.valor_sobra = sobra
        resultado.divergencias_sem_custo = sem_custo

    @staticmethod
    def rotulos_colunas(contagens: list) -> List[str]:
        """"Contado <codvendedor>" por contagem. O mesmo vendedor em mais de
        uma contagem (uma recontagem, por exemplo) ganha a hora da exportação
        no rótulo, para as colunas não ficarem com o mesmo nome."""
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
    # Acurácia
    # ------------------------------------------------------------------

    @staticmethod
    def quantidade_valor(item: ItemAnalise) -> Tuple[float, str]:
        """Quantidade que entra no valor do registro na acurácia: a maior entre
        contado e sistema, sem sinal. Devolve também de onde ela veio
        ("contado" ou "sistema"; vazio quando as duas são iguais, como num
        registro que confere)."""
        contado = abs(item.contado or 0)
        sistema = abs(item.sistema or 0)
        if contado == sistema:
            return contado, ""
        return (contado, "contado") if contado > sistema else (sistema, "sistema")

    @classmethod
    def valor_acuracia(cls, item: ItemAnalise) -> Optional[float]:
        """Valor do registro na acurácia: custo × ``quantidade_valor``. Usar a
        maior quantidade faz uma sobra de item que o sistema dá como zerado
        também pesar, e uma falta e uma sobra do mesmo item pesarem igual.
        ``None`` quando o produto não tem custo no campo escolhido."""
        if item.custo is None:
            return None
        return abs(item.custo) * cls.quantidade_valor(item)[0]

    @classmethod
    def calcular_acuracia(cls, resultado: ResultadoAnalise) -> Acuracia:
        """Percentual de registros que conferem, em quantidade e em valor,
        no geral, por grupo e por localização.

        Só entram os registros comparados com o sistema (conferem, falta e
        sobra). Em valor, cada registro vale ``valor_acuracia``; registro sem
        custo fica fora das somas em valor (conta só em quantidade). Registro
        contado em duas localizações entra nas duas.
        """
        geral = LinhaAcuracia("Geral")
        grupos: Dict[str, LinhaAcuracia] = {}
        locais: Dict[str, LinhaAcuracia] = {}

        for item in resultado.itens:
            if item.situacao not in SITUACOES_COMPARADAS:
                continue
            confere = item.situacao == "confere"
            valor = cls.valor_acuracia(item)
            linhas = [geral, grupos.setdefault(item.grupo or "(sem grupo)",
                                               LinhaAcuracia(item.grupo or "(sem grupo)"))]
            for loc in (item.localizacoes or ["(sem localização)"]):
                linhas.append(locais.setdefault(loc, LinhaAcuracia(loc)))
            for linha in linhas:
                linha.registros += 1
                linha.conferem += 1 if confere else 0
                linha.itens.append(item)
                if valor is None:
                    linha.sem_custo += 1
                else:
                    linha.valor_total += valor
                    linha.valor_confere += valor if confere else 0.0

        def _ordenadas(d):
            return sorted(d.values(), key=lambda linha: linha.nome.lower())

        return Acuracia(geral, _ordenadas(grupos), _ordenadas(locais))

    # ------------------------------------------------------------------
    # Agrupamento dos itens de todas as contagens
    # ------------------------------------------------------------------

    @staticmethod
    def _agrupar_itens(contagens: list) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """
        Agrupa os itens por (codigo, lote), com a quantidade de cada contagem
        separada (``contados``, na ordem das contagens; ``None`` = não contado
        naquela contagem). Dentro da mesma contagem as quantidades são
        somadas: o mesmo produto+lote pode aparecer em mais de uma localização.
        """
        agrupados: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for indice, contagem in enumerate(contagens):
            sinais_entrada = getattr(contagem, "sinais_entrada", {}) or {}
            for item in contagem.itens:
                chave = (item.codigo, item.lote)
                if chave not in agrupados:
                    agrupados[chave] = {
                        "descricao": item.descricao,
                        "grupo": item.grupo,
                        "unidade": item.unidade,
                        "contados": [None] * len(contagens),
                        "localizacoes": set(),
                        "validade": None,
                        "observacoes": [],
                        "sinais": [],
                    }
                dados = agrupados[chave]
                contados = dados["contados"]
                contados[indice] = (contados[indice] or 0.0) + item.qtde_contada
                if not dados["grupo"] and item.grupo:
                    dados["grupo"] = item.grupo
                if item.localizacao:
                    dados["localizacoes"].add(item.localizacao)
                if dados["validade"] is None and item.validade:
                    dados["validade"] = item.validade
                for texto in (item.observacao_produto, item.observacao):
                    if texto and (indice, texto) not in dados["observacoes"]:
                        dados["observacoes"].append((indice, texto))
                for sinal in sinais_entrada.get(item.codigo, []):
                    if (indice, sinal) not in dados["sinais"]:
                        dados["sinais"].append((indice, sinal))
        return agrupados

    # ------------------------------------------------------------------
    # Consultas ao banco (SQLAlchemy Session + text(), padrão do projeto)
    # ------------------------------------------------------------------

    @staticmethod
    def _chunks(items: List, tamanho: int = _TAMANHO_LOTE_BATCH):
        for i in range(0, len(items), tamanho):
            yield items[i:i + tamanho]

    def _buscar_controlarlote(self, session, codigos: List[str]) -> Dict[str, bool]:
        """Lê ``produtos.controlarlote`` direto do banco, sem dedução. Código
        ausente do resultado = não existe em ``produtos``."""
        resultado: Dict[str, bool] = {}
        if not codigos:
            return resultado
        stmt = text(
            "SELECT codproduto, controlarlote FROM produtos WHERE codproduto IN :codigos"
        ).bindparams(bindparam("codigos", expanding=True))
        for lote in self._chunks(codigos):
            for row in session.execute(stmt, {"codigos": lote}):
                resultado[str(row.codproduto).strip()] = bool(row.controlarlote)
        return resultado

    def _buscar_custos(self, session, codempresa: str, codigos: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """Os campos de ``CAMPOS_CUSTO`` de ``produtosestoque`` para a empresa.

        Nem toda versão do ERP tem os cinco campos: os que existem são
        descobertos antes, e um campo ausente fica sem custo em vez de
        derrubar a análise. Uma falha aqui também não derruba: a grade sai
        sem valores em R$.
        """
        resultado: Dict[str, Dict[str, Optional[float]]] = {}
        if not codigos:
            return resultado
        try:
            existentes = {
                str(row[0]).lower()
                for row in session.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE LOWER(TABLE_NAME) = 'produtosestoque'"
                ))
            }
            campos = [c for c in CAMPOS_CUSTO if c in existentes]
            if not campos:
                logger.warning("produtosestoque sem nenhum campo de custo conhecido")
                return resultado
            stmt = text(
                f"SELECT codproduto, {', '.join(campos)} FROM produtosestoque "
                f"WHERE codempresa = :empresa AND codproduto IN :codigos"
            ).bindparams(bindparam("codigos", expanding=True))
            for lote in self._chunks(codigos):
                for row in session.execute(stmt, {"empresa": codempresa, "codigos": lote}):
                    valores = row._mapping
                    resultado[str(valores["codproduto"]).strip()] = {
                        c: (float(valores[c]) if valores[c] is not None else None) for c in campos
                    }
        except Exception as exc:
            logger.error(f"Erro ao buscar custos em produtosestoque: {exc}")
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
    # Texto para a IA
    # ------------------------------------------------------------------

    @staticmethod
    def chave_valor(item: ItemAnalise) -> Tuple[float, float]:
        """Ordem de prioridade das divergências: maior valor em R$ primeiro
        (falta ou sobra), depois maior diferença em quantidade."""
        return (abs(item.valor_diferenca or 0.0), abs(item.diferenca or 0.0))

    @staticmethod
    def texto_por_coluna(pares: List[Tuple[int, str]], colunas: List[str], indices: List[int]) -> str:
        """Junta observações/sinais; com mais de uma contagem, cada texto leva
        o rótulo da contagem de origem ("014: …")."""
        pares = [(i, t) for i, t in pares if i in indices]
        if len({i for i, _t in pares}) <= 1 and len(indices) <= 1:
            return "; ".join(t for _i, t in pares)
        return "; ".join(f"{colunas[i].replace('Contado ', '')}: {t}" for i, t in pares)

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
        maiores divergências em valor (``limite``; ``None`` = todas). Nunca
        inclui os arquivos nem a tabela inteira.

        ``colunas`` = índices das colunas de contado a considerar (``None`` =
        todas). A coluna base entra sempre: é ela que define as divergências.
        """
        indices = self._indices(resultado, colunas)
        rotulo_base = resultado.colunas[resultado.indice_base] if resultado.colunas else "Contado"
        nome_custo = CAMPOS_CUSTO.get(resultado.campo_custo, resultado.campo_custo)

        linhas = self._linhas_resumo(resultado, empresa_nome, data_referencia, indices)
        linhas.append("")

        divergentes = [i for i in resultado.itens if i.situacao in ("falta", "sobra")]
        divergentes.sort(key=self.chave_valor, reverse=True)
        if limite is not None:
            divergentes = divergentes[:limite]

        cab_contados = " | ".join(resultado.colunas[i].lower() for i in indices)
        if divergentes:
            linhas.append(f"# Divergências em ordem de valor (diferença = {rotulo_base} − sistema; "
                          f"valor = diferença × {nome_custo.lower()})")
            linhas.append(f"codproduto | descricao | lote | grupo | localizacao | {cab_contados} | "
                          f"sistema | dif | valor | entrada | observacoes")
            for i in divergentes:
                linhas.append(self._linha_item(resultado, i, indices))
            linhas.append("")

        lotes_novos = [i for i in resultado.itens if i.situacao == "lote_novo"]
        if lotes_novos:
            linhas.append("# Lotes sem cadastro no ERP (contados, mas o lote não existe)")
            linhas.append(f"codproduto | descricao | lote | {cab_contados}")
            for i in lotes_novos:
                linhas.append(f"{i.codigo} | {i.descricao} | {i.lote} | {self._contados(i, indices)}")
            linhas.append("")

        sem_cadastro = [i for i in resultado.itens if i.situacao == "sem_cadastro"]
        if sem_cadastro:
            linhas.append("# Produtos sem cadastro no ERP (código contado que não existe em produtos; "
                          "não é sobra física)")
            linhas.append(f"codproduto | descricao | {cab_contados}")
            for i in sem_cadastro:
                linhas.append(f"{i.codigo} | {i.descricao} | {self._contados(i, indices)}")

        return "\n".join(linhas).strip()

    def montar_payload_produto(
        self, resultado: ResultadoAnalise, codigo: str, data_referencia: date,
        colunas: Optional[List[int]] = None,
    ) -> str:
        """Todos os registros (lotes) de um produto, com tudo o que a grade
        sabe dele — para o aprofundamento "Explicar um produto"."""
        indices = self._indices(resultado, colunas)
        itens = [i for i in resultado.itens if i.codigo == codigo]
        if not itens:
            return ""
        cab_contados = " | ".join(resultado.colunas[i].lower() for i in indices)
        nome_custo = CAMPOS_CUSTO.get(resultado.campo_custo, resultado.campo_custo)
        custo = next((i.custo for i in itens if i.custo is not None), None)
        linhas = [
            f"# Produto {codigo} — {itens[0].descricao}",
            f"Grupo: {itens[0].grupo or '—'} · unidade: {itens[0].unidade or '—'} · "
            f"{nome_custo.lower()}: {formatar_moeda(custo)}",
            f"Estoque do sistema em {data_referencia:%d/%m/%Y}",
            f"lote | validade | localizacao | {cab_contados} | sistema | dif | valor | situacao | "
            f"entrada | observacoes",
        ]
        for i in itens:
            linhas.append(" | ".join([
                i.lote or "—",
                f"{i.validade:%d/%m/%Y}" if i.validade else "—",
                ", ".join(i.localizacoes) or "—",
                self._contados(i, indices),
                self._qtd(i.sistema),
                self._qtd(i.diferenca, sinal=True),
                formatar_moeda(i.valor_diferenca, sinal=True),
                i.situacao.replace("_", " "),
                self.texto_por_coluna(i.sinais, resultado.colunas, indices) or "—",
                self.texto_por_coluna(i.observacoes, resultado.colunas, indices) or "—",
            ]))
        return "\n".join(linhas)

    def montar_payload_discordancias(
        self, resultado: ResultadoAnalise, colunas: Optional[List[int]] = None,
    ) -> str:
        """Registros em que as contagens consideradas não batem entre si
        (inclusive contado numa e ausente noutra) — para o aprofundamento
        "Onde os conferentes discordam"."""
        indices = self._indices(resultado, colunas)
        if len(indices) < 2:
            return ""
        discordantes = [
            i for i in resultado.itens
            if len({i.contados[c] for c in indices}) > 1
        ]
        cab_contados = " | ".join(resultado.colunas[i].lower() for i in indices)
        linhas = [f"# Registros em que as contagens discordam ({len(discordantes)} de "
                  f"{resultado.total_itens})"]
        if not discordantes:
            linhas.append("Nenhum: todas as contagens chegaram aos mesmos números.")
            return "\n".join(linhas)
        linhas.append(f"codproduto | descricao | lote | grupo | localizacao | {cab_contados} | "
                      f"sistema | entrada | observacoes")
        discordantes.sort(key=lambda i: max(abs((i.contados[a] or 0) - (i.contados[b] or 0))
                                            for a in indices for b in indices), reverse=True)
        for i in discordantes:
            linhas.append(" | ".join([
                i.codigo, i.descricao, i.lote or "—", i.grupo or "—", ", ".join(i.localizacoes) or "—",
                self._contados(i, indices), self._qtd(i.sistema),
                self.texto_por_coluna(i.sinais, resultado.colunas, indices) or "—",
                self.texto_por_coluna(i.observacoes, resultado.colunas, indices) or "—",
            ]))
        return "\n".join(linhas)

    # ----- auxiliares do texto -----

    @staticmethod
    def _indices(resultado: ResultadoAnalise, colunas: Optional[List[int]]) -> List[int]:
        base = resultado.indice_base
        indices = list(range(len(resultado.colunas))) if colunas is None else list(colunas)
        if base not in indices:
            indices.insert(0, base)
        return indices

    @staticmethod
    def _qtd(v: Optional[float], sinal: bool = False) -> str:
        if v is None:
            return "—"
        return f"{v:+g}" if sinal else f"{v:g}"

    def _contados(self, item: ItemAnalise, indices: List[int]) -> str:
        return " | ".join(self._qtd(item.contados[c]) for c in indices)

    def _linha_item(self, resultado: ResultadoAnalise, i: ItemAnalise, indices: List[int]) -> str:
        return " | ".join([
            i.codigo, i.descricao, i.lote or "—", i.grupo or "—", ", ".join(i.localizacoes) or "—",
            self._contados(i, indices), self._qtd(i.sistema), self._qtd(i.diferenca, sinal=True),
            formatar_moeda(i.valor_diferenca, sinal=True),
            self.texto_por_coluna(i.sinais, resultado.colunas, indices) or "—",
            self.texto_por_coluna(i.observacoes, resultado.colunas, indices) or "—",
        ])

    def _linhas_resumo(self, resultado: ResultadoAnalise, empresa_nome: str,
                       data_referencia: date, indices: List[int]) -> List[str]:
        rotulo_base = resultado.colunas[resultado.indice_base] if resultado.colunas else "Contado"
        nome_custo = CAMPOS_CUSTO.get(resultado.campo_custo, resultado.campo_custo)
        acuracia = self.calcular_acuracia(resultado).geral
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
        ]
        if resultado.tem_valores:
            linhas.append(
                f"Valor das divergências ({nome_custo.lower()}): falta {formatar_moeda(resultado.valor_falta)}"
                f" · sobra {formatar_moeda(resultado.valor_sobra)}"
                f" · saldo líquido {formatar_moeda(resultado.valor_liquido, sinal=True)}"
            )
            if resultado.divergencias_sem_custo:
                linhas.append(f"Divergências sem custo cadastrado (fora dos valores): "
                              f"{resultado.divergencias_sem_custo}")
        linhas.append(f"Acurácia: {formatar_pct(acuracia.pct_registros)} dos registros comparados"
                      + (f" · {formatar_pct(acuracia.pct_valor)} do valor" if acuracia.pct_valor is not None else ""))
        linhas.append(f"Lotes novos (lote sem cadastro): {resultado.total_lote_novo}")
        if resultado.total_sem_cadastro:
            linhas.append(f"Produtos sem cadastro no ERP: {resultado.total_sem_cadastro}")
        if resultado.total_nao_contado:
            linhas.append(f"Não contados em {rotulo_base} (só em outra contagem): "
                          f"{resultado.total_nao_contado}")
        return linhas
