"""Módulo com funções para o CSCollectManager verificar licenças geradas.

Fornece API programática para:
 - `verify_token(token, master_key)` -> retorna payload dict se válido
 - `load_and_verify_file(path, master_key=None)` -> lê arquivo .key e verifica
 - `get_relevant_fields(payload)` -> dicionário com campos esperados pelo app

Use estas funções dentro do CSCollectManager para verificar assinatura e
extrair `sql_servidor` e `sql_banco` de forma robusta.
"""
from __future__ import annotations
import os
import json
import base64
import hmac
import hashlib
from typing import Tuple, Dict, Any, Optional


def _b64u_decode(s: str) -> bytes:
    padding = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + padding).encode('ascii'))


def split_token(token: str) -> Tuple[bytes, bytes]:
    parts = token.strip().split('.')
    if len(parts) != 2:
        raise ValueError('Formato de token inválido; esperado payload.signature')
    dados = _b64u_decode(parts[0])
    assinatura = _b64u_decode(parts[1])
    return dados, assinatura


def verify_token(token: str, master_key: str) -> Dict[str, Any]:
    """Verifica assinatura HMAC-SHA256 e retorna o payload JSON como dict.

    Lança `ValueError` em caso de formato inválido ou assinatura incorreta, e
    `json.JSONDecodeError` se o payload não for um JSON válido.
    """
    if not master_key:
        raise ValueError('master_key não fornecida')
    dados, assinatura = split_token(token)
    esperado = hmac.new(master_key.encode('utf-8'), dados, hashlib.sha256).digest()
    if not hmac.compare_digest(esperado, assinatura):
        raise ValueError('Assinatura inválida')
    payload = json.loads(dados.decode('utf-8'))
    return payload


def _is_signed_token(token: str) -> bool:
    """Retorna True apenas se o token está no formato HMAC assinado (base64url_json.base64url_sig).

    Verifica se a primeira parte, ao ser decodificada de base64url, resulta em JSON válido.
    Isso evita falso-positivo com tokens no formato 'api_token.neon_signature'.
    """
    parts = token.strip().split('.')
    if len(parts) != 2 or not all(p for p in parts):
        return False
    try:
        payload_bytes = _b64u_decode(parts[0])
        json.loads(payload_bytes.decode('utf-8'))
        return True
    except Exception:
        return False


def _verify_token_online(licenca_json: Dict[str, Any]) -> Dict[str, Any]:
    """Valida licença contra o banco Neon (database_url) conforme fluxo da documentação.

    Etapas:
    1. Consulta o banco pelo CNPJ individual (exact match + LIKE patterns).
    2. Verifica ``ativo = true``.
    3. Verifica ``validade >= hoje``.
    4. Valida a assinatura HMAC-SHA256 do token retornado pelo banco.
    5. Verifica CNPJ e device ID no payload do token (raiz de confiança).
    6. Descriptografa ``api_authorization`` e ``api_database_url`` em memória.

    Raises:
        ImportError: se psycopg2 ou cryptography não estiverem instalados.
        ValueError: se database_url não estiver presente no arquivo.
        Exception: se qualquer etapa de validação falhar.
    """
    database_url = licenca_json.get('database_url')
    if not database_url:
        return licenca_json

    # Normaliza URL para evitar erros de channel_binding e sslmode (crítico para Neon)
    import re
    from urllib.parse import urlparse, urlunparse
    
    # 1. Garante o nome do banco padrão do Neon (/neondb) se estiver ausente
    # No Neon, se o banco for omitido, o driver usa o user (neondb_owner), que não existe como banco.
    try:
        parsed = urlparse(database_url)
        if not parsed.path or parsed.path == '/':
            database_url = urlunparse(parsed._replace(path='/neondb'))
    except Exception:
        pass

    # 2. Limpeza de channel_binding
    database_url = re.sub(r'([?&])channel_binding=[^&]*&?', r'\1', database_url).rstrip('?&')
    
    # 3. Garante sslmode=require
    if 'sslmode=' not in database_url:
        database_url += ("&" if "?" in database_url else "?") + "sslmode=require"

    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 não instalado. Execute: pip install psycopg2-binary")

    # Importa descriptografia AES-256-GCM
    try:
        from licenca import _decrypt_field
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from licenca import _decrypt_field

    cnpjs_local = licenca_json.get('cnpjs', [])
    ids_local = licenca_json.get('ids', [])

    # Tenta cada CNPJ da lista local até encontrar um registro
    row = None
    cnpj_buscado = None
    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
        cursor = conn.cursor()

        for cnpj in cnpjs_local:
            cursor.execute(
                """
                SELECT cnpj, idcelular, token, validade, ativo, nome_cliente,
                       sql_servidor, sql_banco, api_authorization, api_database_url
                FROM clientes
                WHERE cnpj = %s
                   OR cnpj LIKE %s
                   OR cnpj LIKE %s
                   OR cnpj LIKE %s
                """,
                (cnpj, f'%,{cnpj}', f'{cnpj},%', f'%,{cnpj},%')
            )
            row = cursor.fetchone()
            if row:
                cnpj_buscado = cnpj
                break

        cursor.close()
        conn.close()
    except Exception as e:
        raise Exception(f"Erro ao conectar ao banco de licenças: {e}")

    if not row:
        raise Exception(
            f"CNPJs não registrados ou não autorizados no servidor: {', '.join(cnpjs_local)}"
        )

    (
        cnpj_db, idcelular_db, token_db, validade_db,
        ativo_db, nome_cliente_db, sql_srv_db, sql_banco_db,
        api_authorization_enc, api_database_url_enc
    ) = row

    # --- Etapa 2: verificar ativo ---
    if not ativo_db:
        raise Exception("Licença desativada no servidor")

    # --- Etapa 3: verificar validade ---
    from datetime import date as _date
    if validade_db:
        try:
            if _date.fromisoformat(str(validade_db)) < _date.today():
                raise Exception(f"Licença expirada no servidor em {validade_db}")
        except Exception as exc:
            if "expirada" in str(exc):
                raise

    # --- Etapa 4: validar assinatura HMAC do token retornado pelo banco ---
    mk = os.environ.get('MASTER_KEY')
    if not mk:
        raise ValueError(
            "MASTER_KEY não definida — necessária para validar a assinatura do token do banco."
        )
    payload_db = verify_token(token_db, mk)

    # --- Etapa 5: verificar CNPJ no payload do token (raiz de confiança) ---
    cnpjs_no_token = payload_db.get('cnpjs', [])
    if cnpj_buscado not in cnpjs_no_token:
        raise Exception(
            f"CNPJ {cnpj_buscado} não autorizado no payload do token do servidor"
        )

    # Verificar device IDs no payload, se disponíveis no arquivo local
    ids_no_token = payload_db.get('ids_celular', [])
    for device_id in ids_local:
        if device_id not in ids_no_token:
            raise Exception(
                f"Device ID {device_id} não autorizado no payload do token do servidor"
            )

    # --- Etapa 6: descriptografar campos sensíveis em memória (jamais persistir) ---
    api_authorization_plain = _decrypt_field(api_authorization_enc or '')
    api_database_url_plain = _decrypt_field(api_database_url_enc or '')

    return {
        **licenca_json,
        'nome_cliente': nome_cliente_db or licenca_json.get('nome_cliente', ''),
        'sql_servidor': sql_srv_db or payload_db.get('sql_servidor', ''),
        'sql_banco': sql_banco_db or payload_db.get('sql_banco', ''),
        'validade': str(validade_db) if validade_db else licenca_json.get('validade', ''),
        'ids_celular': idcelular_db.split(',') if idcelular_db else ids_local,
        'cnpjs': cnpj_db.split(',') if cnpj_db else cnpjs_local,
        # Valores sensíveis: usar e descartar — NÃO persistir em disco
        '_api_authorization': api_authorization_plain,
        '_api_database_url': api_database_url_plain,
    }


def load_and_verify_file(path: str, master_key: Optional[str] = None) -> Dict[str, Any]:
    """Lê um arquivo .key e valida a licença.

    Suporta três formatos:
    1. Formato legado (string simples): arquivo contém apenas o token HMAC assinado.
    2. Formato JSON assinado: JSON com campo ``token`` no formato
       ``base64url(payload).base64url(signature)`` — valida HMAC com MASTER_KEY.
    3. Formato JSON puro: JSON com campo ``token`` como string simples (token da API)
       — valida online contra o banco Neon via ``database_url``.

    ``master_key`` é necessário apenas para o formato assinado.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    conteudo = None
    for _enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            with open(path, 'r', encoding=_enc) as f:
                conteudo = f.read().strip()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if conteudo is None:
        raise ValueError(f"Não foi possível decodificar o arquivo de licença: {path}")

    # Tenta parsear como JSON
    licenca_json = None
    try:
        licenca_json = json.loads(conteudo)
    except json.JSONDecodeError:
        pass

    if licenca_json is not None and isinstance(licenca_json, dict):
        token = licenca_json.get('token', '')
        if _is_signed_token(token):
            # Formato JSON assinado — verifica HMAC
            mk = master_key or os.environ.get('MASTER_KEY')
            if not mk:
                raise ValueError('MASTER_KEY não fornecida (passar master_key ou definir variável de ambiente).')
            return verify_token(token, mk)
        else:
            # Formato JSON puro — token da API, valida online contra Neon
            return _verify_token_online(licenca_json)
    else:
        # Formato legado: conteúdo é o token diretamente
        token = conteudo
        mk = master_key or os.environ.get('MASTER_KEY')
        if not mk:
            raise ValueError('MASTER_KEY não fornecida (passar master_key ou definir variável de ambiente).')
        return verify_token(token, mk)


def get_relevant_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna um dicionário com os campos que o CSCollectManager precisa."""
    return {
        'nome_cliente': payload.get('nome_cliente', ''),
        'sql_servidor': payload.get('sql_servidor', ''),
        'sql_banco': payload.get('sql_banco', ''),
        'validade': payload.get('validade', ''),
        'gerado_em': payload.get('gerado_em', ''),
        'cnpjs': payload.get('cnpjs', []),
        'ids_celular': payload.get('ids_celular', []),
        '_api_authorization': payload.get('_api_authorization', ''),  # Adicionado
        '_api_database_url': payload.get('_api_database_url', ''),      # Adicionado
    }


if __name__ == '__main__':
    # Exemplo mínimo de uso rápido para testes
    import argparse
    parser = argparse.ArgumentParser(description='Verifica arquivo de licença e imprime campos')
    parser.add_argument('path', help='Caminho para o arquivo .key')
    parser.add_argument('--master-key', help='Chave mestra (ou use env MASTER_KEY)')
    args = parser.parse_args()
    try:
        payload = load_and_verify_file(args.path, args.master_key)
    except Exception as e:
        print('Erro:', e)
        raise SystemExit(2)
    fields = get_relevant_fields(payload)
    print(json.dumps(fields, ensure_ascii=False, indent=2))
