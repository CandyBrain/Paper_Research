"""Session persistence using JSON files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import Paper, SearchResult, DatabaseSource


SESSIONS_DIR = Path(__file__).parent.parent.parent / "sessions"


def _paper_to_dict(paper: Paper) -> dict:
    return {
        "title": paper.title,
        "authors": paper.authors,
        "year": paper.year,
        "doi": paper.doi,
        "abstract": paper.abstract,
        "journal": paper.journal,
        "url": paper.url,
        "is_oa": paper.is_oa,
        "pdf_url": paper.pdf_url,
        "source": paper.source.value,
        "raw_id": paper.raw_id,
        "summary": paper.summary,
    }


def _dict_to_paper(d: dict) -> Paper:
    d = d.copy()
    d["source"] = DatabaseSource(d["source"])
    return Paper(**d)


def _result_to_dict(result: SearchResult) -> dict:
    return {
        "papers": [_paper_to_dict(p) for p in result.papers],
        "source": result.source.value,
        "error": result.error,
        "total_found": result.total_found,
    }


def _dict_to_result(d: dict) -> SearchResult:
    return SearchResult(
        papers=[_dict_to_paper(p) for p in d["papers"]],
        source=DatabaseSource(d["source"]),
        error=d.get("error"),
        total_found=d.get("total_found", 0),
    )


def save_session(
    name: str,
    query: str,
    search_results: list[SearchResult],
    all_papers: list[Paper],
    selected: set[int],
    dl_results: list[tuple[Paper, bool, str]],
    ai_analysis: dict | None = None,
    search_mode: str = "",
    manual_pdf_paths: dict[int, str] | None = None,
    dl_statuses: dict[int, str] | None = None,
    citations_data: dict[int, dict] | None = None,
    references_data: dict[int, dict] | None = None,
) -> Path:
    """Save current session to a JSON file."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "name": name,
        "saved_at": datetime.now().isoformat(),
        "query": query,
        "search_mode": search_mode,
        "ai_analysis": ai_analysis,
        "search_results": [_result_to_dict(r) for r in search_results],
        "all_papers": [_paper_to_dict(p) for p in all_papers],
        "selected": sorted(selected),
        "dl_results": [
            {"paper": _paper_to_dict(p), "success": s, "msg": m}
            for p, s, m in dl_results
        ],
        "manual_pdf_paths": {str(k): v for k, v in (manual_pdf_paths or {}).items()},
        "dl_statuses": {str(k): v for k, v in (dl_statuses or {}).items()},
        "citations_data": {str(k): v for k, v in (citations_data or {}).items()},
        "references_data": {str(k): v for k, v in (references_data or {}).items()},
    }

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in name)
    safe_name = safe_name.strip().replace(" ", "_")
    if not safe_name:
        safe_name = "session"
    filepath = SESSIONS_DIR / f"{safe_name}.json"

    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return filepath


def load_session(filepath: Path) -> dict[str, Any]:
    """Load a saved session from JSON file."""
    data = json.loads(filepath.read_text(encoding="utf-8"))

    return {
        "name": data.get("name", ""),
        "saved_at": data.get("saved_at", ""),
        "query": data.get("query", ""),
        "search_mode": data.get("search_mode", ""),
        "ai_analysis": data.get("ai_analysis"),
        "search_results": [_dict_to_result(r) for r in data.get("search_results", [])],
        "all_papers": [_dict_to_paper(p) for p in data.get("all_papers", [])],
        "selected": set(data.get("selected", [])),
        "dl_results": [
            (_dict_to_paper(d["paper"]), d["success"], d["msg"])
            for d in data.get("dl_results", [])
        ],
        "manual_pdf_paths": {int(k): v for k, v in data.get("manual_pdf_paths", {}).items()},
        "dl_statuses": {int(k): v for k, v in data.get("dl_statuses", {}).items()},
        "citations_data": {int(k): v for k, v in data.get("citations_data", {}).items()},
        "references_data": {int(k): v for k, v in data.get("references_data", {}).items()},
    }


def list_sessions() -> list[dict]:
    """List all saved sessions with metadata."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            search_mode = data.get("search_mode", "")
            mode_label = "🤖" if search_mode == "ai" else "🔑"
            sessions.append({
                "name": data.get("name", f.stem),
                "saved_at": data.get("saved_at", ""),
                "query": data.get("query", "")[:80],
                "paper_count": len(data.get("all_papers", [])),
                "mode_label": mode_label,
                "filepath": f,
            })
        except Exception:
            continue
    return sessions


def delete_session(filepath: Path) -> bool:
    """Delete a saved session file."""
    try:
        filepath.unlink()
        return True
    except Exception:
        return False


def autosave(
    query: str,
    search_results: list[SearchResult],
    all_papers: list[Paper],
    selected: set[int],
    dl_results: list[tuple[Paper, bool, str]],
    ai_analysis: dict | None = None,
    search_mode: str = "",
    manual_pdf_paths: dict[int, str] | None = None,
    dl_statuses: dict[int, str] | None = None,
    citations_data: dict[int, dict] | None = None,
    references_data: dict[int, dict] | None = None,
) -> Path:
    """Auto-save current state to _autosave.json."""
    return save_session(
        "_autosave",
        query, search_results, all_papers, selected, dl_results,
        ai_analysis=ai_analysis, search_mode=search_mode,
        manual_pdf_paths=manual_pdf_paths, dl_statuses=dl_statuses,
        citations_data=citations_data, references_data=references_data,
    )


def load_autosave() -> dict[str, Any] | None:
    """Load auto-saved session if it exists."""
    filepath = SESSIONS_DIR / "_autosave.json"
    if filepath.exists():
        try:
            return load_session(filepath)
        except Exception:
            return None
    return None
