"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings as env_settings
from src.services.session_manager import load_autosave

from backend.workspace import workspace
from backend.routers.search import router as search_router
from backend.routers.papers import router as papers_router, translate_router
from backend.routers.sessions import router as sessions_router
from backend.routers.export import router as export_router
from backend.routers.settings import router as settings_router
from backend.routers.projects import router as projects_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # 1. Load environment-based settings as defaults
    if env_settings.anthropic_api_key:
        workspace.anthropic_api_key = env_settings.anthropic_api_key
    if env_settings.scopus_api_key:
        workspace.scopus_api_key = env_settings.scopus_api_key
    if env_settings.core_api_key:
        workspace.core_api_key = env_settings.core_api_key
    if env_settings.proxy_url:
        workspace.proxy_url = env_settings.proxy_url
    if env_settings.papers_dir:
        workspace.download_dir = str(env_settings.papers_dir)
    workspace.max_results_per_db = env_settings.max_results_per_db

    # 2. Override with saved settings file (user's last saved settings take priority)
    from backend.routers.settings import load_settings_from_file, _save_settings_to_file
    load_settings_from_file()

    # 3. Persist merged settings so they survive restarts
    _save_settings_to_file()

    # 3. Try to load autosave (workspace data: papers, citations, etc.)
    try:
        autosave_data = load_autosave()
        if autosave_data and autosave_data.get("all_papers"):
            workspace.load_from_session(autosave_data)
            logger.info(
                "Autosave loaded: %d papers, query='%s'",
                len(workspace.papers),
                workspace.last_query[:50],
            )
        else:
            logger.info("No autosave data to load.")
    except Exception as e:
        logger.warning("Failed to load autosave: %s", e, exc_info=True)

    yield  # App runs here

    # Shutdown: nothing special needed


app = FastAPI(
    title="Paper Research Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search_router)
app.include_router(papers_router)
app.include_router(translate_router)
app.include_router(sessions_router)
app.include_router(export_router)
app.include_router(settings_router)
app.include_router(projects_router)

# Serve frontend static files if built
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
