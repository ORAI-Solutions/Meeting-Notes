from __future__ import annotations

from typing import Iterable
from sqlmodel import Session, select

from app.models.transcript_segment import TranscriptSegment


class TranscriptsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_segments(self, segments: Iterable[TranscriptSegment]) -> None:
        for seg in segments:
            self.session.add(seg)
        self.session.commit()

    def delete_for_meeting(self, meeting_id: int) -> int:
        """Delete all transcript segments for a meeting.

        Returns number of rows intended to be deleted. SQLite via ORM does not
        easily return affected row count reliably here; we return a best-effort
        number by querying first to keep things simple and clear.
        """
        to_delete = self.list_by_meeting(meeting_id)
        for seg in to_delete:
            self.session.delete(seg)
        self.session.commit()
        return len(to_delete)

    def list_by_meeting(self, meeting_id: int) -> list[TranscriptSegment]:
        statement = select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(
            TranscriptSegment.t_start_ms.asc()
        )
        return list(self.session.exec(statement))

    def count_for_meeting(self, meeting_id: int) -> int:
        # Simple count via list; acceptable for small datasets here.
        return len(self.list_by_meeting(meeting_id))


