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
        
        # Monta query base (ajustada para o esquema desta base)
        query = """
            SELECT
                p.CodProduto AS codigo,
                COALESCE(p.CodOriginal, '') AS referencia,
                p.DescricaoProduto AS descricao,
                ISNULL(p.Unidade, p.UnidadeSaida) AS unidade,
                p.CodGrupo AS codgrupo,
                COALESCE(g.NomeGrupo, '') AS grupo_nome,
                p.CodTipoProduto AS codtipo,
                COALESCE(t.NomeTipoProduto, '') AS tipo_nome,
                (COALESCE(pe.EstoqueLoja, 0) + COALESCE(pe.EstoqueDeposito, 0)) AS estoque,
                COALESCE(pe.CustoMedio, pe.CustoMedioContabil, 0) AS custo,
                COALESCE(pe.PrecoUnitario1, 0) AS venda,
                COALESCE(pe.Localizacao, '') AS localizacao,
                COALESCE(p.PesoVariavel, 0) AS pesovariavel,
                COALESCE(pe.CompoeVenda, 0) AS produto_venda,
                COALESCE(pe.EncomendaSN, 0) AS encomenda
            FROM produtos p
            LEFT JOIN GrupoEstoque g ON g.CodGrupo = p.CodGrupo
            LEFT JOIN TipoProduto t ON t.CodTipoProduto = p.CodTipoProduto
            LEFT JOIN ProdutosEstoque pe ON pe.CodProduto = p.CodProduto
            WHERE 1=1
        """
        
        params = {}
        conditions = []
        
        # Filtro por produtos específicos
        if filters.get("produtos"):
            prods = filters["produtos"]
            if isinstance(prods, (list, tuple)):
                if len(prods) == 1:
                    conditions.append("p.CodProduto = :produto_0")
                    params["produto_0"] = str(prods[0])
                else:
                    ph = []
                    for i, v in enumerate(prods):
                        k = f"produto_{i}"
                        ph.append(":" + k)
                        params[k] = str(v)
                    conditions.append("p.CodProduto IN (" + ", ".join(ph) + ")")
            else:
                conditions.append("p.CodProduto = :produto_0")
                params["produto_0"] = str(prods)
        
        # Filtro por grupos
        if filters.get("grupos"):
            grupos = filters["grupos"]
            if isinstance(grupos, (list, tuple)):
                if len(grupos) == 1:
                    conditions.append("p.CodGrupo = :grupo_0")
                    params["grupo_0"] = grupos[0]
                else:
                    ph = []
                    for i, v in enumerate(grupos):
                        k = f"grupo_{i}"
                        ph.append(":" + k)
                        params[k] = v
                    conditions.append("p.CodGrupo IN (" + ", ".join(ph) + ")")
            else:
                conditions.append("p.CodGrupo = :grupo_0")
                params["grupo_0"] = grupos
        
        # Filtro por fornecedor
        if filters.get("fornecedor"):
            conditions.append("p.CodFornecedor = :fornecedor")
            params["fornecedor"] = filters["fornecedor"]
        
        # Filtro por fabricante
        if filters.get("fabricante"):
            conditions.append("p.CodFabricante = :fabricante")
            params["fabricante"] = filters["fabricante"]
        
        # Filtro por localizações
        if filters.get("localizacoes"):
            locs = filters["localizacoes"]
            if isinstance(locs, (list, tuple)):
                if len(locs) == 1:
                    conditions.append("pe.CodLocal = :local_0")
                    params["local_0"] = locs[0]
                else:
                    ph = []
                    for i, v in enumerate(locs):
                        k = f"local_{i}"
                        ph.append(":" + k)
                        params[k] = v
                    conditions.append("pe.CodLocal IN (" + ", ".join(ph) + ")")
            else:
                conditions.append("pe.CodLocal = :local_0")
                params["local_0"] = locs
        
        # Filtro por tipos de produto
        if filters.get("tipos_produto"):
            tipos = filters["tipos_produto"]
            if isinstance(tipos, (list, tuple)):
                if len(tipos) == 1:
                    conditions.append("p.CodTipoProduto = :tipo_0")
                    params["tipo_0"] = tipos[0]
                else:
                    ph = []
                    for i, v in enumerate(tipos):
                        k = f"tipo_{i}"
                        ph.append(":" + k)
                        params[k] = v
                    conditions.append("p.CodTipoProduto IN (" + ", ".join(ph) + ")")
            else:
                conditions.append("p.CodTipoProduto = :tipo_0")
                params["tipo_0"] = tipos
        
        # Filtro por local de estoque
        # Nota: alguns produtos não possuem linha em produtosestoque (LEFT JOIN).
        # Para não excluir esses produtos, consideramos também os casos onde
        # não existe registro em produtosestoque (pe.codproduto IS NULL).
        # Aplica filtro por local de estoque apenas quando não estamos
        # buscando por uma lista de produtos específicos.
        if not filters.get("produtos"):
            local_estoque = filters.get("local_estoque", "loja")
            if local_estoque == "loja":
                conditions.append("(COALESCE(pe.EstoqueLoja, 0) > 0 OR pe.CodProduto IS NULL)")
            elif local_estoque == "deposito":
                conditions.append("(COALESCE(pe.EstoqueDeposito, 0) > 0 OR pe.CodProduto IS NULL)")
        
        # Filtro por localização preenchida
        filtro_loc = filters.get("filtro_localizacao", "ambos")
        if filtro_loc == "com":
            conditions.append("pe.Localizacao IS NOT NULL AND pe.Localizacao <> ''")
        elif filtro_loc == "sem":
            conditions.append("(pe.Localizacao IS NULL OR pe.Localizacao = '')")
        
        # Filtro por estoque
        filtro_estoque = filters.get("filtro_estoque", "todos")
        if filtro_estoque == "negativo":
            conditions.append("(COALESCE(pe.EstoqueLoja,0) + COALESCE(pe.EstoqueDeposito,0)) < 0")
        elif filtro_estoque == "positivo":
            conditions.append("(COALESCE(pe.EstoqueLoja,0) + COALESCE(pe.EstoqueDeposito,0)) > 0")
        elif filtro_estoque == "zerado":
            conditions.append("(COALESCE(pe.EstoqueLoja,0) + COALESCE(pe.EstoqueDeposito,0)) = 0")
        
        # Filtro por encomenda
        filtro_encomenda = filters.get("filtro_encomenda", "ambos")
        if filtro_encomenda == "somente_encomenda":
            conditions.append("COALESCE(pe.EncomendaSN, 0) = 1")
        elif filtro_encomenda == "somente_nao_encomenda":
            conditions.append("(COALESCE(pe.EncomendaSN, 0) = 0)")
        
        # Filtro peso variável
        if filters.get("somente_peso_variavel"):
            conditions.append("p.PesoVariavel = 1")
        
        # Filtro produtos para venda
        if filters.get("somente_venda"):
            conditions.append("COALESCE(pe.CompoeVenda, 0) = 1")
        
        # Adiciona condições à query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Ordenação
        query += " ORDER BY p.DescricaoProduto"
        
        # Executa query
        try:
            # Debug: mostrar SQL e parâmetros executados (útil para entender filtros)
            print("[ProductRepository] Executando SQL:")
            print(query)
            print("[ProductRepository] Params:", params)

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
            SELECT codgrupo, NomeGrupo AS descricao
            FROM GrupoEstoque
            WHERE ISNULL(Ativo, 1) = 1
            ORDER BY NomeGrupo
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
            SELECT codtipoproduto AS codtipo, nometipoproduto AS descricao
            FROM TipoProduto
            ORDER BY nometipoproduto
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
            SELECT codlocal, NomeLocalEstoque AS descricao
            FROM LocalEstoque
            WHERE ISNULL(Ativo, 1) = 1
            ORDER BY NomeLocalEstoque
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
