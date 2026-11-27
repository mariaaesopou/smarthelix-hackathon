"""Postgres access for the pipeline's own bookkeeping (runs, batches, pointers).

Spark moves the bulk data over JDBC; this module is for the small control-plane
SQL that needs real transactions, which Spark's JDBC writer cannot do.
"""

import os

import psycopg

from .errors import PermanentError, RetryableError


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise PermanentError("DATABASE_URL is not set")  # configuration never fixes itself
    return url


def connect() -> psycopg.Connection:
    try:
        # autocommit: every transaction is then an explicit `with conn.transaction()` block, which
        # is a real BEGIN/COMMIT. Without it, a stray SELECT opens an implicit transaction and the
        # block becomes a mere savepoint inside it, which is rolled back when the connection closes.
        return psycopg.connect(database_url(), autocommit=True)
    except psycopg.OperationalError as exc:
        # Database restarting, network blip: the next attempt may well work.
        raise RetryableError(f"database unreachable: {exc}") from exc
