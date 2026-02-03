import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Visual Sitemap Generator"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./sitemap.db"
    
    # Crawler Defaults
    DEFAULT_MAX_PAGES: int = 50
    DEFAULT_MAX_DEPTH: int = 3
    DEFAULT_MAX_TIME_SECONDS: int = 1800  # 30分
    DEFAULT_CONCURRENT_LIMIT: int = 3
    DEFAULT_TIMEOUT: int = 60000  # 60s (ms for Playwright)
    DEFAULT_WAIT_UNTIL: str = "domcontentloaded"
    DEFAULT_RATE_LIMIT_DELAY: float = 0.5  # 秒
    
    # Screenshot Settings
    PC_VIEWPORT_WIDTH: int = 1920
    PC_VIEWPORT_HEIGHT: int = 1080
    SP_VIEWPORT_WIDTH: int = 390
    SP_VIEWPORT_HEIGHT: int = 844
    SCREENSHOT_QUALITY: int = 80
    SCREENSHOT_FORMAT: str = "jpeg"
    
    # Tracking Parameters to Remove (Default)
    TRACKING_PARAMS: List[str] = [
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gclid", "fbclid", "_ga", "_gl", "mc_cid", "mc_eid"
    ]
    
    # Output
    OUTPUT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "outputs")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    class Config:
        case_sensitive = True

settings = Settings()
