#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Testa carregamento e regeneração de Licenca.key"""

import sys
import json
sys.path.insert(0, '.')

from licenca import carregar_licenca_de_arquivo, verificar_licenca, salvar_licenca_json, gerar_licenca

# Carregar o arquivo Licenca.key existente
print("1. Carregando Licenca.key...")
try:
    payload, token = carregar_licenca_de_arquivo('Licenca.key')
    print(f"   ✓ Carregado com sucesso")
    print(f"   - CNPJ(s): {payload.get('cnpjs')}")
    print(f"   - IDs: {payload.get('ids_celular')}")
    print(f"   - Cliente: {payload.get('nome_cliente')}")
except Exception as e:
    print(f"   ✗ Erro ao carregar: {e}")
    sys.exit(1)

# Decodificar o token para verificar conteúdo
print("\n2. Decodificando token...")
try:
    token_payload = verificar_licenca(token, validar_validade=False)
    api_auth = token_payload.get('api_authorization')
    api_db_url = token_payload.get('api_database_url')
    print(f"   ✓ Token decodificado")
    print(f"   - api_authorization: {api_auth[:20]}..." if api_auth else "   - api_authorization: (vazio)")
    print(f"   - api_database_url: {api_db_url[:50]}..." if api_db_url else "   - api_database_url: (vazio)")
except Exception as e:
    print(f"   ✗ Erro ao decodificar: {e}")
    sys.exit(1)

# Regenerar o token com os mesmos valores
print("\n3. Regenerando token com os valores de API...")
try:
    novo_token = gerar_licenca(
        payload.get('cnpjs', []),
        payload.get('ids_celular', []),
        payload.get('validade', ''),
        payload.get('nome_cliente', ''),
        payload.get('sql_servidor', ''),
        payload.get('sql_banco', ''),
        api_authorization=api_auth,
        api_database_url=api_db_url,
    )
    print(f"   ✓ Token regenerado")
except Exception as e:
    print(f"   ✗ Erro ao regenerar: {e}")
    sys.exit(1)

# Verificar se o novo token contém os valores
print("\n4. Verificando novo token...")
try:
    novo_payload = verificar_licenca(novo_token, validar_validade=False)
    nova_api_auth = novo_payload.get('api_authorization')
    nova_api_db_url = novo_payload.get('api_database_url')
    print(f"   ✓ Novo token decodificado")
    print(f"   - api_authorization: {nova_api_auth[:20]}..." if nova_api_auth else "   - api_authorization: (vazio)")
    print(f"   - api_database_url: {nova_api_db_url[:50]}..." if nova_api_db_url else "   - api_database_url: (vazio)")
    
    # Verificar se os valores foram preservados
    if nova_api_auth == api_auth and nova_api_db_url == api_db_url:
        print("   ✓ Valores de API preservados corretamente")
    else:
        print("   ✗ Valores de API NÃO foram preservados")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Erro ao verificar novo token: {e}")
    sys.exit(1)

# Salvar no arquivo JSON
print("\n5. Salvando em novo arquivo (licenca_test.key)...")
try:
    salvar_licenca_json(
        novo_token,
        payload.get('cnpjs', []),
        payload.get('ids_celular', []),
        payload.get('validade'),
        payload.get('database_url'),
        payload.get('api_url'),
        nova_api_auth,
        nova_api_db_url,
        'licenca_test.key'
    )
    print(f"   ✓ Arquivo salvo")
    
    # Verificar se o arquivo foi criado corretamente
    with open('licenca_test.key', 'r', encoding='utf-8') as f:
        conteudo = json.load(f)
    
    print(f"   ✓ Arquivo verificado")
    print(f"   - api_authorization no arquivo: {'SIM' if conteudo.get('api_authorization') else 'NÃO'}")
    print(f"   - api_database_url no arquivo: {'SIM' if conteudo.get('api_database_url') else 'NÃO'}")
    
    if conteudo.get('api_authorization') == nova_api_auth and conteudo.get('api_database_url') == nova_api_db_url:
        print("   ✓ Valores foram salvos corretamente no arquivo JSON")
    else:
        print("   ✗ Valores NÃO foram salvos corretamente")
        sys.exit(1)
        
except Exception as e:
    print(f"   ✗ Erro ao salvar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✓✓✓ Todos os testes de integração passaram!")
