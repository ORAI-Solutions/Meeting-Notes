# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Meeting Notes Desktop Application - Optimized Build.
This version excludes CUDA runtime libraries which are downloaded on demand.
Build with: pyinstaller desktop_optimized.spec
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

# Paths (PyInstaller spec lacks __file__ in some invocations)
ROOT_DIR = Path.cwd()
FRONTEND_DIST = ROOT_DIR.parent / 'frontend' / 'dist'

# Verify frontend is built
if not FRONTEND_DIST.exists():
    print(f"ERROR: Frontend not built. Run 'pnpm build' in the frontend directory first.")
    sys.exit(1)

block_cipher = None

# Collect all necessary data
datas = []
binaries = []
hiddenimports = []

# Add frontend files
datas.append((str(FRONTEND_DIST), 'frontend'))

# Collect FastAPI/Starlette data
datas += collect_data_files('fastapi')
datas += collect_data_files('starlette')

# Collect other necessary data files
datas += collect_data_files('webview')
datas += collect_data_files('certifi')

# GPU-capable stacks: faster-whisper (CTranslate2) and llama-cpp
# Collect everything needed for faster-whisper (includes ctranslate2 binaries)
fw_data, fw_bins, fw_hidden = collect_all('faster_whisper')
datas += fw_data

# IMPORTANT: Filter out CUDA runtime DLLs - they will be downloaded on demand
cuda_dlls_to_exclude = [
    'cublas64_12.dll',
    'cublasLt64_12.dll',
    'cudart64_12.dll',
    'cudnn64_9.dll',
    'cudnn64_8.dll',
    'cudnn_ops64_9.dll',
    'cudnn_ops64_8.dll',
    'cudnn_adv64_9.dll',
    'cudnn_adv64_8.dll',
    'cudnn_cnn64_9.dll',
    'cudnn_cnn64_8.dll',
]

# Filter binaries to exclude CUDA runtime DLLs
filtered_bins = []
for binary_tuple in fw_bins:
    # binary_tuple is typically (source_path, dest_dir)
    if len(binary_tuple) >= 1:
        source_path = Path(str(binary_tuple[0]))
        if source_path.name.lower() not in cuda_dlls_to_exclude:
            filtered_bins.append(binary_tuple)
        else:
            print(f"Excluding CUDA runtime DLL: {source_path.name}")

binaries += filtered_bins
hiddenimports += fw_hidden

# Ensure CTranslate2 shared libs are bundled (but exclude CUDA runtime)
try:
    ct2_libs = collect_dynamic_libs('ctranslate2')
    filtered_ct2_libs = []
    for lib_tuple in ct2_libs:
        if len(lib_tuple) >= 1:
            source_path = Path(str(lib_tuple[0]))
            if source_path.name.lower() not in cuda_dlls_to_exclude:
                filtered_ct2_libs.append(lib_tuple)
            else:
                print(f"Excluding CUDA runtime DLL from ctranslate2: {source_path.name}")
    binaries += filtered_ct2_libs
    hiddenimports += ['ctranslate2']
except Exception as e:
    print(f"Warning: could not collect ctranslate2 DLLs: {e}")

# Llama-cpp dynamic libraries (CPU/GPU builds) - but exclude CUDA runtime
try:
    datas += collect_data_files('llama_cpp')
    llama_libs = collect_dynamic_libs('llama_cpp')
    
    # Filter out CUDA runtime DLLs from llama_cpp
    filtered_llama_libs = []
    for lib_tuple in llama_libs:
        if len(lib_tuple) >= 1:
            source_path = Path(str(lib_tuple[0]))
            if source_path.name.lower() not in cuda_dlls_to_exclude:
                filtered_llama_libs.append(lib_tuple)
            else:
                print(f"Excluding CUDA runtime DLL from llama_cpp: {source_path.name}")
    
    binaries += filtered_llama_libs
    hiddenimports += ['llama_cpp']
except Exception as e:
    print(f"llama-cpp not found or incomplete, skipping extra collection: {e}")

# SKIP bundling NVIDIA CUDA/CUBLAS/CUDNN runtime DLLs - they will be downloaded on demand
# This saves approximately 750MB+ in the final build
print("Note: CUDA runtime libraries will be downloaded on first GPU use")

# Hidden imports for FastAPI and dependencies
hiddenimports += [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'sqlalchemy',
    'sqlmodel',
    'anyio',
    'sniffio',
    'httptools',
    'websockets',
    'watchfiles',
    'python-multipart',
    'sounddevice',
    'soundcard',
    'numpy',
    'scipy',
    'soxr',
    'noisereduce',
    'faster_whisper',
    'ctranslate2',
    'llama_cpp',
    # Note: We're NOT including torch here to save space
    # 'torch',
    # 'torchaudio',
    'webview',
    'webview.platforms',
    'webview.platforms.edgechromium',
    'requests',
    'certifi',
]

# Analysis
a = Analysis(
    ['app/desktop.py'],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'tkinter',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'black',
        'ruff',
        'isort',
        # Exclude torch to save significant space (if it's not needed at runtime)
        'torch',
        'torchaudio',
        'torchvision',
        # Exclude test frameworks
        'unittest',
        'test',
        'tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Meeting Notes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't use UPX, can cause issues with some DLLs
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../frontend/public/icon.ico' if (ROOT_DIR.parent / 'frontend' / 'public' / 'icon.ico').exists() else None,
    version_file=None,
    uac_admin=False,  # Don't require admin rights
    uac_uiaccess=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Meeting Notes'
)
