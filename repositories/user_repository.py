"""
user_repository.py
==================
Repositório para acesso a dados de usuários.
"""

from typing import Optional, List
from repositories.base_repository import BaseRepository
from models.user import User


class UserRepository(BaseRepository[User]):
    """
    Repositório para operações de usuário no banco de dados.
    """
    
    def get_by_username(self, username: str) -> Optional[User]:
        """
        Busca usuário pelo nome.
        
        Args:
            username: Nome de usuário
            
        Returns:
            User ou None
        """
        sql = """
            SELECT 
                CodUsuario,
                NomeUsuario,
                InativosN,
                PDVGerenteSN
            FROM dbo.Usuarios WITH (NOLOCK)
            WHERE NomeUsuario = ?
        """
        
        row = self.execute_query(sql, (username,), fetch_one=True)
        
        if row:
            return User(
                id=row[0],
                username=row[1] or "",
                is_active=row[2] == 0,
                is_manager=row[3] == 1
            )
        return None
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Busca usuário por ID.
        
        Args:
            user_id: ID do usuário
            
        Returns:
            User ou None
        """
        sql = """
            SELECT 
                CodUsuario,
                NomeUsuario,
                InativosN,
                PDVGerenteSN
            FROM dbo.Usuarios WITH (NOLOCK)
            WHERE CodUsuario = ?
        """
        
        row = self.execute_query(sql, (user_id,), fetch_one=True)
        
        if row:
            return User(
                id=row[0],
                username=row[1] or "",
                is_active=row[2] == 0,
                is_manager=row[3] == 1
            )
        return None
    
    def get_all_active(self) -> List[User]:
        """
        Retorna todos os usuários ativos.
        
        Returns:
            Lista de usuários ativos
        """
        sql = """
            SELECT 
                CodUsuario,
                NomeUsuario,
                InativosN,
                PDVGerenteSN
            FROM dbo.Usuarios WITH (NOLOCK)
            WHERE ISNULL(InativosN, 0) = 0
            ORDER BY NomeUsuario
        """
        
        results = self.execute_query(sql)
        
        return [
            User(
                id=row[0],
                username=row[1] or "",
                is_active=True,
                is_manager=row[3] == 1
            )
            for row in results
        ] if results else []
