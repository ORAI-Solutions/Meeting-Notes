from __future__ import annotations

from typing import Any, Dict
import shutil

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.deps import get_session
from app.repositories.settings import get_app_settings, save_app_settings
from app.models.app_settings import AppSettingsModel, migrate_settings_dict, ASRSettings
from app.config import Settings
from app.models.base import init_db, engine
from sqlmodel import SQLModel
from app.services.model_manager import get_llm_presets, get_download_state, download_llm_preset, download_llm_from_url
from app.services.asr_model_manager import (
    get_asr_presets,
    get_asr_download_state,
    download_asr_preset,
    is_asr_model_present,
)
from app.services.cuda_runtime_manager import get_cuda_manager
from pathlib import Path
import os


router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    asr: ASRSettings | None = None
    # Accept flat llm_device for backward compatibility
    llm_device: str | None = None
    # New llm block for preset/path persistence
    llm: dict | None = None


@router.get("")
def read_settings(session: Session = Depends(get_session)) -> Dict[str, Any]:
    return get_app_settings(session)


@router.post("")
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)) -> Dict[str, Any]:
    # Accept partial update; only 'asr' currently supported
    raw = body.dict(exclude_none=True)
    patch: Dict[str, Any] = migrate_settings_dict(raw)
    return save_app_settings(session, patch)


class WipeRequest(BaseModel):
    wipe_db: bool = True
    wipe_audio: bool = True


@router.post("/wipe")
def wipe_data(body: WipeRequest) -> Dict[str, Any]:
    settings = Settings()
    result: Dict[str, Any] = {"ok": False, "wiped_db": False, "wiped_audio": False}

    if body.wipe_audio:
        try:
            shutil.rmtree(settings.audio_dir, ignore_errors=True)
            result["wiped_audio"] = True
        except Exception:
            result["wiped_audio"] = False

    if body.wipe_db:
        # Ensure no open connections hold the file
        try:
            engine.dispose()
        except Exception:
            pass
        try:
            if settings.database_path.exists():
                try:
                    settings.database_path.unlink()
                except Exception:
                    # Try removing WAL/SHM and retry
                    wal = settings.database_path.parent / (settings.database_path.name + "-wal")
                    shm = settings.database_path.parent / (settings.database_path.name + "-shm")
                    try:
                        if wal.exists():
                            wal.unlink()
                    except Exception:
                        pass
                    try:
                        if shm.exists():
                            shm.unlink()
                    except Exception:
                        pass
                    # Retry DB unlink once
                    settings.database_path.unlink()
            result["wiped_db"] = True
        except Exception:
            # Fallback: drop all tables to clear content if file deletion fails (e.g., file lock)
            try:
                SQLModel.metadata.drop_all(bind=engine)
                SQLModel.metadata.create_all(bind=engine)
                result["wiped_db"] = True
            except Exception:
                result["wiped_db"] = False

    # Recreate directories and empty database
    try:
        settings.ensure_dirs()
        init_db()
    except Exception:
        pass

    # ok = all requested operations succeeded
    ok_db = (not body.wipe_db) or result["wiped_db"]
    ok_audio = (not body.wipe_audio) or result["wiped_audio"]
    result["ok"] = bool(ok_db and ok_audio)
    return result


class LlmPreset(BaseModel):
    id: str
    label: str
    filename: str


class LlmOptions(BaseModel):
    gpu_available: bool
    models: list[str]
    presets: list[LlmPreset]


@router.get("/llm/options")
def llm_options() -> LlmOptions:
    # Probe GPU availability for llama-cpp-python (v0.3+)
    gpu_available = False
    try:
        from llama_cpp import llama_supports_gpu_offload  # type: ignore

        gpu_available = bool(llama_supports_gpu_offload())
    except Exception:
        gpu_available = False

    # List GGUF files under default models directory
    from app.config import Settings as AppSettings

    settings = AppSettings()
    models_dir = settings.models_dir / "llm"
    try:
        models_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    model_paths: list[str] = []
    try:
        for root, _, files in os.walk(models_dir):
            for f in files:
                if f.lower().endswith(".gguf"):
                    model_paths.append(str(Path(root) / f))
    except Exception:
        model_paths = []

    presets = get_llm_presets()
    return LlmOptions(
        gpu_available=gpu_available,
        models=sorted(model_paths),
        presets=[LlmPreset(id=p.id, label=p.label, filename=p.filename) for p in presets],
    )


class LlmDownloadRequest(BaseModel):
    preset_id: str | None = None
    url: str | None = None
    filename: str | None = None


class LlmDownloadResponse(BaseModel):
    status: str
    progress: float
    message: str | None = None
    path: str | None = None


@router.post("/llm/download")
def llm_download(body: LlmDownloadRequest) -> LlmDownloadResponse:
    state = get_download_state()
    if state.get("status") == "running":
        # Already running; return current state
        return LlmDownloadResponse(
            status=str(state.get("status")),
            progress=float(state.get("progress", 0.0)),
            message=str(state.get("message")) if state.get("message") else None,
            path=str(state.get("path")) if state.get("path") else None,
        )
    # Start download synchronously (file sizes are large; UI polls progress)
    try:
        if body.url:
            path = download_llm_from_url(body.url, filename=body.filename)
        else:
            if not body.preset_id:
                raise ValueError("preset_id or url required")
            path = download_llm_preset(body.preset_id)
        state = get_download_state()
        return LlmDownloadResponse(
            status=str(state.get("status")),
            progress=float(state.get("progress", 1.0)),
            message=str(state.get("message")) if state.get("message") else None,
            path=str(path),
        )
    except Exception as e:
        state = get_download_state()
        return LlmDownloadResponse(
            status="error",
            progress=float(state.get("progress", 0.0)),
            message=str(e),
            path=None,
        )


@router.get("/llm/download/status")
def llm_download_status() -> LlmDownloadResponse:
    state = get_download_state()
    return LlmDownloadResponse(
        status=str(state.get("status")),
        progress=float(state.get("progress", 0.0)),
        message=str(state.get("message")) if state.get("message") else None,
        path=str(state.get("path")) if state.get("path") else None,
    )


# ASR settings & downloads

class AsrPreset(BaseModel):
    id: str
    label: str
    size_bytes: int | None = None


class AsrOptions(BaseModel):
    model_present: bool
    model_path: str | None
    presets: list[AsrPreset]


@router.get("/asr/options")
def asr_options(session: Session = Depends(get_session)) -> AsrOptions:
    # Determine configured model id (default large-v3)
    settings_dict = get_app_settings(session)
    asr_cfg = settings_dict.get("asr", {}) if isinstance(settings_dict, dict) else {}
    model_id = str(asr_cfg.get("model_id", "large-v3"))
    present = is_asr_model_present(model_id)
    from app.services.asr_model_manager import resolve_asr_model_path_from_id

    model_path = str(resolve_asr_model_path_from_id(model_id)) if present else None
    presets = get_asr_presets()
    return AsrOptions(
        model_present=bool(present),
        model_path=model_path,
        presets=[AsrPreset(id=p.id, label=p.label, size_bytes=p.size_bytes) for p in presets],
    )


class AsrDownloadRequest(BaseModel):
    preset_id: str | None = None  # defaults to current configured id


class AsrDownloadResponse(BaseModel):
    status: str
    progress: float
    message: str | None = None
    path: str | None = None


@router.post("/asr/download")
def asr_download(body: AsrDownloadRequest, session: Session = Depends(get_session)) -> AsrDownloadResponse:
    # Choose preset id
    preset_id = body.preset_id
    if not preset_id:
        settings_dict = get_app_settings(session)
        asr_cfg = settings_dict.get("asr", {}) if isinstance(settings_dict, dict) else {}
        preset_id = str(asr_cfg.get("model_id", "large-v3"))

    state = get_asr_download_state()
    if state.get("status") == "running":
        return AsrDownloadResponse(
            status=str(state.get("status")),
            progress=float(state.get("progress", 0.0)),
            message=str(state.get("message")) if state.get("message") else None,
            path=str(state.get("path")) if state.get("path") else None,
        )

    # Start download in background and return immediately
    try:
        import threading

        def _bg() -> None:
            try:
                download_asr_preset(str(preset_id))
            except Exception:
                # state is updated by the download call on error
                pass

        t = threading.Thread(target=_bg, daemon=True)
        t.start()
        state = get_asr_download_state()
        return AsrDownloadResponse(
            status=str(state.get("status")),
            progress=float(state.get("progress", 0.0)),
            message=str(state.get("message")) if state.get("message") else None,
            path=str(state.get("path")) if state.get("path") else None,
        )
    except Exception as e:
        state = get_asr_download_state()
        return AsrDownloadResponse(
            status="error",
            progress=float(state.get("progress", 0.0)),
            message=str(e),
            path=None,
        )


@router.get("/asr/download/status")
def asr_download_status() -> AsrDownloadResponse:
    state = get_asr_download_state()
    return AsrDownloadResponse(
        status=str(state.get("status")),
        progress=float(state.get("progress", 0.0)),
        message=str(state.get("message")) if state.get("message") else None,
        path=str(state.get("path")) if state.get("path") else None,
    )


# CUDA Runtime Management


class CudaStatus(BaseModel):
    installed_libraries: Dict[str, bool]
    is_downloading: bool
    current_download: str | None
    download_progress: Dict[str, float]
    error_message: str | None
    cuda_directory: str
    whisper_gpu_ready: bool
    llama_gpu_ready: bool


@router.get("/cuda/status")
def cuda_status() -> CudaStatus:
    """Get current CUDA runtime status."""
    cuda_mgr = get_cuda_manager()
    status = cuda_mgr.get_status()
    return CudaStatus(**status)


class CudaDownloadRequest(BaseModel):
    feature: str  # "whisper_gpu" or "llama_gpu"


class CudaDownloadResponse(BaseModel):
    success: bool
    message: str
    download_size_mb: float | None = None


@router.post("/cuda/download")
def cuda_download(body: CudaDownloadRequest) -> CudaDownloadResponse:
    """Download required CUDA libraries for a feature."""
    cuda_mgr = get_cuda_manager()
    
    # Check what's needed
    ready, missing = cuda_mgr.check_gpu_ready(body.feature)
    if ready:
        return CudaDownloadResponse(
            success=True,
            message="All required CUDA libraries are already installed",
            download_size_mb=0
        )
    
    # Get download size
    download_size = cuda_mgr.get_download_size(missing)
    
    # Start download in background
    import threading
    
    def _download():
        cuda_mgr.download_libraries(missing)
    
    thread = threading.Thread(target=_download, daemon=True)
    thread.start()
    
    return CudaDownloadResponse(
        success=True,
        message=f"Downloading {len(missing)} libraries for {body.feature}",
        download_size_mb=download_size
    )


@router.post("/cuda/cleanup")
def cuda_cleanup() -> Dict[str, bool]:
    """Remove all downloaded CUDA runtime libraries."""
    cuda_mgr = get_cuda_manager()
    try:
        cuda_mgr.cleanup_unused_libraries()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

