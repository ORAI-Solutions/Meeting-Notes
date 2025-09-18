"""
CUDA Runtime Manager - Downloads and manages CUDA runtime libraries on demand.
This allows us to ship a smaller binary and download GPU support only when needed.
"""

import os
import sys
import hashlib
import shutil
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import requests
from app.config import Settings

@dataclass
class CUDALibrary:
    """Metadata for a CUDA runtime library."""
    name: str
    url: str
    size_mb: float
    sha256: str
    required_for: List[str]  # e.g., ["whisper_gpu", "llama_gpu"]

# CUDA 12.9 Runtime Libraries for Windows x64
# These URLs point to the official NVIDIA PyPI wheels
CUDA_LIBRARIES: Dict[str, CUDALibrary] = {
    "cublas": CUDALibrary(
        name="nvidia-cublas-cu12",
        url="https://files.pythonhosted.org/packages/45/a1/a17fade6567c57452cfc8f967a40d1035bb9301db52f27808167fbb2be2f/nvidia_cublas_cu12-12.9.1.4-py3-none-win_amd64.whl",
        size_mb=100.0,  # Estimated size, includes cuBLASLt functionality
        sha256="",  # Will need to be calculated after download
        required_for=["whisper_gpu", "llama_gpu"]  # Includes cuBLASLt functionality
    ),
    "cudart": CUDALibrary(
        name="nvidia-cuda-runtime-cu12", 
        url="https://files.pythonhosted.org/packages/59/df/e7c3a360be4f7b93cee39271b792669baeb3846c58a4df6dfcf187a7ffab/nvidia_cuda_runtime_cu12-12.9.79-py3-none-win_amd64.whl",
        size_mb=1.2,  # Estimated size
        sha256="",  # Will need to be calculated after download
        required_for=["whisper_gpu", "llama_gpu"]
    ),
    "cudnn": CUDALibrary(
        name="nvidia-cudnn-cu12",
        url="https://files.pythonhosted.org/packages/9a/ce/1af9fa57f4bbea3ce4f46997b39bdd170f3a1e2a40cda7fd7b16f0d73288/nvidia_cudnn_cu12-9.13.0.50-py3-none-win_amd64.whl",
        size_mb=800.0,  # Estimated size
        sha256="",  # Will need to be calculated after download
        required_for=["whisper_gpu"]  # Primarily for neural network operations
    )
}

class CUDAState:
    """Tracks CUDA library installation state."""
    def __init__(self):
        self.available_libraries: Dict[str, bool] = {}
        self.download_progress: Dict[str, float] = {}
        self.is_downloading = False
        self.current_download = None
        self.error_message: Optional[str] = None

cuda_state = CUDAState()

class CUDARuntimeManager:
    """Manages CUDA runtime libraries for GPU acceleration."""
    
    def __init__(self):
        self.settings = Settings()
        self.cuda_dir = Path(self.settings.appdata_dir) / "cuda_runtime"
        self.cuda_dir.mkdir(parents=True, exist_ok=True)
        self._check_installed_libraries()
        
    def _check_installed_libraries(self):
        """Check which CUDA libraries are already installed."""
        for lib_name, lib_info in CUDA_LIBRARIES.items():
            dll_name = self._get_dll_name(lib_name)
            installed = self._is_library_installed(dll_name)
            cuda_state.available_libraries[lib_name] = installed
            
    def _get_dll_name(self, lib_name: str) -> str:
        """Get the actual DLL filename for a library."""
        dll_mapping = {
            "cublas": "cublas64_12.dll",  # Also includes cublasLt64_12.dll
            "cudart": "cudart64_12.dll",
            "cudnn": "cudnn64_9.dll",
        }
        return dll_mapping.get(lib_name, f"{lib_name}.dll")
    
    def _is_library_installed(self, dll_name: str) -> bool:
        """Check if a DLL is installed in our CUDA directory or system."""
        # For cublas, check for both main DLL and cublasLt
        dlls_to_check = [dll_name]
        if dll_name == "cublas64_12.dll":
            dlls_to_check.append("cublasLt64_12.dll")
            
        for dll in dlls_to_check:
            # Check our managed directory
            if (self.cuda_dir / dll).exists():
                continue
                
            # Check if it's in the PyInstaller bundle
            if getattr(sys, 'frozen', False):
                bundle_dir = Path(sys._MEIPASS)
                if (bundle_dir / dll).exists():
                    continue
                    
            # Check system PATH
            found_in_path = False
            for path_dir in os.environ.get("PATH", "").split(os.pathsep):
                if Path(path_dir) / dll:
                    if (Path(path_dir) / dll).exists():
                        found_in_path = True
                        break
                        
            if not found_in_path:
                return False
                
        return True
    
    def get_required_libraries(self, feature: str) -> List[str]:
        """Get list of required libraries for a feature (e.g., 'whisper_gpu', 'llama_gpu')."""
        required = []
        for lib_name, lib_info in CUDA_LIBRARIES.items():
            if feature in lib_info.required_for:
                required.append(lib_name)
        return required
    
    def check_gpu_ready(self, feature: str) -> Tuple[bool, List[str]]:
        """Check if all required libraries for a feature are available."""
        required = self.get_required_libraries(feature)
        missing = []
        
        for lib_name in required:
            if not cuda_state.available_libraries.get(lib_name, False):
                missing.append(lib_name)
                
        return len(missing) == 0, missing
    
    def get_download_size(self, libraries: List[str]) -> float:
        """Get total download size in MB for the specified libraries."""
        total_mb = 0.0
        for lib_name in libraries:
            if lib_name in CUDA_LIBRARIES:
                total_mb += CUDA_LIBRARIES[lib_name].size_mb
        return total_mb
    
    def download_libraries(self, libraries: List[str], progress_callback=None) -> bool:
        """Download and install the specified CUDA libraries."""
        if cuda_state.is_downloading:
            return False
            
        cuda_state.is_downloading = True
        cuda_state.error_message = None
        
        try:
            for lib_name in libraries:
                if lib_name not in CUDA_LIBRARIES:
                    continue
                    
                lib_info = CUDA_LIBRARIES[lib_name]
                cuda_state.current_download = lib_name
                
                # Download the wheel file
                wheel_path = self.cuda_dir / f"{lib_info.name}.whl"
                if not self._download_file(lib_info.url, wheel_path, lib_name, progress_callback):
                    cuda_state.error_message = f"Failed to download {lib_name}"
                    return False
                
                # Verify checksum (skip if empty)
                if lib_info.sha256 and not self._verify_checksum(wheel_path, lib_info.sha256):
                    cuda_state.error_message = f"Checksum verification failed for {lib_name}"
                    wheel_path.unlink(missing_ok=True)
                    return False
                
                # Extract DLLs from wheel
                if not self._extract_dlls_from_wheel(wheel_path, lib_name):
                    cuda_state.error_message = f"Failed to extract {lib_name}"
                    return False
                    
                # Clean up wheel file
                wheel_path.unlink(missing_ok=True)
                
                # Mark as installed
                cuda_state.available_libraries[lib_name] = True
                
            # Add our CUDA directory to PATH if not already there
            self._update_path()
            return True
            
        except Exception as e:
            cuda_state.error_message = str(e)
            return False
        finally:
            cuda_state.is_downloading = False
            cuda_state.current_download = None
    
    def _download_file(self, url: str, dest_path: Path, lib_name: str, progress_callback=None) -> bool:
        """Download a file with progress tracking."""
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            cuda_state.download_progress[lib_name] = progress
                            
                            if progress_callback:
                                progress_callback(lib_name, progress)
                                
            return True
        except Exception as e:
            print(f"Download error: {e}")
            return False
    
    def _verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify file checksum."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        actual_sha256 = sha256_hash.hexdigest()
        
        # Log the actual checksum for future reference
        print(f"File: {file_path.name}, SHA256: {actual_sha256}")
        
        return actual_sha256 == expected_sha256
    
    def _extract_dlls_from_wheel(self, wheel_path: Path, lib_name: str) -> bool:
        """Extract DLL files from a wheel package."""
        try:
            with zipfile.ZipFile(wheel_path, 'r') as zip_ref:
                # Find and extract all DLL files
                for file_info in zip_ref.filelist:
                    if file_info.filename.endswith('.dll'):
                        # Extract to our CUDA directory
                        target_path = self.cuda_dir / Path(file_info.filename).name
                        with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
            return True
        except Exception as e:
            print(f"Extraction error: {e}")
            return False
    
    def _update_path(self):
        """Add CUDA directory to system PATH for this process."""
        cuda_path = str(self.cuda_dir)
        if cuda_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{cuda_path}{os.pathsep}{os.environ.get('PATH', '')}"
            
            # Also update sys.path for Python imports
            if cuda_path not in sys.path:
                sys.path.insert(0, cuda_path)
    
    def cleanup_unused_libraries(self):
        """Remove downloaded CUDA libraries that are no longer needed."""
        for dll_file in self.cuda_dir.glob("*.dll"):
            dll_file.unlink()
        
        # Reset state
        self._check_installed_libraries()
    
    def get_status(self) -> Dict:
        """Get current CUDA runtime status."""
        return {
            "installed_libraries": cuda_state.available_libraries,
            "is_downloading": cuda_state.is_downloading,
            "current_download": cuda_state.current_download,
            "download_progress": cuda_state.download_progress,
            "error_message": cuda_state.error_message,
            "cuda_directory": str(self.cuda_dir),
            "whisper_gpu_ready": self.check_gpu_ready("whisper_gpu")[0],
            "llama_gpu_ready": self.check_gpu_ready("llama_gpu")[0],
        }

# Global instance
_cuda_manager: Optional[CUDARuntimeManager] = None

def get_cuda_manager() -> CUDARuntimeManager:
    """Get or create the global CUDA runtime manager instance."""
    global _cuda_manager
    if _cuda_manager is None:
        _cuda_manager = CUDARuntimeManager()
    return _cuda_manager
