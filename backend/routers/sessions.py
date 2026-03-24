"""Session management endpoints."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.services.session_manager import (
    save_session,
    load_session,
    load_autosave,
    list_sessions,
    delete_session,
    autosave,
    SESSIONS_DIR,
)

from backend.schemas import (
    SessionSaveRequest,
    SessionInfo,
    SessionListResponse,
)
from backend.workspace import workspace
from backend.utils import paper_to_response

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_filepath(name: str) -> Path:
    """Build the filepath for a session by name."""
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in name)
    safe_name = safe_name.strip().replace(" ", "_")
    if not safe_name:
        safe_name = "session"
    return SESSIONS_DIR / f"{safe_name}.json"


# ── Fixed routes MUST come before /{name} ──


@router.get("", response_model=SessionListResponse)
async def get_sessions():
    """List all saved sessions."""
    sessions = list_sessions()
    return SessionListResponse(
        sessions=[
            SessionInfo(
                name=s["name"],
                saved_at=s["saved_at"],
                query=s["query"],
                paper_count=s["paper_count"],
                mode_label=s["mode_label"],
            )
            for s in sessions
        ]
    )


@router.get("/current")
async def get_current_workspace():
    """Return the current workspace state for frontend hydration.
    If workspace is empty, try to restore from autosave first."""

    # Auto-restore from autosave if workspace is empty
    if not workspace.papers:
        try:
            autosave_data = load_autosave()
            if autosave_data and autosave_data.get("all_papers"):
                workspace.load_from_session(autosave_data)
        except Exception:
            pass

    return {
        "papers": [paper_to_response(p) for p in workspace.papers],
        "last_query": workspace.last_query,
        "search_mode": workspace.search_mode,
        "ai_analysis": workspace.ai_analysis,
        "selected": sorted(workspace.selected),
        "dl_statuses": {str(k): v for k, v in workspace.dl_statuses.items()},
        "manual_pdf_paths": {str(k): v for k, v in workspace.manual_pdf_paths.items()},
        "citations_data": {str(k): v for k, v in workspace.citations_data.items()},
        "references_data": {str(k): v for k, v in workspace.references_data.items()},
    }


@router.post("/autosave")
async def trigger_autosave():
    """Trigger an autosave of the current workspace."""
    if not workspace.papers:
        return {"message": "Nothing to autosave."}

    filepath = autosave(
        query=workspace.last_query,
        search_results=workspace.search_results,
        all_papers=workspace.papers,
        selected=workspace.selected,
        dl_results=[],
        ai_analysis=workspace.ai_analysis,
        search_mode=workspace.search_mode,
        manual_pdf_paths=workspace.manual_pdf_paths,
        dl_statuses=workspace.dl_statuses,
        citations_data=workspace.citations_data,
        references_data=workspace.references_data,
    )

    return {"message": "Autosave complete.", "filepath": str(filepath)}


# ── Dynamic routes with path parameter ──


@router.post("")
async def create_session(req: SessionSaveRequest):
    """Save the current workspace as a named session."""
    if not workspace.papers:
        raise HTTPException(status_code=400, detail="No papers to save.")

    filepath = save_session(
        name=req.name,
        query=workspace.last_query,
        search_results=workspace.search_results,
        all_papers=workspace.papers,
        selected=workspace.selected,
        dl_results=[],
        ai_analysis=workspace.ai_analysis,
        search_mode=workspace.search_mode,
        manual_pdf_paths=workspace.manual_pdf_paths,
        dl_statuses=workspace.dl_statuses,
        citations_data=workspace.citations_data,
        references_data=workspace.references_data,
    )

    return {"message": f"Session saved: {filepath.name}", "filepath": str(filepath)}


@router.get("/{name}")
async def load_session_by_name(name: str):
    """Load a saved session by name into the workspace."""
    filepath = _session_filepath(name)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Session '{name}' not found.")

    session_data = load_session(filepath)
    workspace.load_from_session(session_data)

    return {
        "message": f"Session '{name}' loaded.",
        "query": workspace.last_query,
        "paper_count": len(workspace.papers),
        "papers": [paper_to_response(p) for p in workspace.papers],
    }


@router.delete("/{name}")
async def delete_session_by_name(name: str):
    """Delete a saved session by name."""
    filepath = _session_filepath(name)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Session '{name}' not found.")

    success = delete_session(filepath)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete session.")

    return {"message": f"Session '{name}' deleted."}
