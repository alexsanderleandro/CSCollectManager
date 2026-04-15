"""
workers.py
==========
Workers para operações assíncronas em threads separadas.

Implementa QThread e QRunnable para:
- Carregamento de dados com lazy loading
- Exportação de arquivos
- Operações de longa duração sem travar a UI
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import (
    QObject, QThread, QRunnable, QThreadPool,
    Signal, Slot, QMutex, QWaitCondition
)


class WorkerState(Enum):
    """Estados do worker."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class WorkerProgress:
    """Dados de progresso do worker."""
    current: int
    total: int
    percentage: float
    message: str
    
    @classmethod
    def create(cls, current: int, total: int, message: str = "") -> "WorkerProgress":
        """Cria instância com cálculo de percentual."""
        percentage = (current / total * 100) if total > 0 else 0
        return cls(current=current, total=total, percentage=percentage, message=message)


# =============================================================================
# BASE WORKER SIGNALS
# =============================================================================

class WorkerSignals(QObject):
    """
    Sinais para workers.
    
    Signals:
        started: Worker iniciou
        progress: Progresso (current, total, percentage, message)
        data_ready: Dados prontos (dados)
        page_ready: Página de dados pronta (page_number, data)
        finished: Worker finalizado (resultado)
        error: Erro ocorreu (exception)
        cancelled: Worker cancelado
    """
    started = Signal()
    progress = Signal(int, int, float, str)  # current, total, percentage, message
    data_ready = Signal(object)  # qualquer dado
    page_ready = Signal(int, object)  # page_number, data
    finished = Signal(object)  # resultado final
    error = Signal(Exception)
    cancelled = Signal()


# =============================================================================
# DATA LOADER WORKER (QThread)
# =============================================================================

class DataLoaderWorker(QThread):
    """
    Worker para carregamento de dados com paginação.
    
    Usa QThread para carregamento paginado de dados,
    permitindo lazy loading e atualização incremental da UI.
    
    Signals:
        started: Worker iniciou
        progress: Progresso (current, total, percentage, message)
        page_ready: Página de dados pronta (page_number, data)
        finished: Worker finalizado (total_records)
        error: Erro ocorreu (exception)
        cancelled: Worker cancelado
    """
    
    # Sinais
    progress = Signal(int, int, float, str)
    page_ready = Signal(int, object)
    finished = Signal(int)
    error = Signal(Exception)
    cancelled = Signal()
    
    def __init__(
        self,
        fetch_function: Callable,
        page_size: int = 1000,
        parent=None
    ):
        """
        Inicializa o worker.
        
        Args:
            fetch_function: Função que retorna (data, total) com params (page, page_size)
            page_size: Registros por página
            parent: QObject pai
        """
        super().__init__(parent)
        
        self._fetch_function = fetch_function
        self._page_size = page_size
        self._state = WorkerState.IDLE
        self._cancel_requested = False
        self._pause_requested = False
        
        # Mutex para sincronização
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()
    
    @property
    def state(self) -> WorkerState:
        """Estado atual do worker."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Verifica se está executando."""
        return self._state == WorkerState.RUNNING
    
    @property
    def is_cancelled(self) -> bool:
        """Verifica se foi cancelado."""
        return self._cancel_requested
    
    def cancel(self):
        """Solicita cancelamento do worker."""
        self._mutex.lock()
        self._cancel_requested = True
        self._pause_requested = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
    
    def pause(self):
        """Pausa o worker."""
        self._mutex.lock()
        self._pause_requested = True
        self._mutex.unlock()
    
    def resume(self):
        """Resume o worker pausado."""
        self._mutex.lock()
        self._pause_requested = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
    
    def run(self):
        """Executa o carregamento de dados."""
        self._state = WorkerState.RUNNING
        self._cancel_requested = False
        
        try:
            # Primeira página para obter total
            self.progress.emit(0, 0, 0, "Iniciando carregamento...")
            
            page = 1
            total_loaded = 0
            total_records = 0
            
            while True:
                # Verifica cancelamento
                if self._cancel_requested:
                    self._state = WorkerState.CANCELLED
                    self.cancelled.emit()
                    return
                
                # Verifica pausa
                self._mutex.lock()
                while self._pause_requested and not self._cancel_requested:
                    self._state = WorkerState.PAUSED
                    self._pause_condition.wait(self._mutex)
                self._mutex.unlock()
                
                if self._cancel_requested:
                    self._state = WorkerState.CANCELLED
                    self.cancelled.emit()
                    return
                
                self._state = WorkerState.RUNNING
                
                # Busca página
                try:
                    data, total = self._fetch_function(page, self._page_size)
                except Exception as e:
                    self._state = WorkerState.ERROR
                    self.error.emit(e)
                    return
                
                total_records = total
                
                if not data:
                    break
                
                # Emite dados da página
                self.page_ready.emit(page, data)
                
                total_loaded += len(data)
                percentage = (total_loaded / total_records * 100) if total_records > 0 else 100
                
                self.progress.emit(
                    total_loaded,
                    total_records,
                    percentage,
                    f"Carregados {total_loaded:,} de {total_records:,} registros"
                )
                
                # Verifica se terminou
                if total_loaded >= total_records:
                    break
                
                page += 1
            
            self._state = WorkerState.FINISHED
            self.finished.emit(total_loaded)
            
        except Exception as e:
            self._state = WorkerState.ERROR
            self.error.emit(e)


# =============================================================================
# EXPORT WORKER (QThread)
# =============================================================================

class ExportWorker(QThread):
    """
    Worker para exportação de arquivos.
    
    Signals:
        progress: Progresso (current, total, percentage, message)
        finished: Exportação concluída (filepath)
        error: Erro ocorreu (exception)
        cancelled: Exportação cancelada
    """
    
    progress = Signal(int, int, float, str)
    finished = Signal(str)
    error = Signal(Exception)
    cancelled = Signal()
    
    def __init__(
        self,
        export_function: Callable,
        export_args: tuple = None,
        export_kwargs: dict = None,
        parent=None
    ):
        """
        Inicializa o worker.
        
        Args:
            export_function: Função de exportação
            export_args: Argumentos posicionais
            export_kwargs: Argumentos nomeados
            parent: QObject pai
        """
        super().__init__(parent)
        
        self._export_function = export_function
        self._export_args = export_args or ()
        self._export_kwargs = export_kwargs or {}
        self._cancel_requested = False
        self._state = WorkerState.IDLE
    
    @property
    def state(self) -> WorkerState:
        """Estado atual."""
        return self._state
    
    def cancel(self):
        """Solicita cancelamento."""
        self._cancel_requested = True
    
    @property
    def is_cancelled(self) -> bool:
        """Verifica se foi cancelado."""
        return self._cancel_requested
    
    def run(self):
        """Executa a exportação."""
        self._state = WorkerState.RUNNING
        self._cancel_requested = False
        
        try:
            # Callback de progresso para a função de exportação
            def progress_callback(percentage: int, message: str):
                if self._cancel_requested:
                    raise InterruptedError("Exportação cancelada pelo usuário")
                self.progress.emit(percentage, 100, float(percentage), message)
            
            # Adiciona callback aos kwargs se a função aceitar
            kwargs = self._export_kwargs.copy()
            kwargs["progress_callback"] = progress_callback
            
            # Executa exportação
            result = self._export_function(*self._export_args, **kwargs)
            
            if self._cancel_requested:
                self._state = WorkerState.CANCELLED
                self.cancelled.emit()
                return
            
            self._state = WorkerState.FINISHED
            
            # Result pode ser string (filepath) ou tuple (filepath, info)
            if isinstance(result, tuple):
                filepath = result[0]
            else:
                filepath = str(result) if result else ""
            
            self.finished.emit(filepath)
            
        except InterruptedError:
            self._state = WorkerState.CANCELLED
            self.cancelled.emit()
            
        except Exception as e:
            self._state = WorkerState.ERROR
            self.error.emit(e)


# =============================================================================
# PHOTO EXPORT WORKER (QThread)
# =============================================================================

class PhotoExportWorker(QThread):
    """
    Worker específico para exportação de fotos.
    
    Signals:
        progress: Progresso (current, total, percentage, message)
        finished: Exportação concluída (filepath, photo_count)
        error: Erro ocorreu (exception)
        cancelled: Exportação cancelada
    """
    
    progress = Signal(int, int, float, str)
    finished = Signal(str, int)  # filepath, photo_count
    error = Signal(Exception)
    cancelled = Signal()
    
    def __init__(
        self,
        photo_service,
        codprodutos: List[int] = None,
        output_path: str = None,
        filename: str = "Fotos.zip",
        convert_to: str = "jpg",
        quality: int = 85,
        parent=None
    ):
        """
        Inicializa o worker.
        
        Args:
            photo_service: Instância de PhotoExportService
            codprodutos: Lista de códigos de produtos
            output_path: Diretório de saída
            filename: Nome do arquivo ZIP
            convert_to: Formato de saída (jpg/png)
            quality: Qualidade JPEG
            parent: QObject pai
        """
        super().__init__(parent)
        
        self._photo_service = photo_service
        self._codprodutos = codprodutos
        self._output_path = output_path
        self._filename = filename
        self._convert_to = convert_to
        self._quality = quality
        self._cancel_requested = False
        self._state = WorkerState.IDLE
    
    @property
    def state(self) -> WorkerState:
        """Estado atual."""
        return self._state
    
    def cancel(self):
        """Solicita cancelamento."""
        self._cancel_requested = True
    
    def run(self):
        """Executa a exportação de fotos."""
        self._state = WorkerState.RUNNING
        self._cancel_requested = False
        
        try:
            def progress_callback(percentage: int, message: str):
                if self._cancel_requested:
                    raise InterruptedError("Exportação cancelada")
                self.progress.emit(percentage, 100, float(percentage), message)
            
            zip_path, photos = self._photo_service.export_photos_to_zip(
                codprodutos=self._codprodutos,
                output_path=self._output_path,
                filename=self._filename,
                convert_to=self._convert_to,
                quality=self._quality,
                progress_callback=progress_callback
            )
            
            if self._cancel_requested:
                self._state = WorkerState.CANCELLED
                self.cancelled.emit()
                return
            
            self._state = WorkerState.FINISHED
            self.finished.emit(zip_path, len(photos))
            
        except InterruptedError:
            self._state = WorkerState.CANCELLED
            self.cancelled.emit()
            
        except Exception as e:
            self._state = WorkerState.ERROR
            self.error.emit(e)


# =============================================================================
# GENERIC TASK RUNNABLE (QRunnable)
# =============================================================================

class TaskRunnable(QRunnable):
    """
    Runnable genérico para executar tarefas no thread pool.
    
    Útil para tarefas curtas que não precisam de controle de pausa.
    """
    
    def __init__(
        self,
        function: Callable,
        args: tuple = None,
        kwargs: dict = None,
        signals: WorkerSignals = None
    ):
        """
        Inicializa o runnable.
        
        Args:
            function: Função a executar
            args: Argumentos posicionais
            kwargs: Argumentos nomeados
            signals: Sinais para comunicação
        """
        super().__init__()
        
        self._function = function
        self._args = args or ()
        self._kwargs = kwargs or {}
        self.signals = signals or WorkerSignals()
        
        # Auto-delete após execução
        self.setAutoDelete(True)
    
    def run(self):
        """Executa a tarefa."""
        try:
            self.signals.started.emit()
            result = self._function(*self._args, **self._kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(e)


# =============================================================================
# BATCH PROCESSOR (QThread)
# =============================================================================

class BatchProcessor(QThread):
    """
    Processador de lotes para operações em grande volume.
    
    Processa itens em lotes para evitar travamento da UI
    e permitir feedback de progresso.
    
    Signals:
        progress: Progresso (current, total, percentage, message)
        batch_ready: Lote processado (batch_number, results)
        finished: Processamento concluído (total_processed)
        error: Erro ocorreu (exception)
        cancelled: Processamento cancelado
    """
    
    progress = Signal(int, int, float, str)
    batch_ready = Signal(int, object)
    finished = Signal(int)
    error = Signal(Exception)
    cancelled = Signal()
    
    def __init__(
        self,
        items: List[Any],
        process_function: Callable,
        batch_size: int = 100,
        parent=None
    ):
        """
        Inicializa o processador.
        
        Args:
            items: Lista de itens a processar
            process_function: Função que processa um item
            batch_size: Tamanho do lote
            parent: QObject pai
        """
        super().__init__(parent)
        
        self._items = items
        self._process_function = process_function
        self._batch_size = batch_size
        self._cancel_requested = False
        self._state = WorkerState.IDLE
    
    def cancel(self):
        """Solicita cancelamento."""
        self._cancel_requested = True
    
    def run(self):
        """Executa o processamento em lotes."""
        self._state = WorkerState.RUNNING
        self._cancel_requested = False
        
        total = len(self._items)
        processed = 0
        batch_number = 0
        
        try:
            for i in range(0, total, self._batch_size):
                if self._cancel_requested:
                    self._state = WorkerState.CANCELLED
                    self.cancelled.emit()
                    return
                
                batch = self._items[i:i + self._batch_size]
                batch_results = []
                
                for item in batch:
                    if self._cancel_requested:
                        self._state = WorkerState.CANCELLED
                        self.cancelled.emit()
                        return
                    
                    try:
                        result = self._process_function(item)
                        batch_results.append(result)
                    except Exception as e:
                        batch_results.append(None)
                        print(f"Erro ao processar item: {e}")
                    
                    processed += 1
                
                batch_number += 1
                percentage = (processed / total * 100) if total > 0 else 100
                
                self.progress.emit(
                    processed,
                    total,
                    percentage,
                    f"Processados {processed:,} de {total:,}"
                )
                
                self.batch_ready.emit(batch_number, batch_results)
            
            self._state = WorkerState.FINISHED
            self.finished.emit(processed)
            
        except Exception as e:
            self._state = WorkerState.ERROR
            self.error.emit(e)


# =============================================================================
# WORKER MANAGER
# =============================================================================

class WorkerManager(QObject):
    """
    Gerenciador de workers.
    
    Centraliza a criação e controle de workers,
    evitando vazamentos de memória.
    """
    
    def __init__(self, parent=None):
        """
        Inicializa o gerenciador de workers.

        Cria a lista interna de workers ativos e obtém a instância
        global do thread pool para execução de tarefas rápidas.

        Args:
            parent: QObject pai (opcional).
        """
        super().__init__(parent)
        
        self._workers: List[QThread] = []
        self._thread_pool = QThreadPool.globalInstance()
    
    def create_data_loader(
        self,
        fetch_function: Callable,
        page_size: int = 1000
    ) -> DataLoaderWorker:
        """Cria worker para carregamento de dados."""
        worker = DataLoaderWorker(fetch_function, page_size, self)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        return worker
    
    def create_export_worker(
        self,
        export_function: Callable,
        export_args: tuple = None,
        export_kwargs: dict = None
    ) -> ExportWorker:
        """Cria worker para exportação."""
        worker = ExportWorker(export_function, export_args, export_kwargs, self)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        return worker
    
    def create_photo_export_worker(
        self,
        photo_service,
        **kwargs
    ) -> PhotoExportWorker:
        """Cria worker para exportação de fotos."""
        worker = PhotoExportWorker(photo_service, **kwargs, parent=self)
        self._workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        return worker
    
    def run_task(
        self,
        function: Callable,
        args: tuple = None,
        kwargs: dict = None
    ) -> WorkerSignals:
        """
        Executa tarefa no thread pool.
        
        Returns:
            Sinais para monitorar a tarefa
        """
        signals = WorkerSignals()
        runnable = TaskRunnable(function, args, kwargs, signals)
        self._thread_pool.start(runnable)
        return signals
    
    def cancel_all(self):
        """Cancela todos os workers ativos."""
        for worker in self._workers:
            if worker.isRunning():
                if hasattr(worker, 'cancel'):
                    worker.cancel()
                worker.quit()
                worker.wait(3000)
    
    def _cleanup_worker(self, worker: QThread):
        """Remove worker da lista após conclusão."""
        if worker in self._workers:
            self._workers.remove(worker)
    
    def active_workers_count(self) -> int:
        """Retorna número de workers ativos."""
        return sum(1 for w in self._workers if w.isRunning())
