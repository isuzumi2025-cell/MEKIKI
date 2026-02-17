import asyncio
import os
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, List, Set, Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from app.core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RobotsChecker:
    """Checks if URLs are allowed by robots.txt"""
    
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._parsers: Dict[str, RobotFileParser] = {}
        self._failed_hosts: Set[str] = set()
    
    async def fetch_robots(self, base_url: str) -> RobotFileParser:
        """Fetch and parse robots.txt for a domain"""
        parsed = urlparse(base_url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        
        if host in self._parsers:
            return self._parsers[host]
        
        if host in self._failed_hosts:
            return None
        
        robots_url = f"{host}/robots.txt"
        parser = RobotFileParser()
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                    self._parsers[host] = parser
                    logger.info(f"Loaded robots.txt from {host}")
                    return parser
                else:
                    # No robots.txt = allow all
                    self._failed_hosts.add(host)
                    return None
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt from {host}: {e}")
            self._failed_hosts.add(host)
            return None
    
    async def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        if not settings.RESPECT_ROBOTS:
            return True
        
        parser = await self.fetch_robots(url)
        if parser is None:
            return True  # No robots.txt = allow
        
        return parser.can_fetch(self.user_agent, url)

class Crawler:
    def __init__(self, run_id: str = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(settings.OUTPUT_DIR, self.run_id)
        self.images_dir = os.path.join(self.output_dir, "images")
        self.report_dir = os.path.join(self.output_dir, "report")
        self.log_path = os.path.join(self.output_dir, "crawl.log")
        
        self.visited_urls: Set[str] = set()
        self.pending_urls: Set[str] = set()  # URLs queued but not yet visited
        self.queue: asyncio.Queue = asyncio.Queue()
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, str]] = []
        
        # Ensure directories exist
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.report_dir, exist_ok=True)
        
        # Setup File Logging
        file_handler = logging.FileHandler(self.log_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.playwright = None
        
        # Concurrency control
        self.sem = asyncio.Semaphore(settings.CONCURRENCY)
        self.processing_count = 0
        
        # Robots.txt checker
        self.robots_checker = RobotsChecker(settings.USER_AGENT)

    def _get_url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def _normalize_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            # Strip fragments and query params for basic crawling unless critical
            # Ideally we might want keep some params, but for MVP strict norm is safer
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
        except Exception:
            return url

    def _is_allowed_domain(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Handle empty domain (relative links should be resolved before this)
            if not domain: return False
            
            # SECURITY: Strict domain matching (exact or subdomain)
            for allowed in settings.ALLOWED_DOMAINS:
                if domain == allowed or domain.endswith("." + allowed):
                    return True
            return False
        except:
            return False

    async def init_browser(self):
        logger.info("Initializing Playwright Browser...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=settings.HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox"] # Docker/Linux friendly
        )
        
        context_args = {
            "user_agent": settings.USER_AGENT,
            "viewport": {"width": 1280, "height": 800},
            "ignore_https_errors": True
        }
        
        # BASIC AUTH (SECURITY: credentials not logged)
        if settings.AUTH_TYPE == "basic" and settings.AUTH_USER and settings.AUTH_PASS:
            logger.info("Configuring Basic Auth (credentials hidden)")
            context_args["http_credentials"] = {
                "username": settings.AUTH_USER,
                "password": settings.AUTH_PASS
            }
            
        self.context = await self.browser.new_context(**context_args)
        
        # COOKIE AUTH
        if settings.AUTH_TYPE == "cookie" and settings.COOKIES:
            logger.info(f"Injecting {len(settings.COOKIES)} cookies")
            await self.context.add_cookies(settings.COOKIES)

    async def login(self):
        """Handle Form Login if configured."""
        if settings.AUTH_TYPE != "form":
            return

        if not settings.LOGIN_URL:
            logger.warning("Auth type is 'form' but LOGIN_URL is missing.")
            return

        # SECURITY: Do not log LOGIN_URL to prevent credential endpoint leak
        logger.info("Attempting Form Login (URL hidden)")
        page = await self.context.new_page()
        try:
            await page.goto(settings.LOGIN_URL, wait_until="networkidle")
            
            sels = settings.AUTH_SELECTORS
            if settings.AUTH_USER and sels.get("user"):
                await page.fill(sels["user"], settings.AUTH_USER)
            
            if settings.AUTH_PASS and sels.get("pass"):
                await page.fill(sels["pass"], settings.AUTH_PASS)
            
            if sels.get("submit"):
                await page.click(sels["submit"])
                # Wait for navigation or specific condition
                await page.wait_for_load_state("networkidle")
                logger.info("Form Login submitted.")
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            # We continue anyway, maybe public parts are visible
        finally:
            await page.close()

    async def close(self):
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
        logger.info("Browser closed.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((PlaywrightTimeoutError, Exception)),
        reraise=True
    )
    async def _navigate_with_retry(self, page: Page, url: str):
        """Navigate to URL with retry on transient failures"""
        logger.debug(f"Navigating to {url}")
        return await page.goto(url, wait_until="domcontentloaded", timeout=settings.TIMEOUT_SECONDS * 1000)

    async def process_page(self, url: str):
        async with self.sem:
            page_hash = self._get_url_hash(url)
            logger.info(f"Crawling: {url}")
            
            # Rate limiting
            if settings.REQUEST_DELAY > 0:
                await asyncio.sleep(settings.REQUEST_DELAY)

            page_data = {
                "id": page_hash,
                "url": url,
                "title": "",
                "status": 0,
                "screenshot": "",
                "thumbnail": "",
                "h1": "",
                "meta_desc": "",
                "canonical": "",
                "links": []
            }

            page = await self.context.new_page()
            try:
                # Navigate with retry for transient errors
                response = await self._navigate_with_retry(page, url)
                
                # Check redirects
                final_url = page.url
                if self._normalize_url(final_url) != self._normalize_url(url):
                    page_data["redirect_to"] = final_url

                page_data["status"] = response.status
                
                # If error status, just return (or screenshot error page?)
                if response.status >= 400:
                    logger.warning(f"Status {response.status} for {url}")
                
                # Wait for body/selector
                try:
                    await page.wait_for_selector(settings.WAIT_FOR_SELECTOR, timeout=5000)
                except:
                    pass # Continue even if selector missing

                # Metadata Extraction
                page_data["title"] = await page.title()
                
                # Extract meta/h1 using evaluate for speed
                meta_info = await page.evaluate("""
                    () => {
                        const h1 = document.querySelector('h1')?.innerText || '';
                        const desc = document.querySelector('meta[name="description"]')?.content || '';
                        const canon = document.querySelector('link[rel="canonical"]')?.href || '';
                        return { h1, desc, canon };
                    }
                """)
                page_data["h1"] = meta_info["h1"]
                page_data["meta_desc"] = meta_info["desc"]
                page_data["canonical"] = meta_info["canon"]

                # Screenshots
                # Full Page
                screenshot_filename = f"{page_hash}.png"
                screenshot_path = os.path.join(self.images_dir, screenshot_filename)
                await page.screenshot(path=screenshot_path, full_page=True)
                page_data["screenshot"] = f"images/{screenshot_filename}"
                
                # Thumbnail
                thumb_filename = f"{page_hash}_thumb.png"
                thumb_path = os.path.join(self.images_dir, thumb_filename)
                # Helper to resize effectively: set viewport small or just clip?
                # For now, simple viewport screenshot as thumbnail
                await page.screenshot(path=thumb_path, full_page=False) 
                page_data["thumbnail"] = f"images/{thumb_filename}"
                
                # Save HTML (optional, maybe skipping for speed if large site, but requirements said "HTML(保存)")
                html_path = os.path.join(self.output_dir, "html", f"{page_hash}.html")
                os.makedirs(os.path.dirname(html_path), exist_ok=True)
                content = await page.content()
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(content)

                # Link Extraction
                hrefs = await page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('a[href]')).map(a => a.href)
                    }
                """)
                
                unique_links = set()
                for href in hrefs:
                    try:
                        full_url = urljoin(url, href)
                        norm_url = self._normalize_url(full_url)
                        
                        if norm_url == self._normalize_url(url): continue
                        
                        unique_links.add(norm_url)
                        
                        is_internal = self._is_allowed_domain(norm_url)
                        
                        # Store Edge
                        target_hash = self._get_url_hash(norm_url)
                        
                        # Dedupe edges on logic level if needed, but for now store all discovered
                        # We shouldn't add duplicate edges to self.edges list to keep it clean
                        edge_key = f"{page_hash}->{target_hash}"
                        # (Ideally check if exists, but list append is fast. We can dedupe later)
                        
                        self.edges.append({
                            "source": page_hash,
                            "target": target_hash,
                            "type": "internal" if is_internal else "external"
                        })
                        
                        # Add to Queue (with deduplication)
                        if is_internal:
                            if norm_url not in self.visited_urls and norm_url not in self.pending_urls:
                                # Check robots.txt before queueing
                                if await self.robots_checker.is_allowed(norm_url):
                                    self.pending_urls.add(norm_url)
                                    await self.queue.put(norm_url)
                                else:
                                    logger.debug(f"Blocked by robots.txt: {norm_url}")
                                
                    except Exception as loop_e:
                        continue

                page_data["links_count"] = len(unique_links)
                self.nodes.append(page_data)

            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                page_data["error"] = str(e)
                page_data["status"] = 999
                self.nodes.append(page_data)
            finally:
                await page.close()

    async def worker(self):
        while True:
            try:
                # Check max pages
                if len(self.visited_urls) >= settings.MAX_PAGES:
                    # Drain queue? Or just stop.
                    # If we just return, other workers might be stuck.
                    # We should probably check before popping.
                    # But queue.get() waits.
                    
                    # If we verified count, we can cancel?
                    # Let's check logic:
                    # Ideally we break. 
                    if self.queue.empty():
                        break
                
                if len(self.visited_urls) >= settings.MAX_PAGES:
                    # We are done.
                    # Consume to unblock join() if strictly needed, but better to just return
                     # If we are using task cancel, it's fine.
                     break

                url = await self.queue.get()
                
                if url in self.visited_urls:
                    self.queue.task_done()
                    continue
                
                # Double check limit before processing
                if len(self.visited_urls) >= settings.MAX_PAGES:
                    self.queue.task_done()
                    continue

                self.visited_urls.add(url)
                
                await self.process_page(url)
                
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker Error: {e}")
                self.queue.task_done()

    async def save_results(self):
        # Filter config for secrets
        safe_config = settings.model_dump()
        safe_config["AUTH_PASS"] = "***"
        safe_config["COOKIES"] = "***"

        result_data = {
            "meta": {
                "run_id": self.run_id,
                "start_url": settings.START_URL,
                "timestamp": datetime.now().isoformat(),
                "total_pages": len(self.nodes)
            },
            "config": safe_config,
            "nodes": self.nodes,
            "edges": self.edges # Could dedupe here
        }
        
        json_path = os.path.join(self.output_dir, "data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved results to {json_path}")

    async def run(self):
        await self.init_browser()
        await self.login()
        
        # Start BFS
        start_norm = self._normalize_url(settings.START_URL)
        await self.queue.put(start_norm)
        
        # Start Workers
        workers = []
        for _ in range(settings.CONCURRENCY):
            workers.append(asyncio.create_task(self.worker()))
        
        # Monitor conditions
        while True:
            # If queue is empty and no processing?
            # Or satisfy Max Pages
            if len(self.visited_urls) >= settings.MAX_PAGES:
                logger.info("Max pages reached.")
                break
            
            if self.queue.empty() and self.sem._value == settings.CONCURRENCY:
                # Approximate detection of completion
                # Wait a bit to be sure
                await asyncio.sleep(1)
                if self.queue.empty() and self.sem._value == settings.CONCURRENCY:
                    logger.info("Queue empty and no active workers.")
                    break
            
            await asyncio.sleep(0.5)

        # Cancel workers
        for w in workers:
            w.cancel()
        
        await self.save_results()
        await self.close()

if __name__ == "__main__":
    crawler = Crawler()
    asyncio.run(crawler.run())
