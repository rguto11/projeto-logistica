"""Configuracao e acesso ao PostgreSQL (pool de conexoes + helpers)."""
import os
import threading
from contextlib import contextmanager, suppress

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

_pool = None
_trava = threading.Lock()


def parametros_conexao():
    senha = os.environ.get("DB_PASSWORD")
    if not senha:
        raise RuntimeError(
            "variavel de ambiente DB_PASSWORD nao definida (defina-a no docker-compose.yml ou no .env)"
        )
    return {
        "host": os.environ.get("DB_HOST", "db"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "logistica"),
        "user": os.environ.get("DB_USER", "logistica"),
        "password": senha,
        "connect_timeout": 5,
    }


def _obter_pool():
    global _pool
    if _pool is None:
        with _trava:
            if _pool is None:
                _pool = ThreadedConnectionPool(1, 10, **parametros_conexao())
    return _pool


@contextmanager
def conexao():
    """Entrega uma conexao do pool; commit ao sair, rollback em caso de erro."""
    pool = _obter_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        with suppress(psycopg2.Error):  # conexao possivelmente morta; a excecao original e a relevante
            conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def consultar(sql, params=()):
    with conexao() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def consultar_um(sql, params=()):
    linhas = consultar(sql, params)
    return linhas[0] if linhas else None


def executar_retornando(sql, params=()):
    """Executa INSERT/UPDATE ... RETURNING * e devolve a linha."""
    with conexao() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def conexao_unica():
    """Conexao direta (fora do pool), usada pelo init_db."""
    return psycopg2.connect(**parametros_conexao())
