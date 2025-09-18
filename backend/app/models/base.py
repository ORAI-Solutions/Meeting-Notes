from __future__ import annotations

from sqlmodel import SQLModel, create_engine
from sqlalchemy.engine import Engine
from app.config import Settings

_settings = Settings()

# SQLite with WAL enabled
engine: Engine = create_engine(
    f"sqlite:///{_settings.database_path}", connect_args={"check_same_thread": False}
)


def init_db() -> None:
    # Enable WAL
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    SQLModel.metadata.create_all(engine)


