"""
Utils Package
=============
Utilitários e helpers do sistema.

Responsabilidades:
- Fornecer funções auxiliares
- Gerenciar configurações
- Helpers de formatação
- Logging
- Constantes
"""

from utils.config import AppConfig
from utils.theme_manager import ThemeManager
from utils.validators import Validators
from utils.formatters import Formatters
from utils.logger import get_logger, log_exception, log_function_call, AppLogger
from utils.constants import (
    APP_INFO, Paths, Icons, Messages, Colors,
    Shortcuts, DatabaseConfig, ExportConfig as ExportConstants,
    UIConfig, init_app_directories
)
from utils.error_handler import (
    setup_error_handler, show_error, show_warning, show_info,
    handle_exception, ErrorHandler, ErrorDialog
)
from utils.workers import (
    WorkerState,
    WorkerProgress,
    WorkerSignals,
    DataLoaderWorker,
    ExportWorker,
    PhotoExportWorker,
    TaskRunnable,
    BatchProcessor,
    WorkerManager,
)

__all__ = [
    "AppConfig",
    "ThemeManager",
    "Validators",
    "Formatters",
    # Workers
    "WorkerState",
    "WorkerProgress",
    "WorkerSignals",
    "DataLoaderWorker",
    "ExportWorker",
    "PhotoExportWorker",
    "TaskRunnable",
    "BatchProcessor",
    "WorkerManager",
    # Logger
    "get_logger",
    "log_exception",
    "log_function_call",
    "AppLogger",
    # Constants
    "APP_INFO",
    "Paths",
    "Icons",
    "Messages",
    "Colors",
    "Shortcuts",
    "DatabaseConfig",
    "ExportConstants",
    "UIConfig",
    "init_app_directories",
    # Error Handler
    "setup_error_handler",
    "show_error",
    "show_warning",
    "show_info",
    "handle_exception",
    "ErrorHandler",
    "ErrorDialog",
]
