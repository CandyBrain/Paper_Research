from abc import ABC, abstractmethod

import httpx

from src.models import SearchResult, DatabaseSource


class BaseSearcher(ABC):
    def __init__(self, api_key: str = "", proxy_url: str = ""):
        self.api_key = api_key
        self.proxy_url = proxy_url

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> SearchResult:
        ...

    @property
    @abstractmethod
    def source(self) -> DatabaseSource:
        ...

    @property
    def requires_api_key(self) -> bool:
        return False

    @property
    def requires_proxy(self) -> bool:
        return False

    def _get_client(self) -> httpx.AsyncClient:
        kwargs = {"timeout": 30.0, "follow_redirects": True}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return httpx.AsyncClient(**kwargs)
