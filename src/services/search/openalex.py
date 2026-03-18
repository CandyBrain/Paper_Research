import httpx

from src.models import SearchResult, Paper, DatabaseSource
from src.services.search.base import BaseSearcher


class OpenAlexSearcher(BaseSearcher):

    @property
    def source(self) -> DatabaseSource:
        return DatabaseSource.OPENALEX

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
        """Reconstruct abstract text from OpenAlex abstract_inverted_index format.

        The inverted index maps each word to a list of positions where it appears.
        We invert this back to a flat list sorted by position and join with spaces.
        """
        if not inverted_index:
            return None
        word_positions: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions) or None

    async def search(self, query: str, max_results: int = 10) -> SearchResult:
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "per_page": max_results,
            "sort": "relevance_score:desc",
        }
        try:
            async with self._get_client() as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return SearchResult(
                source=self.source,
                error=f"OpenAlex HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return SearchResult(source=self.source, error=f"OpenAlex error: {exc}")

        total_found = data.get("meta", {}).get("count", 0)
        papers: list[Paper] = []

        for work in data.get("results", []):
            try:
                authors = [
                    authorship["author"]["display_name"]
                    for authorship in work.get("authorships", [])
                    if authorship.get("author", {}).get("display_name")
                ]

                doi_raw = work.get("doi")
                doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None

                primary_loc = work.get("primary_location") or {}
                source_info = primary_loc.get("source") or {}
                journal = source_info.get("display_name")

                oa = work.get("open_access") or {}

                abstract = self._reconstruct_abstract(
                    work.get("abstract_inverted_index")
                )

                paper = Paper(
                    title=work.get("title") or "Untitled",
                    authors=authors,
                    year=work.get("publication_year"),
                    doi=doi,
                    abstract=abstract,
                    journal=journal,
                    url=work.get("id"),
                    is_oa=oa.get("is_oa"),
                    pdf_url=oa.get("oa_url"),
                    source=self.source,
                    raw_id=work.get("id"),
                )
                papers.append(paper)
            except Exception:
                continue

        return SearchResult(
            papers=papers,
            source=self.source,
            total_found=total_found,
        )
