"""
Controllers Package
====================
Camada de controle (Controller) do padrão MVC.

Responsabilidades:
- Intermediar comunicação entre Views e Services
- Processar eventos da interface do usuário
- Validar dados de entrada
- Coordenar fluxos de trabalho
- Atualizar as views com dados do modelo
"""

from controllers.base_controller import BaseController
from controllers.login_controller import LoginController
from controllers.main_controller import MainController
from controllers.inventory_controller import InventoryController
from controllers.product_controller import ProductController, ExportConfig

__all__ = [
    "BaseController",
    "LoginController",
    "MainController",
    "InventoryController",
    "ProductController",
    "ExportConfig",
]
