from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session

from app.models.base import engine


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


