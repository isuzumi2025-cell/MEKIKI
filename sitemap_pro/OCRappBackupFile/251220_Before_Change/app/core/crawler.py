"""
Webクローラー
指定されたルートURLから同一ドメイン内のリンクを辿ってスクレイピング
"""
from urllib.parse import urljoin, urlparse
from typing import List, Set, Optional, Callable
from app.core.scraper import WebScraper
import time


class WebCrawler:
    """Webクローラークラス"""
    
    def __init__(
        self,
        max_pages: int = 50,
        max_depth: int = 5,
        delay: float = 1.0,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Args:
            max_pages: 最大ページ数
            max_depth: 最大深さ
            delay: リクエスト間の遅延（秒）
            username: Basic認証ユーザー名
            password: Basic認証パスワード
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.username = username
        self.password = password
        self.scraper = WebScraper()
        self.visited_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
    
    def crawl(
        self,
        root_url: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[dict]:
        """
        ルートURLからクローリングを開始
        
        Args:
            root_url: 開始URL
            progress_callback: 進捗コールバック (url, current, total) -> None
        
        Returns:
            [{"url": str, "title": str, "text": str, "screenshot_path": str, "error": str or None}, ...]
        """
        self.visited_urls.clear()
        self.failed_urls.clear()
        
        root_domain = urlparse(root_url).netloc
        results = []
        queue = [(root_url, 0)]  # (url, depth)
        
        while queue and len(results) < self.max_pages:
            current_url, depth = queue.pop(0)
            
            # 深さチェック
            if depth > self.max_depth:
                continue
            
            # 既に訪問済み
            if current_url in self.visited_urls:
                continue
            
            # ドメインチェック
            current_domain = urlparse(current_url).netloc
            if current_domain != root_domain:
                continue
            
            try:
                # スクレイピング実行
                if progress_callback:
                    progress_callback(current_url, len(results), self.max_pages)
                
                title, text, img_full, img_view = self.scraper.fetch_text(
                    current_url,
                    username=self.username,
                    password=self.password
                )
                
                # スクリーンショットを保存（オプション）
                screenshot_path = None  # 必要に応じて保存処理を追加
                
                # 暫定版: 画像全体を1つのエリアとして扱う
                # 将来的にはPlaywrightで要素ごとの位置を取得する可能性あり
                # img_viewのサイズを取得
                img_width, img_height = img_view.size if img_view else (1280, 800)
                areas = [{
                    "text": text,
                    "bbox": [0, 0, img_width, img_height],
                    "area_id": 1
                }]
                
                results.append({
                    "url": current_url,
                    "title": title,
                    "text": text,
                    "screenshot_path": screenshot_path,
                    "areas": areas,  # bbox付きテキスト領域
                    "screenshot_image": img_view,  # PIL Image
                    "error": None  # 成功時はNone
                })
                
                self.visited_urls.add(current_url)
                
                # リンクを抽出してキューに追加（次の深さ）
                if depth < self.max_depth:
                    links = self._extract_links(current_url, text)
                    for link in links:
                        if link not in self.visited_urls and link not in [q[0] for q in queue]:
                            queue.append((link, depth + 1))
                
                # 遅延
                if self.delay > 0:
                    time.sleep(self.delay)
                    
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ エラー: {current_url} - {error_msg}")
                self.failed_urls.add(current_url)
                
                # エラー情報を含めて結果に追加（マッチングから除外できるように）
                results.append({
                    "url": current_url,
                    "title": f"取得失敗: {current_url}",
                    "text": "",
                    "screenshot_path": None,
                    "areas": [],
                    "screenshot_image": None,
                    "error": error_msg  # エラーメッセージを記録
                })
                continue
        
        return results
    
    def _extract_links(self, base_url: str, html_text: str) -> List[str]:
        """
        HTMLテキストからリンクを抽出（簡易版）
        実際の実装では、BeautifulSoupなどを使うとより正確
        """
        import re
        
        # 簡易的なリンク抽出（href属性を探す）
        pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(pattern, html_text, re.IGNORECASE)
        
        links = []
        for match in matches:
            # 相対URLを絶対URLに変換
            absolute_url = urljoin(base_url, match)
            
            # フラグメント（#）を除去
            absolute_url = absolute_url.split('#')[0]
            
            # 有効なURLかチェック
            parsed = urlparse(absolute_url)
            if parsed.scheme in ['http', 'https']:
                links.append(absolute_url)
        
        return links
    
    def get_statistics(self) -> dict:
        """クローリング統計を取得"""
        return {
            "visited_count": len(self.visited_urls),
            "failed_count": len(self.failed_urls),
            "visited_urls": list(self.visited_urls),
            "failed_urls": list(self.failed_urls)
        }

