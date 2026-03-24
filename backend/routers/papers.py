"""Paper-level endpoints: download, summarize, citations, references, attach."""

import asyncio
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from src.services.downloader import PaperDownloader
from src.services.summarizer import PaperSummarizer
from src.services.citations import fetch_all_citations, fetch_all_references

from backend.schemas import (
    SummarizeRequest,
    TranslateRequest,
    DownloadResponse,
    SummarizeResponse,
    TranslateResponse,
    CitationResponse,
    ReferenceResponse,
    RefreshResponse,
    AttachResponse,
    PaperResponse,
)
from backend.workspace import workspace
from backend.utils import translate_abstract

router = APIRouter(prefix="/api/papers", tags=["papers"])


def _get_paper(idx: int):
    """Retrieve a paper by index, raising 404 if out of range."""
    if idx < 0 or idx >= len(workspace.papers):
        raise HTTPException(status_code=404, detail=f"Paper index {idx} not found.")
    return workspace.papers[idx]


@router.get("/{idx}/pdf")
async def serve_pdf(idx: int):
    """Serve the downloaded/attached PDF file for viewing."""
    _get_paper(idx)

    # Check manual pdf path first, then download path
    pdf_path = workspace.manual_pdf_paths.get(idx)
    if not pdf_path and workspace.dl_statuses.get(idx) == "success":
        # Reconstruct path from download dir + filename
        paper = workspace.papers[idx]
        candidate = Path(workspace.download_dir) / paper.filename
        if candidate.exists():
            pdf_path = str(candidate)

    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF 파일이 없습니다. 먼저 다운로드하세요.")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=\"{Path(pdf_path).name}\""},
    )


@router.post("/{idx}/download", response_model=DownloadResponse)
async def download_paper(idx: int):
    """Download PDF for the paper at the given index."""
    paper = _get_paper(idx)

    download_dir = workspace.download_dir
    if not download_dir:
        raise HTTPException(
            status_code=400,
            detail="Download directory not set. Update settings first.",
        )

    downloader = PaperDownloader(
        proxy_url=workspace.proxy_url,
        elsevier_api_key=workspace.scopus_api_key,
        springer_api_key=workspace.springer_api_key,
        use_browser=workspace.use_browser,
    )
    output_dir = Path(download_dir)

    # First, collect all candidate PDF URLs
    candidates = await downloader.find_all_pdf_urls(paper)

    success, msg = await downloader.download_pdf(paper, output_dir)

    if success:
        workspace.dl_statuses[idx] = "success"
        # Also store as manual_pdf_path so it shows as linked
        workspace.manual_pdf_paths[idx] = msg  # msg is filepath on success
    else:
        workspace.dl_statuses[idx] = "failed"

    from backend.utils import do_autosave
    do_autosave()

    # On failure, return the candidate URLs so the user can try manually
    pdf_links = []
    if not success and candidates:
        from backend.schemas import PdfCandidate
        pdf_links = [
            PdfCandidate(url=c["url"], source=c["source"])
            for c in candidates
            if c["url"] and not c["url"].startswith("https://doi.org/")
        ]
        # Also add DOI link
        if paper.doi:
            pdf_links.append(PdfCandidate(url=f"https://doi.org/{paper.doi}", source="DOI 페이지"))

    return DownloadResponse(
        success=success,
        message=msg,
        filepath=msg if success else None,
        pdf_links=pdf_links,
    )


@router.post("/{idx}/summarize", response_model=SummarizeResponse)
async def summarize_paper(idx: int, req: SummarizeRequest):
    """Summarize the paper using Claude API."""
    paper = _get_paper(idx)

    if not workspace.anthropic_api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key is required for summarization.",
        )

    summarizer = PaperSummarizer(api_key=workspace.anthropic_api_key)

    manual_path = req.manual_pdf_path or workspace.manual_pdf_paths.get(idx, "")
    download_dir = req.download_dir or workspace.download_dir

    # PaperSummarizer.summarize_paper is sync
    summary = await asyncio.to_thread(
        summarizer.summarize_paper,
        paper,
        req.language,
        download_dir,
        manual_path,
    )

    paper.summary = summary

    from backend.utils import do_autosave
    do_autosave()

    return SummarizeResponse(summary=summary)


@router.get("/{idx}/citations", response_model=CitationResponse)
async def get_citations(idx: int):
    """Fetch papers that cite this paper."""
    paper = _get_paper(idx)

    # Check cache (only use if non-empty results)
    if idx in workspace.citations_data:
        cached = workspace.citations_data[idx]
        if cached.get("citations"):
            return CitationResponse(
                citations=cached["citations"],
                total_count=cached["total_count"],
            )

    citations, total_count = await fetch_all_citations(paper)
    workspace.citations_data[idx] = {
        "citations": citations,
        "total_count": total_count,
    }

    return CitationResponse(citations=citations, total_count=total_count)


@router.get("/{idx}/references", response_model=ReferenceResponse)
async def get_references(idx: int):
    """Fetch papers referenced by this paper."""
    paper = _get_paper(idx)

    # Check cache (only use if non-empty results)
    if idx in workspace.references_data:
        cached = workspace.references_data[idx]
        if cached.get("references"):
            return ReferenceResponse(
                references=cached["references"],
                total_count=cached["total_count"],
            )

    references, total_count = await fetch_all_references(paper)
    workspace.references_data[idx] = {
        "references": references,
        "total_count": total_count,
    }

    return ReferenceResponse(references=references, total_count=total_count)


@router.post("/{idx}/refresh", response_model=RefreshResponse)
async def refresh_paper(idx: int):
    """Re-search a single paper by title to update its metadata (DOI, abstract, etc.)."""
    paper = _get_paper(idx)

    from src.services.search.openalex import OpenAlexSearcher
    from src.services.search.semantic_scholar import SemanticScholarSearcher
    from src.utils.dedup import _is_valid_paper_doi

    title = paper.title
    best = None

    # Try OpenAlex first, then Semantic Scholar
    for SearcherClass in [OpenAlexSearcher, SemanticScholarSearcher]:
        try:
            searcher = SearcherClass()
            result = await searcher.search(title, max_results=5)
            for candidate in result.papers:
                if not candidate.title:
                    continue
                # Simple title similarity check
                t1 = candidate.title.lower().strip().rstrip(".")
                t2 = title.lower().strip().rstrip(".")
                if t1 == t2 or t1 in t2 or t2 in t1:
                    if _is_valid_paper_doi(candidate.doi):
                        best = candidate
                        break
            if best:
                break
        except Exception:
            continue

    if not best:
        return RefreshResponse(success=False, message="일치하는 논문을 찾지 못했습니다.")

    # Update the paper in-place, preserving summary and source
    old_summary = paper.summary
    paper.doi = best.doi or paper.doi
    paper.abstract = best.abstract or paper.abstract
    paper.authors = best.authors if best.authors else paper.authors
    paper.year = best.year or paper.year
    paper.journal = best.journal or paper.journal
    paper.url = best.url or paper.url
    paper.is_oa = best.is_oa if best.is_oa is not None else paper.is_oa
    paper.pdf_url = best.pdf_url or paper.pdf_url
    paper.summary = old_summary  # preserve existing summary

    # Clear stale download/citation caches for this paper
    workspace.dl_statuses.pop(idx, None)
    workspace.citations_data.pop(idx, None)
    workspace.references_data.pop(idx, None)

    from backend.utils import do_autosave
    do_autosave()

    updated = PaperResponse(
        title=paper.title,
        authors=paper.authors,
        year=paper.year,
        doi=paper.doi,
        abstract=paper.abstract,
        journal=paper.journal,
        url=paper.url,
        is_oa=paper.is_oa,
        pdf_url=paper.pdf_url,
        source=paper.source.value if hasattr(paper.source, 'value') else str(paper.source),
        raw_id=paper.raw_id,
        summary=paper.summary,
    )

    return RefreshResponse(
        success=True,
        message=f"논문 정보 업데이트 완료 (DOI: {paper.doi or 'N/A'})",
        paper=updated,
    )


@router.post("/{idx}/attach", response_model=AttachResponse)
async def attach_pdf(idx: int, file: UploadFile = File(...)):
    """Upload and attach a PDF file to a paper."""
    _get_paper(idx)

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    download_dir = workspace.download_dir
    if not download_dir:
        raise HTTPException(
            status_code=400,
            detail="Download directory not set. Update settings first.",
        )

    output_dir = Path(download_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dest = output_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    workspace.manual_pdf_paths[idx] = str(dest)

    from backend.utils import do_autosave
    do_autosave()

    return AttachResponse(success=True, message=f"PDF attached: {dest}", path=str(dest))


@router.delete("/{idx}/attach", response_model=AttachResponse)
async def detach_pdf(idx: int):
    """Unlink an attached PDF from a paper (does not delete the file)."""
    _get_paper(idx)

    if idx in workspace.manual_pdf_paths:
        removed = workspace.manual_pdf_paths.pop(idx)
        from backend.utils import do_autosave
        do_autosave()
        return AttachResponse(success=True, message=f"PDF unlinked: {removed}")

    return AttachResponse(success=False, message="No PDF was attached to this paper.")


# ── Translate (not paper-specific, but grouped here) ──────────


translate_router = APIRouter(prefix="/api", tags=["papers"])


@translate_router.post("/translate", response_model=TranslateResponse)
async def translate_text(req: TranslateRequest):
    """Translate text (typically an abstract) to Korean."""
    if not workspace.anthropic_api_key:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key is required for translation.",
        )

    translated = await asyncio.to_thread(
        translate_abstract, req.text, workspace.anthropic_api_key
    )
    return TranslateResponse(translated=translated)
