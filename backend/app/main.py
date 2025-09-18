from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from logging.handlers import RotatingFileHandler

from app.config import Settings
from app.models.base import init_db
from app.api.devices import router as devices_router
from app.api.meetings import router as meetings_router
from app.api.settings import router as settings_router
from app.repositories.settings import get_app_settings


settings = Settings()


def create_app() -> FastAPI:
    app = FastAPI(title="Meeting Notes Backend", version="0.1.0")

    # CORS for local dev and Tauri
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "tauri://localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        settings.ensure_dirs()
        # Minimal structured logging to local file
        try:
            log_file = settings.logs_dir / "backend.log"
            handler = RotatingFileHandler(str(log_file), maxBytes=5_000_000, backupCount=2)
            formatter = logging.Formatter(
                fmt='%(asctime)s %(levelname)s %(name)s %(message)s'
            )
            handler.setFormatter(formatter)
            root = logging.getLogger()
            if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
                root.addHandler(handler)
            root.setLevel(logging.INFO)
        except Exception:
            pass
        init_db()

        

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(devices_router)
    app.include_router(meetings_router)
    app.include_router(settings_router)
    

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):  # type: ignore[override]
        logging.getLogger("app").exception("Unhandled exception")
        return JSONResponse(status_code=500, content={"error": str(exc)})

    return app


app = create_app()


if __name__ == "__main__":
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="Meeting Notes Backend Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    
    args = parser.parse_args()
    
    uvicorn.run(
        "app.main:app" if args.reload else app,
        host=args.host,
        port=args.port,
        reload=args.reload
    )


