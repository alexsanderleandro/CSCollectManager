"""
connection_manager.py
=====================
Gerenciador de conexões com banco de dados.
"""

from typing import Optional
from contextlib import contextmanager
import pyodbc

# Importa o módulo authentication existente
import authentication as auth_module


class ConnectionManager:
    """
    Gerenciador centralizado de conexões com banco de dados.
    
    Encapsula o uso do módulo authentication.py existente,
    fornecendo uma interface limpa para a aplicação.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
    
    @contextmanager
    def get_connection(self, autocommit: bool = False):
        """
        Obtém conexão com o banco de dados.
        
        Args:
            autocommit: Se True, ativa autocommit
            
        Yields:
            Conexão pyodbc
        """
        with auth_module.get_connection(autocommit=autocommit) as conn:
            yield conn
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Testa a conexão atual.
        
        Returns:
            Tupla (sucesso, mensagem)
        """
        return auth_module.test_connection()
    
    def get_current_config(self) -> auth_module.DBConfig:
        """
        Retorna configuração atual.
        
        Returns:
            DBConfig atual
        """
        return auth_module.get_db_config()
    
    def set_config(
        self,
        server: str,
        database: str,
        auth: str = "trusted",
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> None:
        """
        Define configuração de conexão.
        
        Args:
            server: Nome do servidor
            database: Nome do banco
            auth: Tipo de autenticação (trusted/sql)
            username: Usuário (para auth=sql)
            password: Senha (para auth=sql)
        """
        cfg = auth_module.DBConfig(
            server=server,
            database=database,
            auth=auth,
            username=username,
            password=password
        )
        auth_module.set_db_config(cfg)
    
    def execute_query(self, sql: str, params: tuple = (), fetch_all: bool = True):
        """
        Executa query e retorna resultados.
        
        Args:
            sql: Query SQL
            params: Parâmetros
            fetch_all: Se True, retorna todos os resultados
            
        Returns:
            Resultados da query
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            
            if fetch_all:
                return cursor.fetchall()
            return cursor.fetchone()
    
    def execute_non_query(self, sql: str, params: tuple = ()) -> int:
        """
        Executa comando sem retorno.
        
        Args:
            sql: Comando SQL
            params: Parâmetros
            
        Returns:
            Número de linhas afetadas
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
    
    def execute_scalar(self, sql: str, params: tuple = ()):
        """
        Executa query e retorna valor escalar.
        
        Args:
            sql: Query SQL
            params: Parâmetros
            
        Returns:
            Primeiro valor do primeiro registro
        """
        result = self.execute_query(sql, params, fetch_all=False)
        return result[0] if result else None
