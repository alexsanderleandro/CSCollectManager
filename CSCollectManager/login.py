"""
login.py
========
Leitura padronizada de conexões (cslogin.xml) + persistência de seleção padrão,
último login e última empresa selecionada.

Este módulo apenas:
- Descobre/abre cslogin.xml (em paths padrão ou fornecido).
- Retorna lista de configurações (servidor/banco/tipo).
- Persiste seleção padrão e último login em JSON (padrão C:\\CEOSoftware\\login.json).

Uso rápido:
    from login import read_connections, choose_initial_connection, choose_initial_company
"""

from __future__ import annotations

import os
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple


# -----------------------------
# Paths padrão
# -----------------------------

DEFAULT_PATHS = [
    os.path.join(os.getcwd(), "cslogin.xml"),
    os.path.join(os.path.dirname(__file__), "cslogin.xml"),
    r"C:\ceosoftware\cslogin.xml",
]

DEFAULT_PREF_PATH = os.path.join(r"C:\CEOSoftware", "login.json")


@dataclass(frozen=True)
class ConnectionEntry:
    login_id: str = ""
    tipo_banco: str = ""      # ex.: "MSSQL"
    servidor: str = ""
    banco: str = ""
    codempresa: str = ""      # empresa selecionada (opcional)
    nomeempresa: str = ""     # empresa selecionada (opcional)
    ultimo_usuario: str = ""

    @staticmethod
    def from_dict(d: Dict[str, str]) -> "ConnectionEntry":
        return ConnectionEntry(
            login_id=d.get("LoginID", "") or d.get("login_id", "") or "",
            tipo_banco=d.get("TipoBanco", "") or d.get("tipo_banco", "") or "",
            servidor=d.get("NomeServidor", "") or d.get("servidor", "") or "",
            banco=d.get("NomeBanco", "") or d.get("banco", "") or "",
            codempresa=d.get("CodEmpresa", "") or d.get("codempresa", "") or "",
            nomeempresa=d.get("NomeEmpresa", "") or d.get("nomeempresa", "") or "",
            ultimo_usuario=d.get("UltimoUsuario", "") or d.get("ultimo_usuario", "") or "",
        )


def get_cslogin_path(provided: Optional[str] = None) -> Optional[str]:
    """Retorna o path do cslogin.xml ou None se não encontrado."""
    if provided and os.path.exists(provided):
        return provided
    for p in DEFAULT_PATHS:
        if p and os.path.exists(p):
            return p
    return None


def read_cslogin(path: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Lê cslogin.xml e retorna uma lista de dicts com chaves:
      'LoginID','TipoBanco','NomeServidor','NomeBanco','UltimoUsuario' (quando existirem).
    Se não achar arquivo ou erro de parse, retorna lista vazia.
    """
    p = get_cslogin_path(path)
    if not p:
        return []
    try:
        tree = ET.parse(p)
        root = tree.getroot()
    except Exception:
        return []

    out: List[Dict[str, str]] = []
    for conf in root.findall(".//Configuracao"):
        try:
            entry: Dict[str, str] = {}
            entry["LoginID"] = conf.attrib.get("LoginID", "") or ""
            for child in conf:
                tag = (child.tag or "").strip()
                entry[tag] = (child.text or "").strip()
            out.append(entry)
        except Exception:
            continue
    return out


def read_connections(path: Optional[str] = None) -> List[ConnectionEntry]:
    """Versão tipada: retorna lista de ConnectionEntry."""
    return [ConnectionEntry.from_dict(d) for d in read_cslogin(path)]


# -----------------------------
# Persistência de preferências
# -----------------------------

def _load_json(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_json(path: str, data: Dict) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_default_connection(pref_path: str = DEFAULT_PREF_PATH) -> Optional[Dict[str, str]]:
    """Retorna {"tipo","srv","db","codempresa","nomeempresa"} ou None."""
    data = _load_json(pref_path)
    val = data.get("default_connection")
    if isinstance(val, dict):
        return {
            "tipo": val.get("tipo", ""),
            "srv": val.get("srv", ""),
            "db": val.get("db", ""),
            "codempresa": val.get("codempresa", ""),
            "nomeempresa": val.get("nomeempresa", ""),
        }
    return None


def save_default_connection(
    tipo: str,
    srv: str,
    db: str,
    codempresa: str = "",
    nomeempresa: str = "",
    pref_path: str = DEFAULT_PREF_PATH,
) -> bool:
    """Salva {"tipo","srv","db","codempresa","nomeempresa"} em default_connection."""
    data = _load_json(pref_path)
    data["default_connection"] = {
        "tipo": tipo,
        "srv": srv,
        "db": db,
        "codempresa": codempresa,
        "nomeempresa": nomeempresa,
    }
    return _save_json(pref_path, data)


def load_last_login(pref_path: str = DEFAULT_PREF_PATH) -> Optional[Dict[str, str]]:
    """Retorna {"user","srv","db","codempresa","nomeempresa"} ou None."""
    data = _load_json(pref_path)
    val = data.get("last_login")
    if isinstance(val, dict):
        return {
            "user": val.get("user", ""),
            "srv": val.get("srv", ""),
            "db": val.get("db", ""),
            "codempresa": val.get("codempresa", ""),
            "nomeempresa": val.get("nomeempresa", ""),
        }

    # fallback: tenta pegar user do default_connection.user (backward compatibility)
    dc = data.get("default_connection")
    if isinstance(dc, dict):
        user = dc.get("user", "")
        srv = dc.get("srv", "")
        db = dc.get("db", "")
        codempresa = dc.get("codempresa", "")
        nomeempresa = dc.get("nomeempresa", "")
        if user or srv or db or codempresa or nomeempresa:
            return {
                "user": user or "",
                "srv": srv or "",
                "db": db or "",
                "codempresa": codempresa or "",
                "nomeempresa": nomeempresa or "",
            }
    return None


def save_last_login(
    user: str,
    srv: str = "",
    db: str = "",
    codempresa: str = "",
    nomeempresa: str = "",
    pref_path: str = DEFAULT_PREF_PATH,
) -> bool:
    """
    Salva last_login e, por compatibilidade, também atualiza default_connection.user e empresa.
    """
    data = _load_json(pref_path)
    data["last_login"] = {
        "user": user,
        "srv": srv,
        "db": db,
        "codempresa": codempresa,
        "nomeempresa": nomeempresa,
    }

    # compatibilidade: manter 'user' também em default_connection
    dc = data.get("default_connection")
    if not isinstance(dc, dict):
        dc = {}
    if srv:
        dc["srv"] = srv
    if db:
        dc["db"] = db
    if codempresa:
        dc["codempresa"] = codempresa
    if nomeempresa:
        dc["nomeempresa"] = nomeempresa
    dc["user"] = user
    data["default_connection"] = dc

    return _save_json(pref_path, data)


# -----------------------------
# Helpers para UI
# -----------------------------

def choose_initial_connection(
    cslogin_path: Optional[str] = None,
    pref_path: str = DEFAULT_PREF_PATH,
) -> Tuple[Optional[ConnectionEntry], List[ConnectionEntry]]:
    """
    Retorna (selecionada, todas).

    Estratégia:
      1) lê conexões do cslogin.xml
      2) tenta casar com default_connection (tipo/srv/db)
      3) se não achar, retorna a primeira conexão (se existir)
    """
    conns = read_connections(cslogin_path)
    if not conns:
        return None, []

    dc = load_default_connection(pref_path=pref_path)
    if dc:
        for c in conns:
            if (c.tipo_banco or "").strip() == (dc.get("tipo", "") or "").strip() and \
               (c.servidor or "").strip() == (dc.get("srv", "") or "").strip() and \
               (c.banco or "").strip() == (dc.get("db", "") or "").strip():
                return c, conns

    return conns[0], conns


def choose_initial_company(
    companies: list[tuple[str, str]],
    pref_path: str = DEFAULT_PREF_PATH,
    fallback_first: bool = True,
) -> tuple[str, str] | None:
    """
    Escolhe automaticamente a empresa inicial para a UI (ListBox/Combo).

    companies: lista [(codempresa, nomeempresa), ...] (ex.: vindo de authentication.list_companies)

    Estratégia:
      1) tenta usar codempresa salvo em default_connection (login.json)
      2) se não encontrar e fallback_first=True, usa a primeira da lista
    """
    if not companies:
        return None

    dc = load_default_connection(pref_path=pref_path)
    if dc:
        cod_pref = (dc.get("codempresa") or "").strip()
        if cod_pref:
            for cod, nome in companies:
                if str(cod).strip() == cod_pref:
                    return (str(cod).strip(), str(nome).strip())

    return companies[0] if fallback_first else None
