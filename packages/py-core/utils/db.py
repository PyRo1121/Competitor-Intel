from contextlib import contextmanager

from db.connection import (
    DB_PATH,
    DEFAULT_TIMEOUT,
    get_conn,
    get_cursor,
    transaction,
)
from db.schema import init_database as _init_database


def init_database():
    return _init_database()


@contextmanager
def db_session(timeout: float = DEFAULT_TIMEOUT):
    with transaction(timeout=timeout) as conn:
        yield conn


__all__ = [
    "DB_PATH",
    "DEFAULT_TIMEOUT",
    "db_session",
    "get_conn",
    "get_cursor",
    "init_database",
    "transaction",
]
