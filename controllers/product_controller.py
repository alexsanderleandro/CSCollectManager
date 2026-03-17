"""
product_controller.py
=====================
Controller para gerenciamento de produtos com alta performance.

Integra:
- Lazy loading com 50.000+ produtos
- Threads separadas para exportação
- Barra de progresso
- Consultas paginadas
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QWidget, QMessageBox, QFileDialog

from models.lazy_table_model import LazyTableModel, LazySortFilterProxyModel
from services.product_service import ProductService, ProductFilter
from services.export_service import ExportService, EmpresaInfo, UsuarioInfo
from services.photo_export_service import PhotoExportService
from utils.workers import (
    DataLoaderWorker, ExportWorker, PhotoExportWorker, WorkerManager
)
from widgets.progress_dialog import ProgressDialog, ProgressOverlay


@dataclass
class ExportConfig:
    """Configuração de exportação."""
    empresa: EmpresaInfo
    usuario: UsuarioInfo
    output_dir: str = None
    include_photos: bool = False
    photo_format: str = "jpg"
    photo_quality: int = 85


class ProductController(QObject):
    """
    Controller de produtos com suporte a alta performance.
    
    Signals:
        loading_started: Início do carregamento
        loading_progress: Progresso (loaded, total, percentage, message)
        loading_finished: Carregamento concluído (total)
        loading_error: Erro no carregamento
        export_started: Início da exportação
        export_progress: Progresso da exportação
        export_finished: Exportação concluída (filepath)
        export_error: Erro na exportação
        status_message: Mensagem de status
    """
    
    loading_started = Signal()
    loading_progress = Signal(int, int, float, str)
    loading_finished = Signal(int)
    loading_error = Signal(str)
    
    export_started = Signal()
    export_progress = Signal(int, int, float, str)
    export_finished = Signal(str)
    export_error = Signal(str)
    
    status_message = Signal(str)
    
    # Configuração de performance
    PAGE_SIZE = 2000  # Registros por página
    LOAD_THRESHOLD = 1000  # Carregar mais quando restam X registros
    
    def __init__(self, parent: QWidget = None):
        """
        Inicializa o controller.
        
        Args:
            parent: Widget pai
        """
        super().__init__(parent)
        
        self._parent = parent
        
        # Services
        self._product_service = ProductService()
        self._export_service = ExportService()
        self._photo_service = PhotoExportService()
        
        # Model
        self._model = LazyTableModel()
        self._proxy_model = LazySortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        
        # Workers
        self._worker_manager = WorkerManager(self)
        self._current_loader: Optional[DataLoaderWorker] = None
        self._current_exporter: Optional[ExportWorker] = None
        
        # State
        self._current_filter: Optional[ProductFilter] = None
        self._is_loading = False
        self._is_exporting = False
        
        # Configuração do modelo
        self._model.set_page_size(self.PAGE_SIZE)
        self._model.set_load_threshold(self.LOAD_THRESHOLD)
        self._model.request_more_data.connect(self._on_request_more_data)
    
    @property
    def model(self) -> LazyTableModel:
        """Retorna modelo de dados."""
        return self._model
    
    @property
    def proxy_model(self) -> LazySortFilterProxyModel:
        """Retorna proxy model com filtro/ordenação."""
        return self._proxy_model
    
    @property
    def is_loading(self) -> bool:
        """Verifica se está carregando."""
        return self._is_loading
    
    @property
    def is_exporting(self) -> bool:
        """Verifica se está exportando."""
        return self._is_exporting
    
    # ==========================================
    # DATA LOADING (Lazy Loading)
    # ==========================================
    
    def load_products(self, filters: ProductFilter = None):
        """
        Inicia carregamento de produtos com lazy loading.
        
        Args:
            filters: Filtros a aplicar
        """
        if self._is_loading:
            self.cancel_loading()
        
        self._current_filter = filters
        self._is_loading = True
        
        # Limpa dados anteriores
        self._model.clear()
        self._model.begin_loading()
        
        self.loading_started.emit()
        self.status_message.emit("Carregando produtos...")
        
        # Cria worker com função de fetch
        def fetch_page(page: int, page_size: int):
            return self._product_service.get_products_paginated(
                filters=self._current_filter,
                page=page,
                page_size=page_size
            )
        
        self._current_loader = self._worker_manager.create_data_loader(
            fetch_function=fetch_page,
            page_size=self.PAGE_SIZE
        )
        
        # Conecta sinais
        self._current_loader.page_ready.connect(self._on_page_ready)
        self._current_loader.progress.connect(self._on_loading_progress)
        self._current_loader.finished.connect(self._on_loading_finished)
        self._current_loader.error.connect(self._on_loading_error)
        self._current_loader.cancelled.connect(self._on_loading_cancelled)
        
        # Inicia
        self._current_loader.start()
    
    def cancel_loading(self):
        """Cancela carregamento em andamento."""
        if self._current_loader and self._current_loader.isRunning():
            self._current_loader.cancel()
    
    @Slot(int, object)
    def _on_page_ready(self, page: int, data: List[Dict[str, Any]]):
        """Processa página de dados carregada."""
        if page == 1:
            # Primeira página: define total
            _, total = self._product_service.get_products_paginated(
                self._current_filter, 1, 1
            )
            self._model.set_total_records(total)
        
        self._model.append_data(data)
    
    @Slot(int, int, float, str)
    def _on_loading_progress(self, current: int, total: int, percentage: float, message: str):
        """Atualiza progresso do carregamento."""
        self.loading_progress.emit(current, total, percentage, message)
        self.status_message.emit(f"Carregando: {current:,} de {total:,} produtos")
    
    @Slot(int)
    def _on_loading_finished(self, total: int):
        """Finaliza carregamento."""
        self._is_loading = False
        self._model.end_loading()
        self.loading_finished.emit(total)
        self.status_message.emit(f"Carregados {total:,} produtos")
    
    @Slot(Exception)
    def _on_loading_error(self, error: Exception):
        """Trata erro no carregamento."""
        self._is_loading = False
        self._model.end_loading()
        self.loading_error.emit(str(error))
        self.status_message.emit(f"Erro: {error}")
    
    @Slot()
    def _on_loading_cancelled(self):
        """Trata cancelamento."""
        self._is_loading = False
        self._model.end_loading()
        self.status_message.emit("Carregamento cancelado")
    
    @Slot(int)
    def _on_request_more_data(self, offset: int):
        """Carrega mais dados (lazy loading automático)."""
        if self._is_loading or self._model.is_fully_loaded:
            return
        
        # Calcula próxima página
        current_page = (offset // self.PAGE_SIZE) + 1
        next_page = current_page + 1
        
        self._load_next_page(next_page)
    
    def _load_next_page(self, page: int):
        """Carrega próxima página de dados."""
        if self._is_loading:
            return
        
        self._is_loading = True
        
        def fetch_page(p: int, page_size: int):
            return self._product_service.get_products_paginated(
                filters=self._current_filter,
                page=p,
                page_size=page_size
            )
        
        self._current_loader = self._worker_manager.create_data_loader(
            fetch_function=lambda p, ps: fetch_page(page, ps),
            page_size=self.PAGE_SIZE
        )
        
        self._current_loader.page_ready.connect(
            lambda _, data: self._model.append_data(data)
        )
        self._current_loader.finished.connect(
            lambda _: setattr(self, '_is_loading', False)
        )
        self._current_loader.error.connect(
            lambda e: self.status_message.emit(f"Erro ao carregar: {e}")
        )
        
        self._current_loader.start()
    
    # ==========================================
    # EXPORT (Thread Separada)
    # ==========================================
    
    def export_carga(
        self,
        config: ExportConfig,
        codprodutos: List[int] = None,
        show_dialog: bool = True
    ):
        """
        Exporta carga para arquivo TXT.
        
        Args:
            config: Configuração da exportação
            codprodutos: Lista de produtos (None = todos carregados)
            show_dialog: Se deve mostrar diálogo de progresso
        """
        if self._is_exporting:
            QMessageBox.warning(
                self._parent,
                "Exportação em Andamento",
                "Aguarde a exportação atual terminar."
            )
            return
        
        # Se não especificou produtos, usa todos carregados
        if codprodutos is None:
            codprodutos = self._model.get_all_codprodutos()
        
        if not codprodutos:
            QMessageBox.warning(
                self._parent,
                "Sem Produtos",
                "Nenhum produto para exportar."
            )
            return
        
        self._is_exporting = True
        self.export_started.emit()
        
        # Diálogo de progresso
        progress_dialog = None
        if show_dialog and self._parent:
            progress_dialog = ProgressDialog(
                title="Exportando Carga",
                message="Preparando exportação...",
                parent=self._parent,
                cancelable=True
            )
            progress_dialog.cancelled.connect(self._cancel_export)
        
        # Busca dados completos dos produtos
        self.status_message.emit("Buscando dados dos produtos...")
        
        try:
            # Busca em lotes para performance
            produtos_data = self._fetch_products_for_export(codprodutos)
        except Exception as e:
            self._is_exporting = False
            self.export_error.emit(str(e))
            return
        
        # Cria worker de exportação
        def export_function(progress_callback=None):
            return self._export_service.export_carga(
                empresa=config.empresa,
                usuario=config.usuario,
                produtos=produtos_data,
                output_path=config.output_dir,
                progress_callback=progress_callback
            )
        
        self._current_exporter = self._worker_manager.create_export_worker(
            export_function=export_function
        )
        
        # Conecta sinais
        if progress_dialog:
            self._current_exporter.progress.connect(progress_dialog.update_progress)
            self._current_exporter.finished.connect(
                lambda path: progress_dialog.finish(True, f"Exportado: {path}")
            )
            self._current_exporter.error.connect(progress_dialog.show_error)
            progress_dialog.show()
        
        self._current_exporter.progress.connect(self._on_export_progress)
        self._current_exporter.finished.connect(self._on_export_finished)
        self._current_exporter.error.connect(self._on_export_error)
        self._current_exporter.cancelled.connect(self._on_export_cancelled)
        
        self._current_exporter.start()
    
    def export_photos(
        self,
        codprodutos: List[int] = None,
        output_dir: str = None,
        filename: str = "Fotos.zip",
        convert_to: str = "jpg",
        quality: int = 85,
        show_dialog: bool = True
    ):
        """
        Exporta fotos para arquivo ZIP.
        
        Args:
            codprodutos: Lista de produtos (None = todos carregados)
            output_dir: Diretório de saída
            filename: Nome do arquivo ZIP
            convert_to: Formato (jpg/png)
            quality: Qualidade JPEG
            show_dialog: Se deve mostrar diálogo
        """
        if self._is_exporting:
            QMessageBox.warning(
                self._parent,
                "Exportação em Andamento",
                "Aguarde a exportação atual terminar."
            )
            return
        
        if codprodutos is None:
            codprodutos = self._model.get_all_codprodutos()
        
        if not codprodutos:
            QMessageBox.warning(
                self._parent,
                "Sem Produtos",
                "Nenhum produto para exportar fotos."
            )
            return
        
        self._is_exporting = True
        self.export_started.emit()
        
        # Diálogo de progresso
        progress_dialog = None
        if show_dialog and self._parent:
            progress_dialog = ProgressDialog(
                title="Exportando Fotos",
                message="Preparando exportação de fotos...",
                parent=self._parent,
                cancelable=True
            )
            progress_dialog.cancelled.connect(self._cancel_export)
        
        # Cria worker específico para fotos
        self._current_exporter = PhotoExportWorker(
            photo_service=self._photo_service,
            codprodutos=codprodutos,
            output_path=output_dir,
            filename=filename,
            convert_to=convert_to,
            quality=quality,
            parent=self
        )
        
        # Conecta sinais
        if progress_dialog:
            self._current_exporter.progress.connect(progress_dialog.update_progress)
            self._current_exporter.finished.connect(
                lambda path, count: progress_dialog.finish(
                    True, f"Exportadas {count} fotos para {path}"
                )
            )
            self._current_exporter.error.connect(progress_dialog.show_error)
            progress_dialog.show()
        
        self._current_exporter.progress.connect(self._on_export_progress)
        self._current_exporter.finished.connect(
            lambda path, _: self._on_export_finished(path)
        )
        self._current_exporter.error.connect(self._on_export_error)
        self._current_exporter.cancelled.connect(self._on_export_cancelled)
        
        self._current_exporter.start()
    
    def _cancel_export(self):
        """Cancela exportação em andamento."""
        if self._current_exporter:
            self._current_exporter.cancel()
    
    def _fetch_products_for_export(
        self,
        codprodutos: List[int],
        batch_size: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Busca dados completos dos produtos para exportação.
        
        Args:
            codprodutos: Lista de códigos
            batch_size: Tamanho do lote
            
        Returns:
            Lista de produtos com dados completos
        """
        all_products = []
        
        for i in range(0, len(codprodutos), batch_size):
            batch = codprodutos[i:i + batch_size]
            
            filter_batch = ProductFilter(produtos=batch)
            products = self._product_service.get_products(filter_batch)
            all_products.extend(products)
        
        return all_products
    
    @Slot(int, int, float, str)
    def _on_export_progress(self, current: int, total: int, percentage: float, message: str):
        """Atualiza progresso da exportação."""
        self.export_progress.emit(current, total, percentage, message)
        self.status_message.emit(message)
    
    @Slot(str)
    def _on_export_finished(self, filepath: str):
        """Finaliza exportação."""
        self._is_exporting = False
        self.export_finished.emit(filepath)
        self.status_message.emit(f"Exportação concluída: {filepath}")
    
    @Slot(Exception)
    def _on_export_error(self, error: Exception):
        """Trata erro na exportação."""
        self._is_exporting = False
        self.export_error.emit(str(error))
        self.status_message.emit(f"Erro na exportação: {error}")
    
    @Slot()
    def _on_export_cancelled(self):
        """Trata cancelamento da exportação."""
        self._is_exporting = False
        self.status_message.emit("Exportação cancelada")
    
    # ==========================================
    # FILTER & SEARCH
    # ==========================================
    
    def apply_filter(self, filters: ProductFilter):
        """Aplica novos filtros e recarrega dados."""
        self.load_products(filters)
    
    def search_text(self, text: str, columns: List[int] = None):
        """
        Filtra por texto na tabela.
        
        Args:
            text: Texto a buscar
            columns: Colunas onde buscar (None = todas)
        """
        if columns:
            self._proxy_model.set_filter_columns(columns)
        self._proxy_model.set_filter_text(text)
    
    def sort_by_column(self, column: int, ascending: bool = True):
        """Ordena por coluna."""
        from PySide6.QtCore import Qt
        order = Qt.SortOrder.AscendingOrder if ascending else Qt.SortOrder.DescendingOrder
        self._proxy_model.sort(column, order)
    
    # ==========================================
    # SELECTION
    # ==========================================
    
    def get_selected_products(self, proxy_rows: List[int]) -> List[Any]:
        """
        Retorna produtos das linhas selecionadas.
        
        Args:
            proxy_rows: Índices do proxy model
            
        Returns:
            Lista de ProductData
        """
        source_rows = self._proxy_model.get_source_rows(proxy_rows)
        return self._model.get_selected_products(source_rows)
    
    def get_selected_codprodutos(self, proxy_rows: List[int]) -> List[int]:
        """Retorna códigos dos produtos selecionados."""
        products = self.get_selected_products(proxy_rows)
        return [p.codproduto for p in products]
    
    # ==========================================
    # STATISTICS
    # ==========================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas dos dados carregados."""
        return {
            "total_records": self._model.total_records,
            "loaded_records": self._model.loaded_records,
            "fully_loaded": self._model.is_fully_loaded,
            "is_loading": self._is_loading,
            "is_exporting": self._is_exporting,
            "filtered_count": self._proxy_model.rowCount(),
        }
    
    # ==========================================
    # CLEANUP
    # ==========================================
    
    def cleanup(self):
        """Limpa recursos e cancela operações."""
        self.cancel_loading()
        self._cancel_export()
        self._worker_manager.cancel_all()
        self._model.clear()
