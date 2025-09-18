from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock, Thread
from typing import Dict, List, Optional

from app.config import Settings


@dataclass(frozen=True)
class ASRPreset:
    id: str
    label: str
    model_id: str  # faster-whisper model id for WhisperModel(...)
    size_bytes: Optional[int] = None  # indicative only


def get_asr_models_dir(settings: Optional[Settings] = None) -> Path:
    s = settings or Settings()
    base = s.models_dir / "whisper" / "faster-whisper"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_asr_presets() -> List[ASRPreset]:
    
    return [
        ASRPreset(
            id="large-v3",
            label="Whisper Large v3 (CT2) (~3-4 GB, high accuracy)",
            model_id="large-v3",
            size_bytes=3_500_000_000,
        ),
        ASRPreset(
            id="distil-large-v3",
            label="Distil Whisper Large v3 (CT2) (~1.3-2 GB, faster)",
            model_id="distil-large-v3",
            size_bytes=1_800_000_000,
        ),
    ]


def resolve_asr_model_path_from_id(preset_id: str, settings: Optional[Settings] = None) -> Path:
    """Return the target directory where faster-whisper will store the model files."""
    models_dir = get_asr_models_dir(settings)
    return models_dir / preset_id


def _dir_contains_ct2_model(path: Path) -> bool:
    try:
        if not path.exists() or not path.is_dir():
            return False
        # Typical ctranslate2 whisper model files
        required = ["tokenizer.json", "config.json"]
        has_required = all((path / f).exists() for f in required)
        has_model_bin = any((path / n).exists() for n in ["model.bin", "model.bin.0", "ggml-model.bin"])
        return bool(has_required and has_model_bin)
    except Exception:
        return False


def discover_asr_model_dir(preset_id: str, settings: Optional[Settings] = None) -> Path | None:
    """Locate an existing CT2 model directory for the given preset under our models root.

    Some faster-whisper versions may store models under repo-like names instead of the
    plain preset id. We scan recursively for a directory that looks like a CT2 model.
    """
    root = get_asr_models_dir(settings)
    # 1) Expected location
    candidate = root / preset_id
    if _dir_contains_ct2_model(candidate):
        return candidate
    # 2) Scan one level deep
    try:
        for child in root.rglob("*"):
            try:
                if child.is_dir() and _dir_contains_ct2_model(child):
                    # Prefer directories that include the preset id in their path
                    if preset_id in str(child).lower():
                        return child
            except Exception:
                continue
    except Exception:
        pass
    return None


_dl_lock = Lock()
_dl_state: Dict[str, object] = {
    "status": "idle",  # idle|running|done|error
    "preset_id": None,
    "progress": 0.0,  # best-effort; faster-whisper download API has no direct progress hooks
    "message": None,
    "path": None,
}


def get_asr_download_state() -> Dict[str, object]:
    with _dl_lock:
        return dict(_dl_state)


def _set_state(**kwargs: object) -> None:
    with _dl_lock:
        _dl_state.update(kwargs)


def _perform_fw_download(preset_id: str, settings: Optional[Settings] = None) -> Path:
    """Use faster-whisper's own downloader by instantiating WhisperModel once."""
    # Import here to avoid heavy import at module load
    from faster_whisper import WhisperModel  # type: ignore

    s = settings or Settings()
    target_dir = resolve_asr_model_path_from_id(preset_id, s)
    target_dir.mkdir(parents=True, exist_ok=True)

    # faster-whisper downloads into download_root/<model_id>
    _set_state(status="running", preset_id=preset_id, progress=0.01, message="starting", path=None)

    # Best-effort progress monitor by directory size
    expected_bytes = None
    try:
        for p in get_asr_presets():
            if p.id == preset_id:
                expected_bytes = p.size_bytes
                break
    except Exception:
        expected_bytes = None

    def _calc_dir_size_bytes(p: Path) -> int:
        total = 0
        try:
            if not p.exists():
                return 0
            for sub in p.rglob("*"):
                try:
                    if sub.is_file():
                        total += sub.stat().st_size
                except Exception:
                    pass
        except Exception:
            return total
        return total

    _stop_flag = {"stop": False}

    def _monitor() -> None:
        import time
        while not _stop_flag["stop"]:
            try:
                size = _calc_dir_size_bytes(target_dir)
                if expected_bytes and expected_bytes > 0:
                    frac = min(0.99, max(0.02, float(size) / float(expected_bytes)))
                else:
                    prev = float(get_asr_download_state().get("progress", 0.0) or 0.0)
                    frac = min(0.8, prev + 0.02)
                _set_state(progress=frac, message="downloading")
            except Exception:
                pass
            time.sleep(1.0)

    mon = Thread(target=_monitor, daemon=True)
    mon.start()
    try:
        model = WhisperModel(
            preset_id,
            device="cpu",
            compute_type="int8",
            download_root=str(get_asr_models_dir(s)),
        )
        # Force a tiny inference to ensure tokenizer and model are fully resolved on disk
        _set_state(progress=0.99, message="finalizing")
        try:
            
            pass
        except Exception:
            pass
    except Exception as e:
        _stop_flag["stop"] = True
        _set_state(status="error", message=str(e))
        raise
    # At this point, files live under download_root/<preset_id>
    _stop_flag["stop"] = True
    _set_state(status="done", progress=1.0, message="downloaded", path=str(target_dir))
    return target_dir


def download_asr_preset(preset_id: str, settings: Optional[Settings] = None) -> Path:
    presets = {p.id: p for p in get_asr_presets()}
    if preset_id not in presets:
        raise ValueError(f"Unknown ASR preset id: {preset_id}")

    s = settings or Settings()
    dst_dir = resolve_asr_model_path_from_id(preset_id, s)
    if dst_dir.exists() and any(dst_dir.iterdir()):
        # Already present
        _set_state(status="done", progress=1.0, message="already-present", path=str(dst_dir))
        return dst_dir

    return _perform_fw_download(preset_id, s)


 


def is_asr_model_present(preset_id: str = "large-v3", settings: Optional[Settings] = None) -> bool:
    return discover_asr_model_dir(preset_id, settings) is not None


