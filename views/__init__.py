"""
Views Package
=============
Camada de visualização (View) do padrão MVC.

Responsabilidades:
- Definir interfaces de usuário com PySide6
- Exibir dados ao usuário
- Capturar eventos de interação
- Delegar ações aos Controllers
- Manter-se "burra" (sem lógica de negócio)
"""

from views.login_view import LoginView
from views.main_view import MainView
from views.main_window import MainWindow
from views.inventory_view import InventoryView
from views.product_list_view import ProductListView
from views.about_dialog import AboutDialog, SystemInfoDialog

__all__ = [
    "LoginView",
    "MainView",
    "MainWindow",
    "InventoryView",
    "ProductListView",
    "AboutDialog",
    "SystemInfoDialog",
]
