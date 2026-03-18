from pydantic import BaseModel
from enum import Enum
from typing import Optional


class DatabaseSource(str, Enum):
    OPENALEX = "OpenAlex"
    PUBMED = "PubMed"
    SEMANTIC_SCHOLAR = "Semantic Scholar"
    CORE = "CORE"
    SCOPUS = "Scopus"


class Paper(BaseModel):
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    journal: Optional[str] = None
    url: Optional[str] = None
    is_oa: Optional[bool] = None
    pdf_url: Optional[str] = None
    source: DatabaseSource
    raw_id: Optional[str] = None
    summary: Optional[str] = None

    @property
    def display_authors(self) -> str:
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    @property
    def filename(self) -> str:
        first_author = self.authors[0].split()[-1] if self.authors else "Unknown"
        year = self.year or "NoYear"
        short_title = "_".join(self.title.split()[:3])
        safe_title = "".join(c if c.isalnum() or c == "_" else "" for c in short_title)
        return f"{first_author}_{year}_{safe_title}.pdf"


class SearchResult(BaseModel):
    papers: list[Paper] = []
    source: DatabaseSource
    error: Optional[str] = None
    total_found: int = 0


class SearchRequest(BaseModel):
    query: str
    databases: list[DatabaseSource]
    max_results_per_db: int = 10
