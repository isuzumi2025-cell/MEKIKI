"""
認証ハンドラモジュール
Basic認証、フォームログイン、手動介入をサポート
"""
from typing import Dict, Any, Optional
from playwright.async_api import Page, BrowserContext
import asyncio


class AuthHandler:
    """認証処理ハンドラ"""
    
    @staticmethod
    async def handle_auth(
        page: Page, 
        context: BrowserContext,
        auth_config: Dict[str, Any],
        pause_callback: Optional[callable] = None
    ) -> bool:
        """
        認証設定に基づいて認証処理を実行
        
        Args:
            page: Playwright Page
            context: Browser Context
            auth_config: 認証設定
            pause_callback: 手動介入時の一時停止コールバック
            
        Returns:
            bool: 認証成功かどうか
        """
        mode = auth_config.get("mode", "none")
        
        if mode == "none":
            return True
        
        elif mode == "basic":
            # Basic認証はcontextレベルで設定済みのはず
            return True
        
        elif mode == "form":
            return await AuthHandler._handle_form_login(page, auth_config)
        
        elif mode == "manual":
            return await AuthHandler._handle_manual_login(page, auth_config, pause_callback)
        
        return True
    
    @staticmethod
    async def _handle_form_login(page: Page, auth_config: Dict[str, Any]) -> bool:
        """フォームログイン処理"""
        try:
            login_url = auth_config.get("login_url")
            username_selector = auth_config.get("username_selector")
            password_selector = auth_config.get("password_selector")
            submit_selector = auth_config.get("submit_selector")
            user = auth_config.get("user")
            password = auth_config.get("pass")
            success_indicator = auth_config.get("success_indicator")
            
            if not all([login_url, username_selector, password_selector, submit_selector, user, password]):
                print("Form login config incomplete")
                return False
            
            # ログインページへ移動
            await page.goto(login_url, wait_until="networkidle", timeout=30000)
            
            # 入力
            await page.fill(username_selector, user)
            await page.fill(password_selector, password)
            
            # 送信
            await page.click(submit_selector)
            
            # ログイン成功待機
            if success_indicator:
                try:
                    await page.wait_for_selector(success_indicator, timeout=15000)
                    return True
                except:
                    print(f"Login success indicator not found: {success_indicator}")
                    return False
            else:
                # インジケータなしの場合はネットワーク安定を待つ
                await page.wait_for_load_state("networkidle")
                return True
                
        except Exception as e:
            print(f"Form login failed: {e}")
            return False
    
    @staticmethod
    async def _handle_manual_login(
        page: Page, 
        auth_config: Dict[str, Any],
        pause_callback: Optional[callable] = None
    ) -> bool:
        """
        手動介入ログイン処理（2FA等）
        
        pause_callback が指定されている場合、それを呼び出してユーザー操作を待つ。
        指定されていない場合は固定時間待機（デモ用）。
        """
        try:
            login_url = auth_config.get("login_url")
            pause_message = auth_config.get("pause_message", "手動でログインを完了してください")
            
            if login_url:
                await page.goto(login_url, wait_until="networkidle", timeout=30000)
            
            print(f"[Manual Auth] {pause_message}")
            
            if pause_callback:
                # コールバックでジョブステータスを paused に変更し、
                # ユーザーがダッシュボードで「続行」を押すのを待つ
                await pause_callback()
            else:
                # デモ用：60秒待機（本番ではジョブのpaused/resume機構を使う）
                print("[Manual Auth] Waiting 60 seconds for manual login...")
                await asyncio.sleep(60)
            
            return True
            
        except Exception as e:
            print(f"Manual login handling failed: {e}")
            return False
    
    @staticmethod
    async def save_session(context: BrowserContext, path: str):
        """セッション情報（Cookie/Storage）を保存"""
        storage = await context.storage_state()
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(storage, f)
        print(f"Session saved to {path}")
    
    @staticmethod
    async def load_session(context: BrowserContext, path: str) -> bool:
        """保存済みセッションを読み込み（contextに適用）"""
        try:
            import json
            import os
            if not os.path.exists(path):
                return False
            # Note: storage_state loading is done at context creation time
            # This method is for checking if session file exists
            return True
        except Exception as e:
            print(f"Session load failed: {e}")
            return False
