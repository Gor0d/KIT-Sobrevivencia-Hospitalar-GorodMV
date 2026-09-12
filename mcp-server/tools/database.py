import os
from pathlib import Path

import oracledb
from dotenv import load_dotenv

# .env fica na raiz do projeto; caminho absoluto para funcionar
# mesmo quando o processo é iniciado a partir de outro diretório
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_pool: oracledb.ConnectionPool | None = None


def get_pool() -> oracledb.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            host=os.getenv("ORACLE_HOST", "localhost"),
            port=int(os.getenv("ORACLE_PORT", "1521")),
            service_name=os.getenv("ORACLE_SERVICE", "ORCL"),
            user=os.getenv("ORACLE_USER"),
            password=os.getenv("ORACLE_PASSWORD"),
            min=1,
            max=5,
            increment=1,
        )
    return _pool


def execute_query(sql: str, params: dict | None = None, max_rows: int | None = None) -> list[dict]:
    """Executa uma query somente-leitura e retorna lista de dicionários."""
    limit = max_rows or int(os.getenv("MAX_ROWS", "500"))
    timeout_ms = int(os.getenv("QUERY_TIMEOUT_MS", "30000"))
    pool = get_pool()
    with pool.acquire() as conn:
        conn.call_timeout = timeout_ms
        with conn.cursor() as cursor:
            cursor.execute(sql, params or {})
            columns = [col[0].lower() for col in cursor.description]
            rows = cursor.fetchmany(limit)
            return [dict(zip(columns, row)) for row in rows]


def get_schema() -> str:
    return os.getenv("ORACLE_SCHEMA", "DBAMV").upper()
