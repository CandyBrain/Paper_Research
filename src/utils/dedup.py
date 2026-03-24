import re

from src.models import Paper, SearchResult


# DOI patterns that indicate non-paper records (journals, ISSN, series, etc.)
_INVALID_DOI_PATTERNS = re.compile(
    r"^10\.\d+/issn\."           # IOP journal ISSN DOIs
    r"|^10\.\d+/journal\."       # generic journal DOIs
    r"|^10\.\d+/\d{4}-\d{3}[\dxX]$"  # bare ISSN as DOI
, re.IGNORECASE)


def _is_valid_paper_doi(doi: str | None) -> bool:
    """Check if a DOI looks like an actual paper DOI (not a journal/series)."""
    if not doi:
        return True  # no DOI is OK, just can't filter
    return not _INVALID_DOI_PATTERNS.search(doi.strip())


def deduplicate_papers(
    results: list[SearchResult] | None = None,
    papers: list[Paper] | None = None,
) -> list[Paper]:
    """Remove duplicate papers based on DOI and title similarity.

    Also filters out non-paper records (journals, ISSN DOIs, etc.).
    Accepts either a list of SearchResult objects or a flat list of Paper objects.
    Returns a deduplicated list preserving the original order.
    """
    all_papers: list[Paper] = []
    if results:
        for result in results:
            all_papers.extend(result.papers)
    if papers:
        all_papers.extend(papers)

    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[Paper] = []

    for paper in all_papers:
        # Filter out non-paper DOIs (journal/ISSN records)
        if not _is_valid_paper_doi(paper.doi):
            continue

        doi_key = paper.doi.lower().strip() if paper.doi else None
        title_key = paper.title.lower().strip()[:80] if paper.title else None

        if doi_key and doi_key in seen_dois:
            continue
        if title_key and title_key in seen_titles:
            continue

        if doi_key:
            seen_dois.add(doi_key)
        if title_key:
            seen_titles.add(title_key)
        unique.append(paper)

    return unique
