from __future__ import annotations

from datetime import date
from typing import Optional
from sqlmodel import SQLModel, Field


class ActionItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    meeting_id: int = Field(index=True, foreign_key="meeting.id")
    text: str
    owner: Optional[str] = None
    due_date: Optional[date] = None
    status: str = Field(default="open")  # open|done


