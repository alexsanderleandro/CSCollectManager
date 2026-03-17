"""
company.py
==========
Modelo de empresa.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Company:
    """
    Representa uma empresa do sistema.
    
    Attributes:
        code: Código da empresa
        name: Nome da empresa
        is_active: Se a empresa está ativa
        cnpj: CNPJ da empresa
    """
    
    code: str = ""
    name: str = ""
    is_active: bool = True
    cnpj: str = ""
    
    @property
    def display_name(self) -> str:
        """Retorna nome formatado para exibição."""
        if self.code:
            return f"{self.code} - {self.name}"
        return self.name
    
    @staticmethod
    def from_tuple(data: tuple) -> "Company":
        """
        Cria Company a partir de tupla (código, nome).
        
        Args:
            data: Tupla (código, nome)
            
        Returns:
            Instância de Company
        """
        return Company(
            code=str(data[0]) if len(data) > 0 else "",
            name=str(data[1]) if len(data) > 1 else ""
        )
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "code": self.code,
            "name": self.name,
            "is_active": self.is_active,
            "cnpj": self.cnpj
        }
