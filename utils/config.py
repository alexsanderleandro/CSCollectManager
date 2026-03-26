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

    # ---------------------------
    # Persistência de preferências
    # ---------------------------
    @classmethod
    def _settings_path(cls) -> str:
        p = cls.BASE_DIR / "user_settings.json"
        return str(p)

    @classmethod
    def _load_settings(cls) -> dict:
        import json
        path = cls._settings_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def _save_settings(cls, data: dict) -> None:
        import json
        path = cls._settings_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def get_last_export_dir(cls) -> str:
        """Retorna o último diretório de exportação salvo ou o padrão."""
        settings = cls._load_settings()
        return settings.get("last_export_dir", cls.DEFAULT_EXPORT_PATH)

    @classmethod
    def set_last_export_dir(cls, path: str) -> None:
        """Salva o último diretório de exportação escolhido pelo usuário."""
        settings = cls._load_settings()
        settings["last_export_dir"] = path
        cls._save_settings(settings)
    
    @classmethod
    def get_log_path(cls) -> str:
        """Retorna caminho para arquivo de log."""
        log_dir = cls.BASE_DIR / "logs"
        os.makedirs(log_dir, exist_ok=True)
        return str(log_dir / "app.log")

    @classmethod
    def get_export_logs_dir(cls) -> str:
        """Retorna diretório de logs de exportação (cria se necessário). Padrão: C:\\ceosoftware\\Logs"""
        default_dir = Path(r"C:\ceosoftware") / "Logs"
        try:
            os.makedirs(default_dir, exist_ok=True)
            return str(default_dir)
        except Exception:
            fallback = cls.BASE_DIR / "Logs"
            os.makedirs(fallback, exist_ok=True)
            return str(fallback)

    # ---------------------------
    # Histórico de exportações
    # ---------------------------
    @classmethod
    def get_export_history_path(cls) -> str:
        """
        Retorna o caminho do arquivo de histórico de exportações.

        Padrão: C:\\ceosoftware\\export_history.json
        """
        # Diretório preferencial do CEOSoftware
        default_dir = Path(r"C:\ceosoftware")
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception:
            # Fallback para BASE_DIR
            default_dir = cls.BASE_DIR

        return str(default_dir / "export_history.json")

    # ---------------------------
    # Assinatura (chaves)
    # ---------------------------
    @classmethod
    def get_keys_dir(cls) -> str:
        """
        Retorna diretório onde as chaves de assinatura ficam (cria se necessário).

        Padrão: C:\\ceosoftware\\keys
        """
        default_dir = Path(r"C:\ceosoftware") / "keys"
        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception:
            default_dir = cls.BASE_DIR / "keys"
            os.makedirs(default_dir, exist_ok=True)
        return str(default_dir)

    @classmethod
    def get_private_key_path(cls) -> str:
        """Caminho para a chave privada (PEM)."""
        # Para HMAC armazenamos uma secret key binária
        return str(Path(cls.get_keys_dir()) / "hmac_key.bin")

    @classmethod
    def get_public_key_path(cls) -> str:
        """Caminho para a chave pública (PEM)."""
        return str(Path(cls.get_keys_dir()) / "public_key.pem")

    @classmethod
    def load_export_history(cls) -> list:
        """Carrega a lista de históricos (lista de dicts)."""
        import json
        path = cls.get_export_history_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    @classmethod
    def append_export_history(cls, entry: dict) -> None:
        """Adiciona uma entrada ao histórico e persiste no arquivo JSON."""
        import json
        path = cls.get_export_history_path()
        try:
            history = cls.load_export_history()
            # Insere no início para manter o mais recente primeiro
            history.insert(0, entry)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            # Não interrompe fluxo de exportação se não conseguir gravar histórico
            pass
