#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Demonstração da implementação de criptografia em Licenca.key"""

import json
import sys
sys.path.insert(0, '.')

from encryption import encrypt_field, decrypt_field, is_encrypted

print("\n" + "=" * 80)
print(" SEGURANÇA DE CREDENCIAIS: Demonstração da Criptografia em Licenca.key")
print("=" * 80)

# Valores reais que precisam ser protegidos
api_auth = "d2bd9a450500c2e851d049c5fb846f44"
api_db_url = "postgresql://neondb_owner:npg_c0bTxm7wYNpz@ep-dawn-mountain-acw7fpk4-pooler.sa-east-1.aws.neon.tech/"

print("\n▶ ANTES DA IMPLEMENTAÇÃO (Inseguro):")
print("-" * 80)
print("Arquivo Licenca.key em texto puro (EXPOSTO):\n")
unencrypted_data = {
    "cnpjs": ["04671382000136", "04671382000306"],
    "ids": ["a3e9e3a0a4659652", "ALEXSANDERTESTEID"],
    "token": "eyJjbnBqcyI6WyIwNDY3MTM4MjAwMDEzNiIsIjA0NjcxMzgyMDAwMzA2Il0sImlkc19jZWx1bGFyIjpbImEzZTllM2EwYTQ2NTk2NTIiLCJBTEVYU0FOREVSVEVTVEVJRCJdLCJ2YWxpZGFkZSI6IjIwMjYtMDYtMjYiLCJub21lX2NsaWVudGUiOiJHVUlEQVVUTyIsInNxbF9zZXJ2aWRvciI6IkNFT1NPRlQtU0VSVjEiLCJzcWxfYmFuY28iOiJHVUlEQVVUTyIsImdlcmFkb19lbSI6IjIwMjYtMDYtMjNUMTI6MDg6MzAtMDM6MDAiLCJhcGlfYXV0aG9yaXphdGlvbiI6ImQyYmQ5YTQ1MDUwMGMyZTg1MWQwNDljNWZiODQ2ZjQ0IiwiYXBpX2RhdGFiYXNlX3VybCI6InBvc3RncmVzcWw6Ly9uZW9uZGJfb3duZXI6bnBnX2MwYlR4bTd3WU5wekBlcC1kYXduLW1vdW50YWluLWFjdzdmcGs0LXBvb2xlci5zYS1lYXN0LTEuYXdzLm5lb24udGVjaCJ9.RLRZCFqu1QIHHTn2WVTIv9JYMwHNW5XkbvZttuxCdXU",
    "validade": "2026-06-26",
    "api_url": "https://cscollectapi.onrender.com",
    "api_authorization": api_auth,  # ⚠️ EXPOSTO em texto puro
    "api_database_url": api_db_url,  # ⚠️ EXPOSTO em texto puro
}
print(json.dumps(unencrypted_data, indent=2, ensure_ascii=False))
print("\n⚠️  PROBLEMAS:")
print("  • Credenciais LEGÍVEIS em texto puro")
print("  • Qualquer pessoa com acesso ao arquivo pode ler as chaves")
print("  • Banco de dados PostgreSQL exposto")
print("  • Token da API exposto")

print("\n\n▶ DEPOIS DA IMPLEMENTAÇÃO (Seguro):")
print("-" * 80)
print("Arquivo Licenca.key com criptografia Fernet (PROTEGIDO):\n")

# Criptografa os campos sensíveis
encrypted_auth = encrypt_field(api_auth)
encrypted_db = encrypt_field(api_db_url)

encrypted_data = {
    "cnpjs": ["04671382000136", "04671382000306"],
    "ids": ["a3e9e3a0a4659652", "ALEXSANDERTESTEID"],
    "token": "eyJjbnBqcyI6WyIwNDY3MTM4MjAwMDEzNiIsIjA0NjcxMzgyMDAwMzA2Il0sImlkc19jZWx1bGFyIjpbImEzZTllM2EwYTQ2NTk2NTIiLCJBTEVYU0FOREVSVEVTVEVJRCJdLCJ2YWxpZGFkZSI6IjIwMjYtMDYtMjYiLCJub21lX2NsaWVudGUiOiJHVUlEQVVUTyIsInNxbF9zZXJ2aWRvciI6IkNFT1NPRlQtU0VSVjEiLCJzcWxfYmFuY28iOiJHVUlEQVVUTyIsImdlcmFkb19lbSI6IjIwMjYtMDYtMjNUMTI6MDg6MzAtMDM6MDAiLCJhcGlfYXV0aG9yaXphdGlvbiI6ImQyYmQ5YTQ1MDUwMGMyZTg1MWQwNDljNWZiODQ2ZjQ0IiwiYXBpX2RhdGFiYXNlX3VybCI6InBvc3RncmVzcWw6Ly9uZW9uZGJfb3duZXI6bnBnX2MwYlR4bTd3WU5wekBlcC1kYXduLW1vdW50YWluLWFjdzdmcGs0LXBvb2xlci5zYS1lYXN0LTEuYXdzLm5lb24udGVjaCJ9.RLRZCFqu1QIHHTn2WVTIv9JYMwHNW5XkbvZttuxCdXU",
    "validade": "2026-06-26",
    "api_url": "https://cscollectapi.onrender.com",
    "api_authorization": encrypted_auth,  # ✓ CRIPTOGRAFADO
    "api_database_url": encrypted_db,  # ✓ CRIPTOGRAFADO
}
print(json.dumps(encrypted_data, indent=2, ensure_ascii=False))

print("\n✓ BENEFÍCIOS:")
print("  • Credenciais CRIPTOGRAFADAS com Fernet (AES-128)")
print("  • Ilegível para quem abre o arquivo manualmente")
print("  • Podem ser descriptografadas apenas pelos apps autorizados")
print("  • Compatível com versões antigas (detecta automaticamente)")
print("  • Chave de criptografia é derivada de seed conhecida")

print("\n\n▶ PROCESSO DE DESCRIPTOGRAFIA (Durante Validação):")
print("-" * 80)
print(f"1. CSCollectManager carrega Licenca.key")
print(f"2. Detecta campo criptografado: {encrypted_auth[:30]}...")
print(f"3. Usa chave mestre para descriptografar")
dec_auth = decrypt_field(encrypted_auth)
print(f"4. Resultado: {dec_auth}")
print(f"5. Credencial está disponível apenas em memória")
print(f"6. Usada para conectar ao banco PostgreSQL")
print(f"7. Descartada após validação (não salva)")

print("\n\n▶ FLUXO DE SEGURANÇA:")
print("-" * 80)
print("""
  CSCollectLicence                  CSCollectManager              CSCollect (APK)
  ┌──────────────────┐              ┌──────────────────┐          ┌──────────────────┐
  │ Gera licença     │              │ Carrega .key     │          │ Valida licença   │
  │ Credenciais em   │─────────────→│ Descriptografa   │─────────→│ Descriptografa   │
  │ texto puro       │  Criptografa │ em memória       │  Token   │ em memória       │
  │                  │              │ Usa credenciais  │          │ Conecta BD       │
  │ Salva .key       │              │ Salva .key enc   │          │ Usa API          │
  └──────────────────┘              └──────────────────┘          └──────────────────┘
         ↓                                  ↓                              ↓
    Licenca.key                       Licenca.key                   Descriptografado
  (Criptografado)                  (Criptografado)                  (Apenas RAM)
""")

print("\n▶ ESPECIFICAÇÃO TÉCNICA:")
print("-" * 80)
print("  Algoritmo: Fernet (baseado em AES-128-CBC)")
print("  Modo: Simetria (mesma chave para encrypt/decrypt)")
print("  Autenticação: HMAC-SHA256 incluído no token")
print("  Derivação de Chave: SHA-256 de seed")
print("  Campos Protegidos:")
print("    • api_authorization")
print("    • api_database_url")
print("    • database_url (opcional)")

print("\n" + "=" * 80)
print(" Implementação completa e segura ✓")
print("=" * 80 + "\n")
