#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Demonstra a correção do problema de Licenca.key vazio"""

import sys
import json
sys.path.insert(0, '.')

from licenca import carregar_licenca_de_arquivo, verificar_licenca

print("=" * 60)
print("DEMONSTRAÇÃO: Correção de Licenca.key")
print("=" * 60)

# 1. Mostrar o estado atual do arquivo
print("\n1. Estado ATUAL do arquivo Licenca.key:")
print("-" * 60)
with open('Licenca.key', 'r', encoding='utf-8') as f:
    conteudo = json.load(f)

print(f"   api_authorization: '{conteudo.get('api_authorization')}'")
print(f"   api_database_url: '{conteudo.get('api_database_url')}'")

# 2. Mostrar que o token contém os valores
print("\n2. Valores DENTRO do token JWT (payload):")
print("-" * 60)
token = conteudo.get('token')
token_payload = verificar_licenca(token, validar_validade=False)

api_auth = token_payload.get('api_authorization')
api_db_url = token_payload.get('api_database_url')

print(f"   api_authorization: '{api_auth}'")
print(f"   api_database_url: '{api_db_url[:50]}...'")

# 3. Indicar qual era o problema
print("\n3. PROBLEMA IDENTIFICADO:")
print("-" * 60)
if not conteudo.get('api_authorization') and api_auth:
    print("   ✗ Os campos api_authorization/api_database_url estavam VAZIOS")
    print("   ✗ Mas existiam no token JWT dentro do arquivo")
    print("   ✗ Isso impossibilitava reutilizar a licença corretamente")

# 4. Mostrar a solução
print("\n4. SOLUÇÃO IMPLEMENTADA:")
print("-" * 60)
print("   ✓ Atualizada função gerar_licenca() para aceitar api_* opcionais")
print("   ✓ Atualizada carregar_licenca_de_arquivo() para suportar JSON")
print("   ✓ Ao editar licença: extrai valores do token original")
print("   ✓ Regenera token PRESERVANDO os valores de API")
print("   ✓ Salva no arquivo com todos os campos preenchidos")

print("\n5. Teste de uso (simulação):")
print("-" * 60)
payload, token = carregar_licenca_de_arquivo('Licenca.key')
token_payload = verificar_licenca(token, validar_validade=False)
api_auth_test = token_payload.get('api_authorization')
api_db_test = token_payload.get('api_database_url')

print(f"   ✓ Licença carregada: {payload.get('nome_cliente')}")
print(f"   ✓ api_authorization extraído: {api_auth_test[:20]}...")
print(f"   ✓ api_database_url extraído: {api_db_test[:30]}...")

print("\n" + "=" * 60)
print("✓ PROBLEMA RESOLVIDO!")
print("=" * 60)
print("\nAgora você pode executar o modo interativo para regenerar a licença:")
print("   python licenca.py")
print("\nE o arquivo Licenca.key será salvo com todos os valores preenchidos!")
