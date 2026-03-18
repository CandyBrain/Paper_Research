"""Paper summarization service using Anthropic Claude API."""

import anthropic
from pathlib import Path
from src.models import Paper


def extract_pdf_text(pdf_path: str, max_pages: int = 30) -> str:
    """Extract text from a PDF file using PyPDF2."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_path)
        pages = reader.pages[:max_pages]
        text = "\n".join(
            page.extract_text() or "" for page in pages
        )
        # Trim to ~60k chars to stay within token limits
        return text[:60000]
    except Exception as e:
        return f"[PDF 텍스트 추출 실패: {e}]"


def find_downloaded_pdf(
    paper: Paper,
    download_dir: str,
    manual_path: str = "",
) -> str | None:
    """Try to find a downloaded PDF for the given paper.

    Priority:
    1. manual_path (user explicitly linked a PDF)
    2. Exact filename match in download_dir (app-downloaded files)
    """
    # 1. User-specified path
    if manual_path and Path(manual_path).exists():
        return manual_path

    if not download_dir:
        return None

    dl_path = Path(download_dir)
    if not dl_path.exists():
        return None

    # 2. Exact filename match only (app이 다운로드한 파일)
    expected = dl_path / paper.filename
    if expected.exists():
        return str(expected)

    return None


class PaperSummarizer:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_full = "claude-sonnet-4-5-20250514"  # for full paper summary
        self.model_light = "claude-haiku-4-5-20251001"  # fallback for abstract-only

    def summarize_paper(
        self,
        paper: Paper,
        language: str = "ko",
        download_dir: str = "",
        manual_path: str = "",
    ) -> str:
        """Summarize a paper. Uses full PDF text if available, otherwise falls back to abstract."""
        lang_instruction = "한국어로 답변해주세요." if language == "ko" else "Answer in English."

        # Try to find and read full PDF
        pdf_path = find_downloaded_pdf(paper, download_dir, manual_path=manual_path)
        if pdf_path:
            full_text = extract_pdf_text(pdf_path)
            if full_text and not full_text.startswith("[PDF"):
                return self._summarize_full_paper(paper, full_text, lang_instruction)

        # Fallback: abstract-only summary
        if not paper.abstract:
            return "초록 없음 - 요약 불가" if language == "ko" else "No abstract available"

        return self._summarize_from_abstract(paper, lang_instruction)

    def _summarize_full_paper(
        self, paper: Paper, full_text: str, lang_instruction: str
    ) -> str:
        """Summarize using the full paper text."""
        prompt = f"""{lang_instruction}

다음은 학술 논문의 전체 텍스트입니다. 아래 형식에 맞춰 논문의 핵심 내용을 섹션별로 요약해주세요.
각 항목을 간결하되 핵심을 빠뜨리지 않게 작성해주세요.

**서론 (Introduction)**: 연구 배경, 문제 제기, 연구 목적 (2-3문장)
**연구 방법론 (Methodology)**: 사용된 연구 방법, 실험 설계, 분석 기법 (2-3문장)
**주요 결과 (Results)**: 핵심 실험/분석 결과 (3-4문장)
**논의 (Discussion)**: 결과의 해석, 의의, 한계점 (2-3문장)
**결론 (Conclusion)**: 최종 결론 및 향후 연구 방향 (1-2문장)

논문 제목: {paper.title}
저자: {paper.display_authors}
저널: {paper.journal or 'N/A'}
연도: {paper.year or 'N/A'}

논문 전문:
{full_text}
"""

        try:
            response = self.client.messages.create(
                model=self.model_light,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            raise RuntimeError(f"전체 논문 요약 실패: {e}") from e

    def _summarize_from_abstract(
        self, paper: Paper, lang_instruction: str
    ) -> str:
        """Fallback: summarize from abstract only (clearly marked)."""
        prompt = f"""{lang_instruction}

다음 논문의 초록을 바탕으로 아래 형식으로 요약해주세요.
(참고: PDF 원문이 없어 초록 기반 요약입니다)

**연구 목적**: (1-2문장)
**핵심 방법론**: (1-2문장)
**주요 결과**: (2-3문장)
**결론**: (1-2문장)

논문 제목: {paper.title}
저자: {paper.display_authors}
저널: {paper.journal or 'N/A'}
연도: {paper.year or 'N/A'}

초록:
{paper.abstract}
"""

        try:
            response = self.client.messages.create(
                model=self.model_light,
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            return "*(초록 기반 요약 — PDF 다운로드 후 재요약하면 전체 논문 요약이 가능합니다)*\n\n" + response.content[0].text
        except anthropic.APIConnectionError as e:
            raise RuntimeError(f"Anthropic API 연결 실패: {e}") from e
        except anthropic.RateLimitError as e:
            raise RuntimeError(f"Anthropic API 속도 제한 초과: {e}") from e
        except anthropic.APIStatusError as e:
            raise RuntimeError(f"Anthropic API 오류 (status {e.status_code}): {e}") from e

    def summarize_batch(
        self,
        papers: list[Paper],
        research_context: str = "",
        language: str = "ko",
        download_dir: str = "",
    ) -> list[Paper]:
        """Summarize multiple papers."""
        for paper in papers:
            try:
                paper.summary = self.summarize_paper(
                    paper, language, download_dir=download_dir
                )
            except Exception as e:
                paper.summary = f"요약 실패: {str(e)}"
        return papers
