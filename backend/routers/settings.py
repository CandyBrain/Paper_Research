"""Settings endpoints with file-based persistence."""

import json
import logging
from pathlib import Path
from fastapi import APIRouter

from backend.schemas import SettingsUpdate, SettingsResponse
from backend.workspace import workspace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

SETTINGS_FILE = Path(__file__).parent.parent.parent / "sessions" / "_settings.json"


def _save_settings_to_file():
    """Persist current settings to disk."""
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "anthropic_api_key": workspace.anthropic_api_key,
            "scopus_api_key": workspace.scopus_api_key,
            "core_api_key": workspace.core_api_key,
            "springer_api_key": workspace.springer_api_key,
            "proxy_url": workspace.proxy_url,
            "download_dir": workspace.download_dir,
            "max_results_per_db": workspace.max_results_per_db,
            "use_browser": workspace.use_browser,
        }
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to save settings: %s", e)


def load_settings_from_file():
    """Load settings from disk on startup."""
    if not SETTINGS_FILE.exists():
        return
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if data.get("anthropic_api_key"):
            workspace.anthropic_api_key = data["anthropic_api_key"]
        if data.get("scopus_api_key"):
            workspace.scopus_api_key = data["scopus_api_key"]
        if data.get("core_api_key"):
            workspace.core_api_key = data["core_api_key"]
        if data.get("springer_api_key"):
            workspace.springer_api_key = data["springer_api_key"]
        if data.get("proxy_url") is not None:
            workspace.proxy_url = data["proxy_url"]
        if data.get("download_dir"):
            workspace.download_dir = data["download_dir"]
        if data.get("max_results_per_db"):
            workspace.max_results_per_db = data["max_results_per_db"]
        if "use_browser" in data:
            workspace.use_browser = data["use_browser"]
        logger.info("Settings loaded from file.")
    except Exception as e:
        logger.warning("Failed to load settings from file: %s", e)


def _build_response() -> SettingsResponse:
    return SettingsResponse(
        anthropic_api_key=workspace.anthropic_api_key,
        scopus_api_key=workspace.scopus_api_key,
        core_api_key=workspace.core_api_key,
        springer_api_key=workspace.springer_api_key,
        proxy_url=workspace.proxy_url,
        download_dir=workspace.download_dir,
        max_results_per_db=workspace.max_results_per_db,
        use_browser=workspace.use_browser,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    return _build_response()


@router.get("/browse")
async def browse_dirs(path: str = ""):
    """List subdirectories at the given path for folder picker UI."""
    import platform

    if not path:
        # Return home directory as default starting point
        path = str(Path.home())

    target = Path(path)

    # For Windows drive root like "C:", fix to "C:/"
    if platform.system() == "Windows" and len(path) == 2 and path[1] == ":":
        target = Path(path + "/")

    if not target.exists() or not target.is_dir():
        return {"current": path, "parent": "", "dirs": [], "error": "경로가 존재하지 않습니다."}

    parent = str(target.parent) if target.parent != target else ""
    dirs = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                dirs.append(entry.name)
    except PermissionError:
        return {"current": str(target), "parent": parent, "dirs": [], "error": "접근 권한이 없습니다."}

    # On Windows, list drive letters when at root
    drives: list[str] = []
    if platform.system() == "Windows" and not parent:
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if Path(drive).exists():
                drives.append(f"{letter}:")

    return {"current": str(target), "parent": parent, "dirs": dirs, "drives": drives}


@router.put("", response_model=SettingsResponse)
async def update_settings(req: SettingsUpdate):
    """Update settings and persist to disk."""
    if req.anthropic_api_key is not None:
        workspace.anthropic_api_key = req.anthropic_api_key
    if req.scopus_api_key is not None:
        workspace.scopus_api_key = req.scopus_api_key
    if req.core_api_key is not None:
        workspace.core_api_key = req.core_api_key
    if req.springer_api_key is not None:
        workspace.springer_api_key = req.springer_api_key
    if req.use_browser is not None:
        workspace.use_browser = req.use_browser
    if req.proxy_url is not None:
        workspace.proxy_url = req.proxy_url
    if req.download_dir is not None:
        workspace.download_dir = req.download_dir
    if req.max_results_per_db is not None:
        workspace.max_results_per_db = req.max_results_per_db

    _save_settings_to_file()

    return _build_response()
