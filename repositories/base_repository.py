"""
base_repository.py
==================
Classe base para todos os repositórios.
"""

from typing import Optional, List, Any, TypeVar, Generic
from contextlib import contextmanager
from database.connection_manager import ConnectionManager

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Repositório base com operações CRUD comuns.
    
    Fornece:
    - Gerenciamento de conexão
    - Métodos auxiliares para queries
    - Tratamento de erros padronizado
    """
    
    def __init__(self):
        self._connection_manager = ConnectionManager()
    
    @contextmanager
    def get_connection(self):
        """Context manager para obter conexão."""
        with self._connection_manager.get_connection() as conn:
            yield conn
    
    def execute_query(
        self,
        sql: str,
        params: tuple = (),
        fetch_one: bool = False
    ) -> Any:
        """
        Executa uma query e retorna resultados.
        
        Args:
            sql: Query SQL
            params: Parâmetros da query
            fetch_one: Se True, retorna apenas um registro
            
        Returns:
            Resultados da query
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            
            if fetch_one:
                return cursor.fetchone()
            return cursor.fetchall()
    
    def execute_scalar(self, sql: str, params: tuple = ()) -> Any:
        """
        Executa query e retorna valor escalar.
        
        Args:
            sql: Query SQL
            params: Parâmetros
            
        Returns:
            Valor escalar (primeira coluna do primeiro registro)
        """
        result = self.execute_query(sql, params, fetch_one=True)
        return result[0] if result else None
    
    def execute_non_query(self, sql: str, params: tuple = ()) -> int:
        """
        Executa comando sem retorno (INSERT, UPDATE, DELETE).
        
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
