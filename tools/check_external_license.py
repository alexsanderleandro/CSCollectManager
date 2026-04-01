"""Verifica um arquivo de licença externo usando o verificador interno.

Uso: python tools/check_external_license.py <caminho_para_key>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import os
os.environ.setdefault('PYTHONPATH', str(ROOT))

def main():
    if len(sys.argv) < 2:
        print('Uso: python tools/check_external_license.py <arquivo.key>')
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print('Arquivo não encontrado:', path)
        return 2

    try:
        import cscollectmanager_verify
        from utils.master_key import load_master_key, get_master_key_str
    except Exception as e:
        print('Erro ao importar módulos:', e)
        return 3

    mk, src = load_master_key()
    print('MASTER_KEY source:', src)
    print('MASTER_KEY (preview):', (mk[:6] + '...') if isinstance(mk, str) else (str(mk)[:6] + '...'))

    try:
        # try with master key if available, else let verifier use env
        if mk is not None:
            payload = cscollectmanager_verify.load_and_verify_file(str(path), mk)
        else:
            payload = cscollectmanager_verify.load_and_verify_file(str(path))
        print('Licença válida. Payload:')
        import json
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print('Falha ao verificar licença:', type(e).__name__, e)
        return 4

if __name__ == '__main__':
    raise SystemExit(main())
