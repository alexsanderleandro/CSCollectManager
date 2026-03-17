"""
connection_service.py
=====================
Serviço de gerenciamento de conexões com banco de dados.
"""

from typing import Optional, List, Tuple, Dict
from models.connection import Connection
from database.connection_manager import ConnectionManager
import authentication as auth_module
import login as login_module


class ConnectionService:
    """
    Serviço responsável pelo gerenciamento de conexões.
    
    Funcionalidades:
    - Listar conexões disponíveis (cslogin.xml)
    - Testar conexões
    - Gerenciar conexão ativa
    - Listar empresas disponíveis
    - Persistir preferências de conexão
    """
    
    def __init__(self):
        self._connection_manager = ConnectionManager()
        self._active_connection: Optional[Connection] = None
    
    def get_available_connections(self) -> List[Connection]:
        """
        Retorna lista de conexões disponíveis do cslogin.xml.
        
        Returns:
            Lista de objetos Connection
        """
        entries = login_module.read_connections()
        connections = []
        
        for entry in entries:
            conn = Connection(
                login_id=entry.login_id,
                server=entry.servidor,
                database=entry.banco,
                db_type=entry.tipo_banco,
                last_user=entry.ultimo_usuario
            )
            connections.append(conn)
        
        return connections
    
    def test_connection(self, connection: Connection) -> Tuple[bool, str]:
        """
        Testa uma conexão com o banco de dados.
        
        Args:
            connection: Conexão a ser testada
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        # Configura a conexão temporariamente
        cfg = auth_module.DBConfig(
            server=connection.server,
            database=connection.database,
            auth="trusted"  # Usa Windows Authentication por padrão
        )
        
        return auth_module.test_connection(cfg)
    
    def set_active_connection(self, connection: Connection) -> None:
        """
        Define a conexão ativa no sistema.
        
        Args:
            connection: Conexão a ser ativada
        """
        self._active_connection = connection
        
        # Configura globalmente no módulo authentication
        cfg = auth_module.DBConfig(
            server=connection.server,
            database=connection.database,
            auth="trusted"
        )
        auth_module.set_db_config(cfg)
        
        # Salva como conexão padrão
        login_module.save_default_connection(
            tipo=connection.db_type,
            srv=connection.server,
            db=connection.database
        )
    
    def get_active_connection(self) -> Optional[Connection]:
        """Retorna a conexão ativa."""
        return self._active_connection
    
    def list_companies(self, only_active: bool = True) -> List[Tuple[str, str]]:
        """
        Lista empresas disponíveis na base conectada.
        
        Args:
            only_active: Se True, retorna apenas empresas ativas
            
        Returns:
            Lista de tuplas (codigo, nome)
        """
        return auth_module.list_companies(only_active=only_active)
    
    def list_databases(self, server: Optional[str] = None) -> List[str]:
        """
        Lista bancos de dados disponíveis no servidor.
        
        Args:
            server: Servidor (usa o atual se não informado)
            
        Returns:
            Lista de nomes de bancos
        """
        return auth_module.list_databases(server=server)
    
    def save_last_login(
        self,
        username: str,
        company_code: str = "",
        company_name: str = ""
    ) -> bool:
        """
        Salva informações do último login.
        
        Args:
            username: Nome de usuário
            company_code: Código da empresa
            company_name: Nome da empresa
            
        Returns:
            True se salvou com sucesso
        """
        conn = self._active_connection
        return login_module.save_last_login(
            user=username,
            srv=conn.server if conn else "",
            db=conn.database if conn else "",
            codempresa=company_code,
            nomeempresa=company_name
        )
    
    def get_last_login(self) -> Optional[Dict[str, str]]:
        """Retorna informações do último login."""
        return login_module.load_last_login()
    
    def get_default_connection(self) -> Optional[Dict[str, str]]:
        """Retorna conexão padrão salva."""
        return login_module.load_default_connection()
