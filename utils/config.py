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
    
    # Exportação (mantido por compatibilidade; use get_default_export_path())
    DEFAULT_EXPORT_PATH = str(Path.home() / "Documents" / "CSCollectManager" / "Exports")

    @classmethod
    def get_app_dir(cls) -> Path:
        """
        Retorna o diretório da aplicação.

        - Executável PyInstaller: pasta onde o .exe está (sys.executable).
        - Script Python normal:   BASE_DIR (pasta raiz do projeto).
        """
        import sys
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        return cls.BASE_DIR

    @classmethod
    def get_default_export_path(cls) -> str:
        """
        Retorna o caminho padrão de exportação: <pasta_do_exe>/Cargas.

        Garante que a pasta é criada ao ser acessada pela primeira vez.
        """
        path = cls.get_app_dir() / "Cargas"
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass
        return str(path)
    
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
        path = cls.get_default_export_path()
        os.makedirs(path, exist_ok=True)
        return path

    # ---------------------------
    # Persistência de preferências
    # ---------------------------
    @classmethod
    def _settings_path(cls) -> str:
        """
        Retorna o caminho completo do arquivo de preferências do usuário.

        O arquivo ``user_settings.json`` é sempre criado ao lado do
        executável (em produção) ou na raiz do projeto (em desenvolvimento).

        Returns:
            Caminho absoluto para ``user_settings.json``.
        """
        p = cls.get_app_dir() / "user_settings.json"
        return str(p)

    @classmethod
    def _load_settings(cls) -> dict:
        """
        Carrega e retorna o dicionário de preferências salvas em disco.

        Retorna um dicionário vazio caso o arquivo não exista ou ocorra
        qualquer erro de leitura/decodificação.

        Returns:
            Dicionário com as preferências do usuário.
        """
        import json
        path = cls._settings_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def _save_settings(cls, data: dict) -> None:
        """
        Persiste o dicionário de preferências em disco.

        Falhas de escrita são ignoradas silenciosamente para não
        interromper o fluxo da aplicação.

        Args:
            data: Dicionário com as preferências a salvar.
        """
        import json
        path = cls._settings_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def get_last_export_dir(cls) -> str:
        """Retorna o último diretório de exportação salvo ou o padrão (Cargas na pasta do exe)."""
        settings = cls._load_settings()
        return settings.get("last_export_dir", cls.get_default_export_path())

    @classmethod
    def set_last_export_dir(cls, path: str) -> None:
        """Salva o último diretório de exportação escolhido pelo usuário."""
        settings = cls._load_settings()
        settings["last_export_dir"] = path
        cls._save_settings(settings)

    # ---------------------------
    # Configurações da API CSCollect
    # ---------------------------

    @classmethod
    def get_api_url(cls) -> str:
        """Retorna a URL base da API CSCollect (ex.: https://cscollectapi.onrender.com)."""
        settings = cls._load_settings()
        return settings.get("api_url", "").strip()

    @classmethod
    def set_api_url(cls, url: str) -> None:
        """Salva a URL base da API CSCollect."""
        settings = cls._load_settings()
        settings["api_url"] = url.strip()
        cls._save_settings(settings)

    @classmethod
    def get_api_authorization(cls) -> str:
        """Retorna o token de autorização da API CSCollect."""
        settings = cls._load_settings()
        return settings.get("api_authorization", "").strip()

    @classmethod
    def set_api_authorization(cls, token: str) -> None:
        """Salva o token de autorização da API CSCollect."""
        settings = cls._load_settings()
        settings["api_authorization"] = token.strip()
        cls._save_settings(settings)

    @classmethod
    def is_api_configured(cls) -> bool:
        """Retorna True se URL e token da API estiverem preenchidos."""
        return bool(cls.get_api_url() and cls.get_api_authorization())
    
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

    @classmethod
    def clear_export_history(cls) -> None:
        """
        Limpa o histórico de exportações persistido no JSON.

        Escreve uma lista vazia no arquivo `export_history.json`. Em caso de falha
        ao escrever, tenta remover o arquivo.
        """
        import json
        import os
        path = cls.get_export_history_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        except Exception:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    # ---------------------------
    # Nomes amigáveis de dispositivos
    # ---------------------------
    @classmethod
    def get_device_names_path(cls) -> str:
        """Retorna o caminho do arquivo nome_device.json (pasta do executável/aplicação)."""
        return str(cls.get_app_dir() / "nome_device.json")

    @classmethod
    def load_device_names(cls) -> dict:
        """
        Carrega o mapa id_device -> nome_device do arquivo nome_device.json.

        Returns:
            Dict[str, str] mapeando id_device para nome_device
        """
        import json
        path = cls.get_device_names_path()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Converte lista [{id_device, nome_device}] para dict
                    return {str(e["id_device"]): e["nome_device"] for e in data if "id_device" in e}
                if isinstance(data, dict):
                    return {str(k): v for k, v in data.items()}
        except Exception:
            pass
        return {}

    @classmethod
    def save_device_name(cls, id_device: str, nome_device: str) -> None:
        """
        Salva ou atualiza o nome amigável de um dispositivo.

        O arquivo é gravado como lista de objetos:
        [{"id_device": "...", "nome_device": "..."}, ...]

        Args:
            id_device: ID do dispositivo (vem da licença .key)
            nome_device: Nome amigável (string vazia remove a entrada)
        """
        import json
        names = cls.load_device_names()
        id_device = str(id_device).strip()
        nome_device = (nome_device or "").strip()
        if nome_device:
            names[id_device] = nome_device
        else:
            names.pop(id_device, None)
        # Grava como lista de objetos para melhor legibilidade
        lista = [{"id_device": k, "nome_device": v} for k, v in sorted(names.items())]
        path = cls.get_device_names_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(lista, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def remove_device_name(cls, id_device: str) -> None:
        """Remove o nome amigável de um dispositivo."""
        cls.save_device_name(id_device, "")

    @classmethod
    def purge_device_names(cls, valid_ids) -> None:
        """
        Remove do arquivo nome_device.json todas as entradas cujo id_device
        não esteja em `valid_ids`.

        Deve ser chamado após salvar um nome para manter o JSON limpo,
        contendo apenas IDs presentes na licença atual.

        Args:
            valid_ids: Coleção (set, list, etc.) de IDs autorizados
        """
        import json
        valid = {str(i) for i in (valid_ids or [])}
        names = cls.load_device_names()
        cleaned = {k: v for k, v in names.items() if k in valid}
        lista = [{"id_device": k, "nome_device": v} for k, v in sorted(cleaned.items())]
        path = cls.get_device_names_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(lista, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
