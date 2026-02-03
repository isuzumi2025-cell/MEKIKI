import sys
import os
try:
    sys.path.append(os.getcwd())
    print("Checking imports...")
    from app.core.scraper import WebScraper
    print("WebScraper: OK")
    from app.core.sitemap_generator import SitemapGenerator
    print("SitemapGenerator: OK")
    from app.core.comparator import Comparator
    print("Comparator: OK")
    from app.core.engine_cloud import CloudOCREngine
    print("CloudOCREngine: OK")
    # We skip GUI import as it requires a display
    # from app.gui.main_window import OCRApp 
    print("Core modules verified successfully.")
except Exception as e:
    print(f"Import Error: {e}")
    sys.exit(1)
