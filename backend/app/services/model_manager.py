from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from threading import Lock
import hashlib
import os
import shutil
import urllib.request
import urllib.error

from app.config import Settings


@dataclass(frozen=True)
class LLMPreset:
    id: str
    label: str
    filename: str
    url: str
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    requires_token: bool = False


def get_llm_models_dir(settings: Optional[Settings] = None) -> Path:
    s = settings or Settings()
    base = s.models_dir / "llm"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_llm_presets() -> List[LLMPreset]:
    # Note: Some models (e.g., Meta Llama) may require license acceptance on Hugging Face.
    # If download fails with 403, inform the user to place the file manually.
    return [
        LLMPreset(
            id="mistral-7b-instruct-q4_k_m",
            label="Mistral 7B Instruct v0.2 Q4_K_M (~4.1 GB)",
            filename="mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            url=(
                "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/"
                "mistral-7b-instruct-v0.2.Q4_K_M.gguf?download=true"
            ),
            size_bytes=4_100_000_000,
            sha256=None,
            requires_token=False,
        ),
        LLMPreset(
            id="llama-3.1-8b-instruct-q4_k_m",
            label="Llama 3.1 8B Instruct Q4_K_M (~4.7 GB)",
            filename="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
            url=(
                "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/"
                "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf?download=true"
            ),
            size_bytes=4_700_000_000,
            sha256=None,
            requires_token=True,
        ),
        LLMPreset(
            id="qwen2.5-3b-instruct-q4_k_m",
            label="Qwen2.5 3B Instruct Q4_K_M (~2.2 GB)",
            filename="Qwen2.5-3B-Instruct-Q4_K_M.gguf",
            url=(
                "https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/"
                "Qwen2.5-3B-Instruct-Q4_K_M.gguf?download=true"
            ),
            size_bytes=2_200_000_000,
            sha256=None,
            requires_token=False,
        ),
        LLMPreset(
            id="phi-2-2_7b-q4_k_m",
            label="Phi-2 2.7B Q4_K_M (~1.6 GB)",
            filename="phi-2.Q4_K_M.gguf",
            url=(
                "https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/"
                "phi-2.Q4_K_M.gguf?download=true"
            ),
            size_bytes=1_600_000_000,
            sha256=None,
            requires_token=False,
        ),
    ]


def resolve_llm_model_path_from_id(preset_id: str, settings: Optional[Settings] = None) -> Path:
    presets = {p.id: p for p in get_llm_presets()}
    if preset_id not in presets:
        raise ValueError(f"Unknown LLM preset id: {preset_id}")
    models_dir = get_llm_models_dir(settings)
    return models_dir / presets[preset_id].filename


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_dl_lock = Lock()
_dl_state: Dict[str, object] = {
    "status": "idle",  # idle|running|done|error
    "preset_id": None,
    "progress": 0.0,
    "message": None,
    "path": None,
}


def get_download_state() -> Dict[str, object]:
    with _dl_lock:
        return dict(_dl_state)


def _set_state(**kwargs: object) -> None:
    with _dl_lock:
        _dl_state.update(kwargs)


def download_llm_preset(preset_id: str, settings: Optional[Settings] = None) -> Path:
    presets = {p.id: p for p in get_llm_presets()}
    if preset_id not in presets:
        raise ValueError(f"Unknown LLM preset id: {preset_id}")
    preset = presets[preset_id]
    dst = resolve_llm_model_path_from_id(preset_id, settings)
    tmp = dst.with_suffix(dst.suffix + ".part")

    # If already present, verify checksum if available and return
    if dst.exists():
        if preset.sha256:
            try:
                if _sha256_file(dst).lower() == preset.sha256.lower():
                    return dst
            except Exception:
                pass
        else:
            return dst

    # Download
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        _set_state(status="running", preset_id=preset_id, progress=0.0, message="starting", path=None)
        with urllib.request.urlopen(preset.url) as r, tmp.open("wb") as f:
            total = getattr(r, "length", None) or preset.size_bytes or 0
            read = 0
            block = 1024 * 1024
            while True:
                chunk = r.read(block)
                if not chunk:
                    break
                f.write(chunk)
                read += len(chunk)
                if total:
                    _set_state(progress=min(0.99, float(read) / float(total)))
    except Exception as e:
        # Cleanup partial
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        _set_state(status="error", message=str(e))
        raise RuntimeError(f"Failed to download preset '{preset.label}': {e}")

    # Verify
    if preset.sha256:
        try:
            digest = _sha256_file(tmp)
            if digest.lower() != preset.sha256.lower():
                tmp.unlink(missing_ok=True)
                raise RuntimeError("Checksum mismatch after download")
        except Exception:
            # If verification fails unexpectedly, remove temp and raise
            try:
                tmp.unlink()
            except Exception:
                pass
            raise

    # Move into place atomically
    tmp.replace(dst)
    _set_state(status="done", progress=1.0, path=str(dst), message="downloaded")
    return dst


def resolve_or_download_llm_model(llm_cfg: Dict[str, object], settings: Optional[Settings] = None) -> Path:
    """Resolve a local model path, downloading the preset if necessary.

    Accepts either:
      - llm_cfg["model_id"] → download preset if missing
      - llm_cfg["model_path"] → return if exists; if the filename matches a known preset and file is missing, download that preset
    """
    s = settings or Settings()
    model_id = str(llm_cfg.get("model_id", "")) if isinstance(llm_cfg, dict) else ""
    model_path_raw = str(llm_cfg.get("model_path", "")) if isinstance(llm_cfg, dict) else ""
    model_path_raw = os.path.expandvars(model_path_raw)

    if model_id:
        dst = resolve_llm_model_path_from_id(model_id, s)
        if not dst.exists():
            dst = download_llm_preset(model_id, s)
        return dst

    if model_path_raw:
        p = Path(model_path_raw)
        if p.exists():
            return p
        # Guess preset by filename
        name = p.name
        for preset in get_llm_presets():
            if preset.filename == name:
                dst = resolve_llm_model_path_from_id(preset.id, s)
                if not dst.exists():
                    dst = download_llm_preset(preset.id, s)
                return dst
        # Not a known preset; user should place the file manually
        raise FileNotFoundError(f"LLM model file not found: {p}")

    # Neither model_id nor model_path provided; choose first preset as default
    default_preset = get_llm_presets()[0]
    dst = resolve_llm_model_path_from_id(default_preset.id, s)
    if not dst.exists():
        dst = download_llm_preset(default_preset.id, s)
    return dst


def _safe_filename_from_url(url: str, fallback: str = "model.gguf") -> str:
    try:
        from urllib.parse import urlparse

        name = os.path.basename(urlparse(url).path)
        if not name:
            return fallback
        # Ensure .gguf extension
        if not name.lower().endswith(".gguf"):
            name += ".gguf"
        return name
    except Exception:
        return fallback


def download_llm_from_url(url: str, filename: Optional[str] = None, settings: Optional[Settings] = None) -> Path:
    """Download a GGUF model from an arbitrary URL without authentication.

    Stores to models/llm/<filename>. Progress is exposed via the shared state.
    """
    s = settings or Settings()
    dst_dir = get_llm_models_dir(s)
    name = filename or _safe_filename_from_url(url)
    dst = dst_dir / name
    tmp = dst.with_suffix(dst.suffix + ".part")

    # If already present, return immediately
    if dst.exists():
        _set_state(status="done", progress=1.0, message="already-present", path=str(dst))
        return dst

    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        _set_state(status="running", preset_id="custom-url", progress=0.0, message="starting", path=None)
        req = urllib.request.Request(url, headers={"User-Agent": "MeetingNotes/1.0"})
        with urllib.request.urlopen(req) as r, tmp.open("wb") as f:
            total = getattr(r, "length", None) or 0
            read = 0
            block = 1024 * 1024
            while True:
                chunk = r.read(block)
                if not chunk:
                    break
                f.write(chunk)
                read += len(chunk)
                if total:
                    _set_state(progress=min(0.99, float(read) / float(total)))
    except Exception as e:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass
        _set_state(status="error", message=str(e))
        raise RuntimeError(f"Failed to download from URL: {e}")

    tmp.replace(dst)
    _set_state(status="done", progress=1.0, path=str(dst), message="downloaded")
    return dst


