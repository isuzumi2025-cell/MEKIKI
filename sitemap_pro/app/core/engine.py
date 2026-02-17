"""
スクレイピングエンジン
Playwright (Renderモード) と httpx (Fastモード) を提供
"""
import asyncio
from typing import Dict, Tuple, Optional, Any
from playwright.async_api import async_playwright
import httpx
from bs4 import BeautifulSoup
import hashlib
import os

from .parser import URLParser
from .auth import AuthHandler
from app.core.config import settings


class BaseEngine:
    """エンジン基底クラス"""
    
    async def fetch(self, url: str, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError


class PlaywrightEngine(BaseEngine):
    """
    Playwright ベースのレンダリングエンジン
    - JSレンダリング
    - フルページスクショ
    - フォームログイン対応
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def fetch(
        self, 
        url: str, 
        auth_config: Optional[Dict] = None,
        capture_sp: bool = False,
        session_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        URLをフェッチしてデータを返す
        
        Args:
            url: 対象URL
            auth_config: 認証設定
            capture_sp: SP版スクショも撮影するか
            session_path: セッションファイルパス（ある場合は読み込み）
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--disable-dev-shm-usage', '--no-sandbox']
            )
            
            # Context setup
            context_args = {
                "viewport": {"width": settings.PC_VIEWPORT_WIDTH, "height": settings.PC_VIEWPORT_HEIGHT},
                "user_agent": "SitemapGenerator/1.0",
                "ignore_https_errors": True
            }
            
            # Basic認証
            if auth_config and auth_config.get("mode") == "basic":
                context_args["http_credentials"] = {
                    "username": auth_config.get("user"),
                    "password": auth_config.get("pass")
                }
            
            # セッション復元
            if session_path and os.path.exists(session_path):
                context_args["storage_state"] = session_path
                
            context = await browser.new_context(**context_args)
            page = await context.new_page()
            
            result = {
                "url": url,
                "final_url": url,
                "status": 0,
                "title": "",
                "html": "",
                "screenshot": None,
                "screenshot_sp": None,
                "links": [],
                "metadata": {},
                "content_hash": None,
                "redirect_chain": [],
                "error": None
            }
            
            try:
                # フォームログイン処理（必要な場合）
                if auth_config and auth_config.get("mode") == "form":
                    login_success = await AuthHandler.handle_auth(page, context, auth_config)
                    if not login_success:
                        result["error"] = "Form login failed"
                        return result
                
                # リダイレクト追跡
                redirect_chain = []
                async def on_response(response):
                    if response.request.redirected_from:
                        redirect_chain.append(response.request.redirected_from.url)
                
                page.on("response", on_response)
                
                # Navigate
                response = await page.goto(
                    url, 
                    wait_until=settings.DEFAULT_WAIT_UNTIL, 
                    timeout=settings.DEFAULT_TIMEOUT
                )
                
                if response:
                    # Defensive access for status
                    if callable(getattr(response, 'status', None)):
                        result["status"] = response.status()
                    else:
                        result["status"] = getattr(response, 'status', 0)
                    
                    result["final_url"] = page.url
                    if redirect_chain:
                        result["redirect_chain"] = redirect_chain + [page.url]
                
                # Title
                result["title"] = await page.title()
                
                # Content
                result["html"] = await page.content()
                
                # メタデータ抽出
                result["metadata"] = URLParser.extract_metadata(result["html"])
                result["metadata"]["final_url"] = result["final_url"]
                result["metadata"]["redirect_chain"] = result["redirect_chain"]
                
                # コンテンツハッシュ
                from app.core.interfaces import MD5Hasher
                hasher = MD5Hasher()
                result["content_hash"] = hasher.compute(result["html"])
                
                # リンク抽出
                result["links"] = URLParser.extract_links(result["html"], result["final_url"])
                
                # スクロールバー非表示
                await page.add_style_tag(
                    content="body { overflow-y: hidden !important; } ::-webkit-scrollbar { display: none; }"
                )
                
                # PC スクショ
                try:
                    screenshot_bytes = await page.screenshot(
                        full_page=True, 
                        type=settings.SCREENSHOT_FORMAT, 
                        quality=settings.SCREENSHOT_QUALITY
                    )
                    result["screenshot"] = screenshot_bytes
                except Exception as e:
                    print(f"PC Screenshot error: {e}")
                
                # SP スクショ（オプション）
                if capture_sp:
                    try:
                        await page.set_viewport_size({
                            "width": settings.SP_VIEWPORT_WIDTH,
                            "height": settings.SP_VIEWPORT_HEIGHT
                        })
                        await page.wait_for_timeout(500)  # レイアウト調整待ち
                        screenshot_sp_bytes = await page.screenshot(
                            full_page=True,
                            type=settings.SCREENSHOT_FORMAT,
                            quality=settings.SCREENSHOT_QUALITY
                        )
                        result["screenshot_sp"] = screenshot_sp_bytes
                    except Exception as e:
                        print(f"SP Screenshot error: {e}")
                
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(tb)
                result["error"] = str(e)
                
            finally:
                await context.close()
                await browser.close()
                
            return result


class FastEngine(BaseEngine):
    """
    httpx ベースの高速エンジン
    - JSレンダリングなし
    - スクショなし
    - 静的サイト向け
    """
    
    async def fetch(
        self, 
        url: str, 
        auth_config: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """URLをフェッチ（スクショなし）"""
        
        auth = None
        if auth_config and auth_config.get("mode") == "basic":
            auth = (auth_config.get("user"), auth_config.get("pass"))

        result = {
            "url": url,
            "final_url": url,
            "status": 0,
            "title": "",
            "html": "",
            "screenshot": None,
            "screenshot_sp": None,
            "links": [],
            "metadata": {},
            "content_hash": None,
            "redirect_chain": [],
            "error": None
        }

        try:
            async with httpx.AsyncClient(
                verify=False, 
                follow_redirects=True, 
                timeout=30.0
            ) as client:
                resp = await client.get(url, auth=auth)
                result["status"] = resp.status_code
                result["final_url"] = str(resp.url)
                result["html"] = resp.text
                
                # リダイレクト履歴
                if resp.history:
                    result["redirect_chain"] = [str(r.url) for r in resp.history] + [str(resp.url)]
                
                if resp.status_code >= 400:
                    result["error"] = f"HTTP {resp.status_code}"
                
                # Parse
                soup = BeautifulSoup(resp.text, 'html.parser')
                if soup.title and soup.title.string:
                    result["title"] = soup.title.string
                
                # メタデータ
                result["metadata"] = URLParser.extract_metadata(resp.text)
                result["metadata"]["final_url"] = result["final_url"]
                result["metadata"]["redirect_chain"] = result["redirect_chain"]
                
                # コンテンツハッシュ
                from app.core.interfaces import MD5Hasher
                hasher = MD5Hasher()
                result["content_hash"] = hasher.compute(result["html"])
                
                # リンク抽出
                result["links"] = URLParser.extract_links(resp.text, str(resp.url))

        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
            
        return result
