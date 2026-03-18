from src.models import Paper, SearchResult


def deduplicate_papers(
    results: list[SearchResult] | None = None,
    papers: list[Paper] | None = None,
) -> list[Paper]:
    """Remove duplicate papers based on DOI and title similarity.

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
