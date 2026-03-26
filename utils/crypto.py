"""
crypto.py
---------
Helpers para geração de assinatura HMAC-SHA256 de arquivos de carga (.db).

Chave compartilhada com o app mobile (CSCollect).
DEVE ser idêntica ao _MASTER_KEY em security/carga_sig.py do app.

API:
    - ensure_keypair(private_path, public_path)
      Mantido por compatibilidade. Grava a MASTER_KEY no arquivo indicado.

    - sign_file(private_path, file_path) -> str
      Calcula HMAC-SHA256 do conteúdo do arquivo e grava <file_path>.sig (binário).
"""
import os
import hmac
import hashlib
from pathlib import Path

# Chave compartilhada com o app mobile.
# DEVE ser idêntica à _MASTER_KEY em security/carga_sig.py do CSCollect.
_MASTER_KEY = "SUA_MASTER_KEY_SUPER_SECRETA"


def ensure_keypair(private_path: str, public_path: str) -> None:
    """Garante que o arquivo de chave contenha a MASTER_KEY correta.

    O argumento `public_path` é ignorado (mantido apenas por compatibilidade).
    Sobrescreve o arquivo se ele existir com conteúdo diferente da MASTER_KEY.
    """
    priv = Path(private_path)
    os.makedirs(priv.parent, exist_ok=True)
    key = _MASTER_KEY.encode("utf-8")
    # Sobrescreve sempre para garantir sincronismo com o app mobile
    with open(priv, "wb") as f:
        f.write(key)


def sign_file(private_path: str, file_path: str) -> str:
    """Calcula HMAC-SHA256 do `file_path` usando a MASTER_KEY compartilhada.

    Grava o resultado binário em `<file_path>.sig` e retorna o caminho.
    """
    # Usa a chave constante diretamente (ignorando o arquivo) para garantir
    # que o .sig seja sempre verificável pelo app mobile.
    key = _MASTER_KEY.encode("utf-8")

    h = hmac.new(key, digestmod=hashlib.sha256)
    # Ler arquivo em blocos para memória eficiente
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    signature = h.digest()

    sig_path = str(Path(file_path).with_suffix(Path(file_path).suffix + ".sig"))
    with open(sig_path, "wb") as f:
        f.write(signature)

    return sig_path