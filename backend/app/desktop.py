"""
Desktop application launcher for Meeting Notes.
Combines the FastAPI backend with the frontend in a single native window.
"""

from __future__ import annotations

import sys
import os
import threading
import time
import socket
from pathlib import Path
from contextlib import closing
import logging

import uvicorn
import webview
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.main import create_app
from app.config import Settings


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_free_port() -> int:
    """Find a free port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def get_frontend_path() -> Path:
    """Get the path to the frontend dist directory."""
    # In development, frontend is in ../frontend/dist relative to backend
    if hasattr(sys, '_MEIPASS'):
        # Running from PyInstaller bundle
        return Path(sys._MEIPASS) / 'frontend'
    else:
        # Running from source
        backend_dir = Path(__file__).parent.parent
        frontend_dist = backend_dir.parent / 'frontend' / 'dist'
        if frontend_dist.exists():
            return frontend_dist
        else:
            raise FileNotFoundError(
                f"Frontend dist not found at {frontend_dist}. "
                "Please build the frontend first with 'pnpm build' in the frontend directory."
            )


def create_desktop_app() -> FastAPI:
    """Create the FastAPI app configured for desktop mode."""
    app = create_app()
    
    # Get frontend path
    frontend_path = get_frontend_path()
    logger.info(f"Serving frontend from: {frontend_path}")
    
    # Mount static files for assets
    assets_path = frontend_path / 'assets'
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
    
    # Serve index.html for all other routes (SPA support)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Skip API routes
        if full_path.startswith(("api/", "ws/", "healthz")):
            return {"error": "Not Found"}, 404
        
        # Serve index.html for all other routes
        index_path = frontend_path / 'index.html'
        if index_path.exists():
            return FileResponse(str(index_path))
        else:
            return {"error": "Frontend not found"}, 404
    
    return app


class ServerThread(threading.Thread):
    """Thread to run the FastAPI server."""
    
    def __init__(self, app: FastAPI, port: int):
        super().__init__(daemon=True)
        self.app = app
        self.port = port
        self.server = None
        self._stop_event = threading.Event()
    
    def run(self):
        """Run the server."""
        config = uvicorn.Config(
            app=self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="info",
            access_log=False  # Reduce console spam
        )
        self.server = uvicorn.Server(config)
        
        logger.info(f"Starting backend server on http://127.0.0.1:{self.port}")
        self.server.run()
    
    def stop(self):
        """Stop the server."""
        if self.server:
            logger.info("Stopping backend server...")
            self.server.should_exit = True
            self._stop_event.set()


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
    """Wait for the server to be ready."""
    import requests
    
    start_time = time.time()
    url = f"http://127.0.0.1:{port}/healthz"
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                logger.info("Backend server is ready")
                return True
        except:
            pass
        time.sleep(0.1)
    
    return False


def main():
    """Main entry point for the desktop application."""
    # Ensure settings directories exist
    settings = Settings()
    settings.ensure_dirs()
    
    # Find a free port
    port = find_free_port()
    logger.info(f"Using port {port} for backend server")
    
    # Create the app
    app = create_desktop_app()
    
    # Start the server in a background thread
    server_thread = ServerThread(app, port)
    server_thread.start()
    
    # Wait for server to be ready
    if not wait_for_server(port):
        logger.error("Failed to start backend server")
        sys.exit(1)
    
    # Create and start the webview window
    window = webview.create_window(
        title="Meeting Notes",
        url=f"http://127.0.0.1:{port}",
        width=1400,
        height=900,
        resizable=True,
        fullscreen=False,
        min_size=(800, 600),
        confirm_close=False,  # We'll handle cleanup ourselves
        text_select=True,  # Allow text selection in the app
    )
    
    def on_closing():
        """Handle window closing event."""
        logger.info("Window closing, shutting down server...")
        server_thread.stop()
        return True
    
    # Attach closing handler
    window.events.closing += on_closing
    
    # Start the GUI (blocks until window is closed)
    logger.info("Starting Meeting Notes desktop application")
    webview.start(
        debug=False,  # Set to True for dev tools
        gui='edgechromium',  # Use Edge WebView2 on Windows (modern and fast)
        http_server=False  # We're using our own server
    )
    
    # Cleanup after window is closed
    logger.info("Application closed")
    server_thread.stop()
    server_thread.join(timeout=5)
    sys.exit(0)


if __name__ == "__main__":
    main()
