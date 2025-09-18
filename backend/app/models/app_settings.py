from __future__ import annotations

from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field


class ASRSettings(BaseModel):
    """Settings for local ASR using faster-whisper."""

    # Whisper model id; we constrain to public identifiers supported by faster-whisper.
    model_id: Literal[
        "tiny",
        "base",
        "small",
        "medium",
        "large-v1",
        "large-v2",
        "large-v3",
        "distil-large-v3",
    ] = Field(default="large-v3")

    # Mode toggles decoding strategy for speed vs accuracy
    mode: Literal["fast", "accurate"] = Field(default="fast")

    # Device preference for inference
    device: Literal["auto", "cpu", "cuda"] = Field(default="auto")

    # Optional fixed language (e.g., "de", "en"); None → auto-detect
    language: Optional[str] = Field(default=None)

    # Voice activity detection
    vad: bool = Field(default=True)


class LLMSettings(BaseModel):
    """Settings for local LLM summarization model selection."""

    # Optional preset identifier from known downloads
    model_id: Optional[str] = Field(default=None)
    # Optional explicit model path to a .gguf file
    model_path: Optional[str] = Field(default=None)


class AppSettingsModel(BaseModel):
    asr: ASRSettings = Field(default_factory=ASRSettings)
    # LLM settings for summarization
    llm_device: Literal["auto", "cpu", "cuda"] = Field(default="auto")
    llm: LLMSettings = Field(default_factory=LLMSettings)

    def to_dict(self) -> Dict[str, Any]:
        # Keep compatibility with current API shape
        return self.dict()


def deep_merge_dict(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            dst[k] = deep_merge_dict(dict(dst.get(k, {})), v)
        else:
            dst[k] = v
    return dst


def migrate_settings_dict(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate arbitrary settings payload to the supported structure.

    - Preserve and coerce the 'asr' block if present; otherwise apply defaults.
    - Drop unrelated legacy keys.
    """
    result: Dict[str, Any] = {}
    asr_in = {}
    try:
        if isinstance(raw, dict) and isinstance(raw.get("asr"), dict):
            asr_in = dict(raw.get("asr") or {})
    except Exception:
        asr_in = {}

    # Normalize keys with safe fallbacks
    normalized_asr: Dict[str, Any] = {}
    normalized_asr["model_id"] = asr_in.get("model_id", "large-v3")
    normalized_asr["mode"] = asr_in.get("mode", "fast")
    dev = str(asr_in.get("device", "auto")).lower()
    normalized_asr["device"] = dev if dev in {"auto", "cpu", "cuda"} else "auto"
    normalized_asr["language"] = asr_in.get("language")
    normalized_asr["vad"] = bool(asr_in.get("vad", True))

    result["asr"] = normalized_asr

    # LLM device
    try:
        llm_dev = str(raw.get("llm_device", "auto")).lower() if isinstance(raw, dict) else "auto"
    except Exception:
        llm_dev = "auto"
    result["llm_device"] = llm_dev if llm_dev in {"auto", "cpu", "cuda"} else "auto"

    # LLM selection (preset id or explicit path)
    llm_in: Dict[str, Any] = {}
    try:
        if isinstance(raw, dict) and isinstance(raw.get("llm"), dict):
            llm_in = dict(raw.get("llm") or {})
    except Exception:
        llm_in = {}

    normalized_llm: Dict[str, Any] = {}
    try:
        mid = llm_in.get("model_id")
        normalized_llm["model_id"] = str(mid).strip() if isinstance(mid, str) and mid.strip() else None
    except Exception:
        normalized_llm["model_id"] = None

    try:
        mpath = llm_in.get("model_path")
        normalized_llm["model_path"] = str(mpath).strip() if isinstance(mpath, str) and mpath.strip() else None
    except Exception:
        normalized_llm["model_path"] = None

    result["llm"] = normalized_llm
    return result


