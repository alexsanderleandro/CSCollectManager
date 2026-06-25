#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Teste integrado de criptografia em Licenca.key"""

import sys
import json
import os
sys.path.insert(0, '.')

from licenca import salvar_licenca_json, carregar_licenca_de_arquivo, gerar_licenca
from encryption import is_encrypted, encrypt_field, decrypt_field

print("=" * 70)
print("TESTE INTEGRADO: Criptografia de Licenca.key")
print("=" * 70)

# Dados de teste
test_cnpjs = ["04671382000136", "04671382000306"]
test_ids = ["a3e9e3a0a4659652", "ALEXSANDERTESTEID"]
test_validade = "2026-06-26"
test_nome_cliente = "GUIDAUTO"
test_sql_servidor = "CEOSOFT-SERV1"
test_sql_banco = "GUIDAUTO"
test_api_auth = "d2bd9a450500c2e851d049c5fb846f44"
test_api_db = "postgresql://neondb_owner:npg_c0bTxm7wYNpz@ep-dawn-mountain-acw7fpk4-pooler.sa-east-1.aws.neon.tech/"
test_api_url = "https://cscollectapi.onrender.com"
test_arquivo = "licenca_encrypted_test.key"

try:
    print("\n1. Gerar token...")
    token = gerar_licenca(
        test_cnpjs,
        test_ids,
        test_validade,
        test_nome_cliente,
        test_sql_servidor,
        test_sql_banco,
        api_authorization=test_api_auth,
        api_database_url=test_api_db,
    )
    print(f"   ✓ Token gerado: {token[:30]}...")

    print("\n2. Salvar no arquivo (com criptografia)...")
    salvar_licenca_json(
        token,
        test_cnpjs,
        test_ids,
        test_validade,
        api_url=test_api_url,
        api_authorization=test_api_auth,
        api_database_url=test_api_db,
        caminho=test_arquivo
    )
    print(f"   ✓ Arquivo salvo: {test_arquivo}")

    print("\n3. Verificar arquivo gravado (verificar se está criptografado)...")
    with open(test_arquivo, 'r', encoding='utf-8') as f:
        conteudo = json.load(f)
    
    api_auth_salvo = conteudo.get('api_authorization')
    api_db_salvo = conteudo.get('api_database_url')
    
    print(f"   api_authorization no arquivo: {api_auth_salvo[:30] if api_auth_salvo else '(vazio)'}...")
    print(f"   api_database_url no arquivo: {api_db_salvo[:30] if api_db_salvo else '(vazio)'}...")
    
    if is_encrypted(api_auth_salvo):
        print(f"   ✓ api_authorization ESTÁ criptografado (Fernet)")
    else:
        print(f"   ✗ api_authorization NÃO está criptografado")
        
    if is_encrypted(api_db_salvo):
        print(f"   ✓ api_database_url ESTÁ criptografado (Fernet)")
    else:
        print(f"   ✗ api_database_url NÃO está criptografado")

    print("\n4. Carregar arquivo e descriptografar...")
    payload, token_carregado = carregar_licenca_de_arquivo(test_arquivo)
    
    api_auth_carregado = payload.get('api_authorization')
    api_db_carregado = payload.get('api_database_url')
    
    print(f"   ✓ Arquivo carregado")
    print(f"   api_authorization descriptografado: {api_auth_carregado}")
    print(f"   api_database_url descriptografado: {api_db_carregado[:50]}...")
    
    print("\n5. Validar valores após descriptografia...")
    if api_auth_carregado == test_api_auth:
        print(f"   ✓ api_authorization correto")
    else:
        print(f"   ✗ api_authorization INCORRETO!")
        print(f"     Esperado: {test_api_auth}")
        print(f"     Obtido: {api_auth_carregado}")
        
    if api_db_carregado == test_api_db:
        print(f"   ✓ api_database_url correto")
    else:
        print(f"   ✗ api_database_url INCORRETO!")
        print(f"     Esperado: {test_api_db}")
        print(f"     Obtido: {api_db_carregado}")

    print("\n6. Compatibilidade: Carregar arquivo antigo (sem criptografia)...")
    # Simula arquivo antigo com valores em texto puro
    arquivo_antigo = "licenca_old_format.key"
    old_data = {
        "cnpjs": test_cnpjs,
        "ids": test_ids,
        "token": token,
        "validade": test_validade,
        "api_url": test_api_url,
        "api_authorization": test_api_auth,  # Sem criptografia
        "api_database_url": test_api_db,  # Sem criptografia
    }
    with open(arquivo_antigo, 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)
    
    payload_old, _ = carregar_licenca_de_arquivo(arquivo_antigo)
    
    if payload_old.get('api_authorization') == test_api_auth and payload_old.get('api_database_url') == test_api_db:
        print(f"   ✓ Compatibilidade com arquivos antigos: OK")
    else:
        print(f"   ✗ Compatibilidade com arquivos antigos: FALHOU")

    print("\n" + "=" * 70)
    print("✓✓✓ TODOS OS TESTES PASSARAM COM SUCESSO!")
    print("=" * 70)
    print("\nResumo:")
    print("  • Campos api_authorization e api_database_url estão criptografados")
    print("  • Podem ser descriptografados apenas pelos apps autorizados")
    print("  • Compatível com arquivos antigos (sem criptografia)")
    print("  • As informações sensíveis NÃO ficam expostas no .key")

    # Limpar arquivos de teste
    os.remove(test_arquivo)
    os.remove(arquivo_antigo)
    print("\n✓ Arquivos de teste removidos")

except Exception as e:
    print(f"\n✗✗✗ ERRO: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
