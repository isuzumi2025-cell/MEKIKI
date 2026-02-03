import asyncio
import os
import argparse
import logging
from urllib.parse import urlparse
from app.core.config import settings
from app.core.crawler import Crawler
from app.report.generator import ReportGenerator

# Setup basic logging for CLI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cli")

async def main():
    parser = argparse.ArgumentParser(description="Sitemap Pro MVP Crawler")
    parser.add_argument("--url", help="Start URL", default=None)
    parser.add_argument("--max-pages", type=int, help="Max pages to crawl", default=None)
    parser.add_argument("--concurrency", type=int, help="Concurrency limit", default=None)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, help="Headless mode", default=None)
    
    # Auth Args
    parser.add_argument("--auth-type", choices=["none", "basic", "form", "cookie"], help="Auth Type", default=None)
    parser.add_argument("--auth-user", help="Auth User", default=None)
    parser.add_argument("--auth-pass", help="Auth Password", default=None)
    parser.add_argument("--login-url", help="Login URL for form auth", default=None)

    args = parser.parse_args()

    # Override Settings
    if args.url: 
        settings.START_URL = args.url
        # Auto-set ALLOWED_DOMAINS from URL
        parsed = urlparse(args.url)
        settings.ALLOWED_DOMAINS = [parsed.netloc]
        
    if args.max_pages: settings.MAX_PAGES = args.max_pages
    if args.concurrency: settings.CONCURRENCY = args.concurrency
    if args.headless is not None: settings.HEADLESS = args.headless
    
    if args.auth_type: settings.AUTH_TYPE = args.auth_type
    if args.auth_user: settings.AUTH_USER = args.auth_user
    if args.auth_pass: settings.AUTH_PASS = args.auth_pass
    if args.login_url: settings.LOGIN_URL = args.login_url

    print(f"--- Sitemap Pro MVP ---")
    print(f"Start URL: {settings.START_URL}")
    print(f"Domains: {settings.ALLOWED_DOMAINS}")
    print(f"Max Pages: {settings.MAX_PAGES}")
    print(f"Auth Type: {settings.AUTH_TYPE}")
    
    crawler = Crawler()
    await crawler.run()
    
    print(f"Run completed: {crawler.run_id}")
    print(f"Output: {crawler.output_dir}")
    
    # Generate Report
    print("Generating Report...")
    generator = ReportGenerator(crawler.run_id)
    if generator.generate():
        print(f"Report Ready: {os.path.join(generator.report_dir, 'index.html')}")
    else:
        print("Report Generation Failed.")

if __name__ == "__main__":
    asyncio.run(main())
