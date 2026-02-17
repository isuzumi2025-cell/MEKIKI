from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # Core
    START_URL: str = "https://example.com"
    ALLOWED_DOMAINS: List[str] = ["example.com"]
    MAX_PAGES: int = 50
    CONCURRENCY: int = 4
    HEADLESS: bool = True
    
    # Crawler Behavior
    TIMEOUT_SECONDS: int = 30
    WAIT_FOR_SELECTOR: str = "body"
    USER_AGENT: str = "SitemapPro/0.1.0 (Compatible; Playwright)"
    RESPECT_ROBOTS: bool = True  # Respect robots.txt by default
    REQUEST_DELAY: float = 0.0  # Seconds between requests (0 = no delay)
    
    # Authentication
    AUTH_TYPE: str = "none" # none, basic, form, cookie
    AUTH_USER: str = ""
    AUTH_PASS: str = ""
    LOGIN_URL: str = ""
    AUTH_SELECTORS: dict = {
        "user": "#username",
        "pass": "#password",
        "submit": "button[type='submit']"
    }
    COOKIES: List[dict] = []
    
    # Paths
    OUTPUT_DIR: str = "outputs"
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

settings = Settings()
