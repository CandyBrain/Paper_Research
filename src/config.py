import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.scopus_api_key: str = os.getenv("SCOPUS_API_KEY", "")
        self.core_api_key: str = os.getenv("CORE_API_KEY", "")
        self.unpaywall_email: str = os.getenv("UNPAYWALL_EMAIL", "paperresearch@gmail.com")
        self.papers_dir: Path = Path(os.getenv("PAPERS_DIR", "papers"))
        self.max_results_per_db: int = int(os.getenv("MAX_RESULTS_PER_DB", "10"))
        self.proxy_url: str = os.getenv("PROXY_URL", "")

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key) and value:
                setattr(self, key, value)


settings = Settings()
