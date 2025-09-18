from __future__ import annotations

from typing import Optional
from sqlmodel import Session, select

from app.models.summary import Summary


class SummariesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_for_meeting(self, meeting_id: int, abstract_md: str, bullets_md: str) -> Summary:
        existing = self.get_by_meeting(meeting_id)
        if existing is None:
            summary = Summary(meeting_id=meeting_id, abstract_md=abstract_md, bullets_md=bullets_md)
            self.session.add(summary)
            self.session.commit()
            self.session.refresh(summary)
            return summary
        existing.abstract_md = abstract_md
        existing.bullets_md = bullets_md
        self.session.add(existing)
        self.session.commit()
        self.session.refresh(existing)
        return existing

    def get_by_meeting(self, meeting_id: int) -> Optional[Summary]:
        statement = select(Summary).where(Summary.meeting_id == meeting_id)
        return self.session.exec(statement).first()


