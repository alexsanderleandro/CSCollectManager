"""
master_key.py
===============
Helpers para carregar a `MASTER_KEY` usada na verificação de licenças.

Prioridade de busca:
 - variável de ambiente `MASTER_KEY`
 - arquivo `.env` (carregado via `python-dotenv` se disponível)
 - arquivo apontado por `AppConfig.get_private_key_path()` (tenta texto UTF-8, caso contrário retorna bytes)

Retorna uma tupla `(master_key, source)` onde `master_key` é `str` ou `bytes` ou `None`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, Union

try:
    # Import opcional: permite suportar .env quando instalado
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

from .config import AppConfig
import sys


MasterKeyType = Union[str, bytes]


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    return s


def load_master_key(dotenv_path: Optional[str] = None) -> Tuple[Optional[MasterKeyType], Optional[str]]:
    """Tenta carregar a `MASTER_KEY` de várias fontes.

    Args:
        dotenv_path: caminho opcional para um arquivo .env. Se None, usa comportamento padrão do python-dotenv.

    Returns:
        (master_key, source) onde `master_key` é `str` ou `bytes` ou `None` se não encontrado;
        `source` é uma string indicando onde foi encontrada ('env', '.env', 'file-text', 'file-binary').
    """
    # 1) variável de ambiente
    val = os.environ.get("MASTER_KEY")
    if val:
        val = _strip_quotes(val)
        return val, "env"

    # 2) arquivo .env via python-dotenv
    if load_dotenv is not None:
        try:
            if dotenv_path:
                load_dotenv(dotenv_path)
            else:
                load_dotenv()
            val = os.environ.get("MASTER_KEY")
            if val:
                val = _strip_quotes(val)
                return val, ".env"
        except Exception:
            # não interrompe se dotenv falhar
            pass
    else:
        # Sem python-dotenv disponível: tentar ler um arquivo .env simples em locais comuns
        try:
            # incluir locais comuns e, quando congelado, o _MEIPASS e pasta do executável
            candidates = [
                Path('.') / '.env',
                Path.cwd() / '.env',
                Path(AppConfig.BASE_DIR) / '.env',
                Path(r"C:\ceosoftware") / '.env',
            ]
            try:
                if getattr(sys, 'frozen', False):
                    meipass = getattr(sys, '_MEIPASS', None)
                    if meipass:
                        candidates.insert(0, Path(meipass) / '.env')
                    # pasta do executável
                    exe_dir = Path(sys.executable).parent
                    candidates.insert(0, exe_dir / '.env')
            except Exception:
                pass
            for cand in candidates:
                try:
                    if cand.exists():
                        text = cand.read_text(encoding='utf-8')
                        for line in text.splitlines():
                            if not line or line.strip().startswith('#'):
                                continue
                            if '=' not in line:
                                continue
                            k, v = line.split('=', 1)
                            if k.strip() == 'MASTER_KEY':
                                v = _strip_quotes(v.strip())
                                if v:
                                    return v, f".env:{str(cand)}"
                except Exception:
                    continue
        except Exception:
            pass

    # 3) arquivo de chave configurado em AppConfig
    try:
        key_path = Path(AppConfig.get_private_key_path())
        if key_path.exists():
            # tenta ler como texto UTF-8 (caso a chave seja uma string master key)
            try:
                text = key_path.read_text(encoding="utf-8").strip()
                if text:
                    text = _strip_quotes(text)
                    return text, "file-text"
            except Exception:
                # se não decodificar como texto, tenta ler como binário
                try:
                    data = key_path.read_bytes()
                    if data:
                        return data, "file-binary"
                except Exception:
                    pass
    except Exception:
        pass

    return None, None


def get_master_key_str() -> Optional[str]:
    """Retorna `MASTER_KEY` sempre como `str` quando possível (decodifica bytes com utf-8).

    Útil para APIs que esperam a chave como texto.
    """
    val, src = load_master_key()
    if isinstance(val, str):
        return val
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8")
        except Exception:
            return None
    return None
