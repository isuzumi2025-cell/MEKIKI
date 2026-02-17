"""
大規模拡張用インターフェース
MVP では InMemory 実装を使用し、将来的に Redis/PostgreSQL に差し替え可能
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol
from dataclasses import dataclass


# ==============================================================================
# Queue Backend Interface
# ==============================================================================

@dataclass
class QueueItem:
    """キューアイテム"""
    url: str
    depth: int
    parent_id: Optional[int] = None


class QueueBackend(ABC):
    """
    キューバックエンド抽象クラス
    MVPではInMemoryQueue、大規模時はRedisQueueに差し替え
    """
    
    @abstractmethod
    async def enqueue(self, item: QueueItem) -> None:
        """アイテムをキューに追加"""
        pass
    
    @abstractmethod
    async def dequeue(self) -> Optional[QueueItem]:
        """キューからアイテムを取得（FIFO）"""
        pass
    
    @abstractmethod
    async def is_empty(self) -> bool:
        """キューが空かどうか"""
        pass
    
    @abstractmethod
    async def size(self) -> int:
        """キューのサイズ"""
        pass


class InMemoryQueue(QueueBackend):
    """MVP用インメモリキュー"""
    
    def __init__(self):
        self._queue: List[QueueItem] = []
    
    async def enqueue(self, item: QueueItem) -> None:
        self._queue.append(item)
    
    async def dequeue(self) -> Optional[QueueItem]:
        if self._queue:
            return self._queue.pop(0)
        return None
    
    async def is_empty(self) -> bool:
        return len(self._queue) == 0
    
    async def size(self) -> int:
        return len(self._queue)


# ==============================================================================
# Database Backend Interface (for PostgreSQL migration)
# ==============================================================================

class DatabaseBackend(Protocol):
    """
    DB抽象プロトコル
    SQLite と PostgreSQL で共通インターフェース
    """
    
    def get_session(self): ...
    
    def bulk_insert_pages(self, pages: List[Dict[str, Any]]) -> List[int]:
        """バルクインサート（IDリストを返す）"""
        ...
    
    def bulk_insert_links(self, links: List[Dict[str, Any]]) -> None:
        """リンクのバルクインサート"""
        ...


# ==============================================================================
# Content Hasher Interface (for diff crawl)
# ==============================================================================

class ContentHasher(Protocol):
    """コンテンツハッシュ計算インターフェース"""
    
    def compute(self, html: str) -> str:
        """HTMLからハッシュを計算"""
        ...


class MD5Hasher:
    """MD5ベースのシンプルハッシャー（MVP用）"""
    
    def compute(self, html: str) -> str:
        import hashlib
        # HTMLからスクリプト/スタイルを除去して正規化
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # script, style, noscript を除去
        for tag in soup.find_all(['script', 'style', 'noscript']):
            tag.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        return hashlib.md5(text.encode('utf-8')).hexdigest()


# ==============================================================================
# Similarity Checker Interface (for duplicate detection addon)
# ==============================================================================

class SimilarityChecker(Protocol):
    """重複検出インターフェース（SimHash等のアドオン用）"""
    
    def compute_hash(self, text: str) -> int:
        """テキストから近似ハッシュを計算"""
        ...
    
    def is_similar(self, hash1: int, hash2: int, threshold: int = 3) -> bool:
        """2つのハッシュが類似しているか（ハミング距離）"""
        ...


# ==============================================================================
# Sitemap Importer Interface (for large-scale seed injection)
# ==============================================================================

class SitemapImporter(Protocol):
    """sitemap.xml からURLリストを取得"""
    
    async def parse(self, sitemap_url: str) -> List[str]:
        """sitemap.xml をパースしてURLリストを返す"""
        ...


class SimpleSitemapImporter:
    """シンプルなsitemap.xmlインポーター"""
    
    async def parse(self, sitemap_url: str) -> List[str]:
        import httpx
        from bs4 import BeautifulSoup
        
        urls = []
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(sitemap_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'xml')
                    
                    # sitemapindex の場合は再帰的に処理
                    sitemaps = soup.find_all('sitemap')
                    if sitemaps:
                        for sm in sitemaps:
                            loc = sm.find('loc')
                            if loc:
                                child_urls = await self.parse(loc.text)
                                urls.extend(child_urls)
                    else:
                        # urlset の場合
                        for url_tag in soup.find_all('url'):
                            loc = url_tag.find('loc')
                            if loc:
                                urls.append(loc.text)
        except Exception as e:
            print(f"Sitemap parse error: {e}")
        
        return urls


# ==============================================================================
# Crawler Extension Points
# ==============================================================================

class CrawlerHooks:
    """
    クローラー拡張フック
    各処理ステップでカスタムロジックを挿入可能
    """
    
    async def on_job_start(self, job_id: str) -> None:
        """ジョブ開始時"""
        pass
    
    async def on_job_complete(self, job_id: str, summary: Dict[str, Any]) -> None:
        """ジョブ完了時"""
        pass
    
    async def on_page_crawled(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """ページクロール後（データ変換等）"""
        return page_data
    
    async def on_before_enqueue(self, url: str, depth: int) -> bool:
        """キュー追加前（Falseを返すとスキップ）"""
        return True
    
    async def should_skip_page(self, url: str) -> bool:
        """ページをスキップすべきか（差分クロール等）"""
        return False
