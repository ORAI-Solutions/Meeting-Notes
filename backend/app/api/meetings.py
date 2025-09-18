from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
import json
from pathlib import Path
import os

from app.deps import get_session
from app.models.meeting import Meeting
from app.models.audio_file import AudioFile
from app.repositories.meetings import MeetingsRepository
from app.repositories.audio_files import AudioFilesRepository
from app.repositories.transcripts import TranscriptsRepository
from app.services.transcription_service import start_transcription_job, get_status
from app.repositories.settings import get_app_settings
from app.services.summarization_service import summarize_meeting, LlmConfig
import logging
logger = logging.getLogger("app.api")


router = APIRouter(prefix="/meetings", tags=["meetings"])


class StartMeetingRequest(BaseModel):
    title: Optional[str] = None
    language: Optional[str] = None
    mic_device_id: Optional[str] = None
    output_device_id: Optional[str] = None


class StopResponse(BaseModel):
    ok: bool
    frames: Optional[int] = None
    rate: Optional[int] = None
    channels: Optional[int] = None
    sys_backend: Optional[str] = None


class UpdateMeetingRequest(BaseModel):
    title: Optional[str] = None


@router.post("/start")
async def start_meeting(body: StartMeetingRequest, session: Session = Depends(get_session)) -> dict[str, str]:
    
    devices_payload: Dict[str, Any] = {
        "mic_device_id": body.mic_device_id,
        "output_device_id": body.output_device_id,
    }
    meeting = Meeting(
        title=body.title or "Untitled Meeting",
        language=body.language,
        devices_used=json.dumps(devices_payload, ensure_ascii=False),
        status="recording",
    )
    meeting = MeetingsRepository(session).create(meeting)

    
    meeting_dir_id = str(meeting.id)
    try:
        from app.services.audio_capture import start_recording
        import asyncio

        loop = asyncio.get_running_loop()
        start_recording(meeting_dir_id, body.mic_device_id, body.output_device_id, loop=loop)
    except Exception:
        
        pass

    return {"meeting_id": meeting_dir_id}


@router.post("/{meeting_id}/stop")
async def stop_meeting(meeting_id: int, session: Session = Depends(get_session)) -> StopResponse:
    
    try:
        from app.services.audio_capture import stop_recording

        info = stop_recording(str(meeting_id))
    except Exception:
        info = {}

    
    repo_m = MeetingsRepository(session)
    meeting = repo_m.get(meeting_id)
    if meeting is not None:
        meeting.ended_at = datetime.utcnow()
        meeting.status = "done"

        
        try:
            current_devices = json.loads(meeting.devices_used) if meeting.devices_used else {}
        except Exception:
            current_devices = {}
        if isinstance(info, dict) and info.get("sys_backend"):
            current_devices["sys_backend"] = info.get("sys_backend")
            meeting.devices_used = json.dumps(current_devices, ensure_ascii=False)
        meeting = repo_m.update(meeting)

        
        rate = info.get("rate") if isinstance(info, dict) else None
        
        # Mic audio (if exists)
        mic_path = info.get("mic_path") if isinstance(info, dict) else None
        if mic_path:
            try:
                path_obj = Path(mic_path)
                if path_obj.exists():
                    file_bytes = path_obj.stat().st_size
                    mic_frames = info.get("mic_frames") if isinstance(info, dict) else None
                    duration_ms = int((mic_frames or 0) * 1000 / rate) if rate else 0
                    audio = AudioFile(
                        meeting_id=meeting.id,  # type: ignore[arg-type]
                        kind="mic",
                        path=str(path_obj),
                        codec="wav",
                        sample_rate=int(rate) if rate else 0,
                        duration_ms=duration_ms,
                        bytes=int(file_bytes),
                    )
                    AudioFilesRepository(session).create(audio)
            except Exception:
                pass
        
        # System audio (if exists)
        sys_path = info.get("sys_path") if isinstance(info, dict) else None
        if sys_path:
            try:
                path_obj = Path(sys_path)
                if path_obj.exists():
                    file_bytes = path_obj.stat().st_size
                    sys_frames = info.get("sys_frames") if isinstance(info, dict) else None
                    duration_ms = int((sys_frames or 0) * 1000 / rate) if rate else 0
                    audio = AudioFile(
                        meeting_id=meeting.id,  # type: ignore[arg-type]
                        kind="system",
                        path=str(path_obj),
                        codec="wav",
                        sample_rate=int(rate) if rate else 0,
                        duration_ms=duration_ms,
                        bytes=int(file_bytes),
                    )
                    AudioFilesRepository(session).create(audio)
            except Exception:
                pass

    return StopResponse(
        ok=True,
        frames=info.get("frames") if isinstance(info, dict) else None,
        rate=info.get("rate") if isinstance(info, dict) else None,
        channels=info.get("channels") if isinstance(info, dict) else None,
        sys_backend=info.get("sys_backend") if isinstance(info, dict) else None,
    )


@router.get("")
def list_meetings(limit: int = 50, offset: int = 0, session: Session = Depends(get_session)) -> List[Meeting]:
    return MeetingsRepository(session).list(limit=limit, offset=offset)


@router.get("/{meeting_id}")
def get_meeting_detail(meeting_id: int, session: Session = Depends(get_session)) -> Dict[str, Any]:
    repo_m = MeetingsRepository(session)
    meeting = repo_m.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    audio_files = AudioFilesRepository(session).list_by_meeting(meeting_id)
    segments = TranscriptsRepository(session).list_by_meeting(meeting_id)
    
    # Load summary if present
    from app.repositories.summaries import SummariesRepository
    summary = SummariesRepository(session).get_by_meeting(meeting_id)
    action_items = []
    
    return {
        "meeting": meeting,
        "audio_files": audio_files,
        "transcript_segments": segments,
        "summary": summary,
        "action_items": action_items,
    }


class TranscribeRequest(BaseModel):
    track: str | None = None  # reserved for future use
    language: str | None = None
    mode: str | None = None  # fast|accurate
    device: str | None = None  # auto|cpu|cuda


class TranscribeStatus(BaseModel):
    status: str
    progress: float
    message: str | None = None


@router.post("/{meeting_id}/transcribe")
def transcribe_meeting(meeting_id: int, body: TranscribeRequest, session: Session = Depends(get_session)) -> TranscribeStatus:
    
    meeting = MeetingsRepository(session).get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    
    cfg: dict[str, object] = {}
    if body.language is not None:
        cfg["language"] = body.language
    if body.mode in {"fast", "accurate"}:
        cfg["mode"] = body.mode
    if body.device in {"auto", "cpu", "cuda"}:
        cfg["device"] = body.device

    st = start_transcription_job(meeting_id, session, cfg_dict=cfg)
    return TranscribeStatus(status=st.status, progress=st.progress, message=st.message)


@router.get("/{meeting_id}/transcribe/status")
def transcription_status(meeting_id: int) -> TranscribeStatus:
    st = get_status(meeting_id)
    return TranscribeStatus(status=st.status, progress=st.progress, message=st.message)


class SummarizeResponse(BaseModel):
    ok: bool


class SummarizeRequest(BaseModel):
    length: str | None = None  # short | mid | long


@router.post("/{meeting_id}/summarize")
def summarize_endpoint(meeting_id: int, body: SummarizeRequest | None = None, session: Session = Depends(get_session)) -> Dict[str, Any]:
    
    meeting = MeetingsRepository(session).get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    length = (body.length if body else None) or "mid"
    token_map: Dict[str, int] = {"short": 4096, "mid": 8192, "long": 16384}
    max_tokens = token_map.get(length, 4096)
    cfg = LlmConfig(max_tokens=max_tokens)
    result = summarize_meeting(meeting_id, session, cfg=cfg, length=length)
    return {"ok": True, **result}


@router.put("/{meeting_id}")
def update_meeting(meeting_id: int, body: UpdateMeetingRequest, session: Session = Depends(get_session)) -> Meeting:
    repo_m = MeetingsRepository(session)
    meeting = repo_m.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    if body.title is not None:
        meeting.title = body.title
        meeting = repo_m.update(meeting)
    
    return meeting


 


