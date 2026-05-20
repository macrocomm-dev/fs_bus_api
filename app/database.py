"""
SQLAlchemy database engine and session factory.

The connection string is built from settings so it works both locally
(via the Cloud SQL Auth Proxy) and inside Cloud Run.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


def _build_url(settings) -> str:
    """Build the SQLAlchemy connection URL from the current settings.

    This helper keeps all database URL rules in one place so the rest of the
    code does not need to care whether the app is talking to PostgreSQL over a
    normal TCP host/port or through the Cloud SQL Unix socket path used inside
    Google Cloud environments.
    """
    user = settings.db_user.strip()
    password = settings.db_password.strip()
    name = settings.db_name.strip()
    host = settings.db_host.strip()

    # Cloud Run + Cloud SQL commonly use a Unix socket path like
    # /cloudsql/<project>:<region>:<instance>. Build that DSN accordingly.
    if host.startswith("/cloudsql/"):
        return (
            f"postgresql+psycopg2://{user}:{quote_plus(password)}"
            f"@/{name}?host={quote_plus(host)}"
        )

    return (
        f"postgresql+psycopg2://{user}:{quote_plus(password)}"
        f"@{host}:{settings.db_port}/{name}"
    )


def get_engine():
    """Create the shared SQLAlchemy engine used by the whole application.

    The engine is the long-lived object that knows how to open database
    connections. We enable ``pool_pre_ping`` so stale connections are checked
    before use, which reduces confusing connection errors after idle periods.
    """
    settings = get_settings()
    url = _build_url(settings)
    return create_engine(url, pool_pre_ping=True)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class that all SQLAlchemy ORM models inherit from.

    SQLAlchemy uses this class to keep track of every mapped table definition.
    Defining a single shared base means models can reference each other and be
    managed by the same metadata collection.
    """
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db():
    """Yield a database session for one request and always close it afterward.

    FastAPI calls this dependency at the start of a request handler. The
    ``yield`` pattern gives the route code a session to use and guarantees the
    connection is cleaned up even if the request raises an exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
