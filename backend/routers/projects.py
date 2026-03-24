"""Research project endpoints: create, manage papers, AI chat."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.schemas import (
    ProjectCreateRequest,
    ProjectAddPapersRequest,
    ProjectChatRequest,
    ProjectInfo,
    ProjectListResponse,
    ProjectDetailResponse,
    PaperResponse,
    ChatMessage,
)
from backend.workspace import workspace
from backend.utils import paper_to_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])

PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


def _safe_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in name)
    safe = safe.strip().replace(" ", "_")
    return safe or "project"


def _project_path(name: str) -> Path:
    return PROJECTS_DIR / f"{_safe_name(name)}.json"


def _load_project(name: str) -> dict:
    path = _project_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"프로젝트 '{name}'을 찾을 수 없습니다.")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_project(data: dict):
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _project_path(data["name"])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _paper_dict(p) -> dict:
    """Convert a Paper object or dict to a serializable dict."""
    if hasattr(p, "title"):
        return {
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "doi": p.doi,
            "abstract": p.abstract,
            "journal": p.journal,
            "url": p.url,
            "is_oa": p.is_oa,
            "pdf_url": p.pdf_url,
            "source": p.source.value if hasattr(p.source, "value") else str(p.source),
            "raw_id": p.raw_id,
            "summary": p.summary,
        }
    return p


def _paper_response(d: dict) -> PaperResponse:
    return PaperResponse(
        title=d.get("title", ""),
        authors=d.get("authors", []),
        year=d.get("year"),
        doi=d.get("doi"),
        abstract=d.get("abstract"),
        journal=d.get("journal"),
        url=d.get("url"),
        is_oa=d.get("is_oa"),
        pdf_url=d.get("pdf_url"),
        source=d.get("source", "OpenAlex"),
        raw_id=d.get("raw_id"),
        summary=d.get("summary"),
    )


# ── CRUD ──

@router.get("", response_model=ProjectListResponse)
async def list_projects():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for f in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            projects.append(ProjectInfo(
                name=data["name"],
                created_at=data.get("created_at", ""),
                paper_count=len(data.get("papers", [])),
            ))
        except Exception:
            continue
    return ProjectListResponse(projects=projects)


@router.post("")
async def create_project(req: ProjectCreateRequest):
    path = _project_path(req.name)
    if path.exists():
        raise HTTPException(status_code=409, detail="같은 이름의 프로젝트가 이미 존재합니다.")
    data = {
        "name": req.name,
        "created_at": datetime.now().isoformat(),
        "papers": [],
        "chat_history": [],
    }
    _save_project(data)
    return {"message": f"프로젝트 '{req.name}' 생성 완료"}


@router.get("/{name}", response_model=ProjectDetailResponse)
async def get_project(name: str):
    data = _load_project(name)
    return ProjectDetailResponse(
        name=data["name"],
        papers=[_paper_response(p) for p in data.get("papers", [])],
        chat_history=[ChatMessage(**m) for m in data.get("chat_history", [])],
    )


@router.delete("/{name}")
async def delete_project(name: str):
    path = _project_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"프로젝트 '{name}'을 찾을 수 없습니다.")
    path.unlink()
    return {"message": f"프로젝트 '{name}' 삭제 완료"}


# ── Paper management ──

@router.post("/{name}/papers")
async def add_papers(name: str, req: ProjectAddPapersRequest):
    data = _load_project(name)
    existing_dois = {p.get("doi") for p in data["papers"] if p.get("doi")}

    added = 0
    for idx in req.paper_indices:
        if idx < 0 or idx >= len(workspace.papers):
            continue
        paper = workspace.papers[idx]
        # Skip duplicates by DOI
        if paper.doi and paper.doi in existing_dois:
            continue
        data["papers"].append(_paper_dict(paper))
        if paper.doi:
            existing_dois.add(paper.doi)
        added += 1

    _save_project(data)
    return {"message": f"{added}편의 논문이 추가되었습니다.", "paper_count": len(data["papers"])}


@router.delete("/{name}/papers/{idx}")
async def remove_paper(name: str, idx: int):
    data = _load_project(name)
    papers = data.get("papers", [])
    if idx < 0 or idx >= len(papers):
        raise HTTPException(status_code=404, detail="논문 인덱스가 범위를 벗어났습니다.")
    removed = papers.pop(idx)
    _save_project(data)
    return {"message": f"'{removed.get('title', '')[:40]}' 제거 완료"}


# ── AI Chat ──

@router.post("/{name}/chat", response_model=ChatMessage)
async def chat(name: str, req: ProjectChatRequest):
    if not workspace.anthropic_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key가 필요합니다.")

    data = _load_project(name)
    all_papers = data.get("papers", [])

    if not all_papers:
        raise HTTPException(status_code=400, detail="프로젝트에 논문이 없습니다.")

    # Filter to selected papers if indices provided
    if req.paper_indices is not None:
        papers = [all_papers[i] for i in req.paper_indices if 0 <= i < len(all_papers)]
    else:
        papers = all_papers

    if not papers:
        raise HTTPException(status_code=400, detail="선택된 논문이 없습니다.")

    # Build paper context
    paper_context_parts = []
    for i, p in enumerate(papers):
        part = f"[논문 {i+1}] {p.get('title', 'Untitled')}"
        if p.get("authors"):
            authors = p["authors"][:3]
            part += f"\n  저자: {', '.join(authors)}"
        if p.get("year"):
            part += f" ({p['year']})"
        if p.get("journal"):
            part += f"\n  저널: {p['journal']}"
        if p.get("doi"):
            part += f"\n  DOI: {p['doi']}"
        if p.get("abstract"):
            part += f"\n  초록: {p['abstract'][:500]}"
        if p.get("summary"):
            part += f"\n  AI 요약: {p['summary'][:800]}"
        paper_context_parts.append(part)

    paper_context = "\n\n".join(paper_context_parts)

    lang_instruction = {
        "ko": "한국어로 답변하세요.",
        "en": "Answer in English.",
        "ja": "日本語で回答してください。",
        "zh": "请用中文回答。",
    }.get(req.language, "한국어로 답변하세요.")

    system_prompt = f"""당신은 학술 연구 보조 AI입니다. 아래 논문들을 기반으로 사용자의 연구를 돕습니다.

## 프로젝트: {data['name']}
## 포함된 논문 ({len(papers)}편)

{paper_context}

## 지침
- 위 논문들의 내용을 근거로 답변하세요.
- 논문을 인용할 때는 [논문 번호] 형식으로 표시하세요 (예: [논문 1]).
- 논문에 없는 내용은 일반 지식으로 보충하되, 명확히 구분해 주세요.
- 학술적으로 정확하고 체계적으로 답변하세요.
- {lang_instruction}
"""

    # Build messages from chat history (keep last 20 turns to manage tokens)
    history = data.get("chat_history", [])
    messages = []
    for m in history[-20:]:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": req.message})

    # Call Claude API
    import anthropic
    client = anthropic.Anthropic(api_key=workspace.anthropic_api_key)

    def _call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            system=system_prompt,
            messages=messages,
        )

    try:
        response = await asyncio.to_thread(_call_api)
        assistant_msg = response.content[0].text
    except Exception as e:
        logger.error("Chat API error: %s", e)
        raise HTTPException(status_code=500, detail=f"AI 응답 오류: {e}")

    # Save to history
    data["chat_history"].append({"role": "user", "content": req.message})
    data["chat_history"].append({"role": "assistant", "content": assistant_msg})
    _save_project(data)

    return ChatMessage(role="assistant", content=assistant_msg)
