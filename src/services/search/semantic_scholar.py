import httpx

from src.models import SearchResult, Paper, DatabaseSource
from src.services.search.base import BaseSearcher


class SemanticScholarSearcher(BaseSearcher):

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    FIELDS = "title,authors,year,abstract,venue,externalIds,isOpenAccess,openAccessPdf"

    @property
    def source(self) -> DatabaseSource:
        return DatabaseSource.SEMANTIC_SCHOLAR

    async def search(self, query: str, max_results: int = 10) -> SearchResult:
        params = {
            "query": query,
            "limit": max_results,
            "fields": self.FIELDS,
        }
        try:
            async with self._get_client() as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return SearchResult(
                source=self.source,
                error=f"Semantic Scholar HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return SearchResult(source=self.source, error=f"Semantic Scholar error: {exc}")

        total_found = data.get("total", 0)
        papers: list[Paper] = []

        for item in data.get("data", []):
            try:
                authors = [
                    a["name"]
                    for a in item.get("authors", [])
                    if a.get("name")
                ]

                external_ids = item.get("externalIds") or {}
                doi = external_ids.get("DOI")

                oa_pdf = item.get("openAccessPdf") or {}
                pdf_url = oa_pdf.get("url")

                paper_id = item.get("paperId")
                url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

                paper = Paper(
                    title=item.get("title") or "Untitled",
                    authors=authors,
                    year=item.get("year"),
                    doi=doi,
                    abstract=item.get("abstract"),
                    journal=item.get("venue") or None,
                    url=url,
                    is_oa=item.get("isOpenAccess"),
                    pdf_url=pdf_url,
                    source=self.source,
                    raw_id=paper_id,
                )
                papers.append(paper)
            except Exception:
                continue

        return SearchResult(
            papers=papers,
            source=self.source,
            total_found=total_found,
        )
