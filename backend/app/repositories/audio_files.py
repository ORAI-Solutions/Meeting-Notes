from __future__ import annotations

from typing import List

from sqlmodel import Session, select

from app.models.audio_file import AudioFile


class AudioFilesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, audio_file: AudioFile) -> AudioFile:
        self.session.add(audio_file)
        self.session.commit()
        self.session.refresh(audio_file)
        return audio_file

    def list_by_meeting(self, meeting_id: int) -> list[AudioFile]:
        statement = select(AudioFile).where(AudioFile.meeting_id == meeting_id).order_by(AudioFile.id.asc())
        return list(self.session.exec(statement))
    
    def get_by_meeting_and_kind(self, meeting_id: int, kind: str) -> AudioFile | None:
        statement = select(AudioFile).where(
            AudioFile.meeting_id == meeting_id,
            AudioFile.kind == kind
        )
        return self.session.exec(statement).first()


