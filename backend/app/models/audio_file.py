from __future__ import annotations

from typing import Optional
from sqlmodel import SQLModel, Field


class AudioFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: int = Field(index=True, foreign_key="meeting.id")
    kind: str  # mic|system
    path: str
    codec: str
    sample_rate: int
    duration_ms: int
    bytes: int


