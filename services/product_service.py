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
    produtos: Optional[List[int]] = None          # Lista de códigos de produto
    grupos: Optional[List[int]] = None            # Lista de códigos de grupo
    fornecedor: Optional[int] = None              # Código do fornecedor
    fabricante: Optional[int] = None              # Código do fabricante
    localizacoes: Optional[List[int]] = None      # Lista de códigos de localização
    tipos_produto: Optional[List[int]] = None     # Lista de códigos de tipo
    
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
        )


class ProductService:
    """
    Serviço para consulta de produtos.
    
    Responsabilidades:
    - Montar SQL dinâmico baseado nos filtros
    - Aplicar regras de negócio (ativos, com EAN)
    - Calcular estoque total (depósito + loja)
    - Preparar dados para a grid
    """
    
    # Query base com regras fixas
    _BASE_QUERY = """
        SELECT 
            p.codproduto,
            p.descricao AS descricaoproduto,
            COALESCE(p.codean, '') + 
                CASE WHEN p.unidade IS NOT NULL AND p.unidade <> '' 
                     THEN '/' + p.unidade 
                     ELSE '' 
                END AS codeanunidade,
            p.codgrupo,
            COALESCE(g.descricao, '') AS nomegrupo,
            COALESCE(le.descricao, '') AS nomeLocalEstoque,
            COALESCE(pl.numlote, '') AS numlote,
            pl.datafabricacao,
            pl.datavalidade,
            COALESCE(pe.estoqueloja, 0) AS estoqueloja,
            COALESCE(pe.estoquedeposito, 0) AS estoquedeposito,
            (COALESCE(pe.estoqueloja, 0) + COALESCE(pe.estoquedeposito, 0)) AS estoque,
            p.codfornecedor,
            COALESCE(forn.nome, '') AS nomefornecedor,
            p.codfabricante,
            COALESCE(fab.nome, '') AS nomefabricante,
            p.codtipo,
            COALESCE(tp.descricao, '') AS nometipo,
            p.referencia,
            p.unidade,
            p.codean,
            COALESCE(pe.customedio, 0) AS customedio,
            COALESCE(pe.vendaatual, 0) AS precovenda,
            pe.codlocal
        FROM produtos p
        LEFT JOIN gruposestoque g ON g.codgrupo = p.codgrupo
        LEFT JOIN produtosestoque pe ON pe.codproduto = p.codproduto
        LEFT JOIN locaisestoque le ON le.codlocal = pe.codlocal
        LEFT JOIN produtoslotes pl ON pl.codproduto = p.codproduto 
            AND pl.codlocal = pe.codlocal
            AND pl.principal = 1
        LEFT JOIN pessoas forn ON forn.codpessoa = p.codfornecedor
        LEFT JOIN pessoas fab ON fab.codpessoa = p.codfabricante
        LEFT JOIN tiposproduto tp ON tp.codtipo = p.codtipo
        WHERE p.ativo = 1
          AND COALESCE(p.codean, '') <> ''
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
        _, params = self._build_query(filters)
        
        count_query = f"""
            SELECT COUNT(DISTINCT p.codproduto)
            FROM produtos p
            LEFT JOIN produtosestoque pe ON pe.codproduto = p.codproduto
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            {self._build_where_clause(filters)}
        """
        
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
        query, params = self._build_query(filters)
        
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
        filters: Optional[ProductFilter] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Monta query SQL com filtros dinâmicos.
        
        Args:
            filters: Filtros a aplicar
            
        Returns:
            Tupla (query SQL, parâmetros)
        """
        query = self._BASE_QUERY
        params = {}
        
        if filters:
            where_clause = self._build_where_clause(filters)
            query += where_clause
            params = self._build_params(filters)
        
        # Ordenação padrão
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
        if filters.produtos:
            placeholders = ", ".join([f":prod_{i}" for i in range(len(filters.produtos))])
            conditions.append(f"p.codproduto IN ({placeholders})")
        
        # Filtro por grupos
        if filters.grupos:
            placeholders = ", ".join([f":grupo_{i}" for i in range(len(filters.grupos))])
            conditions.append(f"p.codgrupo IN ({placeholders})")
        
        # Filtro por fornecedor
        if filters.fornecedor:
            conditions.append("p.codfornecedor = :fornecedor")
        
        # Filtro por fabricante
        if filters.fabricante:
            conditions.append("p.codfabricante = :fabricante")
        
        # Filtro por localizações
        if filters.localizacoes:
            placeholders = ", ".join([f":local_{i}" for i in range(len(filters.localizacoes))])
            conditions.append(f"pe.codlocal IN ({placeholders})")
        
        # Filtro por tipos de produto
        if filters.tipos_produto:
            placeholders = ", ".join([f":tipo_{i}" for i in range(len(filters.tipos_produto))])
            conditions.append(f"p.codtipo IN ({placeholders})")
        
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
        
        # Parâmetros para produtos
        if filters.produtos:
            for i, cod in enumerate(filters.produtos):
                params[f"prod_{i}"] = cod
        
        # Parâmetros para grupos
        if filters.grupos:
            for i, cod in enumerate(filters.grupos):
                params[f"grupo_{i}"] = cod
        
        # Parâmetro para fornecedor
        if filters.fornecedor:
            params["fornecedor"] = filters.fornecedor
        
        # Parâmetro para fabricante
        if filters.fabricante:
            params["fabricante"] = filters.fabricante
        
        # Parâmetros para localizações
        if filters.localizacoes:
            for i, cod in enumerate(filters.localizacoes):
                params[f"local_{i}"] = cod
        
        # Parâmetros para tipos de produto
        if filters.tipos_produto:
            for i, cod in enumerate(filters.tipos_produto):
                params[f"tipo_{i}"] = cod
        
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
            "codgrupo": row.codgrupo,
            "nomegrupo": row.nomegrupo or "",
            "nomeLocalEstoque": row.nomeLocalEstoque or "",
            "numlote": row.numlote or "",
            "datafabricacao": row.datafabricacao,
            "datavalidade": row.datavalidade,
            # Campos adicionais para uso interno
            "estoqueloja": float(row.estoqueloja or 0),
            "estoquedeposito": float(row.estoquedeposito or 0),
            "estoque": float(row.estoque or 0),
            "codfornecedor": row.codfornecedor,
            "nomefornecedor": row.nomefornecedor or "",
            "codfabricante": row.codfabricante,
            "nomefabricante": row.nomefabricante or "",
            "codtipo": row.codtipo,
            "nometipo": row.nometipo or "",
            "referencia": row.referencia or "",
            "unidade": row.unidade or "",
            "codean": row.codean or "",
            "customedio": float(row.customedio or 0),
            "precovenda": float(row.precovenda or 0),
            "codlocal": row.codlocal,
        }
    
    # ===== MÉTODOS PARA CARREGAR DADOS DOS FILTROS =====
    
    def get_grupos(self) -> List[Tuple[int, str]]:
        """
        Carrega grupos de estoque para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT DISTINCT g.codgrupo, g.descricao 
            FROM gruposestoque g
            INNER JOIN produtos p ON p.codgrupo = g.codgrupo
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            ORDER BY g.descricao
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codgrupo, row.descricao) for row in result]
        except Exception as e:
            print(f"Erro ao carregar grupos: {e}")
            return []
    
    def get_tipos_produto(self) -> List[Tuple[int, str]]:
        """
        Carrega tipos de produto para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT DISTINCT tp.codtipo, tp.descricao 
            FROM tiposproduto tp
            INNER JOIN produtos p ON p.codtipo = tp.codtipo
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            ORDER BY tp.descricao
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codtipo, row.descricao) for row in result]
        except Exception as e:
            print(f"Erro ao carregar tipos: {e}")
            return []
    
    def get_localizacoes(self) -> List[Tuple[int, str]]:
        """
        Carrega localizações de estoque para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT DISTINCT le.codlocal, le.descricao 
            FROM locaisestoque le
            INNER JOIN produtosestoque pe ON pe.codlocal = le.codlocal
            INNER JOIN produtos p ON p.codproduto = pe.codproduto
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            ORDER BY le.descricao
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codlocal, row.descricao) for row in result]
        except Exception as e:
            print(f"Erro ao carregar localizações: {e}")
            return []
    
    def get_fornecedores(self) -> List[Tuple[int, str]]:
        """
        Carrega fornecedores para filtro.
        
        Returns:
            Lista de (codigo, nome)
        """
        query = """
            SELECT DISTINCT ps.codpessoa, ps.nome 
            FROM pessoas ps
            INNER JOIN produtos p ON p.codfornecedor = ps.codpessoa
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            ORDER BY ps.nome
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codpessoa, row.nome) for row in result]
        except Exception as e:
            print(f"Erro ao carregar fornecedores: {e}")
            return []
    
    def get_fabricantes(self) -> List[Tuple[int, str]]:
        """
        Carrega fabricantes para filtro.
        
        Returns:
            Lista de (codigo, nome)
        """
        query = """
            SELECT DISTINCT ps.codpessoa, ps.nome 
            FROM pessoas ps
            INNER JOIN produtos p ON p.codfabricante = ps.codpessoa
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            ORDER BY ps.nome
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codpessoa, row.nome) for row in result]
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
            SELECT p.codproduto, p.descricao
            FROM produtos p
            WHERE p.ativo = 1
              AND COALESCE(p.codean, '') <> ''
            ORDER BY p.descricao
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codproduto, row.descricao) for row in result]
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
