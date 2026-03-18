import httpx

from src.models import SearchResult, Paper, DatabaseSource
from src.services.search.base import BaseSearcher


class CoreSearcher(BaseSearcher):

    BASE_URL = "https://api.core.ac.uk/v3/search/works"

    @property
    def source(self) -> DatabaseSource:
        return DatabaseSource.CORE

    @property
    def requires_api_key(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> SearchResult:
        if not self.api_key:
            return SearchResult(
                source=self.source,
                error="CORE API key is required but not configured.",
            )

        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"q": query, "limit": max_results}

        try:
            async with self._get_client() as client:
                resp = await client.get(self.BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return SearchResult(
                source=self.source,
                error=f"CORE HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return SearchResult(source=self.source, error=f"CORE error: {exc}")

        total_found = data.get("totalHits", 0)
        papers: list[Paper] = []

        for item in data.get("results", []):
            try:
                authors = [
                    a["name"]
                    for a in item.get("authors", [])
                    if a.get("name")
                ]

                # Try multiple fields for a download/fulltext URL
                pdf_url = None
                source_urls = item.get("sourceFulltextUrls")
                if source_urls and isinstance(source_urls, list):
                    pdf_url = source_urls[0]
                if not pdf_url:
                    pdf_url = item.get("downloadUrl")

                core_id = str(item.get("id", "")) if item.get("id") else None

                paper = Paper(
                    title=item.get("title") or "Untitled",
                    authors=authors,
                    year=item.get("yearPublished"),
                    doi=item.get("doi"),
                    abstract=item.get("abstract"),
                    journal=None,
                    url=f"https://core.ac.uk/works/{core_id}" if core_id else None,
                    is_oa=True,  # CORE indexes open-access content
                    pdf_url=pdf_url,
                    source=self.source,
                    raw_id=core_id,
                )
                papers.append(paper)
            except Exception:
                continue

        return SearchResult(
            papers=papers,
            source=self.source,
            total_found=total_found,
        )
