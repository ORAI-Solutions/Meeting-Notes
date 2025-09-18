from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List

from sqlmodel import Session

from app.config import Settings
from app.repositories.meetings import MeetingsRepository
from app.repositories.audio_files import AudioFilesRepository
from app.repositories.transcripts import TranscriptsRepository
from app.services.asr_engine import WhisperASREngine, ASRConfig


@dataclass
class JobState:
    status: str = "idle"  # idle|running|done|error
    progress: float = 0.0
    message: Optional[str] = None


_jobs: Dict[int, JobState] = {}
_locks: Dict[int, threading.Lock] = {}


def _get_lock(meeting_id: int) -> threading.Lock:
    if meeting_id not in _locks:
        _locks[meeting_id] = threading.Lock()
    return _locks[meeting_id]


def get_status(meeting_id: int) -> JobState:
    return _jobs.get(meeting_id, JobState())


def start_transcription_job(meeting_id: int, session: Session, cfg_dict: dict | None = None) -> JobState:
    lock = _get_lock(meeting_id)
    if meeting_id in _jobs and _jobs[meeting_id].status == "running":
        return _jobs[meeting_id]
    _jobs[meeting_id] = JobState(status="running", progress=0.0, message="starting")

    # Snapshot minimal inputs for worker thread
    settings = Settings()
    repo_m = MeetingsRepository(session)
    repo_a = AudioFilesRepository(session)
    repo_t = TranscriptsRepository(session)
    meeting = repo_m.get(meeting_id)
    audio_mic = repo_a.get_by_meeting_and_kind(meeting_id, "mic")
    audio_sys = repo_a.get_by_meeting_and_kind(meeting_id, "system")
    asr_cfg_raw = cfg_dict or {}

    if meeting is None or not (audio_mic and audio_sys):
        _jobs[meeting_id] = JobState(status="error", progress=0.0, message="meeting or audio not found")
        return _jobs[meeting_id]

    def _worker() -> None:
        try:
            # Build config from DB settings merged with provided overrides
            from app.repositories.settings import get_app_settings

            # Need a fresh session in thread
            from app.models.base import engine as _engine
            with Session(_engine) as s2:
                settings_dict = get_app_settings(s2)
            asr_settings = settings_dict.get("asr", {}) if isinstance(settings_dict, dict) else {}
            merged = dict(asr_settings)
            if isinstance(asr_cfg_raw, dict):
                merged.update(asr_cfg_raw)
            cfg = ASRConfig(
                model_id=str(merged.get("model_id", "large-v3")),
                device=str(merged.get("device", "auto")),
                mode=str(merged.get("mode", "fast")),
                language=(merged.get("language") or None),
                vad=bool(merged.get("vad", True)),
            )

            engine = WhisperASREngine(settings)
            _jobs[meeting_id] = JobState(status="running", progress=0.0, message="loading model")

            # Always dual-track (mic+system)
            track_pref = "mic+system"

            def _on_progress_weighted(base: float, span: float):
                def inner(frac: float, phase: str) -> None:
                    p = base + span * max(0.0, min(1.0, float(frac)))
                    _jobs[meeting_id] = JobState(status="running", progress=float(p), message=phase)
                return inner

            segments_all: List[dict] = []
            if (track_pref == "mic+system") and audio_mic is not None and audio_sys is not None:
                # Transcribe mic as "You"
                mic_segments, mic_info = engine.transcribe_file(Path(audio_mic.path), cfg, progress_cb=_on_progress_weighted(0.0, 0.45))
                for s in mic_segments:
                    s["speaker"] = "You"
                # Transcribe system as "Remote"
                sys_segments, sys_info = engine.transcribe_file(Path(audio_sys.path), cfg, progress_cb=_on_progress_weighted(0.5, 0.45))
                for s in sys_segments:
                    s["speaker"] = "Remote"
                segments_all = _merge_and_filter(mic_segments, sys_segments)
                # Mark near-complete
                _jobs[meeting_id] = JobState(status="running", progress=0.98, message="finalizing")
            else:
                # Should not happen: require both tracks
                raise RuntimeError("Mic and system tracks are required")

            # Persist: replace old segments
            with Session(_engine) as s3:
                TranscriptsRepository(s3).delete_for_meeting(meeting_id)
                from app.models.transcript_segment import TranscriptSegment

                rows = [
                    TranscriptSegment(
                        meeting_id=meeting_id,
                        t_start_ms=int(seg.get("t_start_ms", 0)),
                        t_end_ms=int(seg.get("t_end_ms", 0)),
                        speaker=str(seg.get("speaker", "Speaker")),
                        text=str(seg.get("text", "")),
                        confidence=float(seg["confidence"]) if seg.get("confidence") is not None else None,
                    )
                    for seg in segments_all
                ]
                TranscriptsRepository(s3).add_segments(rows)

                # Persist detected language into Meeting.language (prefer mic, fallback to system)
                try:
                    detected_lang = None
                    if isinstance(mic_info, dict):
                        detected_lang = mic_info.get("language") or detected_lang
                    if isinstance(sys_info, dict) and not detected_lang:
                        detected_lang = sys_info.get("language")
                    if detected_lang:
                        m_row = MeetingsRepository(s3).get(meeting_id)
                        if m_row is not None:
                            m_row.language = str(detected_lang)
                            MeetingsRepository(s3).update(m_row)
                except Exception:
                    pass

            _jobs[meeting_id] = JobState(status="done", progress=1.0, message="completed")
        except Exception as e:
            _jobs[meeting_id] = JobState(status="error", progress=0.0, message=str(e))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return _jobs[meeting_id]


def _filter_and_merge_adjacent(segs: List[dict]) -> List[dict]:
    # no-op: keep segments as returned by model
    return segs


def _merge_and_filter(mic: List[dict], sys: List[dict]) -> List[dict]:
    """Interleave mic and system segments by time and remove obvious duplicates."""
    all_segs = _filter_and_merge_adjacent([*mic, *sys])
    all_segs.sort(key=lambda s: (int(s.get("t_start_ms", 0)), int(s.get("t_end_ms", 0))))
    # Remove exact duplicate texts within 500 ms window
    dedup: List[dict] = []
    for s in all_segs:
        if dedup and s.get("text", "").strip() == dedup[-1].get("text", "").strip() and int(s.get("t_start_ms", 0)) - int(dedup[-1].get("t_start_ms", 0)) < 500:
            # extend previous
            dedup[-1]["t_end_ms"] = max(int(dedup[-1].get("t_end_ms", 0)), int(s.get("t_end_ms", 0)))
        else:
            dedup.append(s)
    return dedup


def _normalize_timestamps(segs: List[dict]) -> List[dict]:
    # no-op: keep timestamps from model
    return segs


