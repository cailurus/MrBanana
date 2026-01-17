import os

from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from api.routes.download import router as download_router
from api.routes.library import router as library_router
from api.routes.player import router as player_router
from api.routes.scrape import router as scrape_router
from api.routes.search import router as search_router
from api.routes.subscription import router as subscription_router
from api.routes.system import router as system_router
from api.routes.version import router as version_router
from api.routes.ws import router as ws_router
from api.constants import API_VERSION
from api.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="Mr. Banana API", version=API_VERSION, lifespan=lifespan)

    # CORS configuration for internal network use
    # In production, consider restricting to specific origins
    allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Create versioned API router
    # Note: Routes already use /api/ prefix in their definitions
    # This maintains backward compatibility while enabling future versioning
    app.include_router(download_router, tags=["download"])
    app.include_router(library_router, tags=["library"])
    app.include_router(player_router, tags=["player"])
    app.include_router(scrape_router, tags=["scrape"])
    app.include_router(search_router, tags=["search"])
    app.include_router(subscription_router, tags=["subscription"])
    app.include_router(system_router, tags=["system"])
    app.include_router(version_router, tags=["version"])
    app.include_router(ws_router, tags=["websocket"])

    # --- Static Files (Frontend) ---
    # Must be mounted after API routes as a fallback for SPA.
    if os.path.exists("static"):
        app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

        @app.get("/favicon.svg")
        async def read_favicon():
            favicon_path = "static/favicon.svg"
            if os.path.exists(favicon_path):
                return FileResponse(favicon_path, media_type="image/svg+xml")
            raise HTTPException(status_code=404)

        @app.get("/")
        async def read_index():
            return FileResponse("static/index.html")

        @app.get("/{full_path:path}")
        async def catch_all(full_path: str):
            if full_path.startswith("api"):
                raise HTTPException(status_code=404)
            # Serve static files if they exist (e.g., .svg, .png, etc.)
            static_file = f"static/{full_path}"
            if os.path.exists(static_file) and os.path.isfile(static_file):
                return FileResponse(static_file)
            return FileResponse("static/index.html")
    else:

        @app.get("/")
        async def root():
            return {"message": "Mr. Banana API is running (Frontend not found. Please build web/ and place in static/)"}

    return app


app = create_app()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
