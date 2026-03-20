"""
product_service.py
==================
Serviço para consulta de produtos com filtros dinâmicos.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import date

from database.connection import get_session
from sqlalchemy import text


@dataclass
class ProductFilter:
    """Filtros para consulta de produtos."""
    produtos: Optional[List] = None               # Lista de códigos de produto (str ou int, conforme o banco)
    grupos: Optional[List] = None                 # Lista de códigos de grupo (str ou int, conforme o banco)
    fornecedor: Optional[List] = None             # Lista de códigos de fornecedor (pe.codfornecedor — int)
    fabricante: Optional[List] = None             # Lista de códigos de fabricante — int
    localizacoes: Optional[List[str]] = None      # Lista de localizações (texto)
    tipos_produto: Optional[List] = None          # Lista de códigos de tipo (str ou int, conforme o banco)

    # Filtros adicionais do painel
    local_estoque: str = "loja"          # "loja" | "deposito"
    filtro_localizacao: str = "ambos"    # "com" | "sem" | "ambos"
    filtro_estoque: str = "todos"        # "negativo" | "positivo" | "zerado" | "todos"
    filtro_encomenda: str = "ambos"      # "somente_encomenda" | "somente_nao_encomenda" | "ambos"
    somente_peso_variavel: bool = False  # p.PesoVariavel = 1
    somente_venda: bool = False          # pe.CompoeVenda = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductFilter":
        """Cria filtro a partir de dicionário."""
        return cls(
            produtos=data.get("produtos"),
            grupos=data.get("grupos"),
            fornecedor=data.get("fornecedor"),
            fabricante=data.get("fabricante"),
            localizacoes=data.get("localizacoes"),
            tipos_produto=data.get("tipos_produto"),
            local_estoque=data.get("local_estoque", "loja"),
            filtro_localizacao=data.get("filtro_localizacao", "ambos"),
            filtro_estoque=data.get("filtro_estoque", "todos"),
            filtro_encomenda=data.get("filtro_encomenda", "ambos"),
            somente_peso_variavel=bool(data.get("somente_peso_variavel", False)),
            somente_venda=bool(data.get("somente_venda", False)),
        )


class ProductService:
    """
    Serviço para consulta de produtos.
    
    Responsabilidades:
    - Montar SQL dinâmico baseado nos filtros
    - Aplicar regras de negócio (ativos, com EAN)
    - Calcular estoque total (depósito + loja)
    - Preparar dados para a grid
    
    Tabelas de referência:
    - produtos: codproduto, descricaoproduto, unidade, codgrupo, controlarestoque, codeanunidade, codtipoproduto, PesoVariavel
    - produtosestoque: codempresa, codproduto, situacao ('A'), localizacao, estoquedeposito, estoqueloja, codfornecedor, CompoeVenda, EncomendaSN
    - LocalEstoque: codlocal, NomeLocalEstoque
    - GrupoEstoque: codgrupo, NomeGrupo, chavegrupo, ordemnomegrupo
    """
    
    # Query base com regras fixas
    _BASE_QUERY = """
        SELECT 
            p.codproduto,
            p.descricaoproduto,
            COALESCE(p.codeanunidade, '') AS codeanunidade,
            p.unidade,
            p.codgrupo,
            COALESCE(g.NomeGrupo, '') AS nomegrupo,
            COALESCE(le.NomeLocalEstoque, '') AS nomeLocalEstoque,
            COALESCE(pe.estoqueloja, 0) AS estoqueloja,
            COALESCE(pe.estoquedeposito, 0) AS estoquedeposito,
            (COALESCE(pe.estoqueloja, 0) + COALESCE(pe.estoquedeposito, 0)) AS estoque,
            COALESCE(pe.codfornecedor, 0) AS codfornecedor,
            p.codtipoproduto,
            COALESCE(p.PesoVariavel, 0) AS pesovariavel,
            COALESCE(pe.CompoeVenda, 0) AS compoevenda,
            COALESCE(pe.EncomendaSN, 0) AS encomenda,
            pe.localizacao,
            CASE WHEN COALESCE(p.controlarlote, 0) <> 0
                 THEN COALESCE(lote.numlote, '')
                 ELSE '' END AS numlote,
            CASE WHEN COALESCE(p.controlarlote, 0) <> 0
                 THEN lote.datafabricacao
                 ELSE NULL END AS datafabricacao,
            CASE WHEN COALESCE(p.controlarlote, 0) <> 0
                 THEN lote.datavalidade
                 ELSE NULL END AS datavalidade
        FROM produtosestoque pe
        INNER JOIN produtos p ON p.codproduto = pe.codproduto
        LEFT JOIN GrupoEstoque g ON g.codgrupo = p.codgrupo
        LEFT JOIN LocalEstoque le ON le.NomeLocalEstoque = pe.localizacao
        OUTER APPLY (
            SELECT TOP 1
                pl.numlote,
                pl.datafabricacao,
                pl.datavalidade
            FROM produtoslote pl
            WHERE pl.codproduto = pe.codproduto
              AND pl.codempresa = pe.codempresa
            ORDER BY pl.datavalidade DESC
        ) AS lote
        WHERE pe.situacao = 'A'
          AND p.controlarestoque = 1
          AND ISNULL(p.codeanunidade, '') <> ''
    """
    
    # Query de contagem
    _COUNT_QUERY = """
        SELECT COUNT(*) AS total
        FROM produtosestoque pe
        INNER JOIN produtos p ON p.codproduto = pe.codproduto
        WHERE pe.situacao = 'A'
          AND p.controlarestoque = 1
          AND ISNULL(p.codeanunidade, '') <> ''
    """
    
    def __init__(self):
        """Inicializa o serviço."""
        pass
    
    def get_products(
        self, 
        filters: Optional[ProductFilter] = None
    ) -> List[Dict[str, Any]]:
        """
        Busca produtos com filtros aplicados.
        
        Args:
            filters: Filtros opcionais para a consulta
            
        Returns:
            Lista de produtos preparados para a grid
        """
        query, params = self._build_query(filters)
        
        try:
            with get_session() as session:
                result = session.execute(text(query), params)
                
                products = []
                for row in result:
                    products.append(self._row_to_dict(row))
                
                return products
                
        except Exception as e:
            print(f"Erro ao buscar produtos: {e}")
            raise
    
    def get_products_count(
        self, 
        filters: Optional[ProductFilter] = None
    ) -> int:
        """
        Retorna contagem de produtos com filtros aplicados.
        
        Args:
            filters: Filtros opcionais
            
        Returns:
            Quantidade de produtos
        """
        params = self._build_params(filters) if filters else {}
        
        count_query = self._COUNT_QUERY
        if filters:
            count_query += self._build_where_clause(filters)
        
        try:
            with get_session() as session:
                result = session.execute(text(count_query), params)
                row = result.fetchone()
                return row[0] if row else 0
                
        except Exception as e:
            print(f"Erro ao contar produtos: {e}")
            return 0
    
    def get_products_paginated(
        self,
        filters: Optional[ProductFilter] = None,
        page: int = 1,
        page_size: int = 1000
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Busca produtos com paginação.
        
        Args:
            filters: Filtros opcionais
            page: Número da página (1-based)
            page_size: Tamanho da página
            
        Returns:
            Tupla (lista de produtos, total de registros)
        """
        # Conta total
        total = self.get_products_count(filters)
        
        # Busca página
        query, params = self._build_query(filters, include_order=False)
        
        # Adiciona paginação (SQL Server)
        offset = (page - 1) * page_size
        query += f"""
            ORDER BY p.codproduto
            OFFSET {offset} ROWS
            FETCH NEXT {page_size} ROWS ONLY
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query), params)
                
                products = []
                for row in result:
                    products.append(self._row_to_dict(row))
                
                return products, total
                
        except Exception as e:
            print(f"Erro ao buscar produtos paginados: {e}")
            raise
    
    def _build_query(
        self, 
        filters: Optional[ProductFilter] = None,
        include_order: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Monta query SQL com filtros dinâmicos.
        
        Args:
            filters: Filtros a aplicar
            include_order: Se True, inclui ORDER BY
            
        Returns:
            Tupla (query SQL, parâmetros)
        """
        query = self._BASE_QUERY
        params = {}
        
        if filters:
            where_clause = self._build_where_clause(filters)
            query += where_clause
            params = self._build_params(filters)
        
        # Ordenação padrão (opcional)
        if include_order:
            query += " ORDER BY p.codproduto"
        
        return query, params
    
    def _build_where_clause(
        self, 
        filters: Optional[ProductFilter] = None
    ) -> str:
        """
        Monta cláusula WHERE dinâmica.
        
        Args:
            filters: Filtros a aplicar
            
        Returns:
            String com condições WHERE
        """
        if not filters:
            return ""
        
        conditions = []
        
        # Filtro por produtos específicos
        # Usa CAST para garantir comparação nvarchar-vs-nvarchar no SQL Server,
        # evitando erro de conversão quando p.codproduto é nvarchar (ex.: 'CF1102').
        if filters.produtos:
            placeholders = ", ".join([f":prod_{i}" for i in range(len(filters.produtos))])
            conditions.append(f"CAST(p.codproduto AS NVARCHAR) IN ({placeholders})")
        
        # Filtro por grupos
        if filters.grupos:
            placeholders = ", ".join([f":grupo_{i}" for i in range(len(filters.grupos))])
            conditions.append(f"CAST(p.codgrupo AS NVARCHAR) IN ({placeholders})")
        
        # Filtro por fornecedor (pe.codfornecedor, não p.codfornecedor)
        if filters.fornecedor:
            placeholders = ", ".join([f":forn_{i}" for i in range(len(filters.fornecedor))])
            conditions.append(f"pe.codfornecedor IN ({placeholders})")

        # Filtro por fabricante (p.codfabricante)
        if filters.fabricante:
            placeholders = ", ".join([f":fab_{i}" for i in range(len(filters.fabricante))])
            conditions.append(f"p.codfabricante IN ({placeholders})")
        
        # Filtro por localizações (pe.localizacao é texto)
        if filters.localizacoes:
            placeholders = ", ".join([f":local_{i}" for i in range(len(filters.localizacoes))])
            conditions.append(f"pe.localizacao IN ({placeholders})")
        
        # Filtro por tipos de produto
        if filters.tipos_produto:
            placeholders = ", ".join([f":tipo_{i}" for i in range(len(filters.tipos_produto))])
            conditions.append(f"CAST(p.codtipoproduto AS NVARCHAR) IN ({placeholders})")

        # ----- Filtros adicionais -----

        # Local de estoque + filtro de estoque combinados
        stock_col = "pe.estoqueloja" if (filters.local_estoque or "loja") == "loja" else "pe.estoquedeposito"
        filtro_est = filters.filtro_estoque or "todos"
        if filtro_est == "negativo":
            conditions.append(f"{stock_col} < 0")
        elif filtro_est == "positivo":
            conditions.append(f"{stock_col} > 0")
        elif filtro_est == "zerado":
            conditions.append(f"{stock_col} = 0")
        # "todos" → sem restrição de estoque

        # Filtro de localização (com/sem/ambos)
        filtro_loc = filters.filtro_localizacao or "ambos"
        if filtro_loc == "com":
            conditions.append("ISNULL(pe.localizacao, '') <> ''")
        elif filtro_loc == "sem":
            conditions.append("ISNULL(pe.localizacao, '') = ''")
        # "ambos" → sem restrição

        # Filtro de encomenda
        filtro_enc = filters.filtro_encomenda or "ambos"
        if filtro_enc == "somente_encomenda":
            conditions.append("pe.EncomendaSN = 1")
        elif filtro_enc == "somente_nao_encomenda":
            conditions.append("pe.EncomendaSN = 0")
        # "ambos" → sem restrição

        # Somente peso variável
        if filters.somente_peso_variavel:
            conditions.append("p.PesoVariavel = 1")

        # Somente produtos para venda
        if filters.somente_venda:
            conditions.append("pe.CompoeVenda = 1")

        if conditions:
            return " AND " + " AND ".join(conditions)
        
        return ""
    
    def _build_params(
        self, 
        filters: Optional[ProductFilter] = None
    ) -> Dict[str, Any]:
        """
        Monta dicionário de parâmetros para a query.
        
        Args:
            filters: Filtros a aplicar
            
        Returns:
            Dicionário de parâmetros
        """
        if not filters:
            return {}
        
        params = {}
        
        # Parâmetros para produtos (sempre str, pois a comparação usa CAST … AS NVARCHAR)
        if filters.produtos:
            for i, cod in enumerate(filters.produtos):
                params[f"prod_{i}"] = str(cod)
        
        # Parâmetros para grupos (sempre str pelo mesmo motivo)
        if filters.grupos:
            for i, cod in enumerate(filters.grupos):
                params[f"grupo_{i}"] = str(cod)
        
        # Parâmetros para fornecedor (coluna int — mantém int)
        if filters.fornecedor:
            for i, cod in enumerate(filters.fornecedor):
                params[f"forn_{i}"] = cod
        
        # Parâmetros para fabricante (coluna int — mantém int)
        if filters.fabricante:
            for i, cod in enumerate(filters.fabricante):
                params[f"fab_{i}"] = cod
        
        # Parâmetros para localizações (texto — mantém str)
        if filters.localizacoes:
            for i, cod in enumerate(filters.localizacoes):
                params[f"local_{i}"] = cod
        
        # Parâmetros para tipos de produto (sempre str, pois a comparação usa CAST … AS NVARCHAR)
        if filters.tipos_produto:
            for i, cod in enumerate(filters.tipos_produto):
                params[f"tipo_{i}"] = str(cod)
        
        return params
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """
        Converte linha do resultado em dicionário para a grid.
        
        Args:
            row: Linha do resultado SQL
            
        Returns:
            Dicionário com dados do produto
        """
        return {
            "codproduto": row.codproduto,
            "descricaoproduto": row.descricaoproduto or "",
            "codeanunidade": row.codeanunidade or "",
            "unidade": row.unidade or "",
            "codgrupo": row.codgrupo,
            "nomegrupo": row.nomegrupo or "",
            "nomeLocalEstoque": row.nomeLocalEstoque or "",
            # Estoques
            "estoqueloja": float(row.estoqueloja or 0),
            "estoquedeposito": float(row.estoquedeposito or 0),
            "estoque": float(row.estoque or 0),
            # Outros
            "codfornecedor": row.codfornecedor or 0,
            "codtipoproduto": row.codtipoproduto or 0,
            "pesovariavel": int(row.pesovariavel or 0),
            "compoevenda": int(row.compoevenda or 0),
            "encomenda": int(row.encomenda or 0),
            "localizacao": row.localizacao or "",
        }
    
    # ===== MÉTODOS PARA CARREGAR DADOS DOS FILTROS =====
    
    def get_grupos(self) -> List[Tuple[int, str]]:
        """
        Carrega grupos de estoque para filtro.

        Returns:
            Lista de (codigo, "codgrupo - NomeGrupo")
        """
        query = """
            SELECT DISTINCT g.codgrupo, g.NomeGrupo
            FROM GrupoEstoque g
            INNER JOIN produtos p ON p.codgrupo = g.codgrupo
            INNER JOIN produtosestoque pe ON pe.codproduto = p.codproduto
            WHERE pe.situacao = 'A'
              AND p.controlarestoque = 1
              AND ISNULL(p.codeanunidade, '') <> ''
            ORDER BY g.codgrupo
        """

        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [
                    (row.codgrupo, f"{row.codgrupo} - {row.NomeGrupo}")
                    for row in result
                ]
        except Exception as e:
            print(f"Erro ao carregar grupos: {e}")
            return []
    
    def get_tipos_produto(self) -> List[Tuple[int, str]]:
        """
        Carrega tipos de produto para filtro.

        Returns:
            Lista de (codigo, "cod - descricao")
        """
        query = """
            SELECT codtipoproduto, nometipoproduto
            FROM tipoproduto
            ORDER BY nometipoproduto
        """

        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [
                    (row.codtipoproduto, f"{row.codtipoproduto} - {row.nometipoproduto}")
                    for row in result
                ]
        except Exception as e:
            print(f"Erro ao carregar tipos de produto: {e}")
            return []
    
    def get_localizacoes(self) -> List[Tuple[str, str]]:
        """
        Carrega localizações de estoque para filtro.
        
        Returns:
            Lista de (localizacao, localizacao) - texto
        """
        query = """
            SELECT DISTINCT pe.localizacao
            FROM produtosestoque pe
            INNER JOIN produtos p ON p.codproduto = pe.codproduto
            WHERE pe.situacao = 'A'
              AND p.controlarestoque = 1
              AND ISNULL(p.codeanunidade, '') <> ''
              AND ISNULL(pe.localizacao, '') <> ''
            ORDER BY pe.localizacao
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.localizacao, row.localizacao) for row in result]
        except Exception as e:
            print(f"Erro ao carregar localizações: {e}")
            return []
    
    def get_fornecedores(self) -> List[Tuple[int, str]]:
        """
        Carrega fornecedores para filtro.

        Returns:
            Lista de (codigo, "cod - nome")
        """
        query = """
            SELECT DISTINCT
                pe.CodFornecedor,
                COALESCE(c.nomecliente, CAST(pe.CodFornecedor AS VARCHAR)) AS nome
            FROM ProdutosEstoque pe
            INNER JOIN produtos p ON p.codproduto = pe.codproduto
            LEFT JOIN clientes c ON c.codcliente = pe.CodFornecedor
            WHERE pe.situacao = 'A'
              AND p.controlarestoque = 1
              AND ISNULL(p.codeanunidade, '') <> ''
              AND pe.CodFornecedor IS NOT NULL
              AND pe.CodFornecedor > 0
            ORDER BY nome
        """

        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [
                    (row.CodFornecedor, f"{row.CodFornecedor} - {row.nome}")
                    for row in result
                ]
        except Exception as e:
            print(f"Erro ao carregar fornecedores: {e}")
            return []
    
    def get_fabricantes(self) -> List[Tuple[int, str]]:
        """
        Carrega fabricantes para filtro.

        Returns:
            Lista de (codigo, "cod - nome")
        """
        query = """
            SELECT c.codcliente, c.NomeCliente
            FROM clientes c
            INNER JOIN tipocliente tc ON tc.codtipocliente = c.codtipocliente
            WHERE tc.NomeTipoCliente = 'Fabricante'
              AND EXISTS (
                  SELECT 1
                  FROM produtos p
                  INNER JOIN produtosestoque pe ON pe.codproduto = p.codproduto
                  WHERE p.codfabricante = c.codcliente
                    AND pe.situacao = 'A'
                    AND p.controlarestoque = 1
                    AND ISNULL(p.codeanunidade, '') <> ''
              )
            ORDER BY c.NomeCliente
        """

        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [
                    (row.codcliente, f"{row.codcliente} - {row.NomeCliente}")
                    for row in result
                ]
        except Exception as e:
            print(f"Erro ao carregar fabricantes: {e}")
            return []
    
    def get_produtos_for_filter(self) -> List[Tuple[int, str]]:
        """
        Carrega lista de produtos para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT DISTINCT p.codproduto, p.descricaoproduto
            FROM produtosestoque pe
            INNER JOIN produtos p ON p.codproduto = pe.codproduto
            WHERE pe.situacao = 'A'
              AND p.controlarestoque = 1
              AND ISNULL(p.codeanunidade, '') <> ''
            ORDER BY p.descricaoproduto
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codproduto, row.descricaoproduto) for row in result]
        except Exception as e:
            print(f"Erro ao carregar produtos: {e}")
            return []
    
    def get_all_filter_data(self) -> Dict[str, List[Tuple[int, str]]]:
        """
        Carrega todos os dados para os filtros de uma vez.
        
        Returns:
            Dicionário com todos os dados de filtros
        """
        return {
            "grupos": self.get_grupos(),
            "tipos_produto": self.get_tipos_produto(),
            "localizacoes": self.get_localizacoes(),
            "fornecedores": self.get_fornecedores(),
            "fabricantes": self.get_fabricantes(),
        }
    
    def search_products(self, search_text: str = "", limit: int = 50, offset: int = 0) -> tuple[List[Dict[str, Any]], int]:
        """
        Busca produtos por código ou descrição com paginação.
        
        Usado pelo diálogo de busca ao pressionar Enter no campo "Buscar Produto".
        Implementa lazy loading para melhor performance.
        
        Args:
            search_text: Texto a buscar (código ou descrição). Se vazio, retorna todos.
            limit: Número máximo de registros a retornar (default 50)
            offset: Número de registros a pular (para paginação)
        
        Returns:
            Tupla (lista_de_produtos, total_encontrado)
        """
        # Primeiro, conta o total de registros que correspondem
        count_query = """
            SELECT COUNT(*) AS total
            FROM produtosestoque pe
            INNER JOIN produtos p ON p.codproduto = pe.codproduto
            WHERE pe.situacao = 'A'
              AND p.controlarestoque = 1
              AND ISNULL(p.codeanunidade, '') <> ''
        """
        
        params = {}
        
        # Se houver texto de busca, adiciona filtro
        if search_text.strip():
            search_term = f"%{search_text}%"
            count_query += """
              AND (
                  CAST(p.codproduto AS VARCHAR) LIKE :search_term
                  OR p.descricaoproduto LIKE :search_term
              )
            """
            params["search_term"] = search_term
        
        # Query para buscar produtos com OFFSET/FETCH (SQL Server)
        search_query = f"""
            SELECT 
                p.codproduto,
                p.descricaoproduto,
                COALESCE(p.codeanunidade, '') AS codeanunidade,
                p.unidade,
                p.codgrupo,
                COALESCE(g.NomeGrupo, '') AS nomegrupo,
                COALESCE(le.NomeLocalEstoque, '') AS nomeLocalEstoque,
                COALESCE(pe.estoqueloja, 0) AS estoqueloja,
                COALESCE(pe.estoquedeposito, 0) AS estoquedeposito,
                (COALESCE(pe.estoqueloja, 0) + COALESCE(pe.estoquedeposito, 0)) AS estoque,
                COALESCE(pe.codfornecedor, 0) AS codfornecedor,
                p.codtipoproduto,
                COALESCE(p.PesoVariavel, 0) AS pesovariavel,
                COALESCE(pe.CompoeVenda, 0) AS compoevenda,
                COALESCE(pe.EncomendaSN, 0) AS encomenda,
                pe.localizacao
            FROM produtosestoque pe
            INNER JOIN produtos p ON p.codproduto = pe.codproduto
            LEFT JOIN GrupoEstoque g ON g.codgrupo = p.codgrupo
            LEFT JOIN LocalEstoque le ON le.NomeLocalEstoque = pe.localizacao
            WHERE pe.situacao = 'A'
              AND p.controlarestoque = 1
              AND ISNULL(p.codeanunidade, '') <> ''
        """
        
        if search_text.strip():
            search_query += """
              AND (
                  CAST(p.codproduto AS VARCHAR) LIKE :search_term
                  OR p.descricaoproduto LIKE :search_term
              )
            """
        
        search_query += f"""
            ORDER BY p.descricaoproduto
            OFFSET {offset} ROWS
            FETCH NEXT {limit} ROWS ONLY
        """
        
        try:
            with get_session() as session:
                # Conta total
                result_count = session.execute(text(count_query), params)
                total = result_count.scalar() or 0
                
                # Busca produtos
                result = session.execute(text(search_query), params)
                
                products = []
                for row in result:
                    products.append(self._row_to_dict(row))
                
                return products, total
        except Exception as e:
            print(f"Erro ao buscar produtos: {e}")
            return [], 0
