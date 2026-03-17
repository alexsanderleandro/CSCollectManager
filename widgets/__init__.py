"""
Widgets Package
===============
Widgets customizados reutilizáveis.

Responsabilidades:
- Fornecer componentes visuais personalizados
- Encapsular comportamentos específicos de UI
- Padronizar aparência e comportamento
"""

from widgets.loading_overlay import LoadingOverlay
from widgets.searchable_combo import SearchableComboBox
from widgets.data_table import DataTableWidget
from widgets.multi_select_combo import MultiSelectCombo, SingleSelectCombo
from widgets.filter_panel import FilterPanel
from widgets.product_table import ProductTable
from widgets.progress_dialog import ProgressDialog, ProgressOverlay
from widgets.lazy_product_table import LazyProductTable
from widgets.status_bar import AppStatusBar, StatusIndicator, ConnectionIndicator, ProgressIndicator

__all__ = [
    "LoadingOverlay",
    "SearchableComboBox",
    "DataTableWidget",
    "MultiSelectCombo",
    "SingleSelectCombo",
    "FilterPanel",
    "ProductTable",
    "ProgressDialog",
    "ProgressOverlay",
    "LazyProductTable",
    "AppStatusBar",
    "StatusIndicator",
    "ConnectionIndicator",
    "ProgressIndicator",
]
