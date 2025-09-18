from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

try:
    import sounddevice as sd
except Exception:
    sd = None  # Allow import on systems without PortAudio yet


router = APIRouter(prefix="/devices", tags=["devices"])


class Device(BaseModel):
    id: str
    name: str
    kind: str  # input | output
    is_default: bool = False


@router.get("")
def list_devices() -> dict[str, list[Device]]:
    inputs: list[Device] = []
    outputs: list[Device] = []

    if sd is None:
        return {"inputs": inputs, "outputs": outputs}

    try:
        devices = sd.query_devices()
        default_input = sd.default.device[0] if sd.default.device is not None else None
        default_output = sd.default.device[1] if sd.default.device is not None else None
        for idx, dev in enumerate(devices):
            name = dev.get("name", f"Device {idx}")
            if dev.get("max_input_channels", 0) > 0:
                inputs.append(Device(id=str(idx), name=name, kind="input", is_default=(idx == default_input)))
            if dev.get("max_output_channels", 0) > 0:
                outputs.append(Device(id=str(idx), name=name, kind="output", is_default=(idx == default_output)))
    except Exception:
        # Fail softly; return empty lists if PortAudio not available
        pass

    return {"inputs": inputs, "outputs": outputs}


