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
    """Valida o token puro contra o banco Neon (database_url) e retorna o payload completo.

    Conecta à tabela `clientes`, verifica se o token está registrado e ativo,
    e monta um payload compatível com o restante do sistema a partir dos dados
    retornados pelo banco.

    Raises:
        ImportError: se psycopg2 não estiver instalado.
        ValueError: se database_url não estiver presente no arquivo.
        Exception: se a validação falhar (token inválido, expirado, inativo, etc.).
    """
    database_url = licenca_json.get('database_url')
    if not database_url:
        # Sem database_url: aceita apenas com os dados locais do arquivo
        return licenca_json

    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 não instalado. Execute: pip install psycopg2-binary")

    token = licenca_json.get('token', '')
    cnpjs_local = licenca_json.get('cnpjs', [])
    cnpjs_str = ','.join(sorted(cnpjs_local))

    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT cnpj, idcelular, token, validade, ativo, nome_cliente,
                   sql_servidor, sql_banco
            FROM clientes
            WHERE cnpj = %s
            """,
            (cnpjs_str,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as e:
        raise Exception(f"Erro ao conectar ao banco de licenças: {e}")

    if not row:
        raise Exception(f"CNPJ não registrado ou não autorizado no servidor de licenças: {cnpjs_str}")

    cnpj_db, idcelular_db, token_db, validade_db, ativo_db, nome_cliente_db, sql_srv_db, sql_banco_db = row

    if not ativo_db:
        raise Exception("Licença desativada no servidor")

    if token_db != token:
        raise Exception("Token não corresponde ao registrado no servidor")

    # Monta payload compatível com o restante do sistema
    from datetime import date as _date
    if validade_db:
        try:
            if _date.fromisoformat(str(validade_db)) < _date.today():
                raise Exception(f"Licença expirada no servidor em {validade_db}")
        except Exception as e:
            if "expirada" in str(e):
                raise

    return {
        **licenca_json,
        'nome_cliente': nome_cliente_db or licenca_json.get('nome_cliente', ''),
        'sql_servidor': sql_srv_db or licenca_json.get('sql_servidor', ''),
        'sql_banco': sql_banco_db or licenca_json.get('sql_banco', ''),
        'validade': str(validade_db) if validade_db else licenca_json.get('validade', ''),
        'ids_celular': idcelular_db.split(',') if idcelular_db else licenca_json.get('ids', []),
        'cnpjs': cnpj_db.split(',') if cnpj_db else cnpjs_local,
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
