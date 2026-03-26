"""
extrair_imagens.py
==================
Rotinas utilitárias para extrair imagens dos anexos de produtos.

Funções:
 - detectar_extensao(bytes_data)
 - exportar_imagem_produto(session, codproduto, pasta_destino=".")
 - exportar_imagens_para_pasta(codprodutos, pasta_destino)

Observações:
 - Compatível com blobs armazenados como bytes ou como string HEX ("0x...").
 - Usa consultas simples ao banco (SQL Server).
"""

import os
from typing import Optional, List

from database.connection import get_session
from sqlalchemy import text


def detectar_extensao(bytes_data: bytes) -> str:
    if not bytes_data:
        return 'bin'
    if bytes_data.startswith(b'\xff\xd8'):
        return 'jpg'
    elif bytes_data.startswith(b'\x89PNG'):
        return 'png'
    elif bytes_data.startswith(b'BM'):
        return 'bmp'
    elif bytes_data.startswith(b'GIF'):
        return 'gif'
    elif bytes_data[:4] == b'RIFF' and bytes_data[8:12] == b'WEBP':
        return 'webp'
    else:
        return 'bin'


def _normalize_filename(name: str) -> str:
    # Remove caracteres perigosos e espaços
    safe = "".join(c for c in (name or '') if (c.isalnum() or c in '-_.'))
    return safe or 'produto'


def exportar_imagem_produto(session, codproduto: str, pasta_destino: str = '.') -> Optional[str]:
    """Extrai a primeira imagem do produto e salva em `pasta_destino`.

    Retorna o caminho do arquivo salvo ou None se não houve imagem.
    """
    # 1) Buscar primeira imagem — tenta ordenar por RegInclusao se disponível, senão pega o primeiro registro.
    # Primeiramente tenta uma query ordenada por RegInclusao (coluna comum nesta base).
    res = None
    try:
        q = text(
            "SELECT TOP 1 * FROM produtosanexos WHERE CodProduto = :codproduto ORDER BY RegInclusao ASC"
        )
        res = session.execute(q, {"codproduto": codproduto}).first()
    except Exception:
        # Fallback sem ORDER BY — pega qualquer anexo existente
        try:
            q = text("SELECT TOP 1 * FROM produtosanexos WHERE CodProduto = :codproduto")
            res = session.execute(q, {"codproduto": codproduto}).first()
        except Exception:
            res = None

    if not res:
        return None

    # Identifica a coluna que contém o blob (arquivoanexo) de forma case-insensitive
    # `res` é um Row; usamos a descrição de colunas via cursor se disponível.
    # Como usamos SQLAlchemy Row, podemos acessar por posição e também por keys.
    # Procuramos por nomes comuns: 'arquivoanexo', 'ArquivoAnexo', 'ArquivoAnexo'
    blob = None
    codanexo_found = None
    try:
        # tenta acessar por chave conhecida
        if 'ArquivoAnexo' in res._mapping:
            blob = res._mapping.get('ArquivoAnexo')
        elif 'arquivoanexo' in res._mapping:
            blob = res._mapping.get('arquivoanexo')
        elif 'ArquivoAnexo'.lower() in {k.lower(): k for k in res._mapping}:
            # pega primeiro que case-insensitive corresponda
            for k in res._mapping:
                if k.lower() == 'arquivoanexo':
                    blob = res._mapping.get(k)
                    break
        else:
            # fallback para a primeira coluna que pareça blob (tipo bytes)
            for v in res:
                if isinstance(v, (bytes, bytearray)):
                    blob = v
                    break
        # tenta achar algum identificador do anexo (nome do arquivo)
        if 'NomeArquivo' in res._mapping:
            codanexo_found = res._mapping.get('NomeArquivo')
        elif 'NomeArquivo'.lower() in {k.lower(): k for k in res._mapping}:
            for k in res._mapping:
                if k.lower() == 'nomearquivo':
                    codanexo_found = res._mapping.get(k)
                    break
    except Exception:
        blob = None

    if not blob:
        return None

    # 2) Converter se vier como HEX string
    if isinstance(blob, str):
        print(f"[extrair_imagens] codproduto={codproduto} codanexo={codanexo_found} arquivoanexo is str len={len(blob)}")
        b = blob
        if b.startswith('0x') or b.startswith('0X'):
            b = b[2:]
        try:
            blob = bytes.fromhex(b)
        except Exception:
            # Não é hex válido — tenta codificar como utf-8
            try:
                blob = b.encode('utf-8')
            except Exception:
                return None

    # 3) Detectar extensão
    ext = detectar_extensao(blob)

    print(f"[extrair_imagens] codproduto={codproduto} detected ext={ext} bytes={len(blob) if blob else 0}")

    # 4) Buscar codeanunidade
    q2 = text(
        "SELECT COALESCE(codeanunidade, '') FROM produtos WHERE codproduto = :codproduto"
    )
    row2 = session.execute(q2, {"codproduto": codproduto}).first()
    if not row2 or not row2[0]:
        return None

    codeanunidade = str(row2[0])
    nome_arquivo = f"{_normalize_filename(codeanunidade)}.{ext}"
    os.makedirs(pasta_destino, exist_ok=True)
    caminho = os.path.join(pasta_destino, nome_arquivo)

    try:
        with open(caminho, 'wb') as f:
            f.write(blob)
    except Exception:
        return None

    return caminho


def exportar_imagens_para_pasta(codprodutos: List[str], pasta_destino: str = '.') -> List[str]:
    """Extrai imagens para a pasta informada. Retorna lista de caminhos salvos."""
    saved = []
    if not codprodutos:
        return saved

    with get_session() as session:
        for cod in codprodutos:
            try:
                caminho = exportar_imagem_produto(session, cod, pasta_destino)
                if caminho:
                    saved.append(caminho)
            except Exception:
                # Ignora produtos com erro e continua
                continue

    return saved
