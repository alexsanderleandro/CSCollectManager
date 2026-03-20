import sys
sys.path.insert(0, '.')
from database.connection import get_session
from sqlalchemy import text

try:
    with get_session() as s:
        print("=== tabelas com 'lote' ===")
        r = s.execute(text(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE LOWER(TABLE_NAME) LIKE '%lote%' ORDER BY TABLE_NAME"
        ))
        tables = [row[0] for row in r]
        for t in tables:
            print(" ", t)

        for t in tables:
            print(f"\n=== colunas de {t} ===")
            r2 = s.execute(text(
                "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                f"WHERE TABLE_NAME = '{t}' ORDER BY ORDINAL_POSITION"
            ))
            for row in r2:
                print(f"  {row[0]}  ({row[1]})")
except Exception as e:
    print("ERRO:", e)
