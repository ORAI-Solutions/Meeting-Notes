from __future__ import annotations

from typing import Iterable, List
from sqlmodel import Session, select

from app.models.action_item import ActionItem


class ActionItemsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_many_for_meeting(self, meeting_id: int, items: Iterable[ActionItem]) -> List[ActionItem]:
        # Simple approach: delete existing then insert
        existing = self.list_by_meeting(meeting_id)
        for item in existing:
            self.session.delete(item)
        self.session.commit()

        saved: List[ActionItem] = []
        for item in items:
            item.meeting_id = meeting_id
            self.session.add(item)
            saved.append(item)
        self.session.commit()
        for item in saved:
            self.session.refresh(item)
        return saved

    def list_by_meeting(self, meeting_id: int) -> list[ActionItem]:
        statement = select(ActionItem).where(ActionItem.meeting_id == meeting_id)
        return list(self.session.exec(statement))


