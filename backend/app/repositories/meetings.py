from __future__ import annotations

from typing import Optional
from sqlmodel import Session, select

from app.models.meeting import Meeting


class MeetingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, meeting: Meeting) -> Meeting:
        self.session.add(meeting)
        self.session.commit()
        self.session.refresh(meeting)
        return meeting

    def get(self, meeting_id: int) -> Optional[Meeting]:
        return self.session.get(Meeting, meeting_id)

    def list(self, limit: int = 50, offset: int = 0) -> list[Meeting]:
        statement = select(Meeting).order_by(Meeting.started_at.desc()).limit(limit).offset(offset)
        return list(self.session.exec(statement))

    def update(self, meeting: Meeting) -> Meeting:
        self.session.add(meeting)
        self.session.commit()
        self.session.refresh(meeting)
        return meeting


