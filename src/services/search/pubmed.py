import xml.etree.ElementTree as ET

import httpx

from src.models import SearchResult, Paper, DatabaseSource
from src.services.search.base import BaseSearcher


class PubMedSearcher(BaseSearcher):

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    @property
    def source(self) -> DatabaseSource:
        return DatabaseSource.PUBMED

    async def search(self, query: str, max_results: int = 10) -> SearchResult:
        try:
            pmids, total_found = await self._esearch(query, max_results)
        except Exception as exc:
            return SearchResult(source=self.source, error=f"PubMed ESearch error: {exc}")

        if not pmids:
            return SearchResult(source=self.source, total_found=0)

        try:
            papers = await self._efetch(pmids)
        except Exception as exc:
            return SearchResult(source=self.source, error=f"PubMed EFetch error: {exc}")

        return SearchResult(
            papers=papers,
            source=self.source,
            total_found=total_found,
        )

    async def _esearch(self, query: str, max_results: int) -> tuple[list[str], int]:
        """Run ESearch and return (list of PMIDs, total count)."""
        params = {
            "db": "pubmed",
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "term": query,
        }
        async with self._get_client() as client:
            resp = await client.get(self.ESEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])
        total_found = int(result.get("count", 0))
        return pmids, total_found

    async def _efetch(self, pmids: list[str]) -> list[Paper]:
        """Fetch article details for the given PMIDs and return Paper list."""
        params = {
            "db": "pubmed",
            "retmode": "xml",
            "id": ",".join(pmids),
        }
        async with self._get_client() as client:
            resp = await client.get(self.EFETCH_URL, params=params)
            resp.raise_for_status()
            xml_text = resp.text

        root = ET.fromstring(xml_text)
        papers: list[Paper] = []

        for article_elem in root.findall(".//PubmedArticle"):
            try:
                paper = self._parse_article(article_elem)
                if paper:
                    papers.append(paper)
            except Exception:
                continue

        return papers

    def _parse_article(self, article_elem: ET.Element) -> Paper | None:
        """Parse a single PubmedArticle XML element into a Paper."""
        medline = article_elem.find(".//MedlineCitation")
        if medline is None:
            return None

        pmid_elem = medline.find("PMID")
        pmid = pmid_elem.text if pmid_elem is not None else None

        article = medline.find("Article")
        if article is None:
            return None

        # Title
        title_elem = article.find("ArticleTitle")
        title = title_elem.text if title_elem is not None and title_elem.text else "Untitled"

        # Abstract - may contain multiple AbstractText sections
        abstract_parts: list[str] = []
        abstract_elem = article.find("Abstract")
        if abstract_elem is not None:
            for text_elem in abstract_elem.findall("AbstractText"):
                label = text_elem.get("Label")
                # text_elem.text may be None; itertext() captures mixed content
                text = "".join(text_elem.itertext()).strip()
                if text:
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
        abstract = " ".join(abstract_parts) if abstract_parts else None

        # Authors
        authors: list[str] = []
        author_list = article.find("AuthorList")
        if author_list is not None:
            for author_elem in author_list.findall("Author"):
                last = author_elem.findtext("LastName", "")
                fore = author_elem.findtext("ForeName", "")
                name = f"{fore} {last}".strip()
                if name:
                    authors.append(name)

        # Journal
        journal_elem = article.find("Journal/Title")
        journal = journal_elem.text if journal_elem is not None else None

        # Year
        year = None
        year_elem = article.find(".//PubDate/Year")
        if year_elem is not None and year_elem.text:
            try:
                year = int(year_elem.text)
            except ValueError:
                pass
        # Fallback: MedlineDate
        if year is None:
            medline_date = article.findtext(".//PubDate/MedlineDate", "")
            if medline_date:
                try:
                    year = int(medline_date[:4])
                except ValueError:
                    pass

        # DOI
        doi = None
        article_id_list = article_elem.find(".//PubmedData/ArticleIdList")
        if article_id_list is not None:
            for aid in article_id_list.findall("ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = aid.text
                    break

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

        return Paper(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            journal=journal,
            url=url,
            is_oa=None,
            pdf_url=None,
            source=self.source,
            raw_id=pmid,
        )
