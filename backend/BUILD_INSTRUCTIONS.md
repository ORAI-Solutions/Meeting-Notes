# Build Instructions for Meeting Notes

## Build Options

There are now **two build variants**:

### 1. Optimized Build (WITHOUT CUDA Libraries) - RECOMMENDED
- **Size**: ~1.6 GB
- **CUDA Support**: On-demand download via app settings
- **Spec File**: `desktop_optimized.spec`

### 2. Full Build (WITH CUDA Libraries)  
- **Size**: ~3.5 GB
- **CUDA Support**: Immediately available
- **Spec File**: `desktop.spec`

## Preparation

### 1. Clean Up Old Builds
```powershell
# In the backend directory:
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
```

### 2. Update Dependencies (without CUDA Runtime)
```powershell
# The CUDA runtime packages are now commented out in pyproject.toml
uv sync
```

**Important: llama-cpp-python Installation**
The `llama-cpp-python` package is **mandatory** for the summarization feature.

If the build fails with an error that llama-cpp-python is missing:
```powershell
# For CPU-only support:
uv pip install llama-cpp-python
```

### 3. Build Frontend (if not already done)
```powershell
cd ../frontend
pnpm install
pnpm build
cd ../backend
```

## Build Process

### Option A: Optimized Build (RECOMMENDED)
```powershell
# In the backend directory:
uv run pyinstaller desktop_optimized.spec --clean --noconfirm
```

**Advantages:**
- Smaller download size (1.6 GB instead of 3.5 GB)
- CUDA libraries are downloaded only when needed
- Users without GPU save disk space

**Disadvantages:**  
- On first GPU use, ~750 MB must be downloaded
- One-time download process on first GPU feature use

### Option B: Full Build (legacy method)
If you want to include the CUDA libraries again:

1. Enable the CUDA packages in `pyproject.toml`:
   - Remove the `#` before the nvidia-cuda/cublas/cudnn lines
   
2. Install the packages:
   ```powershell
   uv sync
   ```

3. Build with the standard spec:
   ```powershell
   uv run pyinstaller desktop.spec --clean --noconfirm
   ```

## After the Build

The finished build is located in: `backend/dist/Meeting Notes/`

### Testing the Optimized Build:
1. Start `Meeting Notes.exe`
2. Go to Settings → GPU Runtime
3. Check the status of CUDA libraries
4. Download GPU support if needed

## Notes

- **CUDA Download Location**: `%APPDATA%\MeetingNotes\cuda_runtime\`
- **Download Sizes**:
  - Whisper GPU: ~850 MB (cudnn + cublas + cudart)
  - LLaMA GPU: ~740 MB (cublasLt + cublas + cudart)
- **Internet Connection**: Only required for the one-time CUDA download

## Troubleshooting

If the build fails:
1. Make sure the frontend has been built
2. Delete `build/` and `dist/` directories
3. Run `uv sync` again
4. Use `--clean` with the PyInstaller command

**llama-cpp-python Error:**
If you see this message during the build:
```
ERROR: Failed to collect llama-cpp-python (REQUIRED)
```
Then llama-cpp-python must be installed explicitly (see step 2 above).

If users receive this error in the finished build:
```
RuntimeError: llama-cpp-python is not available. Install it to enable summarization.
```
Then the package was not correctly included during the build. The build must be repeated with llama-cpp-python correctly installed.

