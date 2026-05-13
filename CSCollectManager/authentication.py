"""
authentication.py
=================
Módulo padronizado para conexão e autenticação em SQL Server (pyodbc).

Objetivos:
- Conexão centralizada e reutilizável (Windows Authentication / SQL Authentication).
- Seleção dinâmica de servidor/banco em tempo de execução.
- Listagem de bancos disponíveis (para telas de seleção).
- Funções de autenticação de usuário no padrão CEOSoftware (stored procedure csspValidaSenha + tabela Usuarios),
  com fallback configurável.

Requisitos:
- pip install pyodbc
- Driver ODBC instalado (ex.: "ODBC Driver 17 for SQL Server" ou "ODBC Driver 18 for SQL Server")

Uso rápido:
    from authentication import DBConfig, set_db_config, get_connection, verify_user

    set_db_config(DBConfig(server="SERVIDOR", database="BD", auth="trusted"))
    with get_connection() as conn:
        ...

    user = verify_user("usuario", "senha")
"""

from __future__ import annotations

import os
import pyodbc
from dataclasses import dataclass
from typing import Dict, Optional, Iterable, Any, List, Tuple
from contextlib import contextmanager


# -----------------------------
# Configuração
# -----------------------------

DEFAULT_DRIVER = os.getenv("MSSQL_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
DEFAULT_SERVER = os.getenv("MSSQL_SERVER", "localhost")
DEFAULT_DATABASE = os.getenv("MSSQL_DATABASE", "master")
DEFAULT_TRUST_CERT = os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes")  # útil p/ Driver 18 em ambientes internos
DEFAULT_ENCRYPT = os.getenv("MSSQL_ENCRYPT", "no")  # ajuste conforme seu ambiente


@dataclass(frozen=True)
class DBConfig:
    """
    Configuração imutável de conexão com o SQL Server.

    Attributes:
        server: Nome ou IP do servidor SQL Server.
        database: Nome do banco de dados.
        auth: Tipo de autenticação: ``"trusted"`` (Windows Auth) ou ``"sql"``.
        username: Usuário SQL (somente quando ``auth="sql"``).
        password: Senha SQL (somente quando ``auth="sql"``).
        driver: Nome do driver ODBC instalado.
        encrypt: Habilita criptografia de tráfego (``"yes"`` | ``"no"``).
        trust_server_certificate: Confiar no certificado do servidor (``"yes"`` | ``"no"``).
        timeout_seconds: Timeout de conexão em segundos.
    """
    server: str
    database: str
    auth: str = "trusted"  # "trusted" (Windows Auth) | "sql" (SQL Login)
    username: Optional[str] = None
    password: Optional[str] = None
    driver: str = DEFAULT_DRIVER
    encrypt: str = DEFAULT_ENCRYPT          # "yes" | "no"
    trust_server_certificate: str = DEFAULT_TRUST_CERT  # "yes" | "no"
    timeout_seconds: int = 10


# Config global (pode ser trocado em runtime pela UI)
_DB_CONFIG: DBConfig = DBConfig(server=DEFAULT_SERVER, database=DEFAULT_DATABASE)


def set_db_config(cfg: DBConfig) -> None:
    """Define a configuração global usada por get_connection()."""
    global _DB_CONFIG
    _DB_CONFIG = cfg


def get_db_config() -> DBConfig:
    """
    Retorna a configuração global de conexão.

    Returns:
        Instância de :class:`DBConfig` atualmente ativa.
    """
    return _DB_CONFIG


def _build_conn_str(cfg: DBConfig) -> str:
    """
    Monta connection string ODBC.
    - trusted: usa Windows Authentication (Trusted_Connection=yes)
    - sql: usa UID/PWD
    """
    base = [
        f"DRIVER={{{cfg.driver}}}",
        f"SERVER={cfg.server}",
        f"DATABASE={cfg.database}",
        f"Encrypt={cfg.encrypt}",
        f"TrustServerCertificate={cfg.trust_server_certificate}",
        f"Connection Timeout={cfg.timeout_seconds}",
    ]

    if cfg.auth.lower() == "trusted":
        base.append("Trusted_Connection=yes")
    elif cfg.auth.lower() == "sql":
        if not cfg.username or not cfg.password:
            raise ValueError("DBConfig.auth='sql' exige username e password.")
        base.append(f"UID={cfg.username}")
        base.append(f"PWD={cfg.password}")
    else:
        raise ValueError("DBConfig.auth deve ser 'trusted' ou 'sql'.")

    return ";".join(base) + ";"


@contextmanager
def get_connection(cfg: Optional[DBConfig] = None, autocommit: bool = False):
    """
    Context manager de conexão.
    Exemplo:
        with get_connection() as conn:
            cur = conn.cursor()
            ...
    """
    c = cfg or _DB_CONFIG
    conn = None
    try:
        conn = pyodbc.connect(_build_conn_str(c), autocommit=autocommit)
        yield conn
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def test_connection(cfg: Optional[DBConfig] = None) -> Tuple[bool, str]:
    """Testa conexão e retorna (ok, mensagem)."""
    try:
        with get_connection(cfg) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        return True, "Conexão OK"
    except Exception as e:
        return False, str(e)


def list_databases(
    server: Optional[str] = None,
    cfg: Optional[DBConfig] = None,
    include_system: bool = False,
) -> List[str]:
    """
    Lista bancos disponíveis no servidor via sys.databases.
    Por padrão filtra os bancos de sistema.
    Observação: requer permissão para consultar sys.databases.
    """
    base_cfg = cfg or _DB_CONFIG
    use_cfg = DBConfig(
        server=server or base_cfg.server,
        database="master",
        auth=base_cfg.auth,
        username=base_cfg.username,
        password=base_cfg.password,
        driver=base_cfg.driver,
        encrypt=base_cfg.encrypt,
        trust_server_certificate=base_cfg.trust_server_certificate,
        timeout_seconds=base_cfg.timeout_seconds,
    )
    sql = "SELECT name FROM sys.databases ORDER BY name"
    system = {"master", "model", "msdb", "tempdb"}
    out: List[str] = []
    with get_connection(use_cfg) as conn:
        cur = conn.cursor()
        cur.execute(sql)
        for (name,) in cur.fetchall():
            if not include_system and str(name).lower() in system:
                continue
            out.append(str(name))
    return out

def list_companies(
    cfg: Optional[DBConfig] = None,
    table: str = "dbo.empresas",
    cod_field: str = "codempresa",
    name_field: str = "nomeempresa",
    only_active: bool = False,
    active_field: str = "inativosn",
) -> List[Tuple[str, str]]:
    """
    Lista empresas disponíveis no banco selecionado.

    Padrão esperado:
      tabela: dbo.empresas
      campos: codempresa, nomeempresa

    Parâmetros:
      - only_active: se True, filtra empresas ativas usando active_field=0 (quando existir).
        (Se sua base não tiver esse campo, deixe False.)

    Retorna: lista de tuplas (codempresa, nomeempresa) como strings, ordenadas por nome.
    """
    c = cfg or _DB_CONFIG
    where = ""
    if only_active:
        where = f"WHERE ISNULL({active_field}, 0) = 0"

    sql = f"""
        SELECT {cod_field} AS CodEmpresa, {name_field} AS NomeEmpresa
        FROM {table} WITH (NOLOCK)
        {where}
        ORDER BY {name_field}
    """

    out: List[Tuple[str, str]] = []
    with get_connection(c) as conn:
        cur = conn.cursor()
        cur.execute(sql)
        for row in cur.fetchall():
            cod = "" if row[0] is None else str(row[0]).strip()
            nome = "" if row[1] is None else str(row[1]).strip()
            if cod or nome:
                out.append((cod, nome))
    return out



# -----------------------------
# Autenticação de usuário (padrão CEOSoftware)
# -----------------------------

def verify_user(
    username: str,
    password: str,
    cfg: Optional[DBConfig] = None,
    require_active: bool = True,
    require_manager: bool = False,
    sp_validate_password: str = "dbo.csspValidaSenha",
    user_table: str = "Usuarios",
    username_field: str = "NomeUsuario",
) -> Optional[Dict[str, Any]]:
    """
    Verifica credenciais no padrão:
      1) Executa stored procedure csspValidaSenha (username, password) -> retorna 1/True se válido
      2) Busca dados do usuário na tabela Usuarios
      3) (Opcional) Exige InativosN=0 e/ou PDVGerenteSN=1

    Retorna dict com dados do usuário em caso de sucesso, ou None em falha.

    Campos retornados (quando disponíveis):
      CodUsuario, NomeUsuario, InativosN, PDVGerenteSN
    """
    if not username:
        return None

    c = cfg or _DB_CONFIG

    with get_connection(c) as conn:
        cur = conn.cursor()

        # 1) Validação de senha via SP (parametrizado)
        try:
            cur.execute(f"EXEC {sp_validate_password} ?, ?", (username, password))
            res = cur.fetchone()
            ok = bool(res and (res[0] == 1 or res[0] is True))
        except Exception:
            ok = False

        if not ok:
            return None

        # 2) Buscar flags / dados do usuário
        # NOTA: nomes dos campos podem variar entre bases; ajuste se necessário.
        try:
            cur.execute(
                f"""
                SELECT CodUsuario, {username_field} AS NomeUsuario, InativosN, PDVGerenteSN
                FROM {user_table} WITH (NOLOCK)
                WHERE {username_field} = ?
                """,
                (username,),
            )
            row = cur.fetchone()
        except Exception:
            row = None

        if not row:
            # usuário validou na SP mas não achou registro detalhado
            return {"CodUsuario": 0, "NomeUsuario": username}

        cod = int(row[0]) if row[0] is not None else 0
        nome_usuario = str(row[1]) if row[1] is not None else ""
        inativos = int(row[2]) if row[2] is not None else 1
        gerente = int(row[3]) if row[3] is not None else 0

        if require_active and inativos != 0:
            return None
        if require_manager and gerente != 1:
            return None

        return {
            "CodUsuario": cod,
            "NomeUsuario": nome_usuario,
            "InativosN": inativos,
            "PDVGerenteSN": gerente,
        }
