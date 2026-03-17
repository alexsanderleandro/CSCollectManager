"""
product_repository.py
=====================
Repositório para acesso a dados de produtos.
"""

from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.connection import get_session


class ProductRepository:
    """
    Repositório para acesso a dados de produtos.
    
    Responsabilidades:
    - Consultar produtos com filtros
    - Carregar dados para combos de filtro
    - Otimizar queries para grandes volumes
    """
    
    def get_produtos(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Carrega produtos com filtros aplicados.
        
        Args:
            filters: Dicionário de filtros
                - produtos: Lista de códigos
                - grupos: Lista de códigos de grupo
                - fornecedor: Código do fornecedor
                - fabricante: Código do fabricante
                - localizacoes: Lista de códigos de localização
                - tipos_produto: Lista de códigos de tipo
                - local_estoque: 'loja' ou 'deposito'
                - filtro_localizacao: 'com', 'sem' ou 'ambos'
                - filtro_estoque: 'negativo', 'positivo', 'zerado' ou 'todos'
                - filtro_encomenda: 'somente_encomenda', 'somente_nao_encomenda' ou 'ambos'
                - somente_peso_variavel: bool
                - somente_venda: bool
        
        Returns:
            Lista de produtos como dicionários
        """
        filters = filters or {}
        
        # Monta query base
        query = """
            SELECT 
                p.codproduto AS codigo,
                p.referencia,
                p.descricao,
                p.unidade,
                p.codgrupo,
                g.descricao AS grupo_nome,
                p.codtipo,
                t.descricao AS tipo_nome,
                pe.estoque,
                pe.customedio AS custo,
                pe.vendaatual AS venda,
                pe.localizacao,
                p.pesovariavel,
                p.venda AS produto_venda,
                p.encomenda
            FROM produtos p
            LEFT JOIN gruposestoque g ON g.codgrupo = p.codgrupo
            LEFT JOIN tiposproduto t ON t.codtipo = p.codtipo
            LEFT JOIN produtosestoque pe ON pe.codproduto = p.codproduto
            WHERE p.ativo = 1
        """
        
        params = {}
        conditions = []
        
        # Filtro por produtos específicos
        if filters.get("produtos"):
            conditions.append("p.codproduto IN :produtos")
            params["produtos"] = tuple(filters["produtos"])
        
        # Filtro por grupos
        if filters.get("grupos"):
            conditions.append("p.codgrupo IN :grupos")
            params["grupos"] = tuple(filters["grupos"])
        
        # Filtro por fornecedor
        if filters.get("fornecedor"):
            conditions.append("p.codfornecedor = :fornecedor")
            params["fornecedor"] = filters["fornecedor"]
        
        # Filtro por fabricante
        if filters.get("fabricante"):
            conditions.append("p.codfabricante = :fabricante")
            params["fabricante"] = filters["fabricante"]
        
        # Filtro por localizações
        if filters.get("localizacoes"):
            conditions.append("pe.codlocal IN :localizacoes")
            params["localizacoes"] = tuple(filters["localizacoes"])
        
        # Filtro por tipos de produto
        if filters.get("tipos_produto"):
            conditions.append("p.codtipo IN :tipos")
            params["tipos"] = tuple(filters["tipos_produto"])
        
        # Filtro por local de estoque
        local_estoque = filters.get("local_estoque", "loja")
        if local_estoque == "loja":
            conditions.append("pe.loja = 1")
        elif local_estoque == "deposito":
            conditions.append("pe.deposito = 1")
        
        # Filtro por localização preenchida
        filtro_loc = filters.get("filtro_localizacao", "ambos")
        if filtro_loc == "com":
            conditions.append("pe.localizacao IS NOT NULL AND pe.localizacao <> ''")
        elif filtro_loc == "sem":
            conditions.append("(pe.localizacao IS NULL OR pe.localizacao = '')")
        
        # Filtro por estoque
        filtro_estoque = filters.get("filtro_estoque", "todos")
        if filtro_estoque == "negativo":
            conditions.append("pe.estoque < 0")
        elif filtro_estoque == "positivo":
            conditions.append("pe.estoque > 0")
        elif filtro_estoque == "zerado":
            conditions.append("pe.estoque = 0")
        
        # Filtro por encomenda
        filtro_encomenda = filters.get("filtro_encomenda", "ambos")
        if filtro_encomenda == "somente_encomenda":
            conditions.append("p.encomenda = 1")
        elif filtro_encomenda == "somente_nao_encomenda":
            conditions.append("(p.encomenda = 0 OR p.encomenda IS NULL)")
        
        # Filtro peso variável
        if filters.get("somente_peso_variavel"):
            conditions.append("p.pesovariavel = 1")
        
        # Filtro produtos para venda
        if filters.get("somente_venda"):
            conditions.append("p.venda = 1")
        
        # Adiciona condições à query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Ordenação
        query += " ORDER BY p.descricao"
        
        # Executa query
        try:
            with get_session() as session:
                result = session.execute(text(query), params)
                
                produtos = []
                for row in result:
                    produtos.append({
                        "codigo": row.codigo,
                        "referencia": row.referencia or "",
                        "descricao": row.descricao or "",
                        "unidade": row.unidade or "UN",
                        "codgrupo": row.codgrupo,
                        "grupo_nome": row.grupo_nome or "",
                        "codtipo": row.codtipo,
                        "tipo_nome": row.tipo_nome or "",
                        "estoque": float(row.estoque or 0),
                        "custo": float(row.custo or 0),
                        "venda": float(row.venda or 0),
                        "localizacao": row.localizacao or "",
                        "peso_variavel": bool(row.pesovariavel),
                        "produto_venda": bool(row.produto_venda),
                        "encomenda": bool(row.encomenda),
                    })
                
                return produtos
                
        except Exception as e:
            print(f"Erro ao carregar produtos: {e}")
            # Retorna lista vazia em caso de erro
            return []
    
    def get_grupos(self) -> List[Tuple[int, str]]:
        """
        Carrega grupos de estoque.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT codgrupo, descricao 
            FROM gruposestoque 
            WHERE ativo = 1
            ORDER BY descricao
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
        Carrega tipos de produto.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT codtipo, descricao 
            FROM tiposproduto 
            ORDER BY descricao
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
        Carrega localizações de estoque.
        
        Returns:
            Lista de (codigo, descricao)
        """
        query = """
            SELECT codlocal, descricao 
            FROM locaisestoque 
            WHERE ativo = 1
            ORDER BY descricao
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
        Carrega fornecedores.
        
        Returns:
            Lista de (codigo, nome)
        """
        query = """
            SELECT codpessoa, nome 
            FROM pessoas 
            WHERE fornecedor = 1 AND ativo = 1
            ORDER BY nome
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
        Carrega fabricantes.
        
        Returns:
            Lista de (codigo, nome)
        """
        query = """
            SELECT codpessoa, nome 
            FROM pessoas 
            WHERE fabricante = 1 AND ativo = 1
            ORDER BY nome
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query))
                return [(row.codpessoa, row.nome) for row in result]
        except Exception as e:
            print(f"Erro ao carregar fabricantes: {e}")
            return []
    
    def get_produto_by_codigo(self, codigo: int) -> Optional[Dict[str, Any]]:
        """
        Busca produto por código.
        
        Args:
            codigo: Código do produto
            
        Returns:
            Dicionário com dados do produto ou None
        """
        filters = {"produtos": [codigo]}
        produtos = self.get_produtos(filters)
        return produtos[0] if produtos else None
    
    def get_produto_anexos(self, codproduto: int) -> List[Dict[str, Any]]:
        """
        Busca anexos (fotos) de um produto.
        
        Args:
            codproduto: Código do produto
            
        Returns:
            Lista de anexos
        """
        query = """
            SELECT 
                codanexo,
                descricao,
                arquivo,
                tipo,
                tamanho,
                datacriacao
            FROM produtosanexos
            WHERE codproduto = :codproduto
            ORDER BY principal DESC, codanexo
        """
        
        try:
            with get_session() as session:
                result = session.execute(text(query), {"codproduto": codproduto})
                return [
                    {
                        "codanexo": row.codanexo,
                        "descricao": row.descricao,
                        "arquivo": row.arquivo,
                        "tipo": row.tipo,
                        "tamanho": row.tamanho,
                        "datacriacao": row.datacriacao,
                    }
                    for row in result
                ]
        except Exception as e:
            print(f"Erro ao carregar anexos: {e}")
            return []
