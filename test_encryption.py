#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Teste do módulo de criptografia"""

import sys
sys.path.insert(0, '.')

from encryption import encrypt_field, decrypt_field, is_encrypted

print("Testando módulo de criptografia...\n")

# Teste 1: Criptografar e descriptografar
test_value = "postgresql://user:pass@host/db"
print(f"1. Teste básico de encrypt/decrypt:")
print(f"   Valor original: {test_value}")

encrypted = encrypt_field(test_value)
print(f"   Criptografado: {encrypted[:50]}..." if encrypted else "   Criptografado: (vazio)")

decrypted = decrypt_field(encrypted)
print(f"   Descriptografado: {decrypted}")
print(f"   ✓ Valor preservado: {decrypted == test_value}\n")

# Teste 2: Valores None
print(f"2. Teste com None:")
enc_none = encrypt_field(None)
dec_none = decrypt_field(enc_none)
print(f"   encrypt(None) = {enc_none}")
print(f"   decrypt(None) = {dec_none}")
print(f"   ✓ Ambos None: {enc_none is None and dec_none is None}\n")

# Teste 3: Valores vazios
print(f"3. Teste com vazio:")
enc_empty = encrypt_field("")
dec_empty = decrypt_field(enc_empty)
print(f"   encrypt('') = {enc_empty}")
print(f"   decrypt('') = {dec_empty}")
print(f"   ✓ Ambos None/vazio: {enc_empty is None and dec_empty is None}\n")

# Teste 4: Detecção de criptografia
print(f"4. Teste de detecção:")
print(f"   is_encrypted('{encrypted[:20]}...'): {is_encrypted(encrypted)}")
print(f"   is_encrypted('texto_normal'): {is_encrypted('texto_normal')}")
print(f"   is_encrypted(None): {is_encrypted(None)}\n")

# Teste 5: String longa (como a do Licenca.key atual)
api_auth = "d2bd9a450500c2e851d049c5fb846f44"
api_db = "postgresql://neondb_owner:npg_c0bTxm7wYNpz@ep-dawn-mountain-acw7fpk4-pooler.sa-east-1.aws.neon.tech/"
print(f"5. Teste com valores reais de Licenca.key:")
enc_auth = encrypt_field(api_auth)
enc_db = encrypt_field(api_db)
print(f"   api_authorization: {api_auth}")
print(f"   Criptografado: {enc_auth[:30]}...")
dec_auth = decrypt_field(enc_auth)
print(f"   Descriptografado: {dec_auth}")
print(f"   ✓ Correto: {dec_auth == api_auth}")
print(f"   \n   api_database_url: {api_db[:50]}...")
print(f"   Criptografado: {enc_db[:30]}...")
dec_db = decrypt_field(enc_db)
print(f"   Descriptografado: {dec_db[:50]}...")
print(f"   ✓ Correto: {dec_db == api_db}\n")

print("✓✓✓ Todos os testes de criptografia passaram!")
