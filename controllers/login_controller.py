"""
login_controller.py
===================
Controller responsável pelo processo de autenticação e seleção de base de dados.
"""

from typing import Optional, List, Tuple, Dict, Any
from PySide6.QtCore import Signal

from controllers.base_controller import BaseController
from services.auth_service import AuthService
from services.connection_service import ConnectionService
from models.user import User
from models.connection import Connection


class LoginController(BaseController):
    """
    Controller para gerenciar o fluxo de login.
    
    Signals:
        login_success: Emitido quando login é bem sucedido
        connections_loaded: Emitido quando conexões são carregadas
        companies_loaded: Emitido quando empresas são carregadas
    """
    
    login_success = Signal(object)  # User
    login_failed = Signal(str)  # mensagem de erro
    connections_loaded = Signal(list)  # Lista de Connection
    companies_loaded = Signal(list)  # Lista de tuplas (cod, nome)
    connection_tested = Signal(bool, str)  # sucesso, mensagem
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._auth_service = AuthService()
        self._connection_service = ConnectionService()
        self._current_user: Optional[User] = None
        self._current_connection: Optional[Connection] = None
    
    @property
    def current_user(self) -> Optional[User]:
        """Retorna o usuário autenticado."""
        return self._current_user
    
    @property
    def current_connection(self) -> Optional[Connection]:
        """Retorna a conexão atual."""
        return self._current_connection
    
    def load_connections(self) -> None:
        """Carrega lista de conexões disponíveis."""
        try:
            self.set_loading(True, "Carregando conexões...")
            connections = self._connection_service.get_available_connections()
            self.connections_loaded.emit(connections)
        except Exception as e:
            self.handle_error(e, "Erro ao carregar conexões")
        finally:
            self.set_loading(False)
    
    def test_connection(self, connection: Connection) -> None:
        """
        Testa uma conexão com o banco de dados.
        
        Args:
            connection: Conexão a ser testada
        """
        try:
            self.set_loading(True, "Testando conexão...")
            success, message = self._connection_service.test_connection(connection)
            self.connection_tested.emit(success, message)
        except Exception as e:
            self.connection_tested.emit(False, str(e))
        finally:
            self.set_loading(False)
    
    def select_connection(self, connection: Connection) -> None:
        """
        Seleciona uma conexão e carrega empresas disponíveis.
        
        Args:
            connection: Conexão selecionada
        """
        try:
            self.set_loading(True, "Conectando...")
            self._current_connection = connection
            self._connection_service.set_active_connection(connection)
            
            # Carrega empresas disponíveis
            companies = self._connection_service.list_companies()
            self.companies_loaded.emit(companies)
        except Exception as e:
            self.handle_error(e, "Erro ao selecionar conexão")
        finally:
            self.set_loading(False)
    
    def authenticate(
        self,
        username: str,
        password: str,
        company_code: str = "",
        company_name: str = ""
    ) -> None:
        """
        Realiza autenticação do usuário.
        
        Args:
            username: Nome de usuário
            password: Senha
            company_code: Código da empresa selecionada
            company_name: Nome da empresa selecionada
        """
        try:
            self.set_loading(True, "Autenticando...")
            
            user = self._auth_service.authenticate(username, password)
            
            if user:
                user.company_code = company_code
                user.company_name = company_name
                self._current_user = user
                
                # Salva último login
                self._connection_service.save_last_login(
                    username,
                    company_code,
                    company_name
                )
                
                self.login_success.emit(user)
            else:
                self.login_failed.emit("Usuário ou senha inválidos")
        except Exception as e:
            self.login_failed.emit(str(e))
        finally:
            self.set_loading(False)
    
    def get_last_login_info(self) -> Optional[Dict[str, str]]:
        """Retorna informações do último login."""
        return self._connection_service.get_last_login()
    
    def get_default_connection(self) -> Optional[Dict[str, str]]:
        """Retorna conexão padrão salva."""
        return self._connection_service.get_default_connection()
