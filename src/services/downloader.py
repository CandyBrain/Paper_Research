"""PDF downloader service using Unpaywall API and httpx."""

import asyncio
from pathlib import Path
from urllib.parse import urlparse, quote

import httpx

from src.models import Paper


# Browser-like headers to avoid bot detection
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class ProxyHelper:
    """Handles university off-campus proxy URL generation."""

    def __init__(self, proxy_url: str = ""):
        self.proxy_url = proxy_url.strip().rstrip("/") if proxy_url else ""
        self.mode = self._detect_mode()

    def _detect_mode(self) -> str:
        """Detect proxy mode: 'prefix', 'ezproxy', or 'none'."""
        if not self.proxy_url:
            return "none"
        # URL prefix mode: ends with ?url= or similar
        if "login?url=" in self.proxy_url or "proxy?url=" in self.proxy_url:
            return "prefix"
        # If it looks like a proxy domain (e.g., libproxy.snu.ac.kr)
        parsed = urlparse(self.proxy_url)
        if parsed.hostname:
            return "ezproxy"
        return "none"

    def make_proxied_url(self, target_url: str) -> str:
        """Convert a target URL to a proxied URL."""
        if self.mode == "none":
            return target_url

        if self.mode == "prefix":
            # e.g., https://libproxy.snu.ac.kr/login?url= + target
            base = self.proxy_url
            if "?url=" in base:
                # Already has ?url= parameter
                return base + quote(target_url, safe="")
            else:
                return base + "/login?url=" + quote(target_url, safe="")

        if self.mode == "ezproxy":
            # Domain rewrite: nature.com → nature-com.libproxy.snu.ac.kr
            parsed_target = urlparse(target_url)
            parsed_proxy = urlparse(self.proxy_url)
            proxy_host = parsed_proxy.hostname or ""

            # Replace dots in target domain with hyphens, append proxy domain
            target_host = parsed_target.hostname or ""
            rewritten_host = target_host.replace(".", "-") + "." + proxy_host

            return (
                f"{parsed_target.scheme}://{rewritten_host}"
                f"{parsed_target.path}"
                + (f"?{parsed_target.query}" if parsed_target.query else "")
            )

        return target_url

    def make_doi_link(self, doi: str) -> str:
        """Create a (optionally proxied) DOI link."""
        doi_url = f"https://doi.org/{doi}"
        if self.mode != "none":
            return self.make_proxied_url(doi_url)
        return doi_url


class PaperDownloader:
    def __init__(self, email: str = "paperresearch@gmail.com", proxy_url: str = ""):
        self.email = email
        self.proxy = ProxyHelper(proxy_url)

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        )

    async def _try_download_url(
        self, url: str, referer: str = "", use_proxy: bool = False
    ) -> tuple[bool, bytes, str]:
        """Try downloading from a URL. Returns (success, content, error_msg)."""
        actual_url = self.proxy.make_proxied_url(url) if use_proxy else url
        headers = {}
        if referer:
            headers["Referer"] = (
                self.proxy.make_proxied_url(referer) if use_proxy else referer
            )

        try:
            async with self._get_client() as client:
                resp = await client.get(actual_url, headers=headers)

                if resp.status_code == 403:
                    return False, b"", f"HTTP 403 (접근 거부): {url}"
                if resp.status_code == 404:
                    return False, b"", f"HTTP 404 (없음): {url}"
                if resp.status_code != 200:
                    return False, b"", f"HTTP {resp.status_code}: {url}"

                content_type = resp.headers.get("content-type", "")
                if "html" in content_type and "pdf" not in content_type:
                    return False, b"", f"HTML 반환 (봇 차단): {url}"

                if resp.content[:5] != b"%PDF-":
                    return False, b"", f"PDF 아님: {url}"

                return True, resp.content, ""
        except httpx.TimeoutException:
            return False, b"", f"시간 초과: {url}"
        except Exception as e:
            return False, b"", f"오류 ({type(e).__name__}): {url}"

    async def find_all_pdf_urls(self, paper: Paper) -> list[dict]:
        """Find all possible PDF URLs from multiple sources, ranked by priority."""
        candidates = []

        # 1. Direct pdf_url from search API
        if paper.pdf_url:
            candidates.append({
                "url": paper.pdf_url,
                "source": "검색 API 직접 링크",
                "referer": "",
            })

        if not paper.doi:
            return candidates

        doi = paper.doi

        # 2. Unpaywall API - all OA locations
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
                resp = await client.get(
                    f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
                )
                if resp.status_code == 200:
                    data = resp.json()

                    best = data.get("best_oa_location") or {}
                    if best.get("url_for_pdf"):
                        candidates.append({
                            "url": best["url_for_pdf"],
                            "source": f"Unpaywall ({best.get('host_type', 'unknown')})",
                            "referer": best.get("url", ""),
                        })

                    for loc in data.get("oa_locations", []):
                        pdf_url = loc.get("url_for_pdf")
                        if pdf_url and not any(c["url"] == pdf_url for c in candidates):
                            candidates.append({
                                "url": pdf_url,
                                "source": f"Unpaywall ({loc.get('host_type', 'unknown')})",
                                "referer": loc.get("url", ""),
                            })
        except Exception:
            pass

        # 3. Europe PMC
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
                    f"?query=DOI:{doi}&format=json&resultType=core"
                )
                if resp.status_code == 200:
                    results = resp.json().get("resultList", {}).get("result", [])
                    for r in results:
                        pmcid = r.get("pmcid")
                        if pmcid:
                            candidates.append({
                                "url": f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf",
                                "source": f"Europe PMC ({pmcid})",
                                "referer": f"https://europepmc.org/article/PMC/{pmcid.replace('PMC', '')}",
                            })
        except Exception:
            pass

        # 4. Semantic Scholar direct PDF
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=BROWSER_HEADERS) as client:
                resp = await client.get(
                    f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    oa_pdf = data.get("openAccessPdf") or {}
                    if oa_pdf.get("url") and not any(c["url"] == oa_pdf["url"] for c in candidates):
                        candidates.append({
                            "url": oa_pdf["url"],
                            "source": "Semantic Scholar OA PDF",
                            "referer": "",
                        })
        except Exception:
            pass

        # 5. Publisher-specific patterns
        doi_suffix = doi.split("/", 1)[-1] if "/" in doi else doi
        publisher_patterns = []

        if "10.3389/" in doi:
            publisher_patterns.append({
                "url": f"https://www.frontiersin.org/articles/{doi}/pdf",
                "source": "Frontiers 직접",
                "referer": f"https://www.frontiersin.org/articles/{doi}/full",
            })
        if "10.1371/" in doi:
            publisher_patterns.append({
                "url": f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable",
                "source": "PLOS 직접",
                "referer": f"https://journals.plos.org/plosone/article?id={doi}",
            })
        if "10.3390/" in doi:
            publisher_patterns.append({
                "url": f"https://www.mdpi.com/{doi_suffix}/pdf",
                "source": "MDPI 직접",
                "referer": f"https://www.mdpi.com/{doi_suffix}",
            })
        if "10.1186/" in doi:
            publisher_patterns.append({
                "url": f"https://link.springer.com/content/pdf/{doi}.pdf",
                "source": "Springer 직접",
                "referer": f"https://link.springer.com/article/{doi}",
            })
        if "10.1038/" in doi:
            publisher_patterns.append({
                "url": f"https://www.nature.com/articles/{doi_suffix}.pdf",
                "source": "Nature 직접",
                "referer": f"https://www.nature.com/articles/{doi_suffix}",
            })

        for p in publisher_patterns:
            if not any(c["url"] == p["url"] for c in candidates):
                candidates.append(p)

        # 6. DOI resolver as last resort (publisher landing page → PDF redirect)
        candidates.append({
            "url": f"https://doi.org/{doi}",
            "source": "DOI 리다이렉트",
            "referer": "",
        })

        return candidates

    async def download_pdf(
        self, paper: Paper, output_dir: Path
    ) -> tuple[bool, str]:
        """Download a single PDF, trying multiple sources with optional proxy fallback."""
        try:
            candidates = await self.find_all_pdf_urls(paper)
        except Exception as e:
            return False, f"PDF URL 조회 실패: {str(e)}"

        if not candidates:
            link = self.proxy.make_doi_link(paper.doi) if paper.doi else "DOI 없음"
            return False, f"PDF URL을 찾을 수 없습니다. 수동 다운로드: {link}"

        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / paper.filename

        errors = []
        has_proxy = self.proxy.mode != "none"

        for candidate in candidates:
            url = candidate["url"]
            source = candidate["source"]
            referer = candidate.get("referer", "")

            # Try 1: Direct download
            success, content, error = await self._try_download_url(url, referer, use_proxy=False)
            if success:
                filepath.write_bytes(content)
                return True, str(filepath)
            errors.append(f"  [{source}] {error}")

            # Try 2: With proxy (if configured and direct failed with 403)
            if has_proxy and "403" in error:
                success, content, error_p = await self._try_download_url(
                    url, referer, use_proxy=True
                )
                if success:
                    filepath.write_bytes(content)
                    return True, str(filepath)
                errors.append(f"  [{source} + 프록시] {error_p}")

        # All failed - provide proxied DOI link for manual download
        if paper.doi:
            manual_link = self.proxy.make_doi_link(paper.doi)
        else:
            manual_link = paper.url or "링크 없음"

        error_summary = "\n".join(errors[:3])
        return False, f"모든 소스 실패. 수동 다운로드: {manual_link}\n{error_summary}"

    async def download_batch(
        self,
        papers: list[Paper],
        output_dir: Path,
        max_concurrent: int = 3,
    ) -> list[tuple[Paper, bool, str]]:
        """Download multiple PDFs with concurrency limit."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _download_with_limit(paper: Paper) -> tuple[Paper, bool, str]:
            async with semaphore:
                success, msg = await self.download_pdf(paper, output_dir)
                return paper, success, msg

        tasks = [_download_with_limit(p) for p in papers]
        return await asyncio.gather(*tasks)
