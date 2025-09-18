# Meeting Notes

Local-first Windows desktop app to record meetings, transcribe locally with Whisper (faster-whisper), and generate summaries with a local LLM (llama.cpp). Privacy by design: audio and transcripts stay on your device.

## Features
- Record microphone and system audio (WASAPI); writes `mic.wav` and `system.wav` per meeting (no mixed track)
- Local transcription via faster-whisper (CTranslate2) with optional preprocessing
- Local summarization via llama-cpp with [#ID] citations that refer to transcript segment IDs
- React + Chakra UI frontend, FastAPI backend, packaged as a Windows executable via PyInstaller

## Architecture
- Desktop shell: Python + pywebview (Edge WebView2)
- Backend: FastAPI + Uvicorn, SQLModel + SQLite (WAL), asyncio jobs
- Frontend: React + TypeScript + Vite + Chakra UI

## Requirements
- Windows 10+ (x64)
- Python 3.11 with `uv` installed
- Node 18+ with `pnpm`
- Edge WebView2 runtime (for pywebview)
- FFmpeg recommended on PATH

## Setup
```bash
# Backend deps
cd backend
uv sync

# Frontend deps
cd ../frontend
pnpm install
```

## Development (Desktop)
```powershell
# From repo root
scripts/dev_desktop.ps1
```
This builds the frontend if missing, starts the FastAPI backend on a free local port, and opens the app window via pywebview.

### Frontend build (Vite)

- The desktop backend serves the static files from `frontend/dist`. After UI changes, build the frontend so Python serves the latest version:

```bash
cd frontend
pnpm -s build
```

- The dev script only builds if `frontend/dist` is missing. If it already exists, it will NOT rebuild; run `pnpm -s build` manually and restart the desktop app.
- PyInstaller specs (`backend/desktop.spec`, `backend/desktop_onefile.spec`) require a built `frontend/dist` and will abort if it is missing.

## Development (API only)
```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Build (Desktop)
```bash
cd backend
pyinstaller desktop.spec         # onedir
# or
pyinstaller desktop_onefile.spec # onefile
```
Artifacts are produced under `backend/dist`.

## Models
- ASR: faster-whisper downloads to `%APPDATA%/MeetingNotes/models/whisper/faster-whisper`.
- LLM: Use Settings → LLM to download a preset, or point to a local GGUF path.

## Privacy
100% local-first. No telemetry. No cloud sync. All data stored under `%APPDATA%/MeetingNotes`.

## Imprint
ORAI Solutions GmbH  
Schwarzbuchenweg 1  
22391 Hamburg

Represented by: Jan Ostermann, Wael Raouf

Contact:   
Email: contact@orai-solutions.de

## License
AGPL-3.0. See [LICENSE](./LICENSE).
