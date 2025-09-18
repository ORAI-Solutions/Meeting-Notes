from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    app_name: str = "Meeting Notes"
    app_author: str = "MeetingNotes"

    # Base roaming app data dir (e.g., %APPDATA%\MeetingNotes)
    appdata_dir: Path = Field(default_factory=lambda: Path(os.getenv("APPDATA", "")) / "MeetingNotes")
    data_dir: Path = Field(default_factory=lambda: Path(os.getenv("APPDATA", "")) / "MeetingNotes" / "data")
    audio_dir: Path = Field(default_factory=lambda: Path(os.getenv("APPDATA", "")) / "MeetingNotes" / "audio")
    models_dir: Path = Field(default_factory=lambda: Path(os.getenv("APPDATA", "")) / "MeetingNotes" / "models")
    logs_dir: Path = Field(default_factory=lambda: Path(os.getenv("APPDATA", "")) / "MeetingNotes" / "logs")

    database_path: Path = Field(default_factory=lambda: Path(os.getenv("APPDATA", "")) / "MeetingNotes" / "data" / "meeting_notes.db")

    class Config:
        env_prefix = "MN_"
        case_sensitive = False

    def ensure_dirs(self) -> None:
        for d in [self.appdata_dir, self.data_dir, self.audio_dir, self.models_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)


