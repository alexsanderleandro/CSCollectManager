"""
Repositories Package
====================
Camada de acesso a dados (Repository Pattern).

Responsabilidades:
- Encapsular acesso ao banco de dados
- Mapear dados do banco para objetos do domínio
- Executar queries SQL
- Abstrair detalhes de persistência dos Services
"""

from repositories.base_repository import BaseRepository
from repositories.inventory_repository import InventoryRepository
from repositories.user_repository import UserRepository
from repositories.product_repository import ProductRepository

__all__ = [
    "BaseRepository",
    "InventoryRepository",
    "UserRepository",
    "ProductRepository",
]
