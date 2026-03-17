"""
formatters.py
=============
Funções de formatação.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Union


class Formatters:
    """
    Classe com métodos de formatação.
    """
    
    @staticmethod
    def format_date(
        value: Optional[Union[datetime, date, str]], 
        format_str: str = "%d/%m/%Y"
    ) -> str:
        """
        Formata data.
        
        Args:
            value: Data a formatar
            format_str: Formato de saída
            
        Returns:
            Data formatada ou string vazia
        """
        if not value:
            return ""
        
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        
        return value.strftime(format_str)
    
    @staticmethod
    def format_datetime(
        value: Optional[Union[datetime, str]], 
        format_str: str = "%d/%m/%Y %H:%M"
    ) -> str:
        """
        Formata data e hora.
        
        Args:
            value: Data/hora a formatar
            format_str: Formato de saída
            
        Returns:
            Data/hora formatada
        """
        return Formatters.format_date(value, format_str)
    
    @staticmethod
    def format_currency(
        value: Optional[Union[float, Decimal, int]], 
        symbol: str = "R$",
        decimal_places: int = 2
    ) -> str:
        """
        Formata valor monetário.
        
        Args:
            value: Valor a formatar
            symbol: Símbolo da moeda
            decimal_places: Casas decimais
            
        Returns:
            Valor formatado
        """
        if value is None:
            return ""
        
        formatted = f"{float(value):,.{decimal_places}f}"
        # Converte para formato brasileiro
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        
        return f"{symbol} {formatted}"
    
    @staticmethod
    def format_number(
        value: Optional[Union[float, Decimal, int]], 
        decimal_places: int = 2
    ) -> str:
        """
        Formata número.
        
        Args:
            value: Valor a formatar
            decimal_places: Casas decimais
            
        Returns:
            Número formatado
        """
        if value is None:
            return ""
        
        formatted = f"{float(value):,.{decimal_places}f}"
        # Converte para formato brasileiro
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        
        return formatted
    
    @staticmethod
    def format_integer(value: Optional[Union[float, int]]) -> str:
        """
        Formata número inteiro com separador de milhar.
        
        Args:
            value: Valor a formatar
            
        Returns:
            Número formatado
        """
        if value is None:
            return ""
        
        formatted = f"{int(value):,}"
        formatted = formatted.replace(",", ".")
        
        return formatted
    
    @staticmethod
    def format_cnpj(value: str) -> str:
        """
        Formata CNPJ.
        
        Args:
            value: CNPJ sem formatação
            
        Returns:
            CNPJ formatado (XX.XXX.XXX/XXXX-XX)
        """
        if not value:
            return ""
        
        # Remove caracteres não numéricos
        cnpj = ''.join(filter(str.isdigit, value))
        
        if len(cnpj) != 14:
            return value
        
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    
    @staticmethod
    def format_cpf(value: str) -> str:
        """
        Formata CPF.
        
        Args:
            value: CPF sem formatação
            
        Returns:
            CPF formatado (XXX.XXX.XXX-XX)
        """
        if not value:
            return ""
        
        cpf = ''.join(filter(str.isdigit, value))
        
        if len(cpf) != 11:
            return value
        
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    
    @staticmethod
    def format_phone(value: str) -> str:
        """
        Formata telefone.
        
        Args:
            value: Telefone sem formatação
            
        Returns:
            Telefone formatado
        """
        if not value:
            return ""
        
        phone = ''.join(filter(str.isdigit, value))
        
        if len(phone) == 10:
            return f"({phone[:2]}) {phone[2:6]}-{phone[6:]}"
        elif len(phone) == 11:
            return f"({phone[:2]}) {phone[2:7]}-{phone[7:]}"
        
        return value
    
    @staticmethod
    def truncate(value: str, max_length: int, suffix: str = "...") -> str:
        """
        Trunca string.
        
        Args:
            value: Texto a truncar
            max_length: Tamanho máximo
            suffix: Sufixo a adicionar
            
        Returns:
            Texto truncado
        """
        if not value or len(value) <= max_length:
            return value
        
        return value[:max_length - len(suffix)] + suffix
