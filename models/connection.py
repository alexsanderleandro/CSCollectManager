"""
connection.py
=============
Modelo de conexão com banco de dados.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Connection:
    """
    Representa uma conexão com banco de dados.
    
    Attributes:
        login_id: Identificador do login (do cslogin.xml)
        server: Nome do servidor
        database: Nome do banco de dados
        db_type: Tipo do banco (MSSQL, etc.)
        auth_type: Tipo de autenticação (trusted, sql)
        username: Usuário para autenticação SQL
        password: Senha para autenticação SQL
        last_user: Último usuário que usou esta conexão
    """
    
    login_id: str = ""
    server: str = ""
    database: str = ""
    db_type: str = "MSSQL"
    auth_type: str = "trusted"
    username: Optional[str] = None
    password: Optional[str] = None
    last_user: str = ""
    
    @property
    def display_name(self) -> str:
        """Retorna nome formatado para exibição em combo/lista."""
        return f"{self.server} - {self.database}"
    
    @property
    def is_valid(self) -> bool:
        """Verifica se a conexão tem dados mínimos válidos."""
        return bool(self.server and self.database)
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "login_id": self.login_id,
            "server": self.server,
            "database": self.database,
            "db_type": self.db_type,
            "auth_type": self.auth_type,
            "username": self.username,
            "last_user": self.last_user
        }
    
    @staticmethod
    def from_dict(data: dict) -> "Connection":
        """Cria Connection a partir de dicionário."""
        return Connection(
            login_id=data.get("login_id", ""),
            server=data.get("server", "") or data.get("srv", ""),
            database=data.get("database", "") or data.get("db", ""),
            db_type=data.get("db_type", "") or data.get("tipo", "MSSQL"),
            auth_type=data.get("auth_type", "trusted"),
            username=data.get("username"),
            last_user=data.get("last_user", "")
        )
