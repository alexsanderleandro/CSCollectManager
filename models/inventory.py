"""
inventory.py
============
Modelos relacionados a inventário.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Inventory:
    """
    Representa um inventário.
    
    Attributes:
        id: Código do inventário
        number: Número do inventário
        description: Descrição
        open_date: Data de abertura
        close_date: Data de fechamento
        status: Status (aberto, fechado, etc.)
        company_code: Código da empresa
    """
    
    id: int = 0
    number: str = ""
    description: str = ""
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    status: str = ""
    company_code: str = ""
    
    @property
    def display_name(self) -> str:
        """Retorna nome formatado para exibição."""
        date_str = self.open_date.strftime("%d/%m/%Y") if self.open_date else ""
        return f"{self.number} - {self.description} ({date_str})"
    
    @property
    def is_open(self) -> bool:
        """Verifica se inventário está aberto."""
        return self.status.lower() in ("aberto", "open", "a")
    
    @property
    def is_closed(self) -> bool:
        """Verifica se inventário está fechado."""
        return self.status.lower() in ("fechado", "closed", "f")
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "number": self.number,
            "description": self.description,
            "open_date": self.open_date.isoformat() if self.open_date else None,
            "close_date": self.close_date.isoformat() if self.close_date else None,
            "status": self.status,
            "company_code": self.company_code
        }


@dataclass
class InventoryItem:
    """
    Representa um item de inventário.
    
    Attributes:
        id: Código do item
        inventory_id: Código do inventário
        product_code: Código do produto
        description: Descrição do produto
        quantity: Quantidade
        unit: Unidade de medida
        barcode: Código de barras
    """
    
    id: int = 0
    inventory_id: int = 0
    product_code: str = ""
    description: str = ""
    quantity: float = 0.0
    unit: str = "UN"
    barcode: str = ""
    
    @property
    def display_text(self) -> str:
        """Retorna texto formatado para exibição."""
        return f"{self.product_code} - {self.description}"
    
    @property
    def quantity_formatted(self) -> str:
        """Retorna quantidade formatada."""
        if self.quantity == int(self.quantity):
            return f"{int(self.quantity)} {self.unit}"
        return f"{self.quantity:.4f} {self.unit}"
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "inventory_id": self.inventory_id,
            "product_code": self.product_code,
            "description": self.description,
            "quantity": self.quantity,
            "unit": self.unit,
            "barcode": self.barcode
        }
    
    @staticmethod
    def from_dict(data: dict) -> "InventoryItem":
        """Cria InventoryItem a partir de dicionário."""
        return InventoryItem(
            id=data.get("id", 0),
            inventory_id=data.get("inventory_id", 0),
            product_code=data.get("product_code", ""),
            description=data.get("description", ""),
            quantity=float(data.get("quantity", 0)),
            unit=data.get("unit", "UN"),
            barcode=data.get("barcode", "")
        )
