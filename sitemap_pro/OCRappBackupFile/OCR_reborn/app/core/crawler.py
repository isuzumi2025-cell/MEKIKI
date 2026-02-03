"""
Webクローラー
指定されたURLを巡回し、PCビューポートで「見たまま」のスクリーンショットを撮影
Playwright を使用した高品質なスクリーンショット機能
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from typing import Optional, Dict, List
from pathlib import Path
import time
import json
import os


class WebCrawler:
    """
    Webサイトをクロールし、スクリーンショットを撮影するクラス
    
    機能:
    - PCビューポート (1920x1080) での撮影
    - 完全なロード待機 (networkidle + sleep)
    - Basic認証対応
    - Cookie保存/復元
    - スクロール対応（全体撮影）
    """
    
    def __init__(self, viewport_width: int = 1920, viewport_height: int = 1080):
        """
        Args:
            viewport_width: ビューポート幅（デフォルト: 1920px）
            viewport_height: ビューポート高さ（デフォルト: 1080px）
        """
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.auth_file = "auth.json"
    
    def crawl(
        self,
        url: str,
        output_path: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        wait_time: int = 2,
        full_page: bool = True,
        headless: bool = True
    ) -> Dict[str, any]:
        """
        指定URLをクロールしてスクリーンショットを撮影
        
        Args:
            url: 対象URL
            output_path: 出力画像パス (.png)
            username: Basic認証ユーザー名（オプション）
            password: Basic認証パスワード（オプション）
            wait_time: 追加待機時間（秒）
            full_page: ページ全体を撮影するか（True: 全体, False: ビューポートのみ）
            headless: ヘッドレスモード（デフォルト: True）
        
        Returns:
            {
                "success": bool,
                "title": str,
                "url": str,
                "screenshot_path": str,
                "viewport_size": (width, height),
                "full_page_size": (width, height) or None,
                "error": str or None
            }
        """
        result = {
            "success": False,
            "title": "",
            "url": url,
            "screenshot_path": "",
            "viewport_size": (self.viewport_width, self.viewport_height),
            "full_page_size": None,
            "error": None
        }
        
        with sync_playwright() as p:
            try:
                # コンテキストオプションの準備
                context_options = {
                    "viewport": {
                        "width": self.viewport_width,
                        "height": self.viewport_height
                    }
                }
                
                # Cookie復元
                if os.path.exists(self.auth_file):
                    try:
                        with open(self.auth_file, 'r') as f:
                            json.load(f)  # バリデーション
                        context_options['storage_state'] = self.auth_file
                        print(f"🔓 保存されたCookieを使用します")
                    except:
                        print(f"⚠️  Cookieファイルが無効です")
                
                # Basic認証設定
                if username and password:
                    context_options['http_credentials'] = {
                        'username': username,
                        'password': password
                    }
                    print(f"🔑 Basic認証を使用します: {username}")
                
                # ブラウザ起動
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(**context_options)
                page = context.new_page()
                
                # ページ遷移
                print(f"🌍 アクセス中: {url}")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # 完全なロード待機
                print(f"⏳ ロード待機中...")
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(wait_time)  # 追加待機（動的コンテンツ対応）
                
                # タイトル取得
                result["title"] = page.title()
                
                # ページサイズ取得（full_pageモードの場合）
                if full_page:
                    page_height = page.evaluate("document.documentElement.scrollHeight")
                    page_width = page.evaluate("document.documentElement.scrollWidth")
                    result["full_page_size"] = (page_width, page_height)
                    print(f"📐 ページサイズ: {page_width}x{page_height}")
                
                # スクリーンショット撮影
                print(f"📸 スクリーンショット撮影中...")
                page.screenshot(path=output_path, full_page=full_page)
                
                result["screenshot_path"] = output_path
                result["success"] = True
                print(f"✅ 完了: {output_path}")
                
                # Cookie保存
                context.storage_state(path=self.auth_file)
                
                browser.close()
                
            except PlaywrightTimeout as e:
                result["error"] = f"タイムアウト: {str(e)}"
                print(f"❌ {result['error']}")
            except Exception as e:
                result["error"] = str(e)
                print(f"❌ エラー: {result['error']}")
        
        return result
    
    def crawl_multiple(
        self,
        urls: List[str],
        output_dir: str,
        **kwargs
    ) -> List[Dict[str, any]]:
        """
        複数URLを一括クロール
        
        Args:
            urls: URL一覧
            output_dir: 出力ディレクトリ
            **kwargs: crawl()に渡すオプション
        
        Returns:
            各URLの結果リスト
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        results = []
        
        for i, url in enumerate(urls):
            filename = f"page_{i+1:03d}.png"
            output_path = os.path.join(output_dir, filename)
            
            print(f"\n{'='*60}")
            print(f"[{i+1}/{len(urls)}] {url}")
            print(f"{'='*60}")
            
            result = self.crawl(url, output_path, **kwargs)
            results.append(result)
        
        return results
    
    def interactive_login(
        self,
        url: str,
        callback_on_ready: callable = None
    ):
        """
        手動ログイン用（画面操作が必要なサイト用）
        ユーザーがブラウザで操作した後、Cookieを保存
        
        Args:
            url: ログインページURL
            callback_on_ready: ユーザー操作完了を待つコールバック
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={
                    "width": self.viewport_width,
                    "height": self.viewport_height
                }
            )
            page = context.new_page()
            
            print(f"🔵 ブラウザを起動しました: {url}")
            try:
                page.goto(url, timeout=60000)
            except Exception as e:
                print(f"⚠️  ページ読み込み警告: {e}")
            
            # ユーザー操作待機
            if callback_on_ready:
                callback_on_ready()
            else:
                input("ログイン操作完了後、Enterキーを押してください...")
            
            # Cookie保存
            try:
                context.storage_state(path=self.auth_file)
                print(f"✅ Cookie情報を {self.auth_file} に保存しました")
            except Exception as e:
                print(f"❌ Cookie保存失敗: {e}")
            
            browser.close()


class URLManager:
    """
    サイトマップやリンク一覧からURLを管理するユーティリティクラス
    """
    
    @staticmethod
    def load_from_file(filepath: str) -> List[str]:
        """
        テキストファイルからURL一覧を読み込む
        （1行に1URL）
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return urls
    
    @staticmethod
    def save_to_file(filepath: str, urls: List[str]):
        """
        URL一覧をテキストファイルに保存
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\n')
    
    @staticmethod
    def extract_links_from_page(url: str, same_domain_only: bool = True) -> List[str]:
        """
        指定URLからリンクを抽出
        
        Args:
            url: 対象URL
            same_domain_only: 同一ドメインのみ抽出するか
        
        Returns:
            抽出されたURL一覧
        """
        from urllib.parse import urljoin, urlparse
        
        links = []
        base_domain = urlparse(url).netloc
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # 全<a>タグからhrefを抽出
                link_elements = page.query_selector_all('a[href]')
                
                for elem in link_elements:
                    href = elem.get_attribute('href')
                    if not href:
                        continue
                    
                    # 絶対URLに変換
                    absolute_url = urljoin(url, href)
                    
                    # 同一ドメインフィルター
                    if same_domain_only:
                        if urlparse(absolute_url).netloc != base_domain:
                            continue
                    
                    if absolute_url not in links:
                        links.append(absolute_url)
                
            except Exception as e:
                print(f"❌ リンク抽出エラー: {e}")
            finally:
                browser.close()
        
        return links

