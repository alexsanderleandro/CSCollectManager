"""
validators.py
=============
Funções de validação.
"""

import re
from typing import Optional, Tuple


class Validators:
    """
    Classe com métodos de validação.
    """
    
    @staticmethod
    def validate_required(value: str, field_name: str = "Campo") -> Tuple[bool, str]:
        """
        Valida campo obrigatório.
        
        Args:
            value: Valor a validar
            field_name: Nome do campo para mensagem
            
        Returns:
            Tupla (válido, mensagem)
        """
        if not value or not value.strip():
            return False, f"{field_name} é obrigatório"
        return True, ""
    
    @staticmethod
    def validate_min_length(
        value: str, 
        min_len: int, 
        field_name: str = "Campo"
    ) -> Tuple[bool, str]:
        """
        Valida tamanho mínimo.
        
        Args:
            value: Valor a validar
            min_len: Tamanho mínimo
            field_name: Nome do campo
            
        Returns:
            Tupla (válido, mensagem)
        """
        if len(value) < min_len:
            return False, f"{field_name} deve ter no mínimo {min_len} caracteres"
        return True, ""
    
    @staticmethod
    def validate_max_length(
        value: str, 
        max_len: int, 
        field_name: str = "Campo"
    ) -> Tuple[bool, str]:
        """
        Valida tamanho máximo.
        
        Args:
            value: Valor a validar
            max_len: Tamanho máximo
            field_name: Nome do campo
            
        Returns:
            Tupla (válido, mensagem)
        """
        if len(value) > max_len:
            return False, f"{field_name} deve ter no máximo {max_len} caracteres"
        return True, ""
    
    @staticmethod
    def validate_numeric(value: str, field_name: str = "Campo") -> Tuple[bool, str]:
        """
        Valida se é numérico.
        
        Args:
            value: Valor a validar
            field_name: Nome do campo
            
        Returns:
            Tupla (válido, mensagem)
        """
        try:
            float(value)
            return True, ""
        except ValueError:
            return False, f"{field_name} deve ser numérico"
    
    @staticmethod
    def validate_integer(value: str, field_name: str = "Campo") -> Tuple[bool, str]:
        """
        Valida se é inteiro.
        
        Args:
            value: Valor a validar
            field_name: Nome do campo
            
        Returns:
            Tupla (válido, mensagem)
        """
        try:
            int(value)
            return True, ""
        except ValueError:
            return False, f"{field_name} deve ser um número inteiro"
    
    @staticmethod
    def validate_email(value: str) -> Tuple[bool, str]:
        """
        Valida formato de email.
        
        Args:
            value: Email a validar
            
        Returns:
            Tupla (válido, mensagem)
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, value):
            return True, ""
        return False, "Email inválido"
    
    @staticmethod
    def validate_cnpj(value: str) -> Tuple[bool, str]:
        """
        Valida CNPJ.
        
        Args:
            value: CNPJ a validar (apenas números)
            
        Returns:
            Tupla (válido, mensagem)
        """
        # Remove caracteres não numéricos
        cnpj = re.sub(r'\D', '', value)
        
        if len(cnpj) != 14:
            return False, "CNPJ deve ter 14 dígitos"
        
        # Verifica se todos os dígitos são iguais
        if cnpj == cnpj[0] * 14:
            return False, "CNPJ inválido"
        
        # Validação dos dígitos verificadores
        def calc_digit(cnpj, weights):
            total = sum(int(d) * w for d, w in zip(cnpj, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        
        if calc_digit(cnpj[:12], weights1) != int(cnpj[12]):
            return False, "CNPJ inválido"
        
        if calc_digit(cnpj[:13], weights2) != int(cnpj[13]):
            return False, "CNPJ inválido"
        
        return True, ""
