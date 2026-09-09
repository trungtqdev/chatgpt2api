from __future__ import annotations

from contextlib import asynccontextmanager
from threading import Event

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api import accounts, ai, image_tasks, register, system
from api.support import resolve_web_asset, start_limited_account_watcher
from services.backup_service import backup_service
from services.config import config


def create_app() -> FastAPI:
    app_version = config.app_version

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop_event = Event()
        thread = start_limited_account_watcher(stop_event)
        backup_service.start()
        config.cleanup_old_images()
        try:
            yield
        finally:
            stop_event.set()
            thread.join(timeout=1)
            backup_service.stop()

    app = FastAPI(title="chatgpt2api", version=app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def ip_whitelist_middleware(request: Request, call_next):
        if request.url.path.startswith("/v1/") and request.method != "OPTIONS":
            from api.support import extract_bearer_token, _legacy_admin_identity
            from services.auth_service import auth_service
            from services.ip_filter import check_api_ip_allowed

            identity = None
            auth_header = request.headers.get("authorization") or request.headers.get("x-api-key")
            token = extract_bearer_token(auth_header) or str(auth_header or "").strip()
            if token:
                identity = _legacy_admin_identity(token) or auth_service.authenticate(token)

            try:
                check_api_ip_allowed(request, identity=identity)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content=exc.detail)

        return await call_next(request)
    app.include_router(ai.create_router())
    app.include_router(accounts.create_router())
    app.include_router(image_tasks.create_router())
    app.include_router(register.create_router())
    app.include_router(system.create_router(app_version))
    if config.images_dir.exists():
        app.mount("/images", StaticFiles(directory=str(config.images_dir)), name="images")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_web(full_path: str):
        asset = resolve_web_asset(full_path)
        if asset is not None:
            return FileResponse(asset)
        if full_path.strip("/").startswith("_next/"):
            raise HTTPException(status_code=404, detail="Not Found")
        fallback = resolve_web_asset("")
        if fallback is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(fallback)

    return app
