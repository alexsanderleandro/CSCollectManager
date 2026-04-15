"""
auth_service.py
===============
Serviço de autenticação de usuários.
"""

from typing import Optional, Dict, Any
from models.user import User
from database.connection_manager import ConnectionManager
import authentication as auth_module


class AuthService:
    """
    Serviço responsável pela autenticação de usuários.
    
    Utiliza o módulo authentication.py existente para validação
    de credenciais contra o banco SQL Server.
    """
    
    def __init__(self):
        """
        Inicializa o serviço de autenticação.

        Instância o gerenciador de conexão utilizado internamente
        para validação de credenciais contra o banco de dados.
        """
        self._connection_manager = ConnectionManager()
    
    def authenticate(
        self,
        username: str,
        password: str,
        require_active: bool = True,
        require_manager: bool = False
    ) -> Optional[User]:
        """
        Autentica um usuário no sistema.
        
        Args:
            username: Nome de usuário
            password: Senha
            require_active: Exigir usuário ativo
            require_manager: Exigir permissão de gerente
            
        Returns:
            User se autenticação bem sucedida, None caso contrário
        """
        if not username or not password:
            return None
        
        # Usa o módulo authentication existente
        user_data = auth_module.verify_user(
            username=username,
            password=password,
            require_active=require_active,
            require_manager=require_manager
        )
        
        if user_data:
            return User.from_dict(user_data)
        
        return None
    
    def validate_session(self, user: User) -> bool:
        """
        Valida se a sessão do usuário ainda é válida.
        
        Args:
            user: Usuário a ser validado
            
        Returns:
            True se sessão válida
        """
        # TODO: Implementar validação de sessão se necessário
        return user is not None and user.is_active
    
    def change_password(
        self,
        username: str,
        current_password: str,
        new_password: str
    ) -> tuple[bool, str]:
        """
        Altera a senha do usuário.
        
        Args:
            username: Nome de usuário
            current_password: Senha atual
            new_password: Nova senha
            
        Returns:
            Tupla (sucesso, mensagem)
        """
        # Primeiro valida a senha atual
        user = self.authenticate(username, current_password)
        if not user:
            return False, "Senha atual incorreta"
        
        # TODO: Implementar alteração de senha via stored procedure
        return False, "Funcionalidade não implementada"
