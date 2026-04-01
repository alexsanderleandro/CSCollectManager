"""Gerador de licença de teste (.key)

Cria um arquivo `test_license.key` na raiz do projeto. Usa a `MASTER_KEY`
procurada por `utils.master_key.load_master_key()` (env -> .env -> AppConfig file).

Uso:
    python tools/generate_test_key.py

O token gerado usa o formato esperado por `cscollectmanager_verify`:
  base64url(payload).base64url(signature)
onde `signature` é HMAC-SHA256(payload, master_key.encode('utf-8')).
"""
from __future__ import annotations

import json
import os
import base64
import hmac
import hashlib
from datetime import datetime
from pathlib import Path

from utils.master_key import load_master_key


def _b64u_no_pad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode('ascii').rstrip('=')


def main():
    mk, src = load_master_key()
    if not mk:
        print('MASTER_KEY não encontrada (setar env ou .env).')
        return 2
    if isinstance(mk, (bytes, bytearray)):
        mk_str = None
        try:
            mk_str = mk.decode('utf-8')
        except Exception:
            # fallback: use bytes directly by decoding as latin1
            mk_str = mk.decode('latin-1')
    else:
        mk_str = str(mk)

    # Payload compatível com o que o app espera
    payload = {
        "nome_cliente": "CEOSoftware",
        "sql_servidor": "CEOSOFT-SERV1",
        "sql_banco": "LOCAL",
        "validade": "2099-12-31",
        "gerado_em": datetime.utcnow().isoformat() + "Z",
        "cnpjs": ["65237752000116"],
        "ids_celular": []
    }

    dados = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    assinatura = hmac.new(mk_str.encode('utf-8'), dados, hashlib.sha256).digest()

    token = f"{_b64u_no_pad(dados)}.{_b64u_no_pad(assinatura)}"

    out_path = Path(os.getcwd()) / "test_license.key"
    out_path.write_text(token, encoding='utf-8')
    print(f'Arquivo gerado: {out_path}')
    print('Payload gerado:')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
