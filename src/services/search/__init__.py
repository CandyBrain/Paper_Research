import asyncio

from src.models import SearchRequest, SearchResult, Paper, DatabaseSource
from src.services.search.openalex import OpenAlexSearcher
from src.services.search.pubmed import PubMedSearcher
from src.services.search.semantic_scholar import SemanticScholarSearcher
from src.services.search.core_api import CoreSearcher
from src.services.search.scopus import ScopusSearcher
from src.utils.dedup import deduplicate_papers


class SearchOrchestrator:
    def __init__(self, api_keys: dict = None, proxy_url: str = ""):
        self.api_keys = api_keys or {}
        self.proxy_url = proxy_url
        self._searchers = {
            DatabaseSource.OPENALEX: OpenAlexSearcher(),
            DatabaseSource.PUBMED: PubMedSearcher(),
            DatabaseSource.SEMANTIC_SCHOLAR: SemanticScholarSearcher(),
            DatabaseSource.CORE: CoreSearcher(
                api_key=self.api_keys.get("core", "")
            ),
            DatabaseSource.SCOPUS: ScopusSearcher(
                api_key=self.api_keys.get("scopus", ""),
                proxy_url=self.proxy_url,
            ),
        }

    async def search_all(self, request: SearchRequest) -> list[SearchResult]:
        """Search all requested databases concurrently and return results."""
        tasks = []
        task_dbs = []
        for db in request.databases:
            searcher = self._searchers.get(db)
            if searcher:
                tasks.append(searcher.search(request.query, request.max_results_per_db))
                task_dbs.append(db)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final: list[SearchResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                db = task_dbs[i]
                final.append(SearchResult(source=db, error=str(result)))
            else:
                final.append(result)
        return final

    @staticmethod
    def deduplicate(results: list[SearchResult]) -> list[Paper]:
        """Remove duplicate papers across search results using DOI and title."""
        return deduplicate_papers(results=results)
