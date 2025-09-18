from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Meeting(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="Untitled Meeting")
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    ended_at: Optional[datetime] = None
    language: Optional[str] = None
    devices_used: Optional[str] = None  # JSON string
    status: str = Field(default="recording")  # recording|processing|done


