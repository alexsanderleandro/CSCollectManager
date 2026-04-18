"""
license_validator.py
====================
Módulo de validação de licença para CSCollectManager.

Suporta o novo formato JSON (.key) com validação offline (token HMAC-SHA256)
e validação online (PostgreSQL) conforme especificado no orientacao.md.

Formato do arquivo .key:
{
  "cnpjs": ["12345678000199", "98765432000188"],
  "ids": ["a3e9e3a0a4659652", "device-123"],
  "token": "base64url(payload).base64url(signature)",
  "validade": "2026-12-31" ou null,
  "database_url": "postgresql://user:pass@host:port/db" ou null
}

Uso:
    from services.license_validator import validar_licenca_completa
    
    resultado = validar_licenca_completa(
        caminho_key="licenca.key",
        cnpj_atual="12345678000199",
        device_id_atual="a3e9e3a0a4659652",
        validar_online=True
    )
"""

from __future__ import annotations

import os
import json
import hmac
import hashlib
import secrets
from datetime import datetime, date
from typing import Dict, Any, Optional
import logging

# Configuração de logging
logger = logging.getLogger(__name__)


# Carrega MASTER_KEY da variável de ambiente
try:
    from dotenv import load_dotenv
    import sys
    
    if getattr(sys, 'frozen', False):
        # Executável congelado pelo PyInstaller
        _meipass_env = os.path.join(sys._MEIPASS, '.env')
        if os.path.isfile(_meipass_env):
            load_dotenv(_meipass_env)
        _exe_env = os.path.join(os.path.dirname(sys.executable), '.env')
        if os.path.isfile(_exe_env):
            load_dotenv(_exe_env, override=False)
    else:
        load_dotenv()
except Exception:
    pass

MASTER_KEY = os.environ.get("MASTER_KEY")
if MASTER_KEY is None:
    raise RuntimeError(
        "Variável de ambiente MASTER_KEY não definida. "
        "Defina-a ou instale python-dotenv e crie um arquivo .env com MASTER_KEY."
    )
MASTER_KEY_BYTES = MASTER_KEY.encode("utf-8")


def _b64u_decode(s: str) -> bytes:
    """Decodifica uma string base64 URL-safe possivelmente sem padding."""
    padding = '=' * (-len(s) % 4)
    return __import__('base64').urlsafe_b64decode((s + padding).encode('ascii'))


# =============================
# 1. Carregamento do Arquivo
# =============================

def carregar_licenca(caminho_key: str) -> Dict[str, Any]:
    """
    Carrega e parseia o arquivo .key no formato JSON.
    
    Args:
        caminho_key: Caminho para o arquivo de licença (.key)
        
    Returns:
        Dicionário com os dados da licença
        
    Raises:
        FileNotFoundError: Se o arquivo não existir
        json.JSONDecodeError: Se o arquivo não for JSON válido
        ValueError: Se faltar campos obrigatórios
    """
    try:
        with open(caminho_key, 'r', encoding='utf-8') as f:
            licenca = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo de licença não encontrado: {caminho_key}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Arquivo de licença corrompido ou formato inválido: {e.msg}",
            e.doc, e.pos
        )
    
    # Valida campos obrigatórios
    campos_obrigatorios = ['cnpjs', 'ids', 'token']
    for campo in campos_obrigatorios:
        if campo not in licenca:
            raise ValueError(f"Campo obrigatório ausente no arquivo de licença: {campo}")
    
    return licenca


# =============================
# 2. Validação do Token (Offline)
# =============================

def validar_token(token: str) -> Dict[str, Any]:
    """
    Valida a assinatura HMAC-SHA256 do token e retorna o payload decodificado.
    
    O token deve estar no formato: base64url(payload).base64url(signature)
    
    Args:
        token: Token assinado
        
    Returns:
        Payload decodificado (dict)
        
    Raises:
        ValueError: Se o formato for inválido ou assinatura incorreta
    """
    try:
        # Token formato: base64url(payload).base64url(signature)
        partes = token.split('.')
        if len(partes) != 2:
            raise ValueError("Formato de token inválido (esperado payload.signature)")
        
        payload_b64, assinatura_b64 = partes
        
        # Decodifica payload e assinatura
        payload_bytes = _b64u_decode(payload_b64)
        assinatura_recebida = _b64u_decode(assinatura_b64)
        
        # Calcula assinatura esperada HMAC-SHA256
        # IMPORTANTE: Assina os bytes do JSON, não a string base64
        assinatura_esperada = hmac.new(
            MASTER_KEY_BYTES,
            payload_bytes,  # Assina os bytes do payload decodificado
            hashlib.sha256
        ).digest()
        
        # Compara assinaturas (proteção contra timing attack)
        if not secrets.compare_digest(assinatura_esperada, assinatura_recebida):
            raise ValueError("Assinatura inválida - token foi adulterado")
        
        # Decodifica payload (base64url -> JSON)
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        return payload
        
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise ValueError(f"Falha ao validar token: {e}")


# =============================
# 3. Validação Completa Offline
# =============================

def validar_licenca_offline(
    licenca: Dict[str, Any],
    cnpj_atual: str,
    device_id_atual: str = None,
    validar_device_id: bool = False
) -> Dict[str, Any]:
    """
    Valida licença completa offline: token, CNPJ, device ID (opcional) e validade.
    
    Args:
        licenca: Dicionário com dados da licença
        cnpj_atual: CNPJ da empresa atual (apenas dígitos)
        device_id_atual: ID do dispositivo atual (opcional)
        validar_device_id: Se True, valida também o device ID
        
    Returns:
        Dicionário com informações da validação:
        {
            'valida': True,
            'payload': {...},
            'nome_cliente': '...',
            'sql_servidor': '...',
            'sql_banco': '...',
            'validade': '...'
        }
        
    Raises:
        ValueError: Se a validação falhar
    """
    # 1. Valida o token e obtém o payload
    payload = validar_token(licenca['token'])
    
    # 2. Verifica CNPJ (OBRIGATÓRIO)
    cnpjs_autorizados = licenca.get('cnpjs', [])
    if cnpj_atual not in cnpjs_autorizados:
        raise ValueError(f"CNPJ {cnpj_atual} não autorizado nesta licença")
    
    # 3. Verifica Device ID (OPCIONAL - apenas se solicitado)
    if validar_device_id and device_id_atual:
        ids_autorizados = licenca.get('ids', [])
        if device_id_atual not in ids_autorizados:
            raise ValueError(f"Device ID {device_id_atual} não autorizado nesta licença")
    
    # 4. Verifica validade
    validade = licenca.get('validade')
    if validade:  # Se tiver validade definida
        try:
            data_validade = date.fromisoformat(validade)
            if date.today() > data_validade:
                raise ValueError(f"Licença expirada em {validade}")
        except ValueError as e:
            if "expirada" in str(e):
                raise
            raise ValueError(f"Formato de validade inválido: {validade}")
    
    # 5. Verifica consistência: payload do token deve corresponder ao arquivo
    if payload.get('cnpjs') != cnpjs_autorizados:
        raise ValueError("Inconsistência detectada: CNPJs no token diferem do arquivo")
    
    # Verifica consistência de IDs apenas se validação de device estiver ativa
    if validar_device_id:
        ids_autorizados = licenca.get('ids', [])
        if payload.get('ids_celular') != ids_autorizados:
            raise ValueError("Inconsistência detectada: IDs no token diferem do arquivo")
    
    # Retorna informações da licença
    return {
        'valida': True,
        'payload': payload,
        'nome_cliente': payload.get('nome_cliente'),
        'sql_servidor': payload.get('sql_servidor'),
        'sql_banco': payload.get('sql_banco'),
        'validade': validade,
        'gerado_em': payload.get('gerado_em')
    }


# =============================
# 4. Validação Online (Database)
# =============================

def validar_licenca_online(
    licenca: Dict[str, Any],
    cnpj_atual: str,
    device_id_atual: str
) -> Dict[str, Any]:
    """
    Valida licença consultando o banco de dados PostgreSQL online.
    
    Args:
        licenca: Dicionário com dados da licença (deve conter database_url)
        cnpj_atual: CNPJ da empresa atual
        device_id_atual: ID do dispositivo atual
        
    Returns:
        Dicionário com informações da validação online:
        {
            'valida': True,
            'nome_cliente': '...',
            'validade': '...',
            'ativo': True
        }
        
    Raises:
        ValueError: Se database_url não estiver presente
        Exception: Se a validação online falhar
    """
    # 1. Obtém a connection string
    database_url = licenca.get('database_url')
    
    if not database_url:
        raise ValueError("Licença não contém database_url para validação online")
    
    # 2. Importa psycopg2 (pode não estar instalado)
    try:
        import psycopg2
        from psycopg2 import extras
    except ImportError:
        raise ImportError(
            "psycopg2 não instalado. Execute: pip install psycopg2-binary"
        )
    
    # 3. Conecta ao banco
    try:
        conn = psycopg2.connect(database_url, connect_timeout=10)
        cursor = conn.cursor()
        
        # 4. Busca registro pela combinação de CNPJs
        cnpjs_str = ','.join(sorted(licenca['cnpjs']))  # Ordena para consistência
        
        query = """
            SELECT cnpj, idcelular, token, validade, ativo, nome_cliente 
            FROM clientes 
            WHERE cnpj = %s
        """
        cursor.execute(query, (cnpjs_str,))
        resultado = cursor.fetchone()
        
        if not resultado:
            raise Exception("Licença não encontrada no banco de dados")
        
        cnpj_db, idcelular_db, token_db, validade_db, ativo_db, nome_cliente_db = resultado
        
        # 5. Verifica se está ativa
        if not ativo_db:
            raise Exception("Licença desativada no servidor")
        
        # 6. Verifica se o token corresponde
        if token_db != licenca['token']:
            raise Exception("Token não corresponde ao registrado no servidor")
        
        # 7. Verifica CNPJ específico (dentro da lista)
        cnpjs_db_list = cnpj_db.split(',')
        if cnpj_atual not in cnpjs_db_list:
            raise Exception(f"CNPJ {cnpj_atual} não autorizado no servidor")
        
        # 8. Verifica Device ID
        ids_db_list = idcelular_db.split(',') if idcelular_db else []
        if device_id_atual not in ids_db_list:
            raise Exception(f"Device ID {device_id_atual} não autorizado no servidor")
        
        # 9. Verifica validade
        if validade_db:
            data_validade = date.fromisoformat(validade_db)
            if date.today() > data_validade:
                raise Exception(f"Licença expirada no servidor em {validade_db}")
        
        cursor.close()
        conn.close()
        
        return {
            'valida': True,
            'nome_cliente': nome_cliente_db,
            'validade': validade_db,
            'ativo': ativo_db
        }
        
    except Exception as e:
        if 'psycopg2' in str(type(e).__module__):
            raise Exception(f"Erro ao conectar ao banco de dados: {e}")
        raise


# =============================
# 5. Validação Híbrida (Recomendada)
# =============================

def validar_licenca_completa(
    caminho_key: str,
    cnpj_atual: str,
    device_id_atual: str = None,
    validar_online: bool = True,
    obrigar_online: bool = False,
    validar_device_id: bool = False
) -> Dict[str, Any]:
    """
    Valida licença com estratégia híbrida (offline + online).
    
    Fluxo:
    1. Sempre valida offline (token, CNPJ, opcionalmente device, validade)
    2. Se validar_online=True e database_url disponível, valida também no servidor
    3. Se obrigar_online=True, falha se validação online não for possível
    
    Args:
        caminho_key: Caminho para o arquivo .key
        cnpj_atual: CNPJ da empresa atual (apenas dígitos)
        device_id_atual: ID do dispositivo atual (opcional)
        validar_online: Se True, tenta validação online (padrão: True)
        obrigar_online: Se True, exige validação online (padrão: False)
        validar_device_id: Se True, valida também device ID (padrão: False)
        
    Returns:
        Dicionário com informações completas da validação
        
    Raises:
        FileNotFoundError: Se arquivo não existir
        ValueError: Se validação offline falhar
        Exception: Se obrigar_online=True e validação online falhar
    """
    # Carrega licença
    licenca = carregar_licenca(caminho_key)
    
    # Validação offline (obrigatória)
    try:
        resultado_offline = validar_licenca_offline(
            licenca, 
            cnpj_atual, 
            device_id_atual, 
            validar_device_id
        )
        logger.info("✓ Validação offline: OK")
    except ValueError as e:
        logger.error(f"✗ Validação offline falhou: {e}")
        raise ValueError(f"Validação offline falhou: {e}")
    
    # Prepara resultado
    resultado = {
        **resultado_offline,
        'validacao_online': False,
        'validacao_online_erro': None
    }
    
    # Validação online (opcional ou obrigatória)
    if validar_online and licenca.get('database_url'):
        try:
            info_online = validar_licenca_online(licenca, cnpj_atual, device_id_atual)
            logger.info(f"✓ Validação online: OK - Cliente: {info_online['nome_cliente']}")
            
            # Atualiza resultado com dados online
            resultado.update({
                'validacao_online': True,
                'nome_cliente': info_online.get('nome_cliente', resultado.get('nome_cliente')),
                'ativo_servidor': info_online.get('ativo', True)
            })
            
        except Exception as e:
            erro_msg = str(e)
            logger.warning(f"⚠ Validação online falhou: {erro_msg}")
            resultado['validacao_online_erro'] = erro_msg
            
            if obrigar_online:
                raise Exception(f"Validação online obrigatória falhou: {erro_msg}")
            else:
                logger.info("  Prosseguindo com validação offline...")
    
    elif validar_online and not licenca.get('database_url'):
        logger.info("ℹ database_url não disponível - validação online ignorada")
    
    return resultado


# =============================
# 6. Utilitário: Obter Device ID
# =============================

def obter_device_id() -> str:
    """
    Obtém o ID do dispositivo atual.
    
    Returns:
        String com o ID do dispositivo (baseado em hardware/MAC)
    """
    import uuid
    
    # Tenta obter MAC address como ID do dispositivo
    try:
        mac = uuid.getnode()
        device_id = hex(mac)[2:].zfill(16)  # Remove '0x' e preenche com zeros
        return device_id
    except Exception:
        # Fallback: gera um ID baseado no hostname
        import socket
        hostname = socket.gethostname()
        return hashlib.sha256(hostname.encode()).hexdigest()[:16]


# =============================
# 7. Exemplo de Uso
# =============================

if __name__ == "__main__":
    # Configuração de logging para teste
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Exemplo de uso
    try:
        resultado = validar_licenca_completa(
            caminho_key="licenca.key",
            cnpj_atual="12345678000199",  # Substituir pelo CNPJ real
            device_id_atual=obter_device_id(),
            validar_online=True,
            obrigar_online=False  # Não obriga validação online
        )
        
        print("\n✅ LICENÇA VÁLIDA")
        print(f"   Cliente: {resultado.get('nome_cliente', 'N/A')}")
        print(f"   Servidor SQL: {resultado.get('sql_servidor', 'N/A')}")
        print(f"   Banco: {resultado.get('sql_banco', 'N/A')}")
        print(f"   Validade: {resultado.get('validade', 'Sem validade')}")
        print(f"   Validação Online: {'Sim' if resultado.get('validacao_online') else 'Não'}")
        
    except Exception as e:
        print(f"\n❌ LICENÇA INVÁLIDA: {e}")
        exit(1)
