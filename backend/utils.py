"""Utility functions for the backend."""

import logging
import anthropic

from src.models import Paper
from backend.schemas import PaperResponse

logger = logging.getLogger(__name__)


def translate_abstract(text: str, api_key: str) -> str:
    """Translate abstract to Korean using Claude."""
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                "다음 학술 논문 초록을 한국어로 번역해주세요. "
                "학술 용어는 적절히 번역하되, 필요한 경우 괄호 안에 영문 원어를 병기해주세요. "
                "번역문만 출력하세요.\n\n"
                f"{text}"
            ),
        }],
    )
    return response.content[0].text.strip()


def do_autosave():
    """Trigger autosave of the current workspace state."""
    try:
        from backend.workspace import workspace
        from src.services.session_manager import autosave
        if workspace.papers:
            autosave(
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
    except Exception as e:
        logger.warning("Autosave failed: %s", e)


def paper_to_response(paper: Paper) -> PaperResponse:
    """Convert a src.models.Paper to a PaperResponse schema."""
    return PaperResponse(
        title=paper.title,
        authors=paper.authors,
        year=paper.year,
        doi=paper.doi,
        abstract=paper.abstract,
        journal=paper.journal,
        url=paper.url,
        is_oa=paper.is_oa,
        pdf_url=paper.pdf_url,
        source=paper.source.value,
        raw_id=paper.raw_id,
        summary=paper.summary,
        display_authors=paper.display_authors,
        filename=paper.filename,
    )
