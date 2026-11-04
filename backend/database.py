import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# SQLite is the only supported database. On Render, point SQLITE_PATH to the
# persistent disk mount (for example: /var/data/scheduler.db).
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", "./scheduler.db")).expanduser()
SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = URL.create("sqlite", database=str(SQLITE_PATH))
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
