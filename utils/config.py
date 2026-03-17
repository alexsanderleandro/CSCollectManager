"""
config.py
=========
Configurações globais da aplicação.
"""

import os
from pathlib import Path
from typing import Optional


class AppConfig:
    """
    Configurações globais da aplicação.
    
    Centraliza paths, constantes e configurações.
    """
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    ASSETS_DIR = BASE_DIR / "assets"
    
    # Aplicação
    APP_NAME = "CSCollectManager"
    APP_VERSION = "1.0.0"
    ORGANIZATION_NAME = "CEOSoftware"
    
    # Banco de dados
    DEFAULT_DRIVER = os.getenv("MSSQL_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    
    # UI
    DEFAULT_FONT_FAMILY = "Segoe UI"
    DEFAULT_FONT_SIZE = 10
    
    # Exportação
    DEFAULT_EXPORT_PATH = str(Path.home() / "Documents" / "CSCollectManager" / "Exports")
    
    @classmethod
    def get_asset_path(cls, filename: str) -> str:
        """
        Retorna caminho completo para um asset.
        
        Args:
            filename: Nome do arquivo
            
        Returns:
            Caminho completo
        """
        return str(cls.ASSETS_DIR / filename)
    
    @classmethod
    def ensure_export_dir(cls) -> str:
        """
        Garante que diretório de exportação existe.
        
        Returns:
            Caminho do diretório
        """
        os.makedirs(cls.DEFAULT_EXPORT_PATH, exist_ok=True)
        return cls.DEFAULT_EXPORT_PATH
    
    @classmethod
    def get_log_path(cls) -> str:
        """Retorna caminho para arquivo de log."""
        log_dir = cls.BASE_DIR / "logs"
        os.makedirs(log_dir, exist_ok=True)
        return str(log_dir / "app.log")
