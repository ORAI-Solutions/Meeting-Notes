# Build Instructions for Meeting Notes

## Build Optionen

Es gibt jetzt **zwei Build-Varianten**:

### 1. Optimierter Build (OHNE CUDA-Bibliotheken) - EMPFOHLEN
- **Größe**: ~1.6 GB
- **CUDA-Support**: On-demand Download über die App-Settings
- **Spec-Datei**: `desktop_optimized.spec`

### 2. Vollständiger Build (MIT CUDA-Bibliotheken)  
- **Größe**: ~3.5 GB
- **CUDA-Support**: Sofort verfügbar
- **Spec-Datei**: `desktop.spec`

## Vorbereitung

### 1. Aufräumen alter Builds
```powershell
# Im backend Verzeichnis:
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
```

### 2. Dependencies aktualisieren (ohne CUDA-Runtime)
```powershell
# Die CUDA-Runtime-Pakete sind jetzt auskommentiert in pyproject.toml
uv sync
```

### 3. Frontend bauen (falls noch nicht gemacht)
```powershell
cd ../frontend
pnpm install
pnpm build
cd ../backend
```

## Build-Prozess

### Option A: Optimierter Build (EMPFOHLEN)
```powershell
# Im backend Verzeichnis:
uv run pyinstaller desktop_optimized.spec --clean --noconfirm
```

**Vorteile:**
- Kleinere Download-Größe (1.6 GB statt 3.5 GB)
- CUDA-Bibliotheken werden nur bei Bedarf heruntergeladen
- Nutzer ohne GPU sparen Speicherplatz

**Nachteile:**  
- Beim ersten GPU-Einsatz müssen ~750 MB heruntergeladen werden
- Einmaliger Download-Prozess beim ersten GPU-Feature

### Option B: Vollständiger Build (alte Methode)
Falls du die CUDA-Bibliotheken wieder einbinden willst:

1. Aktiviere die CUDA-Pakete in `pyproject.toml`:
   - Entferne die `#` vor den nvidia-cuda/cublas/cudnn Zeilen
   
2. Installiere die Pakete:
   ```powershell
   uv sync
   ```

3. Baue mit der normalen Spec:
   ```powershell
   uv run pyinstaller desktop.spec --clean --noconfirm
   ```

## Nach dem Build

Der fertige Build ist in: `backend/dist/Meeting Notes/`

### Testen des optimierten Builds:
1. Starte `Meeting Notes.exe`
2. Gehe zu Settings → GPU Runtime
3. Prüfe den Status der CUDA-Bibliotheken
4. Lade bei Bedarf die GPU-Unterstützung herunter

## Hinweise

- **CUDA-Download-Speicherort**: `%APPDATA%\MeetingNotes\cuda_runtime\`
- **Download-Größen**:
  - Whisper GPU: ~850 MB (cudnn + cublas + cudart)
  - LLaMA GPU: ~740 MB (cublasLt + cublas + cudart)
- **Internet-Verbindung**: Nur für den einmaligen CUDA-Download nötig

## Troubleshooting

Falls der Build fehlschlägt:
1. Stelle sicher, dass das Frontend gebaut wurde
2. Lösche `build/` und `dist/` Verzeichnisse
3. Führe `uv sync` erneut aus
4. Verwende `--clean` beim PyInstaller-Aufruf

