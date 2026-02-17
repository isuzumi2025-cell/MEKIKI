"""
スタンドアローン・スクレイパー
sitemap_proのエンジンを埋め込み、サーバー不要で動作

Features:
- Playwright同期APIでスクレイピング
- Basic認証対応
- スクリーンショット取得
- テキスト抽出
- BFSクロール
"""
import asyncio
import base64
import io
import time
from typing import List, Dict, Optional, Tuple, Set, Callable
from urllib.parse import urljoin, urlparse
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from PIL import Image


@dataclass
class PageResult:
    """ページ結果"""
    url: str
    status_code: int
    title: str
    text_content: str
    screenshot_base64: Optional[str]
    depth: int
    parent_url: Optional[str]
    links: List[str]
    error: Optional[str] = None


class StandaloneScraper:
    """
    スタンドアローン・スクレイパー
    サーバー不要、直接Playwrightを使用
    """
    
    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        viewport_width: int = 1920,
        viewport_height: int = 1080
    ):
        self.headless = headless
        self.timeout = timeout
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        
        # 除外拡張子
        self.excluded_extensions = {
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico',
            '.mp3', '.mp4', '.avi', '.mov', '.wmv',
            '.css', '.js', '.json', '.xml'
        }
    
    def _should_exclude(self, url: str) -> bool:
        """URLを除外すべきか"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        for ext in self.excluded_extensions:
            if path.endswith(ext):
                return True
        return False
    
    def _normalize_url(self, url: str) -> str:
        """URL正規化"""
        parsed = urlparse(url)
        # クエリとフラグメントを除去
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
    
    def scrape_page(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        take_screenshot: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> PageResult:
        """
        単一ページをスクレイピング
        
        Args:
            url: スクレイピングするURL
            username: Basic認証ユーザー名
            password: Basic認証パスワード
            take_screenshot: スクリーンショットを撮るか
            progress_callback: 進捗コールバック
        
        Returns:
            PageResult: スクレイピング結果
        """
        from playwright.sync_api import sync_playwright
        
        if progress_callback:
            progress_callback(f"🌐 フェッチ中: {url}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                
                # コンテキスト設定
                context_options = {
                    'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
                    'device_scale_factor': 2.0
                }
                
                # Basic認証
                if username and password:
                    context_options['http_credentials'] = {
                        'username': username,
                        'password': password
                    }
                
                context = browser.new_context(**context_options)
                page = context.new_page()
                page.set_default_timeout(self.timeout)
                
                # ナビゲーション
                response = page.goto(url, wait_until='domcontentloaded')
                status_code = response.status if response else 0
                
                # 読み込み待機
                page.wait_for_load_state('networkidle', timeout=10000)
                
                # タイトル取得
                title = page.title()
                
                # テキスト抽出
                text_content = page.inner_text('body')
                
                # スクリーンショット
                screenshot_base64 = None
                if take_screenshot:
                    try:
                        screenshot_bytes = page.screenshot(full_page=True)
                        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                    except Exception as e:
                        print(f"⚠️ スクリーンショットエラー: {e}")
                
                # リンク抽出
                links = page.eval_on_selector_all(
                    'a[href]',
                    'elements => elements.map(e => e.href)'
                )
                
                browser.close()
                
                return PageResult(
                    url=url,
                    status_code=status_code,
                    title=title,
                    text_content=text_content,
                    screenshot_base64=screenshot_base64,
                    depth=0,
                    parent_url=None,
                    links=links
                )
                
        except Exception as e:
            return PageResult(
                url=url,
                status_code=0,
                title="",
                text_content="",
                screenshot_base64=None,
                depth=0,
                parent_url=None,
                links=[],
                error=str(e)
            )
    
    def crawl(
        self,
        start_url: str,
        max_pages: int = 10,
        max_depth: int = 2,
        username: Optional[str] = None,
        password: Optional[str] = None,
        delay: float = 1.0,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        respect_robots: bool = False
    ) -> List[PageResult]:
        """
        BFSクロール
        
        Args:
            start_url: 開始URL
            max_pages: 最大ページ数
            max_depth: 最大深度
            username: Basic認証ユーザー名
            password: Basic認証パスワード
            delay: リクエスト間隔（秒）
            progress_callback: 進捗コールバック (url, current, total)
            respect_robots: robots.txtを尊重するか
        
        Returns:
            List[PageResult]: クロール結果
        """
        from playwright.sync_api import sync_playwright
        
        results: List[PageResult] = []
        visited: Set[str] = set()
        queue: List[Tuple[str, int, Optional[str]]] = [(start_url, 0, None)]  # (url, depth, parent)
        
        # ドメイン制限
        start_domain = urlparse(start_url).netloc
        
        print(f"🚀 クロール開始: {start_url}")
        print(f"   最大ページ: {max_pages}, 最大深度: {max_depth}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                
                # コンテキスト設定
                context_options = {
                    'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
                    'device_scale_factor': 2.0
                }
                
                # Basic認証
                if username and password:
                    context_options['http_credentials'] = {
                        'username': username,
                        'password': password
                    }
                    print(f"   🔐 Basic認証: {username}")
                
                context = browser.new_context(**context_options)
                page = context.new_page()
                page.set_default_timeout(self.timeout)
                
                while queue and len(results) < max_pages:
                    url, depth, parent_url = queue.pop(0)
                    
                    # 正規化
                    normalized_url = self._normalize_url(url)
                    
                    # 訪問済みチェック
                    if normalized_url in visited:
                        continue
                    
                    # 深度チェック
                    if depth > max_depth:
                        continue
                    
                    # ドメインチェック
                    if urlparse(url).netloc != start_domain:
                        continue
                    
                    # 拡張子チェック
                    if self._should_exclude(url):
                        continue
                    
                    visited.add(normalized_url)
                    
                    # 進捗
                    if progress_callback:
                        progress_callback(url, len(results) + 1, max_pages)
                    
                    print(f"📄 [{len(results)+1}/{max_pages}] (深度{depth}) {url[:60]}...")
                    
                    try:
                        # ナビゲーション
                        response = page.goto(url, wait_until='domcontentloaded')
                        status_code = response.status if response else 0
                        
                        # 読み込み待機
                        try:
                            page.wait_for_load_state('networkidle', timeout=10000)
                        except:
                            pass
                        
                        # タイトル取得
                        title = page.title()
                        
                        # テキスト抽出
                        try:
                            text_content = page.inner_text('body')
                        except:
                            text_content = ""
                        
                        # スクリーンショット
                        screenshot_base64 = None
                        try:
                            screenshot_bytes = page.screenshot(full_page=True)
                            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                        except Exception as e:
                            print(f"  ⚠️ スクショエラー: {e}")
                        
                        # リンク抽出
                        try:
                            raw_links = page.eval_on_selector_all(
                                'a[href]',
                                'elements => elements.map(e => e.href)'
                            )
                        except:
                            raw_links = []
                        
                        # 結果保存
                        result = PageResult(
                            url=url,
                            status_code=status_code,
                            title=title,
                            text_content=text_content,
                            screenshot_base64=screenshot_base64,
                            depth=depth,
                            parent_url=parent_url,
                            links=raw_links
                        )
                        results.append(result)
                        
                        # 新しいリンクをキューに追加
                        if depth < max_depth:
                            for link in raw_links:
                                if link and urlparse(link).netloc == start_domain:
                                    normalized = self._normalize_url(link)
                                    if normalized not in visited and not self._should_exclude(link):
                                        queue.append((link, depth + 1, url))
                        
                    except Exception as e:
                        print(f"  ❌ エラー: {e}")
                        results.append(PageResult(
                            url=url,
                            status_code=0,
                            title="",
                            text_content="",
                            screenshot_base64=None,
                            depth=depth,
                            parent_url=parent_url,
                            links=[],
                            error=str(e)
                        ))
                    
                    # 遅延
                    if delay > 0:
                        time.sleep(delay)
                
                browser.close()
        
        except Exception as e:
            print(f"❌ クロールエラー: {e}")
        
        print(f"✅ クロール完了: {len(results)} ページ")
        return results
    
    def get_results_as_dict_list(self, results: List[PageResult]) -> List[Dict]:
        """結果を辞書リストに変換（キュー追加用）"""
        return [
            {
                'type': 'web',
                'url': r.url,
                'status_code': r.status_code,
                'title': r.title,
                'text_content': r.text_content,
                'screenshot_base64': r.screenshot_base64,
                'depth': r.depth,
                'parent_url': r.parent_url,
                'error': r.error
            }
            for r in results
        ]


# テスト用
if __name__ == "__main__":
    scraper = StandaloneScraper(headless=True)
    
    # 単一ページテスト
    result = scraper.scrape_page("https://example.com")
    print(f"Title: {result.title}")
    print(f"Text length: {len(result.text_content)}")
    print(f"Links: {len(result.links)}")
