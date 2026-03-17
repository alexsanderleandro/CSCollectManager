"""
Database Package
================
Camada de acesso ao banco de dados.

Responsabilidades:
- Gerenciar conexões com SQL Server
- Fornecer pool de conexões
- Abstrair detalhes de conexão
- Integrar com SQLAlchemy
"""

from database.connection_manager import ConnectionManager
from database.connection import (
    get_engine,
    get_session,
    get_session_factory,
    get_database_manager,
    dispose_engine,
    test_connection,
    DatabaseManager,
    DatabaseConnectionError,
    DatabaseConfigurationError,
)

__all__ = [
    # Connection Manager (pyodbc direto)
    "ConnectionManager",
    
    # SQLAlchemy functions
    "get_engine",
    "get_session",
    "get_session_factory",
    "get_database_manager",
    "dispose_engine",
    "test_connection",
    
    # Classes
    "DatabaseManager",
    "DatabaseConnectionError",
    "DatabaseConfigurationError",
]
