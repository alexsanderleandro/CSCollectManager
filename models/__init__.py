"""
Models Package
==============
Camada de modelos de dados (Model) do padrão MVC.

Responsabilidades:
- Definir estruturas de dados do domínio
- Representar entidades do sistema
- Validar dados em nível de modelo
- Fornecer métodos de serialização/deserialização

Inclui:
- Modelos de domínio (dataclasses)
- Modelos SQLAlchemy ORM para banco de dados
"""

# Modelos de domínio (dataclasses)
from models.user import User
from models.connection import Connection
from models.inventory import Inventory, InventoryItem
from models.company import Company

# Modelos SQLAlchemy ORM
from models.database_models import (
    Base,
    Empresa,
    Usuario,
    Vendedor,
    TipoCliente,
    TipoProduto,
    GrupoEstoque,
    LocalEstoque,
    Produto,
    ProdutoEstoque,
    ProdutoLote,
    ProdutoAnexo,
    create_all_tables,
    drop_all_tables,
    get_table_names,
)

# Modelo de tabela Qt
from models.product_table_model import (
    ProductData,
    ProductTableModel,
    ProductSortFilterProxyModel,
)

# Modelo com lazy loading para alta performance
from models.lazy_table_model import (
    LazyTableModel,
    LazySortFilterProxyModel,
)

__all__ = [
    # Modelos de domínio
    "User",
    "Connection",
    "Inventory",
    "InventoryItem",
    "Company",
    
    # SQLAlchemy Base
    "Base",
    
    # Modelos ORM
    "Empresa",
    "Usuario",
    "Vendedor",
    "TipoCliente",
    "TipoProduto",
    "GrupoEstoque",
    "LocalEstoque",
    "Produto",
    "ProdutoEstoque",
    "ProdutoLote",
    "ProdutoAnexo",
    
    # Modelo Qt para tabelas
    "ProductData",
    "ProductTableModel",
    "ProductSortFilterProxyModel",
    
    # Modelo com lazy loading
    "LazyTableModel",
    "LazySortFilterProxyModel",
    
    # Funções auxiliares
    "create_all_tables",
    "drop_all_tables",
    "get_table_names",
]
