"""
constants.py
============
Constantes e configurações do sistema CSCollectManager.
"""

from dataclasses import dataclass
from typing import Dict, Any
import os


@dataclass(frozen=True)
class AppInfo:
    """Informações da aplicação."""
    NAME: str = "CSCollectManager"
    VERSION: str = "1.0.0"
    BUILD: str = "2026.03.16"
    AUTHOR: str = "CEO Software"
    COMPANY: str = "CEO Software"
    DESCRIPTION: str = "Sistema de Gestão de Coletas para Coletores de Dados"
    COPYRIGHT: str = "© 2026 CEO Software. Todos os direitos reservados."
    WEBSITE: str = "https://www.ceosoftware.com.br"
    EMAIL: str = "suporte@ceosoftware.com.br"


# Instância global
APP_INFO = AppInfo()


class Paths:
    """Caminhos do sistema."""
    
    # Diretório base do usuário
    USER_HOME = os.path.expanduser("~")
    
    # Diretório de dados da aplicação
    APP_DATA = os.path.join(USER_HOME, "Documents", "CSCollectManager")
    
    # Subdiretórios
    EXPORTS_DIR = os.path.join(APP_DATA, "Exports")
    LOGS_DIR = os.path.join(APP_DATA, "logs")
    CONFIG_DIR = os.path.join(APP_DATA, "config")
    TEMP_DIR = os.path.join(APP_DATA, "temp")
    
    @classmethod
    def ensure_dirs(cls):
        """Cria diretórios necessários."""
        for path in [cls.EXPORTS_DIR, cls.LOGS_DIR, cls.CONFIG_DIR, cls.TEMP_DIR]:
            os.makedirs(path, exist_ok=True)


class Icons:
    """Ícones do sistema (caracteres Unicode e nomes)."""
    
    # Ações principais
    EXPORT = "📤"
    IMPORT = "📥"
    SAVE = "💾"
    LOAD = "📂"
    REFRESH = "🔄"
    SEARCH = "🔍"
    FILTER = "🔎"
    ADD = "➕"
    REMOVE = "➖"
    DELETE = "🗑️"
    EDIT = "✏️"
    
    # Status
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    LOADING = "⏳"
    
    # Navegação
    HOME = "🏠"
    SETTINGS = "⚙️"
    USER = "👤"
    LOGOUT = "🚪"
    
    # Dados
    DATABASE = "🗄️"
    TABLE = "📋"
    PRODUCT = "📦"
    PHOTO = "📷"
    FILE = "📄"
    FOLDER = "📁"
    
    # Sistema
    CONNECT = "🔗"
    DISCONNECT = "🔌"
    LOCK = "🔒"
    UNLOCK = "🔓"
    
    # Ordenação
    SORT_ASC = "↑"
    SORT_DESC = "↓"
    
    # Setas
    ARROW_LEFT = "◀"
    ARROW_RIGHT = "▶"
    ARROW_UP = "▲"
    ARROW_DOWN = "▼"


class Messages:
    """Mensagens padrão do sistema."""
    
    # Erros
    ERROR_CONNECTION = "Erro ao conectar ao banco de dados"
    ERROR_LOAD = "Erro ao carregar dados"
    ERROR_SAVE = "Erro ao salvar dados"
    ERROR_EXPORT = "Erro ao exportar"
    ERROR_UNKNOWN = "Ocorreu um erro inesperado"
    
    # Sucesso
    SUCCESS_SAVE = "Dados salvos com sucesso"
    SUCCESS_EXPORT = "Exportação concluída com sucesso"
    SUCCESS_LOAD = "Dados carregados com sucesso"
    
    # Confirmação
    CONFIRM_DELETE = "Tem certeza que deseja excluir?"
    CONFIRM_EXIT = "Deseja realmente sair?"
    CONFIRM_CANCEL = "Deseja cancelar a operação?"
    
    # Avisos
    WARNING_UNSAVED = "Existem alterações não salvas"
    WARNING_NO_SELECTION = "Nenhum item selecionado"
    WARNING_NO_DATA = "Nenhum dado encontrado"


class Colors:
    """Cores do sistema."""
    
    # Tema escuro
    DARK = {
        "background": "#1e1e1e",
        "background_alt": "#252526",
        "foreground": "#cccccc",
        "border": "#3e3e42",
        "accent": "#0078d4",
        "accent_hover": "#1e8ad4",
        "success": "#4caf50",
        "warning": "#ff9800",
        "error": "#f44336",
        "info": "#2196f3",
    }
    
    # Tema claro
    LIGHT = {
        "background": "#ffffff",
        "background_alt": "#f5f5f5",
        "foreground": "#333333",
        "border": "#cccccc",
        "accent": "#0078d4",
        "accent_hover": "#106ebe",
        "success": "#4caf50",
        "warning": "#ff9800",
        "error": "#f44336",
        "info": "#2196f3",
    }
    
    # Cores de status de produto
    PRODUCT_EXPIRED = "#ff6b6b"
    PRODUCT_NEAR_EXPIRY = "#ffa94d"
    PRODUCT_OK = "#69db7c"


class Shortcuts:
    """Atalhos de teclado."""
    
    SAVE = "Ctrl+S"
    OPEN = "Ctrl+O"
    NEW = "Ctrl+N"
    EXPORT = "Ctrl+E"
    SEARCH = "Ctrl+F"
    REFRESH = "F5"
    SETTINGS = "Ctrl+,"
    HELP = "F1"
    QUIT = "Ctrl+Q"
    SELECT_ALL = "Ctrl+A"
    COPY = "Ctrl+C"


class DatabaseConfig:
    """Configurações de banco de dados."""
    
    # Pool de conexões
    POOL_SIZE = 5
    MAX_OVERFLOW = 10
    POOL_RECYCLE = 3600
    POOL_PRE_PING = True
    
    # Timeouts
    CONNECT_TIMEOUT = 30
    QUERY_TIMEOUT = 60


class ExportConfig:
    """Configurações de exportação."""
    
    # Tamanho de página para exportação
    PAGE_SIZE = 5000
    
    # Qualidade de imagem JPEG
    JPEG_QUALITY = 85
    
    # Formatos suportados
    IMAGE_FORMATS = ["jpg", "png"]
    
    # Separador de campos
    FIELD_SEPARATOR = "|"


class UIConfig:
    """Configurações de interface."""
    
    # Tamanhos
    DEFAULT_WINDOW_WIDTH = 1280
    DEFAULT_WINDOW_HEIGHT = 800
    MIN_WINDOW_WIDTH = 1024
    MIN_WINDOW_HEIGHT = 600
    
    # Tabela
    TABLE_ROW_HEIGHT = 25
    TABLE_HEADER_HEIGHT = 30
    
    # Debounce
    SEARCH_DEBOUNCE_MS = 300
    
    # Animações
    ANIMATION_DURATION_MS = 200


# Função helper para criar diretórios na inicialização
def init_app_directories():
    """Inicializa diretórios da aplicação."""
    Paths.ensure_dirs()
