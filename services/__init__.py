"""
Services Package
================
Camada de serviços (Service Layer) do sistema.

Responsabilidades:
- Implementar a lógica de negócio da aplicação
- Orquestrar operações entre múltiplos repositórios
- Validar regras de negócio
- Processar e transformar dados
- Gerenciar transações
"""

from services.auth_service import AuthService
from services.connection_service import ConnectionService
from services.inventory_service import InventoryService
from services.export_service import ExportService, EmpresaInfo, UsuarioInfo, ProdutoExport
from services.product_service import ProductService, ProductFilter
from services.photo_export_service import PhotoExportService, PhotoInfo

__all__ = [
    "AuthService",
    "ConnectionService",
    "InventoryService",
    "ExportService",
    "EmpresaInfo",
    "UsuarioInfo",
    "ProdutoExport",
    "ProductService",
    "ProductFilter",
    "PhotoExportService",
    "PhotoInfo",
]
