from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from config.settings import DATABASE_PATH
from data.models import Base


def get_engine(db_path=None):
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
