# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Meeting Notes Desktop Application (Single File).
Build with: pyinstaller desktop_onefile.spec
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

# GPU-capable stacks: faster-whisper + ctranslate2 and llama-cpp
fw_data, fw_bins, fw_hidden = collect_all('faster_whisper')
datas += fw_data
binaries += fw_bins
hiddenimports += fw_hidden

try:
    binaries += collect_dynamic_libs('ctranslate2')
    hiddenimports += ['ctranslate2']
except Exception as e:
    print(f"Warning: could not collect ctranslate2 DLLs: {e}")

# Llama-cpp - REQUIRED for summarization
try:
    llama_data = collect_data_files('llama_cpp')
    llama_bins = collect_dynamic_libs('llama_cpp')
    datas += llama_data
    binaries += llama_bins
    hiddenimports += ['llama_cpp', 'llama_cpp.llama_cpp', 'llama_cpp.llama']
    print(f"Successfully collected llama-cpp-python: {len(llama_data)} data files, {len(llama_bins)} binaries")
except Exception as e:
    print(f"ERROR: Failed to collect llama-cpp-python (REQUIRED): {e}")
    print("Please ensure llama-cpp-python is properly installed:")
    print("  uv pip install llama-cpp-python")
    print("Or for CUDA support on Windows:")
    print("  uv pip install llama-cpp-python@https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.4-cu124/llama_cpp_python-0.3.4-cp311-cp311-win_amd64.whl")
    sys.exit(1)

for pkg in ['nvidia.cudnn', 'nvidia.cublas', 'nvidia.cuda_runtime']:
    try:
        binaries += collect_dynamic_libs(pkg)
        hiddenimports += [pkg]
    except Exception as e:
        print(f"Warning: could not collect {pkg}: {e}")

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
    'torch',
    'torchaudio',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Meeting Notes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Don't use UPX, can cause issues with some DLLs
    upx_exclude=[],
    runtime_tmpdir=None,
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
