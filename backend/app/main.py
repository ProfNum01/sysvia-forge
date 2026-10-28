from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from backend.app.api.routes import router
from backend.app.core.config import Settings
from backend.app.core.middleware import BodyLimitMiddleware
from backend.app.core.migrations import upgrade_local_schema
from backend.app.models.database import Base, Inspection, audit, connect_database
from backend.app.services.catalog import ensure_catalog_references


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = settings.database_url or f"sqlite:///{settings.data_dir / 'proofsight.db'}"
    engine, sessions = connect_database(url)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        upgrade_local_schema(engine)
        ensure_catalog_references(settings.data_dir)
        with sessions() as db:
            for row in db.scalars(select(Inspection)):
                # Evidence is identified by its immutable photo UUID, not a previous
                # Windows/WSL/container absolute path. The data volume is portable.
                photo_id = str(UUID(row.photo_id))
                row.image_path = str(settings.data_dir / "uploads" / f"{photo_id}.png")
                if not row.image_width and Path(row.image_path).is_file():
                    from PIL import Image
                    with Image.open(row.image_path) as image:
                        row.image_width, row.image_height = image.size
                if row.status == "ANALYZING":
                    row.status = "PROVIDER_ERROR"
                    row.processing_stage = "INTERRUPTED"
                    row.provider_error = "Analysis was interrupted by an application restart. Retry explicitly."
                    audit(db, "ANALYSIS_INTERRUPTED", row.id)
            db.commit()
        yield
        engine.dispose()

    app = FastAPI(title="SYSVIA ProofSight", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessions = sessions
    app.state.mutations = threading.RLock()
    try:
        app.state.live_check = json.loads((settings.data_dir / "meta-live-check.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        app.state.live_check = None
    app.add_middleware(BodyLimitMiddleware, maximum_bytes=settings.max_upload_bytes + 1024 * 1024)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_credentials=False, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "Authorization", "Idempotency-Key"])

    @app.middleware("http")
    async def local_request_safety(request: Request, call_next):
        limit = settings.max_upload_bytes + 1024 * 1024
        length = request.headers.get("content-length")
        try:
            if length and int(length) > limit:
                return JSONResponse(status_code=413, content={"detail": "Request exceeds the upload limit."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid content length."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Avoid echoing input values (including an accidental credential in a form).
        return JSONResponse(status_code=422, content={"detail": "Request validation failed. Check the required fields and file type."})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse(status_code=500, content={"detail": "The operation failed. No provider credentials were included in this response."})

    app.include_router(router)
    return app


app = create_app()
