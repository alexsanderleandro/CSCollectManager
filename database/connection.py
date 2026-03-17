"""
connection.py
=============
Módulo de conexão com SQL Server usando SQLAlchemy + pyodbc.

Fornece:
- Engine SQLAlchemy com pool de conexões
- Sessões gerenciadas
- Integração com authentication.py existente
- Suporte a múltiplas bases de dados
- Tratamento robusto de erros de conexão

Uso:
    from database.connection import get_engine, get_session, DatabaseManager

    # Usando sessão com context manager
    with get_session() as session:
        result = session.execute(text("SELECT * FROM tabela"))
        
    # Ou usando o manager para trocar de base
    db = DatabaseManager()
    db.configure("servidor", "banco")
    with db.session() as session:
        ...
"""

from __future__ import annotations

import logging
from typing import Optional, Generator, Any
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import (
    SQLAlchemyError,
    OperationalError,
    InterfaceError,
    DBAPIError
)

# Importa configuração do módulo authentication existente
import authentication as auth_module
from authentication import DBConfig, get_db_config, set_db_config

# Configuração de logging
logger = logging.getLogger(__name__)


# ============================================================================
# Exceções customizadas
# ============================================================================

class DatabaseConnectionError(Exception):
    """Erro de conexão com o banco de dados."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class DatabaseConfigurationError(Exception):
    """Erro de configuração do banco de dados."""
    pass


# ============================================================================
# Configuração do Pool de Conexões
# ============================================================================

POOL_CONFIG = {
    "pool_size": 5,              # Número de conexões mantidas no pool
    "max_overflow": 10,          # Conexões extras além do pool_size
    "pool_timeout": 30,          # Timeout para obter conexão do pool (segundos)
    "pool_recycle": 3600,        # Recicla conexões após 1 hora
    "pool_pre_ping": True,       # Verifica conexão antes de usar
}


# ============================================================================
# Variáveis globais do módulo
# ============================================================================

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


# ============================================================================
# Funções de construção de connection string
# ============================================================================

def _build_sqlalchemy_url(cfg: DBConfig) -> str:
    """
    Constrói URL de conexão SQLAlchemy para SQL Server.
    
    Formato: mssql+pyodbc://[user:pass@]server/database?driver=...
    
    Args:
        cfg: Configuração do banco de dados
        
    Returns:
        URL de conexão SQLAlchemy
    """
    # Codifica o nome do driver para URL
    driver = quote_plus(cfg.driver)
    
    # Parâmetros de conexão
    params = [
        f"driver={driver}",
        f"Encrypt={cfg.encrypt}",
        f"TrustServerCertificate={cfg.trust_server_certificate}",
        f"Connection+Timeout={cfg.timeout_seconds}",
    ]
    
    # Monta URL base conforme tipo de autenticação
    if cfg.auth.lower() == "trusted":
        # Windows Authentication
        params.append("Trusted_Connection=yes")
        base_url = f"mssql+pyodbc://@{cfg.server}/{cfg.database}"
    elif cfg.auth.lower() == "sql":
        # SQL Server Authentication
        if not cfg.username or not cfg.password:
            raise DatabaseConfigurationError(
                "Autenticação SQL requer username e password"
            )
        # Codifica credenciais para URL
        user = quote_plus(cfg.username)
        password = quote_plus(cfg.password)
        base_url = f"mssql+pyodbc://{user}:{password}@{cfg.server}/{cfg.database}"
    else:
        raise DatabaseConfigurationError(
            f"Tipo de autenticação inválido: {cfg.auth}. Use 'trusted' ou 'sql'."
        )
    
    # Junta URL com parâmetros
    query_string = "&".join(params)
    return f"{base_url}?{query_string}"


def _build_connection_string(cfg: DBConfig) -> str:
    """
    Constrói connection string ODBC tradicional para uso com create_engine.
    
    Esta é uma alternativa mais compatível que funciona melhor com
    diferentes versões do pyodbc.
    
    Args:
        cfg: Configuração do banco de dados
        
    Returns:
        Connection string ODBC
    """
    parts = [
        f"DRIVER={{{cfg.driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
        f"Encrypt={cfg.encrypt}",
        f"TrustServerCertificate={cfg.trust_server_certificate}",
        f"Connection Timeout={cfg.timeout_seconds}",
    ]
    
    if cfg.auth.lower() == "trusted":
        parts.append("Trusted_Connection=yes")
    elif cfg.auth.lower() == "sql":
        if not cfg.username or not cfg.password:
            raise DatabaseConfigurationError(
                "Autenticação SQL requer username e password"
            )
        parts.append(f"UID={cfg.username}")
        parts.append(f"PWD={cfg.password}")
    else:
        raise DatabaseConfigurationError(
            f"Tipo de autenticação inválido: {cfg.auth}"
        )
    
    return ";".join(parts)


# ============================================================================
# Funções principais
# ============================================================================

def get_engine(cfg: Optional[DBConfig] = None, **kwargs) -> Engine:
    """
    Retorna engine SQLAlchemy com pool de conexões configurado.
    
    Se não houver engine criado ou se uma nova configuração for passada,
    cria um novo engine.
    
    Args:
        cfg: Configuração do banco (usa global se não informada)
        **kwargs: Parâmetros adicionais para create_engine
        
    Returns:
        Engine SQLAlchemy configurado
        
    Raises:
        DatabaseConnectionError: Se não conseguir conectar
        DatabaseConfigurationError: Se configuração inválida
    """
    global _engine, _session_factory
    
    # Usa configuração passada ou global
    config = cfg or get_db_config()
    
    # Verifica se precisa criar novo engine
    if _engine is not None:
        # Se mudou a configuração, precisa recriar
        current_url = str(_engine.url)
        new_url = _build_sqlalchemy_url(config)
        
        if current_url != new_url:
            dispose_engine()
    
    # Cria engine se necessário
    if _engine is None:
        try:
            # Usa connection string ODBC (mais compatível)
            conn_str = _build_connection_string(config)
            url = f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"
            
            # Merge configurações do pool com kwargs
            engine_config = {**POOL_CONFIG, **kwargs}
            
            _engine = create_engine(
                url,
                poolclass=QueuePool,
                **engine_config
            )
            
            # Adiciona event listener para logging de conexões
            @event.listens_for(_engine, "connect")
            def on_connect(dbapi_conn, connection_record):
                logger.debug(f"Nova conexão estabelecida com {config.server}/{config.database}")
            
            @event.listens_for(_engine, "checkout")
            def on_checkout(dbapi_conn, connection_record, connection_proxy):
                logger.debug("Conexão obtida do pool")
            
            @event.listens_for(_engine, "checkin")
            def on_checkin(dbapi_conn, connection_record):
                logger.debug("Conexão retornada ao pool")
            
            # Testa a conexão
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info(f"Engine criado com sucesso para {config.server}/{config.database}")
            
            # Reseta session factory
            _session_factory = None
            
        except OperationalError as e:
            raise DatabaseConnectionError(
                f"Não foi possível conectar ao servidor {config.server}: {str(e)}",
                original_error=e
            )
        except InterfaceError as e:
            raise DatabaseConnectionError(
                f"Erro de interface de conexão. Verifique se o driver ODBC está instalado: {str(e)}",
                original_error=e
            )
        except Exception as e:
            raise DatabaseConnectionError(
                f"Erro ao criar engine: {str(e)}",
                original_error=e
            )
    
    return _engine


def get_session_factory() -> sessionmaker:
    """
    Retorna factory de sessões configurada.
    
    Returns:
        sessionmaker configurado
    """
    global _session_factory
    
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=True,
            expire_on_commit=False
        )
    
    return _session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager que fornece uma sessão SQLAlchemy.
    
    Gerencia automaticamente commit/rollback e fechamento.
    
    Yields:
        Sessão SQLAlchemy
        
    Raises:
        DatabaseConnectionError: Se erro de conexão
        
    Exemplo:
        with get_session() as session:
            result = session.execute(text("SELECT * FROM tabela"))
            for row in result:
                print(row)
    """
    factory = get_session_factory()
    session = factory()
    
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Erro na sessão, rollback executado: {str(e)}")
        raise DatabaseConnectionError(
            f"Erro durante operação no banco: {str(e)}",
            original_error=e
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Erro inesperado na sessão: {str(e)}")
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    """
    Descarta o engine atual e fecha todas as conexões do pool.
    
    Útil ao trocar de banco de dados ou encerrar aplicação.
    """
    global _engine, _session_factory
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Engine descartado e pool de conexões fechado")


def test_connection(cfg: Optional[DBConfig] = None) -> tuple[bool, str]:
    """
    Testa conexão com o banco de dados.
    
    Args:
        cfg: Configuração a testar (usa global se não informada)
        
    Returns:
        Tupla (sucesso, mensagem)
    """
    try:
        config = cfg or get_db_config()
        
        # Cria engine temporário para teste
        conn_str = _build_connection_string(config)
        url = f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"
        
        test_engine = create_engine(url, pool_pre_ping=True)
        
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT @@VERSION"))
            version = result.scalar()
            
        test_engine.dispose()
        
        return True, f"Conexão bem-sucedida!\nSQL Server: {version[:50]}..."
        
    except OperationalError as e:
        return False, f"Erro de conexão: {str(e)}"
    except InterfaceError as e:
        return False, f"Erro de driver ODBC: {str(e)}"
    except Exception as e:
        return False, f"Erro: {str(e)}"


# ============================================================================
# Classe DatabaseManager (alternativa orientada a objetos)
# ============================================================================

class DatabaseManager:
    """
    Gerenciador de conexões com banco de dados.
    
    Fornece interface orientada a objetos para gerenciar conexões,
    suportando múltiplas bases de dados e troca dinâmica.
    
    Exemplo:
        db = DatabaseManager()
        db.configure("servidor", "banco")
        
        with db.session() as session:
            result = session.execute(text("SELECT * FROM tabela"))
    """
    
    def __init__(self, auto_connect: bool = False):
        """
        Inicializa o gerenciador.
        
        Args:
            auto_connect: Se True, conecta automaticamente usando config global
        """
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._config: Optional[DBConfig] = None
        
        if auto_connect:
            self._config = get_db_config()
            self._create_engine()
    
    def configure(
        self,
        server: str,
        database: str,
        auth: str = "trusted",
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ) -> "DatabaseManager":
        """
        Configura conexão com o banco.
        
        Args:
            server: Nome/IP do servidor
            database: Nome do banco de dados
            auth: Tipo de autenticação ('trusted' ou 'sql')
            username: Usuário (para auth='sql')
            password: Senha (para auth='sql')
            **kwargs: Parâmetros adicionais do DBConfig
            
        Returns:
            Self para encadeamento
        """
        # Fecha conexão anterior se existir
        if self._engine is not None:
            self.close()
        
        self._config = DBConfig(
            server=server,
            database=database,
            auth=auth,
            username=username,
            password=password,
            **kwargs
        )
        
        return self
    
    def configure_from_global(self) -> "DatabaseManager":
        """
        Configura usando a configuração global do authentication.py.
        
        Returns:
            Self para encadeamento
        """
        if self._engine is not None:
            self.close()
        
        self._config = get_db_config()
        return self
    
    def connect(self) -> "DatabaseManager":
        """
        Estabelece conexão com o banco.
        
        Returns:
            Self para encadeamento
            
        Raises:
            DatabaseConfigurationError: Se não configurado
            DatabaseConnectionError: Se erro de conexão
        """
        if self._config is None:
            raise DatabaseConfigurationError(
                "Banco não configurado. Use configure() primeiro."
            )
        
        self._create_engine()
        return self
    
    def _create_engine(self) -> None:
        """Cria engine interno."""
        if self._config is None:
            raise DatabaseConfigurationError("Configuração não definida")
        
        try:
            conn_str = _build_connection_string(self._config)
            url = f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}"
            
            self._engine = create_engine(
                url,
                poolclass=QueuePool,
                **POOL_CONFIG
            )
            
            # Testa conexão
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Cria session factory
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=True,
                expire_on_commit=False
            )
            
            logger.info(
                f"DatabaseManager conectado a "
                f"{self._config.server}/{self._config.database}"
            )
            
        except Exception as e:
            raise DatabaseConnectionError(
                f"Falha ao conectar: {str(e)}",
                original_error=e
            )
    
    @property
    def engine(self) -> Engine:
        """Retorna engine SQLAlchemy."""
        if self._engine is None:
            self.connect()
        return self._engine
    
    @property
    def is_connected(self) -> bool:
        """Verifica se está conectado."""
        return self._engine is not None
    
    @property
    def current_database(self) -> Optional[str]:
        """Retorna nome do banco atual."""
        return self._config.database if self._config else None
    
    @property
    def current_server(self) -> Optional[str]:
        """Retorna nome do servidor atual."""
        return self._config.server if self._config else None
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager para sessão.
        
        Yields:
            Sessão SQLAlchemy
        """
        if self._session_factory is None:
            self.connect()
        
        session = self._session_factory()
        
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro na sessão: {str(e)}")
            raise DatabaseConnectionError(str(e), original_error=e)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def execute(self, sql: str, params: Optional[dict] = None) -> Any:
        """
        Executa SQL e retorna resultado.
        
        Args:
            sql: Query SQL
            params: Parâmetros nomeados
            
        Returns:
            Resultado da query
        """
        with self.session() as session:
            stmt = text(sql)
            if params:
                result = session.execute(stmt, params)
            else:
                result = session.execute(stmt)
            return result.fetchall()
    
    def execute_scalar(self, sql: str, params: Optional[dict] = None) -> Any:
        """
        Executa SQL e retorna valor escalar.
        
        Args:
            sql: Query SQL
            params: Parâmetros nomeados
            
        Returns:
            Primeiro valor do primeiro registro
        """
        with self.session() as session:
            stmt = text(sql)
            if params:
                result = session.execute(stmt, params)
            else:
                result = session.execute(stmt)
            return result.scalar()
    
    def switch_database(self, database: str) -> "DatabaseManager":
        """
        Troca para outro banco de dados no mesmo servidor.
        
        Args:
            database: Nome do novo banco
            
        Returns:
            Self para encadeamento
        """
        if self._config is None:
            raise DatabaseConfigurationError("Não há configuração ativa")
        
        return self.configure(
            server=self._config.server,
            database=database,
            auth=self._config.auth,
            username=self._config.username,
            password=self._config.password,
            driver=self._config.driver,
            encrypt=self._config.encrypt,
            trust_server_certificate=self._config.trust_server_certificate,
            timeout_seconds=self._config.timeout_seconds
        )
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Testa a conexão atual.
        
        Returns:
            Tupla (sucesso, mensagem)
        """
        return test_connection(self._config)
    
    def close(self) -> None:
        """Fecha conexões e descarta engine."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("DatabaseManager: conexões fechadas")
    
    def __enter__(self) -> "DatabaseManager":
        """Suporte a context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Fecha ao sair do context manager."""
        self.close()
    
    def __del__(self):
        """Cleanup ao destruir objeto."""
        self.close()


# ============================================================================
# Instância singleton do DatabaseManager
# ============================================================================

_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Retorna instância singleton do DatabaseManager.
    
    Returns:
        DatabaseManager singleton
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager()
    
    return _db_manager
