"""Citation lookup service using Semantic Scholar and OpenAlex APIs."""

import httpx
from src.models import Paper, DatabaseSource


HEADERS = {
    "User-Agent": "PaperResearchPlatform/1.0",
    "Accept": "application/json",
}


async def fetch_citations_semantic_scholar(
    paper: Paper, max_results: int = 20
) -> list[dict]:
    """Fetch citing papers from Semantic Scholar API."""
    results = []

    # Try DOI first, then title search
    paper_id = None
    if paper.doi:
        paper_id = f"DOI:{paper.doi}"
    elif paper.raw_id and paper.source == DatabaseSource.SEMANTIC_SCHOLAR:
        paper_id = paper.raw_id

    if not paper_id:
        # Search by title
        async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
            resp = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": paper.title, "limit": 1},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    paper_id = data[0].get("paperId")

    if not paper_id:
        return results

    # Fetch citations
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        resp = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations",
            params={
                "fields": "title,authors,year,externalIds,abstract,journal,isOpenAccess,openAccessPdf",
                "limit": max_results,
            },
        )
        if resp.status_code != 200:
            return results

        for item in resp.json().get("data", []):
            citing = item.get("citingPaper", {})
            if not citing.get("title"):
                continue

            authors = [
                a.get("name", "") for a in citing.get("authors", [])
            ]
            ext_ids = citing.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            oa_pdf = citing.get("openAccessPdf") or {}

            results.append({
                "title": citing["title"],
                "authors": authors,
                "year": citing.get("year"),
                "doi": doi,
                "abstract": citing.get("abstract"),
                "journal": (citing.get("journal") or {}).get("name"),
                "is_oa": citing.get("isOpenAccess", False),
                "pdf_url": oa_pdf.get("url"),
                "source": "Semantic Scholar",
            })

    return results


async def fetch_citations_openalex(
    paper: Paper, max_results: int = 20
) -> list[dict]:
    """Fetch citing papers from OpenAlex API."""
    results = []

    if not paper.doi:
        return results

    # Find the OpenAlex work ID
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        resp = await client.get(
            f"https://api.openalex.org/works/doi:{paper.doi}",
        )
        if resp.status_code != 200:
            return results
        work_id = resp.json().get("id", "")

    if not work_id:
        return results

    # Fetch citing works
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        resp = await client.get(
            "https://api.openalex.org/works",
            params={
                "filter": f"cites:{work_id}",
                "per_page": max_results,
                "sort": "cited_by_count:desc",
            },
        )
        if resp.status_code != 200:
            return results

        for work in resp.json().get("results", []):
            authors = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name")
                if name:
                    authors.append(name)

            doi = (work.get("doi") or "").replace("https://doi.org/", "")
            oa = work.get("open_access", {})
            pdf_url = oa.get("oa_url")

            results.append({
                "title": work.get("display_name", ""),
                "authors": authors,
                "year": work.get("publication_year"),
                "doi": doi or None,
                "abstract": None,  # OpenAlex doesn't return abstract in list
                "journal": (work.get("primary_location") or {}).get("source", {}).get("display_name") if work.get("primary_location") else None,
                "is_oa": oa.get("is_oa", False),
                "pdf_url": pdf_url,
                "source": "OpenAlex",
            })

    return results


async def fetch_all_citations(
    paper: Paper, max_results: int = 20
) -> tuple[list[dict], int]:
    """Fetch citations from multiple sources, deduplicate, and return.

    Returns:
        (list of citation dicts, total_citation_count)
    """
    import asyncio

    # Run both APIs concurrently
    ss_task = fetch_citations_semantic_scholar(paper, max_results)
    oa_task = fetch_citations_openalex(paper, max_results)

    try:
        ss_results, oa_results = await asyncio.gather(
            ss_task, oa_task, return_exceptions=True
        )
    except Exception:
        ss_results, oa_results = [], []

    if isinstance(ss_results, Exception):
        ss_results = []
    if isinstance(oa_results, Exception):
        oa_results = []

    # Deduplicate by DOI, preferring Semantic Scholar (has abstracts)
    seen_dois = set()
    seen_titles = set()
    merged = []

    for item in list(ss_results) + list(oa_results):
        doi = item.get("doi")
        title_lower = item.get("title", "").lower().strip()

        if doi and doi in seen_dois:
            continue
        if title_lower and title_lower in seen_titles:
            continue

        if doi:
            seen_dois.add(doi)
        if title_lower:
            seen_titles.add(title_lower)

        merged.append(item)

    # Get total citation count from Semantic Scholar
    total_count = len(merged)
    if paper.doi:
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://api.semanticscholar.org/graph/v1/paper/DOI:{paper.doi}",
                    params={"fields": "citationCount"},
                )
                if resp.status_code == 200:
                    total_count = resp.json().get("citationCount", total_count)
        except Exception:
            pass

    return merged, total_count


# ── References (papers this paper cites) ─────────────────────


async def fetch_references_semantic_scholar(
    paper: Paper, max_results: int = 50
) -> list[dict]:
    """Fetch referenced papers from Semantic Scholar API."""
    results = []

    paper_id = None
    if paper.doi:
        paper_id = f"DOI:{paper.doi}"
    elif paper.raw_id and paper.source == DatabaseSource.SEMANTIC_SCHOLAR:
        paper_id = paper.raw_id

    if not paper_id:
        async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
            resp = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={"query": paper.title, "limit": 1},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    paper_id = data[0].get("paperId")

    if not paper_id:
        return results

    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        resp = await client.get(
            f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references",
            params={
                "fields": "title,authors,year,externalIds,abstract,journal,isOpenAccess,openAccessPdf",
                "limit": max_results,
            },
        )
        if resp.status_code != 200:
            return results

        for item in resp.json().get("data", []):
            cited = item.get("citedPaper", {})
            if not cited.get("title"):
                continue

            authors = [a.get("name", "") for a in cited.get("authors", [])]
            ext_ids = cited.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            oa_pdf = cited.get("openAccessPdf") or {}

            results.append({
                "title": cited["title"],
                "authors": authors,
                "year": cited.get("year"),
                "doi": doi,
                "abstract": cited.get("abstract"),
                "journal": (cited.get("journal") or {}).get("name"),
                "is_oa": cited.get("isOpenAccess", False),
                "pdf_url": oa_pdf.get("url"),
                "source": "Semantic Scholar",
            })

    return results


async def fetch_references_openalex(
    paper: Paper, max_results: int = 50
) -> list[dict]:
    """Fetch referenced papers from OpenAlex API."""
    results = []

    if not paper.doi:
        return results

    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        resp = await client.get(
            f"https://api.openalex.org/works/doi:{paper.doi}",
        )
        if resp.status_code != 200:
            return results

        referenced_works = resp.json().get("referenced_works", [])

    if not referenced_works:
        return results

    # Fetch details for referenced works (batch by IDs)
    # OpenAlex allows filter by openalex ID with pipe separator
    work_ids = [w.split("/")[-1] for w in referenced_works[:max_results]]

    # Batch in groups of 25 (API limit)
    for batch_start in range(0, len(work_ids), 25):
        batch = work_ids[batch_start:batch_start + 25]
        ids_filter = "|".join(batch)

        async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
            resp = await client.get(
                "https://api.openalex.org/works",
                params={
                    "filter": f"openalex:{ids_filter}",
                    "per_page": 25,
                },
            )
            if resp.status_code != 200:
                continue

            for work in resp.json().get("results", []):
                authors = []
                for authorship in work.get("authorships", []):
                    author = authorship.get("author", {})
                    name = author.get("display_name")
                    if name:
                        authors.append(name)

                doi = (work.get("doi") or "").replace("https://doi.org/", "")
                oa = work.get("open_access", {})

                results.append({
                    "title": work.get("display_name", ""),
                    "authors": authors,
                    "year": work.get("publication_year"),
                    "doi": doi or None,
                    "abstract": None,
                    "journal": (work.get("primary_location") or {}).get("source", {}).get("display_name") if work.get("primary_location") else None,
                    "is_oa": oa.get("is_oa", False),
                    "pdf_url": oa.get("oa_url"),
                    "source": "OpenAlex",
                })

    return results


async def fetch_all_references(
    paper: Paper, max_results: int = 50
) -> tuple[list[dict], int]:
    """Fetch references from multiple sources, deduplicate, and return.

    Returns:
        (list of reference dicts, total_reference_count)
    """
    import asyncio

    ss_task = fetch_references_semantic_scholar(paper, max_results)
    oa_task = fetch_references_openalex(paper, max_results)

    try:
        ss_results, oa_results = await asyncio.gather(
            ss_task, oa_task, return_exceptions=True
        )
    except Exception:
        ss_results, oa_results = [], []

    if isinstance(ss_results, Exception):
        ss_results = []
    if isinstance(oa_results, Exception):
        oa_results = []

    seen_dois = set()
    seen_titles = set()
    merged = []

    for item in list(ss_results) + list(oa_results):
        doi = item.get("doi")
        title_lower = item.get("title", "").lower().strip()

        if doi and doi in seen_dois:
            continue
        if title_lower and title_lower in seen_titles:
            continue

        if doi:
            seen_dois.add(doi)
        if title_lower:
            seen_titles.add(title_lower)

        merged.append(item)

    # Get total reference count
    total_count = len(merged)
    if paper.doi:
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
                resp = await client.get(
                    f"https://api.semanticscholar.org/graph/v1/paper/DOI:{paper.doi}",
                    params={"fields": "referenceCount"},
                )
                if resp.status_code == 200:
                    total_count = resp.json().get("referenceCount", total_count)
        except Exception:
            pass

    return merged, total_count
