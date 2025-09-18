from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Summary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: int = Field(index=True, foreign_key="meeting.id")
    abstract_md: str
    bullets_md: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


