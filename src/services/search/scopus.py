import httpx

from src.models import SearchResult, Paper, DatabaseSource
from src.services.search.base import BaseSearcher


class ScopusSearcher(BaseSearcher):

    SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
    ABSTRACT_URL = "https://api.elsevier.com/content/abstract/doi"

    @property
    def source(self) -> DatabaseSource:
        return DatabaseSource.SCOPUS

    @property
    def requires_api_key(self) -> bool:
        return True

    @property
    def requires_proxy(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 10) -> SearchResult:
        if not self.api_key:
            return SearchResult(
                source=self.source,
                error="Scopus API key is required but not configured.",
            )

        headers = {"Accept": "application/json"}
        params = {
            "query": f"TITLE-ABS-KEY({query})",
            "count": max_results,
            "sort": "relevance",
            "apiKey": self.api_key,
        }

        try:
            async with self._get_client() as client:
                resp = await client.get(
                    self.SEARCH_URL, params=params, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return SearchResult(
                source=self.source,
                error=f"Scopus HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            return SearchResult(source=self.source, error=f"Scopus error: {exc}")

        search_results = data.get("search-results", {})
        total_found = int(search_results.get("opensearch:totalResults", 0))
        entries = search_results.get("entry", [])

        papers: list[Paper] = []
        for entry in entries:
            try:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
            except Exception:
                continue

        # Attempt to fetch abstracts for papers that have a DOI
        await self._fetch_abstracts(papers)

        return SearchResult(
            papers=papers,
            source=self.source,
            total_found=total_found,
        )

    def _parse_entry(self, entry: dict) -> Paper | None:
        """Parse a single Scopus search result entry."""
        title = entry.get("dc:title")
        if not title:
            return None

        # Author - search endpoint only returns dc:creator (first author)
        creator = entry.get("dc:creator")
        authors = [creator] if creator else []

        # Year from prism:coverDate (format: YYYY-MM-DD)
        year = None
        cover_date = entry.get("prism:coverDate", "")
        if cover_date and len(cover_date) >= 4:
            try:
                year = int(cover_date[:4])
            except ValueError:
                pass

        doi = entry.get("prism:doi")
        journal = entry.get("prism:publicationName")

        # Open access: "0" or "1"
        oa_raw = entry.get("openaccess")
        is_oa = oa_raw == "1" if oa_raw is not None else None

        # Scopus ID for linking
        scopus_id = entry.get("dc:identifier", "")  # e.g. "SCOPUS_ID:12345"
        url = None
        for link in entry.get("link", []):
            if link.get("@ref") == "scopus":
                url = link.get("@href")
                break

        return Paper(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=None,  # will be filled by _fetch_abstracts
            journal=journal,
            url=url,
            is_oa=is_oa,
            pdf_url=None,
            source=self.source,
            raw_id=scopus_id.replace("SCOPUS_ID:", "") if scopus_id else None,
        )

    async def _fetch_abstracts(self, papers: list[Paper]) -> None:
        """Best-effort fetch of abstracts via the Scopus Abstract Retrieval API."""
        papers_with_doi = [p for p in papers if p.doi]
        if not papers_with_doi:
            return

        headers = {
            "Accept": "application/json",
        }

        try:
            async with self._get_client() as client:
                for paper in papers_with_doi:
                    try:
                        url = f"{self.ABSTRACT_URL}/{paper.doi}"
                        params = {"apiKey": self.api_key}
                        resp = await client.get(url, params=params, headers=headers)
                        if resp.status_code != 200:
                            continue
                        data = resp.json()
                        # Navigate the nested response structure
                        abs_resp = data.get("abstracts-retrieval-response", {})
                        coredata = abs_resp.get("coredata", {})
                        abstract = coredata.get("dc:description")
                        if abstract and isinstance(abstract, str):
                            paper.abstract = abstract.strip()
                    except Exception:
                        continue
        except Exception:
            pass
