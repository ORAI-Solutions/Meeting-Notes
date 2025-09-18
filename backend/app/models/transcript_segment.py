from __future__ import annotations

from typing import Optional
from sqlmodel import SQLModel, Field


class TranscriptSegment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: int = Field(index=True, foreign_key="meeting.id")
    t_start_ms: int = Field(index=True)
    t_end_ms: int
    speaker: str  # "You" | "Remote" | other
    text: str
    confidence: Optional[float] = None


