#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Testa sintaxe do módulo licenca"""

import sys
sys.path.insert(0, '.')

try:
    import licenca
    print("✓ licenca.py - Sintaxe OK")
except SyntaxError as e:
    print(f"✗ Erro de sintaxe em licenca.py: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✓ licenca.py carregado (outro erro é esperado): {type(e).__name__}: {e}")

# Verificar se as funções existem
if hasattr(licenca, 'gerar_licenca'):
    print("✓ Função gerar_licenca existe")
else:
    print("✗ Função gerar_licenca não encontrada")
    sys.exit(1)

if hasattr(licenca, 'salvar_licenca_json'):
    print("✓ Função salvar_licenca_json existe")
else:
    print("✗ Função salvar_licenca_json não encontrada")
    sys.exit(1)

# Verificar assinatura de gerar_licenca
import inspect
sig = inspect.signature(licenca.gerar_licenca)
print(f"✓ Assinatura de gerar_licenca: {sig}")

# Verificar se os novos parâmetros existem
params = list(sig.parameters.keys())
if 'api_authorization' in params:
    print("✓ Parâmetro 'api_authorization' adicionado")
else:
    print("✗ Parâmetro 'api_authorization' não encontrado")
    sys.exit(1)

if 'api_database_url' in params:
    print("✓ Parâmetro 'api_database_url' adicionado")
else:
    print("✗ Parâmetro 'api_database_url' não encontrado")
    sys.exit(1)

print("\n✓✓✓ Todos os testes passaram!")
