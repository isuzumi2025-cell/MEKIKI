"""
robots.txt パーサー
"""
import httpx
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Optional
import asyncio


class RobotsChecker:
    """robots.txt をパースしてクロール許可を判定"""
    
    def __init__(self):
        self._cache: dict[str, RobotFileParser] = {}
        self._user_agent = "SitemapGenerator/1.0"
    
    async def can_fetch(self, url: str, respect_robots: bool = True) -> bool:
        """
        URLがクロール可能かどうかをチェック
        respect_robots=False の場合は常にTrue
        """
        if not respect_robots:
            return True
        
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # キャッシュ確認
        if base_url not in self._cache:
            await self._load_robots(base_url)
        
        parser = self._cache.get(base_url)
        if parser is None:
            # robots.txt が取得できない場合はクロール許可
            return True
        
        return parser.can_fetch(self._user_agent, url)
    
    async def _load_robots(self, base_url: str):
        """robots.txt を読み込んでキャッシュ"""
        robots_url = urljoin(base_url, "/robots.txt")
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(response.text.splitlines())
                    self._cache[base_url] = parser
                else:
                    # 404等の場合はNoneをキャッシュ（制限なし扱い）
                    self._cache[base_url] = None
        except Exception as e:
            print(f"robots.txt fetch error for {base_url}: {e}")
            self._cache[base_url] = None
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache.clear()


# シングルトンインスタンス
robots_checker = RobotsChecker()
