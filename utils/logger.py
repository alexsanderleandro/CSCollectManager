"""
logger.py
=========
Sistema de logging centralizado para o CSCollectManager.

Fornece:
- Logging em arquivo e console
- Rotação de logs
- Formatação consistente
- Níveis configuráveis
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from typing import Optional
from pathlib import Path


class LoggerConfig:
    """Configurações do logger."""
    
    # Diretório de logs
    LOG_DIR = os.path.join(
        os.path.expanduser("~"),
        "Documents",
        "CSCollectManager",
        "logs"
    )
    
    # Arquivo de log principal
    LOG_FILE = "cscollect.log"
    
    # Tamanho máximo do arquivo (10 MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # Número de arquivos de backup
    BACKUP_COUNT = 5
    
    # Formato padrão
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Formato detalhado (para debug)
    DETAILED_FORMAT = (
        "%(asctime)s | %(levelname)-8s | %(name)-20s | "
        "%(filename)s:%(lineno)d | %(funcName)s | %(message)s"
    )


class ColoredFormatter(logging.Formatter):
    """Formatter com cores para console."""
    
    # Códigos ANSI para cores
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[41m',   # Red background
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Adiciona cor ao nível
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        result = super().format(record)
        
        # Restaura o nome original
        record.levelname = levelname
        return result


class AppLogger:
    """
    Logger centralizado da aplicação.
    
    Uso:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Mensagem")
    """
    
    _instance: Optional['AppLogger'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if AppLogger._initialized:
            return
        
        self._loggers = {}
        self._setup_root_logger()
        AppLogger._initialized = True
    
    def _setup_root_logger(self):
        """Configura o logger raiz."""
        # Cria diretório de logs
        os.makedirs(LoggerConfig.LOG_DIR, exist_ok=True)
        
        # Logger raiz para a aplicação
        root_logger = logging.getLogger("CSCollect")
        root_logger.setLevel(logging.DEBUG)
        
        # Remove handlers existentes
        root_logger.handlers.clear()
        
        # Handler de arquivo com rotação
        log_path = os.path.join(LoggerConfig.LOG_DIR, LoggerConfig.LOG_FILE)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=LoggerConfig.MAX_FILE_SIZE,
            backupCount=LoggerConfig.BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            LoggerConfig.DETAILED_FORMAT,
            LoggerConfig.DATE_FORMAT
        ))
        root_logger.addHandler(file_handler)
        
        # Handler de console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Usa formatter colorido se terminal suporta
        if sys.stdout.isatty():
            console_handler.setFormatter(ColoredFormatter(
                LoggerConfig.LOG_FORMAT,
                LoggerConfig.DATE_FORMAT
            ))
        else:
            console_handler.setFormatter(logging.Formatter(
                LoggerConfig.LOG_FORMAT,
                LoggerConfig.DATE_FORMAT
            ))
        
        root_logger.addHandler(console_handler)
        
        # Handler para erros críticos (arquivo separado)
        error_log_path = os.path.join(LoggerConfig.LOG_DIR, "errors.log")
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=LoggerConfig.MAX_FILE_SIZE,
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            LoggerConfig.DETAILED_FORMAT,
            LoggerConfig.DATE_FORMAT
        ))
        root_logger.addHandler(error_handler)
        
        self._root_logger = root_logger
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Retorna logger para o módulo especificado.
        
        Args:
            name: Nome do módulo (geralmente __name__)
            
        Returns:
            Logger configurado
        """
        if name in self._loggers:
            return self._loggers[name]
        
        # Cria sub-logger
        if name.startswith("CSCollect"):
            logger_name = name
        else:
            logger_name = f"CSCollect.{name}"
        
        logger = logging.getLogger(logger_name)
        self._loggers[name] = logger
        
        return logger
    
    def set_level(self, level: int):
        """Define nível de log global."""
        self._root_logger.setLevel(level)
    
    def set_console_level(self, level: int):
        """Define nível de log do console."""
        for handler in self._root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level)
    
    @property
    def log_dir(self) -> str:
        """Retorna diretório de logs."""
        return LoggerConfig.LOG_DIR
    
    @property
    def log_file(self) -> str:
        """Retorna caminho do arquivo de log."""
        return os.path.join(LoggerConfig.LOG_DIR, LoggerConfig.LOG_FILE)


# Instância global
_app_logger = AppLogger()


def setup_logging(level: str = "DEBUG"):
    """
    Configura o sistema de logging.
    
    Args:
        level: Nível de log (DEBUG, INFO, WARNING, ERROR)
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR
    }
    _app_logger.set_level(level_map.get(level.upper(), logging.DEBUG))


def get_logger(name: str = "app") -> logging.Logger:
    """
    Retorna logger para o módulo.
    
    Args:
        name: Nome do módulo
        
    Returns:
        Logger configurado
    """
    return _app_logger.get_logger(name)


def log_exception(logger: logging.Logger, message: str = "Exceção capturada"):
    """
    Loga exceção com traceback completo.
    
    Args:
        logger: Logger a usar
        message: Mensagem adicional
    """
    logger.exception(message)


def log_function_call(logger: logging.Logger):
    """
    Decorator para logar chamadas de função.
    
    Args:
        logger: Logger a usar
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Chamando {func.__name__}(args={args}, kwargs={kwargs})")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func.__name__} retornou: {result}")
                return result
            except Exception as e:
                logger.exception(f"Erro em {func.__name__}: {e}")
                raise
        return wrapper
    return decorator


# ===== EXEMPLO DE USO =====
if __name__ == "__main__":
    # Obtém logger
    logger = get_logger("test")
    
    # Testa níveis
    logger.debug("Mensagem de debug")
    logger.info("Mensagem informativa")
    logger.warning("Mensagem de aviso")
    logger.error("Mensagem de erro")
    
    try:
        raise ValueError("Erro de teste")
    except Exception:
        log_exception(logger, "Teste de exceção")
    
    print(f"\nLogs salvos em: {_app_logger.log_dir}")
