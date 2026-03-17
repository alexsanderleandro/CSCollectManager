"""
user.py
=======
Modelo de usuário do sistema.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class User:
    """
    Representa um usuário do sistema.
    
    Attributes:
        id: Código do usuário
        username: Nome de usuário
        is_active: Se o usuário está ativo
        is_manager: Se o usuário é gerente/administrador
        company_code: Código da empresa selecionada
        company_name: Nome da empresa selecionada
    """
    
    id: int = 0
    username: str = ""
    is_active: bool = True
    is_manager: bool = False
    company_code: str = ""
    company_name: str = ""
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "User":
        """
        Cria User a partir de dicionário.
        
        Args:
            data: Dicionário com dados do usuário
            
        Returns:
            Instância de User
        """
        return User(
            id=data.get("CodUsuario", 0) or 0,
            username=data.get("NomeUsuario", "") or "",
            is_active=data.get("InativosN", 1) == 0,
            is_manager=data.get("PDVGerenteSN", 0) == 1,
            company_code=data.get("CodEmpresa", "") or "",
            company_name=data.get("NomeEmpresa", "") or ""
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte User para dicionário.
        
        Returns:
            Dicionário com dados do usuário
        """
        return {
            "CodUsuario": self.id,
            "NomeUsuario": self.username,
            "InativosN": 0 if self.is_active else 1,
            "PDVGerenteSN": 1 if self.is_manager else 0,
            "CodEmpresa": self.company_code,
            "NomeEmpresa": self.company_name
        }
    
    @property
    def display_name(self) -> str:
        """Retorna nome formatado para exibição."""
        return self.username.title() if self.username else "Usuário"
    
    def has_permission(self, permission: str) -> bool:
        """
        Verifica se usuário possui determinada permissão.
        
        Args:
            permission: Nome da permissão
            
        Returns:
            True se possui permissão
        """
        # Gerentes têm todas as permissões
        if self.is_manager:
            return True
        
        # TODO: Implementar sistema de permissões granular
        return True
