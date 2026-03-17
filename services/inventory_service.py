"""
inventory_service.py
====================
Serviço de gerenciamento de inventários e produtos.
"""

from typing import Optional, List, Tuple, Dict, Any
from models.inventory import Inventory, InventoryItem
from repositories.inventory_repository import InventoryRepository
from repositories.product_repository import ProductRepository


class InventoryService:
    """
    Serviço responsável pela lógica de negócio de inventários e produtos.
    
    Funcionalidades:
    - Listar inventários disponíveis
    - Obter detalhes de inventário
    - Carregar itens de inventário
    - Validar dados para exportação
    - Carregar produtos com filtros
    - Carregar dados para filtros
    """
    
    def __init__(self):
        self._repository = InventoryRepository()
        self._product_repository = ProductRepository()
    
    # ===== MÉTODOS DE INVENTÁRIO =====
    
    def get_inventories(
        self,
        company_code: str = "",
        status: Optional[str] = None
    ) -> List[Inventory]:
        """
        Retorna lista de inventários.
        
        Args:
            company_code: Filtro por empresa
            status: Filtro por status (aberto, fechado, etc.)
            
        Returns:
            Lista de inventários
        """
        return self._repository.get_all(
            company_code=company_code,
            status=status
        )
    
    def get_inventory_by_id(self, inventory_id: int) -> Optional[Inventory]:
        """
        Busca inventário por ID.
        
        Args:
            inventory_id: ID do inventário
            
        Returns:
            Inventário ou None
        """
        return self._repository.get_by_id(inventory_id)
    
    def get_inventory_items(
        self,
        inventory_id: int,
        page: int = 1,
        page_size: int = 1000
    ) -> List[InventoryItem]:
        """
        Carrega itens de um inventário.
        
        Args:
            inventory_id: ID do inventário
            page: Página (para paginação)
            page_size: Itens por página
            
        Returns:
            Lista de itens
        """
        return self._repository.get_items(
            inventory_id=inventory_id,
            offset=(page - 1) * page_size,
            limit=page_size
        )
    
    def get_item_count(self, inventory_id: int) -> int:
        """
        Retorna quantidade total de itens no inventário.
        
        Args:
            inventory_id: ID do inventário
            
        Returns:
            Quantidade de itens
        """
        return self._repository.count_items(inventory_id)
    
    def validate_for_export(self, inventory: Inventory) -> Tuple[bool, List[str]]:
        """
        Valida se inventário está apto para exportação.
        
        Args:
            inventory: Inventário a validar
            
        Returns:
            Tupla (válido, lista de mensagens de erro)
        """
        errors = []
        
        if not inventory:
            errors.append("Inventário não selecionado")
            return False, errors
        
        # Verifica se tem itens
        count = self.get_item_count(inventory.id)
        if count == 0:
            errors.append("Inventário não possui itens")
        
        return len(errors) == 0, errors
    
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
        return self._repository.search_items(
            inventory_id=inventory_id,
            search_term=search_term
        )
    
    # ===== MÉTODOS DE PRODUTO =====
    
    def get_produtos(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Carrega produtos com filtros aplicados.
        
        Args:
            filters: Dicionário de filtros
            
        Returns:
            Lista de produtos como dicionários
        """
        return self._product_repository.get_produtos(filters or {})
    
    def get_grupos(self) -> List[Tuple[int, str]]:
        """
        Carrega grupos de estoque para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        return self._product_repository.get_grupos()
    
    def get_tipos_produto(self) -> List[Tuple[int, str]]:
        """
        Carrega tipos de produto para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        return self._product_repository.get_tipos_produto()
    
    def get_localizacoes(self) -> List[Tuple[int, str]]:
        """
        Carrega localizações para filtro.
        
        Returns:
            Lista de (codigo, descricao)
        """
        return self._product_repository.get_localizacoes()
    
    def get_fornecedores(self) -> List[Tuple[int, str]]:
        """
        Carrega fornecedores para filtro.
        
        Returns:
            Lista de (codigo, nome)
        """
        return self._product_repository.get_fornecedores()
    
    def get_fabricantes(self) -> List[Tuple[int, str]]:
        """
        Carrega fabricantes para filtro.
        
        Returns:
            Lista de (codigo, nome)
        """
        return self._product_repository.get_fabricantes()
