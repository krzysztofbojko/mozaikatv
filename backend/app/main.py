from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .admin import AdminConfig, AdminControl, AdminController
from .capture import FFmpegCapture
from .catalog import discover_video_sources
from .engine import MosaicEngine
from .settings import Settings


def create_app(
    engine: MosaicEngine | None = None,
    settings: Settings | None = None,
    admin_controller: AdminControl | None = None,
    start_engine: bool = True,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime_engine = engine
        if runtime_engine is None:
            sources = await discover_video_sources(
                resolved_settings.videos_dir,
                resolved_settings.ffprobe_bin,
            )
            runtime_engine = MosaicEngine(
                sources=sources,
                capture=FFmpegCapture(
                    resolved_settings.ffmpeg_bin,
                    resolved_settings.frame_width,
                    resolved_settings.frame_height,
                ),
                frames_dir=resolved_settings.frames_dir,
                refresh_min_seconds=resolved_settings.refresh_min_seconds,
                refresh_max_seconds=resolved_settings.refresh_max_seconds,
                retained_batches=resolved_settings.retained_batches,
            )
        app.state.engine = runtime_engine
        runtime_admin = admin_controller
        if runtime_admin is None and engine is None:
            runtime_admin = await AdminController.create(
                settings=resolved_settings,
                engine=runtime_engine,
            )
        app.state.admin = runtime_admin

        task: asyncio.Task[None] | None = None
        if start_engine:
            task = asyncio.create_task(
                runtime_engine.run_forever(), name="mosaic-engine"
            )
        try:
            yield
        finally:
            runtime_engine.stop()
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Mozaika TV", version="0.1.0", lifespan=lifespan)

    def get_engine(request: Request) -> MosaicEngine:
        return request.app.state.engine

    def get_admin(request: Request) -> AdminControl:
        controller = request.app.state.admin
        if controller is None:
            raise HTTPException(
                status_code=503, detail="Panel administracyjny nie jest dostępny"
            )
        return controller

    @app.get("/api/admin/config")
    async def admin_config(request: Request):
        return get_admin(request).get_payload()

    @app.put("/api/admin/config")
    async def update_admin_config(request: Request, config: AdminConfig):
        try:
            return await get_admin(request).apply(config)
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/mosaic")
    async def mosaic(request: Request):
        state = get_engine(request).current_state
        if state is None:
            raise HTTPException(
                status_code=503, detail="Mozaika jeszcze nie jest gotowa"
            )
        return state

    @app.get("/api/health")
    async def health(request: Request):
        state = get_engine(request).current_state
        if state is None:
            return {"status": "starting", "version": 0, "sources": []}
        return {
            "status": "ok"
            if all(tile.status in {"online", "disabled"} for tile in state.tiles)
            else "degraded",
            "version": state.version,
            "sources": [
                {"id": tile.source_id, "status": tile.status, "error": tile.error}
                for tile in state.tiles
            ],
        }

    @app.get("/api/events")
    async def events(request: Request):
        async def event_stream():
            last_version = 0
            runtime_engine = get_engine(request)
            while not await request.is_disconnected():
                state = runtime_engine.current_state
                if state is not None and state.version > last_version:
                    last_version = state.version
                    yield f"event: mosaic\ndata: {state.model_dump_json()}\n\n"
                    continue
                try:
                    state = await asyncio.wait_for(
                        runtime_engine.wait_for_update(last_version),
                        timeout=15,
                    )
                    last_version = state.version
                    yield f"event: mosaic\ndata: {state.model_dump_json()}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/")
    async def root():
        return JSONResponse({"name": "Mozaika TV", "frontend": "http://localhost:8090"})

    frames_dir = (
        engine.frames_dir if engine is not None else resolved_settings.frames_dir
    )
    frames_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/frames", StaticFiles(directory=frames_dir), name="frames")
    return app


app = create_app()
