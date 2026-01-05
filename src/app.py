from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.config import load_config
from src.dashboard import routes
from src.storage.event_logger import EventLogger


def create_app() -> FastAPI:
    config = load_config()

    app = FastAPI(title="Accident Prediction Dashboard", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path("web/static")
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.state.config = config
    app.state.event_logger = EventLogger(Path(config.paths.event_log_abs))

    app.include_router(routes.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

