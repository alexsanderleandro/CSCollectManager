"""
inventory_repository.py
=======================
Repositório para acesso a dados de inventários.
"""

from typing import Optional, List
from repositories.base_repository import BaseRepository
from models.inventory import Inventory, InventoryItem


class InventoryRepository(BaseRepository[Inventory]):
    """
    Repositório para operações de inventário no banco de dados.
    """
    
    def get_all(
        self,
        company_code: str = "",
        status: Optional[str] = None
    ) -> List[Inventory]:
        """
        Retorna todos os inventários.
        
        Args:
            company_code: Filtro por empresa
            status: Filtro por status
            
        Returns:
            Lista de inventários
        """
        # TODO: Ajustar SQL conforme estrutura real do banco
        sql = """
            SELECT 
                CodInventario,
                NumeroInventario,
                Descricao,
                DataAbertura,
                DataFechamento,
                Status,
                CodEmpresa
            FROM dbo.Inventarios WITH (NOLOCK)
            WHERE 1=1
        """
        params = []
        
        if company_code:
            sql += " AND CodEmpresa = ?"
            params.append(company_code)
        
        if status:
            sql += " AND Status = ?"
            params.append(status)
        
        sql += " ORDER BY DataAbertura DESC"
        
        results = self.execute_query(sql, tuple(params))
        
        return [
            Inventory(
                id=row[0],
                number=row[1] or "",
                description=row[2] or "",
                open_date=row[3],
                close_date=row[4],
                status=row[5] or "",
                company_code=row[6] or ""
            )
            for row in results
        ] if results else []
    
    def get_by_id(self, inventory_id: int) -> Optional[Inventory]:
        """
        Busca inventário por ID.
        
        Args:
            inventory_id: ID do inventário
            
        Returns:
            Inventário ou None
        """
        sql = """
            SELECT 
                CodInventario,
                NumeroInventario,
                Descricao,
                DataAbertura,
                DataFechamento,
                Status,
                CodEmpresa
            FROM dbo.Inventarios WITH (NOLOCK)
            WHERE CodInventario = ?
        """
        
        row = self.execute_query(sql, (inventory_id,), fetch_one=True)
        
        if row:
            return Inventory(
                id=row[0],
                number=row[1] or "",
                description=row[2] or "",
                open_date=row[3],
                close_date=row[4],
                status=row[5] or "",
                company_code=row[6] or ""
            )
        return None
    
    def get_items(
        self,
        inventory_id: int,
        offset: int = 0,
        limit: int = 1000
    ) -> List[InventoryItem]:
        """
        Retorna itens de um inventário.
        
        Args:
            inventory_id: ID do inventário
            offset: Offset para paginação
            limit: Limite de registros
            
        Returns:
            Lista de itens
        """
        # TODO: Ajustar SQL conforme estrutura real do banco
        sql = """
            SELECT 
                i.CodItem,
                i.CodInventario,
                i.CodProduto,
                p.Descricao,
                i.Quantidade,
                p.Unidade,
                p.CodigoBarras
            FROM dbo.InventarioItens i WITH (NOLOCK)
            LEFT JOIN dbo.Produtos p WITH (NOLOCK) ON i.CodProduto = p.CodProduto
            WHERE i.CodInventario = ?
            ORDER BY p.Descricao
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        
        results = self.execute_query(sql, (inventory_id, offset, limit))
        
        return [
            InventoryItem(
                id=row[0],
                inventory_id=row[1],
                product_code=row[2] or "",
                description=row[3] or "",
                quantity=float(row[4]) if row[4] else 0.0,
                unit=row[5] or "UN",
                barcode=row[6] or ""
            )
            for row in results
        ] if results else []
    
    def count_items(self, inventory_id: int) -> int:
        """
        Conta itens de um inventário.
        
        Args:
            inventory_id: ID do inventário
            
        Returns:
            Quantidade de itens
        """
        sql = """
            SELECT COUNT(*) 
            FROM dbo.InventarioItens WITH (NOLOCK)
            WHERE CodInventario = ?
        """
        
        result = self.execute_scalar(sql, (inventory_id,))
        return int(result) if result else 0
    
    def search_items(
        self,
        inventory_id: int,
        search_term: str
    ) -> List[InventoryItem]:
        """
        Busca itens por código ou descrição.
        
        Args:
            inventory_id: ID do inventário
            search_term: Termo de busca
            
        Returns:
            Lista de itens encontrados
        """
        sql = """
            SELECT 
                i.CodItem,
                i.CodInventario,
                i.CodProduto,
                p.Descricao,
                i.Quantidade,
                p.Unidade,
                p.CodigoBarras
            FROM dbo.InventarioItens i WITH (NOLOCK)
            LEFT JOIN dbo.Produtos p WITH (NOLOCK) ON i.CodProduto = p.CodProduto
            WHERE i.CodInventario = ?
              AND (p.CodProduto LIKE ? OR p.Descricao LIKE ? OR p.CodigoBarras LIKE ?)
            ORDER BY p.Descricao
        """
        
        search_pattern = f"%{search_term}%"
        results = self.execute_query(
            sql, 
            (inventory_id, search_pattern, search_pattern, search_pattern)
        )
        
        return [
            InventoryItem(
                id=row[0],
                inventory_id=row[1],
                product_code=row[2] or "",
                description=row[3] or "",
                quantity=float(row[4]) if row[4] else 0.0,
                unit=row[5] or "UN",
                barcode=row[6] or ""
            )
            for row in results
        ] if results else []
