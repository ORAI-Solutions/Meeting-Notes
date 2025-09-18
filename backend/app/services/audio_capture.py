from __future__ import annotations

import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict

import numpy as np
import logging
import warnings
import asyncio
import soxr

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - allow import on systems without PortAudio
    sd = None

try:
    import soundcard as sc  # optional fallback for system loopback
except Exception:
    sc = None

from app.config import Settings


settings = Settings()
logger = logging.getLogger("app.audio")

# Capture tuning
DEFAULT_BLOCKSIZE = 4096  # frames; larger buffers reduce discontinuity
if sc is not None:
    # Best-effort: suppress benign discontinuity warnings from soundcard
    try:
        warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)  # type: ignore[attr-defined]
    except Exception:
        pass


@dataclass
class _StreamBundle:
    mic_stream: Optional[sd.InputStream]
    sys_stream: Optional[sd.InputStream]
    mic_wav: Optional[wave.Wave_write]  # Separate mic track
    sys_wav: Optional[wave.Wave_write]  # Separate system track
    mic_frames: int = 0
    sys_frames: int = 0
    sys_thread: Optional[threading.Thread] = None
    sys_stop_event: Optional[threading.Event] = None
    # Metadata for diagnostics
    mic_rate: Optional[int] = None
    mic_channels: Optional[int] = None
    sys_rate: Optional[int] = None
    sys_channels: Optional[int] = None
    sys_backend: Optional[str] = None  # "sounddevice" | "soundcard"
    target_rate: int = 48000


_recordings: Dict[str, _StreamBundle] = {}


def _open_wav(path: Path, channels: int, samplerate: int) -> wave.Wave_write:
    path.parent.mkdir(parents=True, exist_ok=True)
    wf = wave.open(str(path), "wb")
    wf.setnchannels(channels)
    wf.setsampwidth(2)  # int16
    wf.setframerate(samplerate)
    return wf


def _to_mono_int16(data: np.ndarray) -> np.ndarray:
    """Convert float32/other shaped buffers to mono int16 for WAV writing."""
    data_f32 = data.astype(np.float32, copy=False)
    if data_f32.ndim == 2 and data_f32.shape[1] > 1:
        data_f32 = data_f32.mean(axis=1)
    return np.clip(data_f32 * 32767.0, -32768, 32767).astype(np.int16)


def _queue_put_safe(q: asyncio.Queue, data: np.ndarray) -> None:
    try:
        q.put_nowait(data)
    except asyncio.QueueFull:
        # drop if backpressure
        pass


def start_recording(meeting_id: str, mic_device_id: Optional[str], output_device_id: Optional[str], loop: Optional[asyncio.AbstractEventLoop] = None) -> Dict[str, str]:
    if sd is None:
        raise RuntimeError("sounddevice not available")

    if meeting_id in _recordings:
        return {}

    meeting_dir = settings.audio_dir / meeting_id
    mic_path = meeting_dir / "mic.wav"  # Separate mic track
    sys_path = meeting_dir / "system.wav"  # Separate system track

    mic_stream = None
    sys_stream = None
    mic_wav = None
    sys_wav = None

    # Pre-register bundle so callbacks can reference it immediately
    bundle = _StreamBundle(
        mic_stream=None,
        sys_stream=None,
        mic_wav=None,
        sys_wav=None,
    )
    _recordings[meeting_id] = bundle
    # Open wav files lazily below per-track

    # MIC
    if mic_device_id is not None:
        mic_dev = int(mic_device_id)
    else:
        mic_dev = sd.default.device[0] if sd.default.device is not None else None
    if mic_dev is not None and mic_dev != -1:
        mic_info = sd.query_devices(mic_dev)
        mic_rate = int(mic_info.get("default_samplerate", 48000))
        mic_channels = max(1, min(2, int(mic_info.get("max_input_channels", 1)) or 1))
        def _mic_cb(indata, frames, time, status):  # noqa: ANN001 - external callback signature
            if status:  # pragma: no cover
                pass
            # Convert to float32 mono [-1,1] and resample to target
            f32 = _to_mono_int16(indata).astype(np.float32) / 32768.0
            if bundle.mic_rate and bundle.mic_rate != bundle.target_rate:
                try:
                    f32 = soxr.resample(f32, bundle.mic_rate, bundle.target_rate)
                except Exception:
                    pass
            
            # Write to separate mic track
            if bundle.mic_wav is not None:
                try:
                    bundle.mic_wav.writeframes(np.clip(f32 * 32767.0, -32768, 32767).astype(np.int16).tobytes())
                    bundle.mic_frames += f32.shape[0]
                except Exception:
                    pass
            
            # No mixed track

        mic_stream = sd.InputStream(
            device=mic_dev,
            channels=mic_channels,
            dtype="float32",
            samplerate=mic_rate,
            blocksize=DEFAULT_BLOCKSIZE,
            callback=_mic_cb,
        )
        mic_stream.start()
        bundle.mic_stream = mic_stream
        bundle.mic_rate = mic_rate
        bundle.mic_channels = mic_channels
        # Open separate mic track
        bundle.mic_wav = _open_wav(mic_path, channels=1, samplerate=bundle.target_rate)
        logger.info("Mic capture started", extra={"device": mic_info.get("name"), "rate": mic_rate, "channels": mic_channels})

    # SYSTEM LOOPBACK
    if output_device_id is not None:
        out_dev = int(output_device_id)
    else:
        out_dev = sd.default.device[1] if sd.default.device is not None else None
    if out_dev is not None and out_dev != -1:
        # Query as output device explicitly (helps with WASAPI metadata)
        try:
            out_info = sd.query_devices(out_dev, "output")
        except Exception:
            out_info = sd.query_devices(out_dev)
        out_rate = int(out_info.get("default_samplerate", 48000)) or 48000
        # Use the device's reported channel count (some headsets expose 6/8 channels); we'll downmix.
        sys_channels = max(1, int(out_info.get("max_output_channels", 2) or 2))
        # No mixed track; record system separately only

        # First try sounddevice WASAPI loopback
        try:
            wasapi = None
            try:
                wasapi = sd.WasapiSettings(loopback=True)  # type: ignore[attr-defined]
            except Exception:
                wasapi = None

            def _sys_cb(indata, frames, time, status):  # noqa: ANN001 - external callback signature
                if status:  # pragma: no cover
                    pass
                f32 = _to_mono_int16(indata).astype(np.float32) / 32768.0
                if bundle.sys_rate and bundle.sys_rate != bundle.target_rate:
                    try:
                        f32 = soxr.resample(f32, bundle.sys_rate, bundle.target_rate)
                    except Exception:
                        pass
                
                # Write to separate system track
                if bundle.sys_wav is not None:
                    try:
                        bundle.sys_wav.writeframes(np.clip(f32 * 32767.0, -32768, 32767).astype(np.int16).tobytes())
                        bundle.sys_frames += f32.shape[0]
                    except Exception:
                        pass
                
                # No mixed track

            sys_stream = sd.InputStream(
                device=out_dev,
                channels=sys_channels,
                dtype="float32",
                samplerate=out_rate,
                blocksize=DEFAULT_BLOCKSIZE,
                callback=_sys_cb,
                extra_settings=wasapi,  # type: ignore[arg-type]
            )
            sys_stream.start()
            bundle.sys_stream = sys_stream
            bundle.sys_backend = "sounddevice"
            bundle.sys_rate = out_rate
            bundle.sys_channels = sys_channels
            # Open separate system track
            bundle.sys_wav = _open_wav(sys_path, channels=1, samplerate=bundle.target_rate)
            logger.info("System loopback (sounddevice) started", extra={"device": out_info.get("name"), "rate": out_rate, "channels": sys_channels})
        except Exception:
            # Fallback to soundcard loopback using loopback microphone API
            if sc is None:
                raise
            stop_event = threading.Event()

            def _sc_loop() -> None:
                mic = None
                try:
                    # Try a loopback mic matching selected output name
                    if out_info and out_info.get("name"):
                        mic = sc.get_microphone(str(out_info.get("name")), include_loopback=True)
                except Exception:
                    mic = None
                if mic is None:
                    # Try default speaker's loopback
                    try:
                        spk = sc.default_speaker()
                        mic = sc.get_microphone(spk.name, include_loopback=True)
                    except Exception:
                        mic = None
                if mic is None:
                    return
                with mic.recorder(samplerate=out_rate, blocksize=DEFAULT_BLOCKSIZE) as rec:
                    while not stop_event.is_set():
                        data = rec.record(DEFAULT_BLOCKSIZE)
                        f32 = _to_mono_int16(data).astype(np.float32) / 32768.0
                        if bundle.sys_rate and bundle.sys_rate != bundle.target_rate:
                            try:
                                f32 = soxr.resample(f32, bundle.sys_rate, bundle.target_rate)
                            except Exception:
                                pass
                        
                        # Write to separate system track
                        if bundle.sys_wav is not None:
                            try:
                                bundle.sys_wav.writeframes(np.clip(f32 * 32767.0, -32768, 32767).astype(np.int16).tobytes())
                                bundle.sys_frames += f32.shape[0]
                            except Exception:
                                pass
                        
                        # No mixed track

            t = threading.Thread(target=_sc_loop, daemon=True)
            t.start()
            bundle.sys_stop_event = stop_event
            bundle.sys_thread = t
            bundle.sys_backend = "soundcard"
            bundle.sys_rate = out_rate
            bundle.sys_channels = sys_channels
            # Open separate system track for soundcard backend
            bundle.sys_wav = _open_wav(sys_path, channels=1, samplerate=bundle.target_rate)
            logger.info("System loopback (soundcard) started", extra={"rate": out_rate, "channels": sys_channels})

    # bundle already registered; fields were filled above

    return {
        "mic_path": str(mic_path) if bundle.mic_wav else None,
        "sys_path": str(sys_path) if bundle.sys_wav else None,
    }


def stop_recording(meeting_id: str) -> Dict[str, str]:
    bundle = _recordings.pop(meeting_id, None)
    if not bundle:
        return {}
    try:
        if bundle.mic_stream:
            bundle.mic_stream.stop(); bundle.mic_stream.close()
        if bundle.sys_stream:
            bundle.sys_stream.stop(); bundle.sys_stream.close()
        if bundle.sys_stop_event is not None:
            bundle.sys_stop_event.set()
        if bundle.sys_thread is not None:
            bundle.sys_thread.join(timeout=1.0)
    finally:
        if bundle.mic_wav:
            try:
                bundle.mic_wav.close()
            except Exception:
                pass
        if bundle.sys_wav:
            try:
                bundle.sys_wav.close()
            except Exception:
                pass
    meeting_dir = settings.audio_dir / meeting_id
    return {
        "mic_path": str(meeting_dir / "mic.wav") if bundle.mic_wav else None,
        "sys_path": str(meeting_dir / "system.wav") if bundle.sys_wav else None,
        "mic_frames": bundle.mic_frames,
        "sys_frames": bundle.sys_frames,
        "rate": bundle.target_rate,
        "channels": 1,
        "sys_backend": bundle.sys_backend,
    }

def _mix_and_write_locked(bundle: _StreamBundle) -> None:
    # removed: no mixed track
    return
