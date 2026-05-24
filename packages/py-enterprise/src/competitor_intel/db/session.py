"""Database session management."""

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from competitor_intel.settings import get_settings

_settings = get_settings()

# Create engine with WAL mode
engine = create_engine(
    f"sqlite:///{_settings.db.path}",
    echo=_settings.db.echo,
    connect_args={
        "timeout": 30,
        "check_same_thread": False,
    },
)


# Configure WAL mode on connection
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _connection_record):
    import os

    busy_ms = os.environ.get("CI_SQLITE_BUSY_TIMEOUT_MS", "120000")
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute(f"PRAGMA busy_timeout={busy_ms}")
    cursor.execute("PRAGMA cache_size=-256000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=268435456")
    cursor.execute("PRAGMA wal_autocheckpoint=10000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session():
    """Get a database session context manager."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize database tables."""
    from competitor_intel.db.models import Base

    Base.metadata.create_all(bind=engine)
    return engine
