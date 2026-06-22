"""
rthook_master_key.py
====================
Runtime hook do PyInstaller — executa ANTES de qualquer módulo da aplicação.

Lê o arquivo .env embutido em _MEIPASS (ou ao lado do .exe) e define
a variável de ambiente MASTER_KEY para que license_validator.py e demais
módulos a encontrem via os.environ.get("MASTER_KEY").
"""
import os
import sys


def _load_env_file(path: str) -> bool:
    """Lê um arquivo .env simples e seta variáveis de ambiente.
    Retorna True se MASTER_KEY foi encontrada e definida."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # remove aspas envolventes ('...' ou "...")
                if len(v) >= 2 and v[0] in ('"', "'") and v[-1] == v[0]:
                    v = v[1:-1]
                if k and v:
                    # só define se ainda não estiver no ambiente (não sobrescreve)
                    os.environ.setdefault(k, v)
        return bool(os.environ.get("MASTER_KEY"))
    except Exception:
        return False


def _inject_master_key():
    # Se já está no ambiente, não há nada a fazer
    if os.environ.get("MASTER_KEY"):
        return

    candidates = []

    if getattr(sys, "frozen", False):
        # 1) _MEIPASS  — onde o PyInstaller extrai os datas em --onefile
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, ".env"))
        # 2) pasta do executável — útil quando o usuário coloca um .env ao lado do .exe
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, ".env"))

    for path in candidates:
        if os.path.isfile(path):
            if _load_env_file(path):
                return  # MASTER_KEY definida com sucesso


_inject_master_key()
