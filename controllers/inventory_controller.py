"""
inventory_controller.py
=======================
Controller responsável pelo gerenciamento de inventários e exportação para coletores.
"""

from typing import Optional, List
from PySide6.QtCore import Signal
from pathlib import Path

from controllers.base_controller import BaseController
from services.inventory_service import InventoryService
from services.export_service import ExportService
from models.inventory import Inventory, InventoryItem


class InventoryController(BaseController):
    """
    Controller para gerenciamento de inventários.
    
    Signals:
        inventories_loaded: Lista de inventários carregada
        inventory_items_loaded: Itens de um inventário carregados
        export_completed: Exportação concluída com sucesso
        export_progress: Progresso da exportação (0-100)
    """
    
    inventories_loaded = Signal(list)  # List[Inventory]
    inventory_items_loaded = Signal(list)  # List[InventoryItem]
    export_completed = Signal(str)  # caminho do arquivo exportado
    export_failed = Signal(str)  # mensagem de erro
    export_progress = Signal(int)  # percentual de progresso
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._inventory_service = InventoryService()
        self._export_service = ExportService()
        self._current_inventory: Optional[Inventory] = None
    
    @property
    def current_inventory(self) -> Optional[Inventory]:
        """Retorna o inventário selecionado."""
        return self._current_inventory
    
    def load_inventories(self, company_code: str = "") -> None:
        """
        Carrega lista de inventários disponíveis.
        
        Args:
            company_code: Código da empresa (filtro opcional)
        """
        try:
            self.set_loading(True, "Carregando inventários...")
            inventories = self._inventory_service.get_inventories(company_code)
            self.inventories_loaded.emit(inventories)
        except Exception as e:
            self.handle_error(e, "Erro ao carregar inventários")
        finally:
            self.set_loading(False)
    
    def select_inventory(self, inventory: Inventory) -> None:
        """
        Seleciona um inventário e carrega seus itens.
        
        Args:
            inventory: Inventário a ser selecionado
        """
        try:
            self.set_loading(True, "Carregando itens do inventário...")
            self._current_inventory = inventory
            items = self._inventory_service.get_inventory_items(inventory.id)
            self.inventory_items_loaded.emit(items)
        except Exception as e:
            self.handle_error(e, "Erro ao carregar itens")
        finally:
            self.set_loading(False)
    
    def export_to_collector(
        self,
        inventory: Inventory,
        output_path: str,
        format_type: str = "txt",
        compress: bool = True
    ) -> None:
        """
        Exporta inventário para carga do coletor de dados.
        
        Args:
            inventory: Inventário a ser exportado
            output_path: Caminho de saída do arquivo
            format_type: Formato de exportação (txt, csv, xml)
            compress: Se True, compacta em ZIP
        """
        try:
            self.set_loading(True, "Exportando para coletor...")
            
            # Callback de progresso
            def on_progress(percent: int):
                self.export_progress.emit(percent)
            
            result_path = self._export_service.export_inventory(
                inventory=inventory,
                output_path=output_path,
                format_type=format_type,
                compress=compress,
                progress_callback=on_progress
            )
            
            self.export_completed.emit(result_path)
            self.update_status(f"Exportação concluída: {result_path}")
            
        except Exception as e:
            self.export_failed.emit(str(e))
            self.handle_error(e, "Erro na exportação")
        finally:
            self.set_loading(False)
    
    def get_export_formats(self) -> List[dict]:
        """Retorna formatos de exportação disponíveis."""
        return self._export_service.get_available_formats()
