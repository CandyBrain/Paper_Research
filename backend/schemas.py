"""Request/Response Pydantic models for the FastAPI backend."""

from pydantic import BaseModel
from typing import Optional


# ── Request Models ────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    databases: list[str]
    max_results_per_db: int = 10


class AISearchRequest(BaseModel):
    description: str
    databases: list[str]
    max_results_per_db: int = 10


class SummarizeRequest(BaseModel):
    language: str = "ko"
    download_dir: str = ""
    manual_pdf_path: str = ""


class TranslateRequest(BaseModel):
    text: str


class SettingsUpdate(BaseModel):
    anthropic_api_key: Optional[str] = None
    scopus_api_key: Optional[str] = None
    core_api_key: Optional[str] = None
    springer_api_key: Optional[str] = None
    proxy_url: Optional[str] = None
    download_dir: Optional[str] = None
    max_results_per_db: Optional[int] = None
    use_browser: Optional[bool] = None


class SessionSaveRequest(BaseModel):
    name: str


class ExportMarkdownRequest(BaseModel):
    selected_indices: list[int] = []


# ── Response Models ───────────────────────────────────────────


class PaperResponse(BaseModel):
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    journal: Optional[str] = None
    url: Optional[str] = None
    is_oa: Optional[bool] = None
    pdf_url: Optional[str] = None
    source: str
    raw_id: Optional[str] = None
    summary: Optional[str] = None
    display_authors: str = ""
    filename: str = ""


class SearchResultResponse(BaseModel):
    source: str
    papers: list[PaperResponse] = []
    error: Optional[str] = None
    total_found: int = 0


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    papers: list[PaperResponse]
    query: str
    ai_analysis: Optional[dict] = None


class PdfCandidate(BaseModel):
    url: str
    source: str

class DownloadResponse(BaseModel):
    success: bool
    message: str
    filepath: Optional[str] = None
    pdf_links: list[PdfCandidate] = []


class SummarizeResponse(BaseModel):
    summary: str


class TranslateResponse(BaseModel):
    translated: str


class CitationResponse(BaseModel):
    citations: list[dict]
    total_count: int


class ReferenceResponse(BaseModel):
    references: list[dict]
    total_count: int


class SessionInfo(BaseModel):
    name: str
    saved_at: str
    query: str
    paper_count: int
    mode_label: str


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


class SettingsResponse(BaseModel):
    anthropic_api_key: str = ""
    scopus_api_key: str = ""
    core_api_key: str = ""
    springer_api_key: str = ""
    proxy_url: str = ""
    download_dir: str = ""
    max_results_per_db: int = 10
    use_browser: bool = False


class RefreshResponse(BaseModel):
    success: bool
    message: str
    paper: Optional[PaperResponse] = None


class AttachResponse(BaseModel):
    success: bool
    message: str
    path: Optional[str] = None


# ── Project Models ─────────────────────────────────────────

class ProjectCreateRequest(BaseModel):
    name: str

class ProjectAddPapersRequest(BaseModel):
    paper_indices: list[int]

class ProjectChatRequest(BaseModel):
    message: str
    language: str = "ko"
    paper_indices: list[int] | None = None  # None = use all papers

class ProjectInfo(BaseModel):
    name: str
    created_at: str
    paper_count: int

class ProjectListResponse(BaseModel):
    projects: list[ProjectInfo]

class ChatMessage(BaseModel):
    role: str
    content: str

class ProjectDetailResponse(BaseModel):
    name: str
    papers: list[PaperResponse]
    chat_history: list[ChatMessage]
