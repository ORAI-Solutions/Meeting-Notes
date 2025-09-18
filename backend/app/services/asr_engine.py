from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Callable

import numpy as np
import math

from app.config import Settings


@dataclass
class ASRConfig:
    model_id: str = "large-v3"
    device: str = "auto"  # auto|cpu|cuda
    mode: str = "fast"  # fast|accurate
    language: Optional[str] = None
    vad: bool = True


class WhisperASREngine:
    """Thin wrapper around faster-whisper WhisperModel with simple caching and presets."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or Settings()
        self._cached_key: Optional[Tuple[str, str, str]] = None
        self._model = None

    def _resolve_device_and_compute_type(self, device_pref: str) -> Tuple[str, str]:
        # Prefer GPU if available and device_pref is auto or cuda
        device = device_pref
        
        if device_pref in ["auto", "cuda"]:
            # Check if CUDA libraries are available for Whisper
            try:
                from app.services.cuda_runtime_manager import get_cuda_manager
                cuda_mgr = get_cuda_manager()
                gpu_ready, missing = cuda_mgr.check_gpu_ready("whisper_gpu")
                
                if not gpu_ready and device_pref == "cuda":
                    # User specifically requested CUDA, try to download missing libraries
                    print(f"CUDA requested but missing libraries: {missing}")
                    print("Downloading CUDA runtime libraries for GPU acceleration...")
                    success = cuda_mgr.download_libraries(missing)
                    if success:
                        print("CUDA libraries downloaded successfully")
                        device = "cuda"
                    else:
                        print("Failed to download CUDA libraries, falling back to CPU")
                        device = "cpu"
                elif gpu_ready:
                    device = "cuda"
                else:
                    # auto mode and libraries not available - use CPU
                    device = "cpu"
            except Exception as e:
                print(f"Error checking CUDA availability: {e}")
                device = "cpu"
                
        if device == "cuda":
            compute_type = "float16"
        else:
            # CPU
            compute_type = "int8"
        return device, compute_type

    def _ensure_model(self, model_id: str, device: str, compute_type: str) -> None:
        key = (model_id, device, compute_type)
        if self._model is not None and self._cached_key == key:
            return
        # Lazy import to avoid heavy module import during app startup
        from faster_whisper import WhisperModel  # type: ignore
        # Keep download_root consistent with model manager
        download_root = str((self._settings.models_dir / "whisper" / "faster-whisper").resolve())
        self._model = WhisperModel(
            model_id,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
        self._cached_key = key

    def transcribe_file(
        self,
        audio_path: Path,
        cfg: ASRConfig,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[List[dict], dict]:
        """Transcribe a single audio file into segment dicts.

        Returns (segments, info) where segments is a list of dicts:
          {"t_start_ms", "t_end_ms", "text", "confidence"}
        and info is the faster-whisper info dict-like object.
        """
        device, compute_type = self._resolve_device_and_compute_type(cfg.device)
        self._ensure_model(cfg.model_id, device, compute_type)

        # Prepare decode params by mode
        if cfg.mode == "accurate":
            decode_params = dict(
                beam_size=5,
                best_of=5,
                temperature=0.0,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
            )
        else:
            decode_params = dict(
                beam_size=1,
                best_of=1,
                temperature=0.0,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
            )

        vad_filter = bool(cfg.vad)
        language = cfg.language

        segments_out: List[dict] = []
        # Call faster-whisper
        assert self._model is not None
        # Use faster-whisper's default VAD parameters for stability
        vad_kwargs = {}

        seg_iter, info = self._model.transcribe(
            str(audio_path),
            vad_filter=vad_filter,
            language=language,
            task="transcribe",
            **decode_params,
            **vad_kwargs,
        )
        # Initial decode phase
        if progress_cb is not None:
            try:
                progress_cb(0.05, "decoding")
            except Exception:
                pass
        # Iterate and convert
        for seg in seg_iter:
            start_ms = int(seg.start * 1000.0) if seg.start is not None else 0
            end_ms = int(seg.end * 1000.0) if seg.end is not None else start_ms
            text = seg.text or ""
            # Convert avg_logprob (typically ~[-1.0, 0.0]) to [0,1] and penalize no_speech_prob
            conf = None
            try:
                avg_lp = float(getattr(seg, "avg_logprob", None)) if getattr(seg, "avg_logprob", None) is not None else None
                no_sp = float(getattr(seg, "no_speech_prob", 0.0) or 0.0)
                if avg_lp is not None:
                    base = math.exp(avg_lp)  # [-1..0] → [~0.37..1.0]
                    conf = max(0.0, min(1.0, base * (1.0 - max(0.0, min(1.0, no_sp)))))
            except Exception:
                conf = None
            segments_out.append(
                {
                    "t_start_ms": start_ms,
                    "t_end_ms": end_ms,
                    "text": text,
                    "confidence": conf,
                }
            )
            # Progress update best-effort using known duration
            if progress_cb is not None:
                try:
                    total = float(getattr(info, "duration", 0.0) or 0.0)
                    frac = 0.05
                    if total > 0:
                        frac = min(0.98, max(0.05, float(end_ms) / 1000.0 / total))
                    progress_cb(frac, "decoding")
                except Exception:
                    pass

        # info exposes language and duration
        info_out = {
            "language": getattr(info, "language", None),
            "duration": float(getattr(info, "duration", 0.0) or 0.0),
        }
        if progress_cb is not None:
            try:
                progress_cb(1.0, "completed")
            except Exception:
                pass
        return segments_out, info_out


