"""Connection pool. All tables live in the `tutor` schema inside the existing database."""
from __future__ import annotations

from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

SCHEMA = "tutor"


def make_pool(database_url: str, minconn: int = 1, maxconn: int = 10) -> ThreadedConnectionPool:
    return ThreadedConnectionPool(minconn, maxconn, dsn=database_url, options=f"-c search_path={SCHEMA}")


@contextmanager
def connection(pool):
    """A connection that commits on success and rolls back on any error."""
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)
