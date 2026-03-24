"""Server-side workspace state (replaces st.session_state)."""

from src.models import Paper, SearchResult


class Workspace:
    """Holds all session state for the current workspace."""

    def __init__(self):
        self.papers: list[Paper] = []
        self.search_results: list[SearchResult] = []
        self.selected: set[int] = set()
        self.ai_analysis: dict | None = None
        self.dl_statuses: dict[int, str] = {}
        self.manual_pdf_paths: dict[int, str] = {}
        self.citations_data: dict[int, dict] = {}
        self.references_data: dict[int, dict] = {}
        self.last_query: str = ""
        self.search_mode: str = ""
        self.download_dir: str = ""

        # Settings
        self.anthropic_api_key: str = ""
        self.scopus_api_key: str = ""
        self.core_api_key: str = ""
        self.springer_api_key: str = ""
        self.proxy_url: str = ""
        self.max_results_per_db: int = 10
        self.use_browser: bool = False

    def clear_search(self):
        """Clear per-search state when a new search is performed."""
        self.papers = []
        self.search_results = []
        self.selected = set()
        self.ai_analysis = None
        self.dl_statuses = {}
        self.manual_pdf_paths = {}
        self.citations_data = {}
        self.references_data = {}

    def load_from_session(self, session_data: dict):
        """Restore workspace from loaded session data."""
        from src.utils.dedup import _is_valid_paper_doi

        self.last_query = session_data.get("query", "")
        self.search_mode = session_data.get("search_mode", "")
        self.ai_analysis = session_data.get("ai_analysis")
        self.search_results = session_data.get("search_results", [])

        # Filter out non-paper records when loading
        all_papers = session_data.get("all_papers", [])
        filtered = []
        for p in all_papers:
            doi = p.doi if hasattr(p, "doi") else p.get("doi")
            if _is_valid_paper_doi(doi):
                filtered.append(p)
        self.papers = filtered

        self.selected = session_data.get("selected", set())
        self.manual_pdf_paths = session_data.get("manual_pdf_paths", {})
        self.dl_statuses = session_data.get("dl_statuses", {})
        self.citations_data = session_data.get("citations_data", {})
        self.references_data = session_data.get("references_data", {})


# Global singleton instance
workspace = Workspace()
