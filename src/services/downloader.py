"""PDF downloader service using Unpaywall API, httpx, and optional Playwright."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse, quote

import httpx

from src.models import Paper

logger = logging.getLogger(__name__)


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
    """Handles university off-campus proxy URL generation.

    Supported proxy modes:
      - prefix:      https://libproxy.snu.ac.kr/login?url=<encoded_target>
      - path_prefix: https://libra.cnu.ac.kr/_Lib_Proxy_Url/<target_url>
      - ezproxy:     https://www-nature-com.libproxy.example.ac.kr/path
      - none:        no proxy
    """

    def __init__(self, proxy_url: str = ""):
        self.proxy_url = proxy_url.strip().rstrip("/") if proxy_url else ""
        self.mode = self._detect_mode()

    def _detect_mode(self) -> str:
        """Auto-detect proxy mode from the URL pattern."""
        if not self.proxy_url:
            return "none"
        # URL parameter mode: ?url= in the proxy URL
        if "?url=" in self.proxy_url:
            return "prefix"
        # Path prefix mode: /_Lib_Proxy_Url or similar path-based proxy
        if "/_Lib_Proxy_Url" in self.proxy_url or "/_proxy/" in self.proxy_url.lower():
            return "path_prefix"
        # Check if the URL itself has a path component that acts as proxy prefix
        parsed = urlparse(self.proxy_url)
        if parsed.path and parsed.path not in ("/", ""):
            # Has a path like /login?url= or /_Lib_Proxy_Url
            if "login" in parsed.path.lower():
                return "prefix"
            return "path_prefix"
        # Default: EZproxy domain rewrite
        if parsed.hostname:
            return "ezproxy"
        return "none"

    def make_proxied_url(self, target_url: str) -> str:
        """Convert a target URL to a proxied URL."""
        if self.mode == "none":
            return target_url

        if self.mode == "prefix":
            # e.g., https://libproxy.snu.ac.kr/login?url= + encoded target
            base = self.proxy_url
            if "?url=" in base:
                return base + quote(target_url, safe="")
            else:
                return base + "/login?url=" + quote(target_url, safe="")

        if self.mode == "path_prefix":
            # e.g., https://libra.cnu.ac.kr/_Lib_Proxy_Url/ + raw target URL
            base = self.proxy_url.rstrip("/")
            return f"{base}/{target_url}"

        if self.mode == "ezproxy":
            # Domain rewrite: nature.com → nature-com.libproxy.example.ac.kr
            parsed_target = urlparse(target_url)
            parsed_proxy = urlparse(self.proxy_url)
            proxy_host = parsed_proxy.hostname or ""

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

    def get_login_url(self, target_url: str = "") -> str:
        """Get the proxy login page URL."""
        if self.mode == "none":
            return ""
        parsed = urlparse(self.proxy_url)
        host = parsed.hostname or ""
        scheme = parsed.scheme or "https"
        if target_url:
            return f"{scheme}://{host}/login?url={quote(target_url, safe='')}"
        return f"{scheme}://{host}/login"


class PaperDownloader:
    def __init__(self, email: str = "paperresearch@gmail.com", proxy_url: str = "",
                 elsevier_api_key: str = "", springer_api_key: str = "",
                 use_browser: bool = False):
        self.email = email
        self.proxy = ProxyHelper(proxy_url)
        self.elsevier_api_key = elsevier_api_key
        self.springer_api_key = springer_api_key
        self.use_browser = use_browser

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

    async def _try_elsevier_api(self, doi: str) -> tuple[bool, bytes, str]:
        """Try downloading PDF via Elsevier Article Retrieval API."""
        if not self.elsevier_api_key:
            return False, b"", "Elsevier API key 없음"

        url = f"https://api.elsevier.com/content/article/doi/{doi}"
        headers = {
            "X-ELS-APIKey": self.elsevier_api_key,
            "Accept": "application/pdf",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
                    return True, resp.content, ""
                return False, b"", f"Elsevier API HTTP {resp.status_code}"
        except Exception as e:
            return False, b"", f"Elsevier API 오류: {type(e).__name__}"

    async def _try_springer_api(self, doi: str) -> tuple[bool, bytes, str]:
        """Try downloading PDF via Springer Nature Open Access API."""
        if not self.springer_api_key:
            return False, b"", "Springer API key 없음"

        # Step 1: Get metadata with PDF URL from OpenAccess JSON endpoint
        meta_url = (
            f"https://api.springernature.com/openaccess/json"
            f"?api_key={self.springer_api_key}&q=doi:{doi}"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(meta_url)
                if resp.status_code != 200:
                    return False, b"", f"Springer API HTTP {resp.status_code}"

                data = resp.json()
                records = data.get("records", [])
                if not records:
                    return False, b"", "Springer API: 논문을 찾을 수 없음"

                # Extract PDF URL from the record
                pdf_url = ""
                for record in records:
                    for url_entry in record.get("url", []):
                        if url_entry.get("format") == "pdf":
                            pdf_url = url_entry.get("value", "")
                            break
                    if pdf_url:
                        break

                if not pdf_url:
                    return False, b"", "Springer API: PDF URL 없음 (OA 아닐 수 있음)"

                # Step 2: Download the actual PDF
                pdf_resp = await client.get(pdf_url, headers=BROWSER_HEADERS)
                if pdf_resp.status_code == 200 and pdf_resp.content[:5] == b"%PDF-":
                    return True, pdf_resp.content, ""
                return False, b"", f"Springer PDF 다운로드 실패: HTTP {pdf_resp.status_code}"
        except Exception as e:
            return False, b"", f"Springer API 오류: {type(e).__name__}"

    async def _try_browser_download(self, url: str, referer: str = "") -> tuple[bool, bytes, str]:
        """Try downloading PDF using Playwright browser automation (Cloudflare bypass)."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return False, b"", "Playwright 미설치 (pip install playwright)"

        urls_to_try = [url]
        # Also try proxy URL if configured
        if self.proxy.mode != "none":
            proxied = self.proxy.make_proxied_url(url)
            if proxied != url:
                urls_to_try.append(proxied)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)

                for try_url in urls_to_try:
                    context = await browser.new_context(
                        user_agent=BROWSER_HEADERS["User-Agent"],
                        accept_downloads=True,
                    )
                    pdf_content = await self._browser_attempt(context, try_url)
                    await context.close()

                    if pdf_content and pdf_content[:5] == b"%PDF-":
                        await browser.close()
                        return True, pdf_content, ""

                    # Check if proxy redirected to login page
                    if try_url != url and not pdf_content:
                        login_url = self._get_proxy_login_url(url)
                        if login_url:
                            await browser.close()
                            return False, b"", (
                                f"프록시 로그인 필요. 브라우저에서 먼저 로그인하세요: {login_url}"
                            )

                await browser.close()
                return False, b"", "브라우저 다운로드 실패"
        except Exception as e:
            return False, b"", f"브라우저 오류: {type(e).__name__}: {e}"

    async def _browser_attempt(self, context, url: str) -> bytes:
        """Single browser download attempt. Returns PDF bytes or empty."""
        page = await context.new_page()
        pdf_content: bytes = b""

        # Capture both download events and PDF responses simultaneously
        download_future: asyncio.Future[bytes] = asyncio.get_event_loop().create_future()
        captured: list[bytes] = []

        async def on_download(download):
            try:
                path = await download.path()
                if path:
                    data = Path(path).read_bytes()
                    if not download_future.done():
                        download_future.set_result(data)
            except Exception:
                if not download_future.done():
                    download_future.set_result(b"")

        async def on_response(response):
            ct = response.headers.get("content-type", "")
            if "pdf" in ct:
                try:
                    body = await response.body()
                    if body[:5] == b"%PDF-":
                        captured.append(body)
                        if not download_future.done():
                            download_future.set_result(body)
                except Exception:
                    pass

        page.on("download", on_download)
        page.on("response", on_response)

        try:
            await page.goto(url, timeout=20000)
        except Exception:
            pass  # "Download is starting" error is expected

        # Wait for download with short timeout
        try:
            pdf_content = await asyncio.wait_for(download_future, timeout=15)
        except asyncio.TimeoutError:
            pass

        # Use captured response if download event didn't fire
        if (not pdf_content or pdf_content[:5] != b"%PDF-") and captured:
            pdf_content = captured[0]

        # Check for login page (proxy auth required)
        if not pdf_content or pdf_content[:5] != b"%PDF-":
            try:
                final_url = page.url or ""
                if "login" in final_url.lower():
                    return b""
            except Exception:
                pass

        return pdf_content

    def _get_proxy_login_url(self, target_url: str) -> str:
        """Generate proxy login URL for manual authentication."""
        return self.proxy.get_login_url(target_url)

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

        # 1.5 Publisher API shortcuts (highest priority)
        if self.elsevier_api_key and any(
            doi.startswith(p) for p in ["10.1016/", "10.1006/"]
        ):
            candidates.insert(0, {
                "url": f"__elsevier_api__:{doi}",
                "source": "Elsevier API",
                "referer": "",
            })

        if self.springer_api_key and any(
            doi.startswith(p) for p in [
                "10.1007/", "10.1186/", "10.1038/",
                "10.1140/", "10.1023/", "10.1365/",
                "10.1057/", "10.1245/", "10.1617/",
            ]
        ):
            candidates.insert(0, {
                "url": f"__springer_api__:{doi}",
                "source": "Springer Nature API",
                "referer": "",
            })

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
                        # Extract PMC ID from Unpaywall URL and add NCBI PMC PDF
                        loc_url = loc.get("url") or ""
                        import re
                        pmc_match = re.search(r"pmc/articles/(?:PMC)?(\d+)", loc_url, re.I)
                        if pmc_match:
                            pmcid = f"PMC{pmc_match.group(1)}"
                            pmc_pdf = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/"
                            if not any(c["url"] == pmc_pdf for c in candidates):
                                candidates.append({
                                    "url": pmc_pdf,
                                    "source": f"NCBI PMC ({pmcid})",
                                    "referer": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
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
                            # NCBI PMC (more reliable, works with Playwright)
                            candidates.append({
                                "url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/",
                                "source": f"NCBI PMC ({pmcid})",
                                "referer": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                            })
                            # Europe PMC (fallback)
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
        # Springer (10.1007, 10.1186, 10.1140, 10.1023, etc.)
        if any(doi.startswith(p) for p in ["10.1007/", "10.1186/", "10.1140/", "10.1023/", "10.1365/"]):
            publisher_patterns.append({
                "url": f"https://link.springer.com/content/pdf/{doi}.pdf",
                "source": "Springer 직접",
                "referer": f"https://link.springer.com/article/{doi}",
            })
        if "10.1038/" in doi:
            # Nature uses both nature.com and springer
            publisher_patterns.append({
                "url": f"https://www.nature.com/articles/{doi_suffix}.pdf",
                "source": "Nature 직접",
                "referer": f"https://www.nature.com/articles/{doi_suffix}",
            })
            publisher_patterns.append({
                "url": f"https://link.springer.com/content/pdf/{doi}.pdf",
                "source": "Springer (Nature)",
                "referer": f"https://www.nature.com/articles/{doi_suffix}",
            })
        # Wiley
        if any(doi.startswith(p) for p in ["10.1002/", "10.1111/", "10.1034/"]):
            publisher_patterns.append({
                "url": f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}",
                "source": "Wiley 직접",
                "referer": f"https://onlinelibrary.wiley.com/doi/{doi}",
            })
        # Elsevier / ScienceDirect
        if any(doi.startswith(p) for p in ["10.1016/", "10.1006/"]):
            pii = doi_suffix.replace("/", "")
            publisher_patterns.append({
                "url": f"https://www.sciencedirect.com/science/article/pii/{pii}/pdfft",
                "source": "ScienceDirect 직접",
                "referer": f"https://www.sciencedirect.com/science/article/pii/{pii}",
            })
        # Taylor & Francis
        if "10.1080/" in doi:
            publisher_patterns.append({
                "url": f"https://www.tandfonline.com/doi/pdf/{doi}",
                "source": "Taylor & Francis 직접",
                "referer": f"https://www.tandfonline.com/doi/full/{doi}",
            })
        # IEEE
        if "10.1109/" in doi:
            publisher_patterns.append({
                "url": f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={doi_suffix}",
                "source": "IEEE 직접",
                "referer": f"https://ieeexplore.ieee.org/document/{doi_suffix}",
            })
        # ACS
        if "10.1021/" in doi:
            publisher_patterns.append({
                "url": f"https://pubs.acs.org/doi/pdf/{doi}",
                "source": "ACS 직접",
                "referer": f"https://pubs.acs.org/doi/{doi}",
            })
        # RSC
        if "10.1039/" in doi:
            publisher_patterns.append({
                "url": f"https://pubs.rsc.org/en/content/articlepdf/{doi_suffix}",
                "source": "RSC 직접",
                "referer": f"https://pubs.rsc.org/en/content/articlelanding/{doi_suffix}",
            })
        # IOP Science
        if "10.1088/" in doi:
            publisher_patterns.append({
                "url": f"https://iopscience.iop.org/article/{doi}/pdf",
                "source": "IOP Science 직접",
                "referer": f"https://iopscience.iop.org/article/{doi}",
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
        browser_candidates = []

        for candidate in candidates:
            url = candidate["url"]
            source = candidate["source"]
            referer = candidate.get("referer", "")

            # Publisher API special handling
            if url.startswith("__elsevier_api__:"):
                api_doi = url.split(":", 1)[1]
                success, content, error = await self._try_elsevier_api(api_doi)
                if success:
                    filepath.write_bytes(content)
                    return True, str(filepath)
                errors.append(f"  [{source}] {error}")
                continue

            if url.startswith("__springer_api__:"):
                api_doi = url.split(":", 1)[1]
                success, content, error = await self._try_springer_api(api_doi)
                if success:
                    filepath.write_bytes(content)
                    return True, str(filepath)
                errors.append(f"  [{source}] {error}")
                continue

            # Try 1: Direct download
            success, content, error = await self._try_download_url(url, referer, use_proxy=False)
            if success:
                filepath.write_bytes(content)
                return True, str(filepath)
            errors.append(f"  [{source}] {error}")

            is_access_denied = any(
                kw in error for kw in ("403", "봇 차단", "HTML", "PDF 아님")
            )

            # Try 2: With proxy (if configured and access denied)
            if has_proxy and is_access_denied:
                success, content, error_p = await self._try_download_url(
                    url, referer, use_proxy=True
                )
                if success:
                    filepath.write_bytes(content)
                    return True, str(filepath)
                errors.append(f"  [{source} + 프록시] {error_p}")

            # Collect failed URLs for browser fallback
            if is_access_denied:
                browser_candidates.append(candidate)

        # Try 4: Browser automation fallback on all failed candidates (once)
        if self.use_browser and browser_candidates:
            for candidate in browser_candidates[:3]:  # limit to top 3 to avoid long waits
                url = candidate["url"]
                source = candidate["source"]
                logger.info("브라우저 자동화 시도: %s", url)
                success, content, error_b = await self._try_browser_download(url)
                if success:
                    filepath.write_bytes(content)
                    return True, str(filepath)
                errors.append(f"  [{source} + 브라우저] {error_b}")

        # All failed - provide proxied DOI link for manual download
        if paper.doi:
            manual_link = self.proxy.make_doi_link(paper.doi)
        else:
            manual_link = paper.url or "링크 없음"

        # Check if any error mentions proxy login
        proxy_login_msg = ""
        for err in errors:
            if "프록시 로그인" in err:
                proxy_login_msg = "\n" + err.strip()
                break

        error_summary = "\n".join(errors[:3])
        return False, f"모든 소스 실패. 수동 다운로드: {manual_link}\n{error_summary}{proxy_login_msg}"

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
