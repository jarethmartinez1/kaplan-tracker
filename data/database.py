from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from config.settings import DATABASE_PATH, DATABASE_URL, DB_SIZE_WARN_MB
from data.models import Base


def get_engine(db_path=None):
    """Create a SQLAlchemy engine.

    Uses DATABASE_URL (Postgres/Supabase) when set, otherwise falls back
    to a local SQLite file.
    """
    if DATABASE_URL:
        url = DATABASE_URL
        # Supabase sometimes provides 'postgres://' which SQLAlchemy 2.x
        # requires as 'postgresql://'
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(url, echo=False, pool_pre_ping=True)
    else:
        path = db_path or DATABASE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}", echo=False)

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine=None):
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    engine = engine or get_engine()
    return sessionmaker(bind=engine)()


def check_db_size(engine) -> dict:
    """Check Postgres database size. Returns dict with size_mb and warning flag.

    Only works with Postgres (Supabase). Returns None for SQLite.
    """
    if not DATABASE_URL:
        return None

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT pg_database_size(current_database())")
            )
            size_bytes = result.scalar()
            size_mb = round(size_bytes / (1024 * 1024), 1)
            return {
                "size_mb": size_mb,
                "limit_mb": 500,
                "warn": size_mb >= DB_SIZE_WARN_MB,
            }
    except Exception:
        return None
