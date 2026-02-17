"""
Phase 1: スクレイピング機能の強化
遅延読み込み（Lazy Loading）対応
"""
from playwright.sync_api import sync_playwright, Page
from PIL import Image
from typing import List, Dict, Optional, Tuple
import io
import time


class EnhancedWebScraper:
    """強化版Webスクレイパー - クローリングとLazy Loading対応"""
    
    def __init__(self, headless: bool = True, viewport_width: int = 1280, viewport_height: int = 800):
        """
        Args:
            headless: ヘッドレスモードで実行するか
            viewport_width: ビューポート幅
            viewport_height: ビューポート高さ
        """
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
    
    def scrape_with_lazy_loading(
        self,
        url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        max_scrolls: int = 10,
        scroll_delay: float = 1.0
    ) -> Tuple[str, str, Image.Image, Image.Image]:
        """
        遅延読み込み対応でWebページをスクレイピング
        
        Args:
            url: 対象URL
            username: Basic認証ユーザー名
            password: Basic認証パスワード
            max_scrolls: 最大スクロール回数
            scroll_delay: スクロール間の待機時間（秒）
        
        Returns:
            (title, text, full_page_image, viewport_image)
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            
            context_options = {
                'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
                'device_scale_factor': 2.0
            }
            
            # Basic認証設定
            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            try:
                print(f"🌍 アクセス中: {url}")
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # ページ下部までスクロール（Lazy Loading対応）
                self._scroll_to_bottom(page, max_scrolls, scroll_delay)
                
                # タイトルとテキスト取得
                title = page.title()
                text_content = page.inner_text("body")
                
                # 1画面分のスクリーンショット
                page.evaluate("window.scrollTo(0, 0)")  # トップに戻る
                time.sleep(0.5)
                viewport_bytes = page.screenshot(full_page=False)
                viewport_image = Image.open(io.BytesIO(viewport_bytes))
                
                # フルページスクリーンショット
                full_bytes = page.screenshot(full_page=True)
                full_image = Image.open(io.BytesIO(full_bytes))
                
                print(f"✅ 取得完了: {title}")
                return title, text_content, full_image, viewport_image
                
            except Exception as e:
                raise Exception(f"スクレイピングエラー: {str(e)}")
            finally:
                context.close()
                browser.close()
    
    def _scroll_to_bottom(self, page: Page, max_scrolls: int, delay: float):
        """
        ページ下部までスクロール（遅延読み込み対応）
        
        Args:
            page: Playwrightのページオブジェクト
            max_scrolls: 最大スクロール回数
            delay: スクロール間の待機時間
        """
        print(f"📜 ページをスクロール中...")
        
        for i in range(max_scrolls):
            # 現在の高さを取得
            prev_height = page.evaluate("document.body.scrollHeight")
            
            # 下にスクロール
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(delay)
            
            # 新しい高さを取得
            new_height = page.evaluate("document.body.scrollHeight")
            
            # 高さが変わらなければ終了（これ以上読み込むものがない）
            if new_height == prev_height:
                print(f"✅ スクロール完了（{i + 1}回）")
                break
        else:
            print(f"✅ 最大スクロール回数に到達（{max_scrolls}回）")
    
    def crawl_site(
        self,
        base_url: str,
        max_pages: int = 50,
        same_domain_only: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> List[Dict]:
        """
        サイト内をクローリング
        
        Args:
            base_url: 開始URL
            max_pages: 最大ページ数
            same_domain_only: 同一ドメインのみ
            username: Basic認証ユーザー名
            password: Basic認証パスワード
        
        Returns:
            [{"url": str, "title": str, "text": str, "full_image": Image, "viewport_image": Image}, ...]
        """
        from urllib.parse import urlparse, urljoin
        import re
        
        visited = set()
        to_visit = [base_url]
        results = []
        base_domain = urlparse(base_url).netloc
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            
            context_options = {
                'viewport': {'width': self.viewport_width, 'height': self.viewport_height},
                'device_scale_factor': 2.0
            }
            
            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            try:
                while to_visit and len(results) < max_pages:
                    current_url = to_visit.pop(0)
                    
                    if current_url in visited:
                        continue
                    
                    # ドメインチェック
                    if same_domain_only:
                        current_domain = urlparse(current_url).netloc
                        if current_domain != base_domain:
                            continue
                    
                    try:
                        print(f"🌍 [{len(results) + 1}/{max_pages}] {current_url}")
                        
                        page.goto(current_url, timeout=60000)
                        page.wait_for_load_state("networkidle")
                        
                        # Lazy Loading対応スクロール
                        self._scroll_to_bottom(page, max_scrolls=5, delay=0.5)
                        
                        # データ取得
                        title = page.title()
                        text_content = page.inner_text("body")
                        
                        # スクリーンショット
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(0.3)
                        viewport_bytes = page.screenshot(full_page=False)
                        viewport_image = Image.open(io.BytesIO(viewport_bytes))
                        
                        full_bytes = page.screenshot(full_page=True)
                        full_image = Image.open(io.BytesIO(full_bytes))
                        
                        results.append({
                            "url": current_url,
                            "title": title,
                            "text": text_content,
                            "full_image": full_image,
                            "viewport_image": viewport_image
                        })
                        
                        visited.add(current_url)
                        
                        # リンクを抽出
                        links = page.evaluate("""
                            () => {
                                return Array.from(document.querySelectorAll('a[href]'))
                                    .map(a => a.href)
                                    .filter(href => href.startsWith('http'));
                            }
                        """)
                        
                        for link in links:
                            # フラグメント除去
                            link = link.split('#')[0]
                            if link and link not in visited and link not in to_visit:
                                to_visit.append(link)
                        
                        time.sleep(1.0)  # 負荷軽減
                        
                    except Exception as e:
                        print(f"⚠️ エラー: {current_url} - {str(e)}")
                        visited.add(current_url)
                        continue
                
            finally:
                context.close()
                browser.close()
        
        print(f"✅ クローリング完了: {len(results)}ページ取得")
        return results

