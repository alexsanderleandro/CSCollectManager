"""
main_controller.py
==================
Controller principal que coordena as funcionalidades após o login.
"""

from typing import Optional, List, Dict, Any
from PySide6.QtCore import Signal, Slot, QThread, QObject

from controllers.base_controller import BaseController
from models.user import User
from services.inventory_service import InventoryService
from views.main_window import MainWindow


class DataLoaderWorker(QObject):
    """Worker para carregar dados em thread separada."""
    
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(int, str)
    
    def __init__(self, inventory_service: InventoryService):
        super().__init__()
        self._service = inventory_service
        self._filters = {}
    
    def set_filters(self, filters: Dict[str, Any]):
        """Define filtros para busca."""
        self._filters = filters
    
    def run(self):
        """Executa carregamento."""
        try:
            self.progress.emit(10, "Carregando grupos...")
            grupos = self._service.get_grupos()
            
            self.progress.emit(30, "Carregando tipos de produto...")
            tipos = self._service.get_tipos_produto()
            
            self.progress.emit(50, "Carregando localizações...")
            localizacoes = self._service.get_localizacoes()
            
            self.progress.emit(70, "Carregando produtos...")
            produtos = self._service.get_produtos(self._filters)
            
            self.progress.emit(100, "Concluído")
            
            self.finished.emit({
                "grupos": grupos,
                "tipos_produto": tipos,
                "localizacoes": localizacoes,
                "produtos": produtos
            })
            
        except Exception as e:
            self.error.emit(str(e))


class MainController(BaseController):
    """
    Controller principal da aplicação.
    
    Gerencia:
    - Navegação entre módulos
    - Estado global da aplicação
    - Coordenação entre diferentes controllers
    - Carregamento de dados
    - Exportação de carga
    """
    
    module_changed = Signal(str)  # nome do módulo
    user_logged_out = Signal()
    data_loaded = Signal(dict)
    export_completed = Signal(str)  # caminho do arquivo
    
    def __init__(self, view: MainWindow, user: User = None, parent=None):
        super().__init__(parent)
        self._view = view
        self._user = user
        self._current_module: str = ""
        self._inventory_service = InventoryService()
        
        # Thread para carregamento
        self._loader_thread: QThread = None
        self._loader_worker: DataLoaderWorker = None
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Conecta sinais da view."""
        self._view.logout_requested.connect(self.logout)
        self._view.export_requested.connect(self._on_export_requested)
        self._view.filter_panel.select_clicked.connect(self._on_apply_filters)
    
    @property
    def user(self) -> User:
        """Retorna o usuário logado."""
        return self._user
    
    @property
    def current_module(self) -> str:
        """Retorna o módulo atual."""
        return self._current_module
    
    def navigate_to(self, module_name: str) -> None:
        """
        Navega para um módulo específico.
        
        Args:
            module_name: Nome do módulo (inventory, export, settings, etc.)
        """
        self._current_module = module_name
        self.module_changed.emit(module_name)
        self.update_status(f"Módulo: {module_name}")
    
    def logout(self) -> None:
        """Realiza logout do usuário."""
        self._user = None
        self._current_module = ""
        self.user_logged_out.emit()
    
    def get_user_permissions(self) -> List[str]:
        """Retorna lista de permissões do usuário."""
        permissions = ["inventory", "export", "settings"]
        if self._user and self._user.is_manager:
            permissions.append("admin")
        return permissions
    
    def load_initial_data(self):
        """Carrega dados iniciais."""
        self._view.set_status("Carregando dados...")
        self._view.show_progress(True, 0)
        
        # Cria worker e thread
        self._loader_thread = QThread()
        self._loader_worker = DataLoaderWorker(self._inventory_service)
        self._loader_worker.moveToThread(self._loader_thread)
        
        # Conecta sinais
        self._loader_thread.started.connect(self._loader_worker.run)
        self._loader_worker.finished.connect(self._on_data_loaded)
        self._loader_worker.error.connect(self._on_load_error)
        self._loader_worker.progress.connect(self._on_load_progress)
        self._loader_worker.finished.connect(self._loader_thread.quit)
        
        self._loader_thread.start()
    
    def refresh_products(self, filters: Dict[str, Any] = None):
        """
        Atualiza lista de produtos com filtros.
        
        Args:
            filters: Filtros a aplicar
        """
        self._view.set_status("Filtrando produtos...")
        self._view.show_progress(True, 0)
        
        try:
            produtos = self._inventory_service.get_produtos(filters or {})
            self._view.load_products(produtos)
            self._view.set_status(f"{len(produtos)} produtos encontrados")
        except Exception as e:
            self.show_error("Erro ao filtrar produtos", str(e))
        finally:
            self._view.show_progress(False)
    
    @Slot()
    def _on_apply_filters(self):
        """Aplica filtros selecionados."""
        filters = self._view.filter_panel.get_filters()
        self.refresh_products(filters)
    
    @Slot(dict)
    def _on_data_loaded(self, data: Dict[str, Any]):
        """Callback quando dados são carregados."""
        self._view.show_progress(False)
        
        # Carrega filtros
        self._view.load_filter_data(
            grupos=data.get("grupos", []),
            tipos_produto=data.get("tipos_produto", []),
            localizacoes=data.get("localizacoes", [])
        )
        
        # Carrega produtos
        self._view.load_products(data.get("produtos", []))
        
        self._view.set_status("Dados carregados com sucesso")
        self.data_loaded.emit(data)
    
    @Slot(str)
    def _on_load_error(self, error: str):
        """Callback quando ocorre erro no carregamento."""
        self._view.show_progress(False)
        self._view.set_status("Erro ao carregar dados")
        self.show_error("Erro ao carregar dados", error)
    
    @Slot(int, str)
    def _on_load_progress(self, value: int, message: str):
        """Callback de progresso do carregamento."""
        self._view.show_progress(True, value)
        self._view.set_status(message)
    
    @Slot(dict)
    def _on_export_requested(self, data: Dict[str, Any]):
        """
        Callback quando exportação é solicitada.
        
        Args:
            data: Dados com filtros e seleção
        """
        self._view.set_status("Exportando carga...")
        self._view.show_progress(True, 0)
        
        try:
            # TODO: Implementar exportação real
            selected_codes = data.get("selected_codes", [])
            export_photos = data.get("exportar_fotos", False)
            
            # Simula progresso
            self._view.show_progress(True, 50)
            
            # Aqui chamaria o export_service
            # result = self._export_service.export(selected_codes, export_photos)
            
            self._view.show_progress(True, 100)
            self._view.set_status(f"Exportação concluída: {len(selected_codes)} produtos")
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self._view,
                "Exportação Concluída",
                f"Foram exportados {len(selected_codes)} produtos com sucesso!"
            )
            
        except Exception as e:
            self.show_error("Erro na exportação", str(e))
        finally:
            self._view.show_progress(False)
