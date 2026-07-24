"""
config.py
=========
Configurações globais da aplicação.
"""

import os
from pathlib import Path
from typing import Optional

# Importa funções de descriptografia para campos sensíveis
try:
    from encryption import decrypt_field, is_encrypted
except ImportError:
    def decrypt_field(v): return v
    def is_encrypted(v): return False


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
        Retorna o caminho padrão de exportação: <pasta_do_exe>/cargas.

        Garante que a pasta é criada ao ser acessada pela primeira vez.
        """
        path = cls.get_app_dir() / "cargas"
        try:
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass
        return str(path)

    @classmethod
    def get_contagens_path(cls) -> str:
        """
        Retorna o caminho da pasta de contagens: <pasta_do_exe>/contagens.

        Garante que a pasta é criada ao ser acessada pela primeira vez.
        """
        path = cls.get_app_dir() / "contagens"
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

    @classmethod
    def get_last_contagens_dir(cls) -> str:
        """Retorna o último diretório de contagens salvo ou o padrão (contagens na pasta do exe)."""
        settings = cls._load_settings()
        return settings.get("last_contagens_dir", cls.get_contagens_path())

    @classmethod
    def set_last_contagens_dir(cls, path: str) -> None:
        """Salva o último diretório de download de contagens escolhido pelo usuário."""
        settings = cls._load_settings()
        settings["last_contagens_dir"] = path
        cls._save_settings(settings)

    # ---------------------------
    # Configurações da API CSCollect (lidas do arquivo licenca.key)
    # ---------------------------

    # Override em memória para api_authorization (descriptografado do Neon durante login)
    _api_authorization_override: str = ""

    @classmethod
    def set_api_authorization_override(cls, value: str) -> None:
        """Define o token de autorização da API em memória (obtido do Neon durante verificação da licença)."""
        cls._api_authorization_override = (value or "").strip()

    @classmethod
    def _find_key_file(cls) -> str:
        """
        Localiza o arquivo de licença (.key) no diretório da aplicação.

        Tenta primeiro ``licenca.key``; se não existir, retorna o primeiro
        arquivo ``*.key`` encontrado na pasta.  Retorna string vazia se nenhum
        for encontrado.
        """
        import glob
        app_dir = cls.get_app_dir()
        default = app_dir / "licenca.key"
        if default.exists():
            return str(default)
        candidates = glob.glob(str(app_dir / "*.key"))
        return candidates[0] if candidates else ""

    @classmethod
    def _load_key_file(cls) -> dict:
        """
        Carrega e retorna o conteúdo do arquivo de licença (.key) em formato JSON.

        Tenta múltiplos encodings (utf-8, utf-8-sig, latin-1, cp1252) para lidar
        com arquivos gerados em diferentes plataformas/editores.

        Retorna dicionário vazio em caso de erro ou arquivo não encontrado.
        """
        import json
        path = cls._find_key_file()
        if not path:
            return {}
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
            try:
                with open(path, 'r', encoding=enc) as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except UnicodeDecodeError:
                continue
            except Exception:
                break
        return {}

    @classmethod
    def get_api_url(cls) -> str:
        """Retorna a URL base da API CSCollect lida do arquivo licenca.key."""
        return cls._load_key_file().get("api_url", "").strip()

    @classmethod
    def get_api_authorization(cls) -> str:
        """
        Retorna o token de autorização da API CSCollect.

        Prioridade:
        1. Override em memória (``_api_authorization_override``) — preenchido após
           verificação online da licença via Neon (``_api_authorization`` do payload).
        2. Campo ``api_authorization`` do arquivo licenca.key.

        O campo ``token`` do .key é exclusivo para validação de licença mobile
        e NÃO é enviado nos headers da API HTTP (evita erro 401).
        """
        if cls._api_authorization_override:
            return cls._api_authorization_override
        data = cls._load_key_file()
        val = (data.get("api_authorization") or "").strip()
        return decrypt_field(val) if is_encrypted(val) else val

    @classmethod
    def get_license_token(cls) -> str:
        """
        Retorna o token da licença do cliente lido do arquivo licenca.key.

        Este é o campo ``token`` do .key, equivalente ao campo ``serial`` dentro
        do payload do arquivo .sig, e é a chave HMAC usada para assinar/validar
        a assinatura do ZIP exportado pelo app CSCollect.

        NÃO confundir com ``api_authorization``, que é o token de autenticação
        dos endpoints HTTP da API.
        """
        return cls._load_key_file().get("token", "").strip()

    @classmethod
    def get_api_database_url(cls) -> str:
        """Retorna a URL de conexão direta ao banco Neon lida do arquivo licenca.key."""
        url = cls._load_key_file().get("api_database_url", "").strip()
        
        # Descriptografa se necessário
        if is_encrypted(url):
            url = decrypt_field(url) or ""
            
        if not url:
            return ""

        # Limpeza robusta da URL para Neon/psycopg2
        import re
        from urllib.parse import urlparse, urlunparse
        
        # 1. Garante o nome do banco padrão do Neon (/neondb) se estiver ausente
        # Isso evita que o driver use o nome do usuário (neondb_owner) como nome do banco.
        try:
            parsed = urlparse(url)
            if not parsed.path or parsed.path == '/':
                parsed = parsed._replace(path='/neondb')
                url = urlunparse(parsed)
        except Exception:
            pass

        # 2. Remove channel_binding mas preserva o separador (? ou &) para não quebrar params seguintes
        url = re.sub(r'([?&])channel_binding=[^&]*&?', r'\1', url)
        url = url.rstrip('?&')
        
        # 3. Garante sslmode=require (obrigatório para Neon)
        if 'sslmode=' not in url:
            url += ("&" if "?" in url else "?") + "sslmode=require"
            
        return url

    @classmethod
    def is_api_configured(cls) -> bool:
        """Retorna True se URL e token da API estiverem preenchidos no licenca.key."""
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
