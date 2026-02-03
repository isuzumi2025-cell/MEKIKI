from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse, urljoin
import os
import json
import io
import time
import re

# 巨大な画像を許可
Image.MAX_IMAGE_PIXELS = None

class WebScraper:
    def __init__(self, auth_file="auth.json"):
        self.auth_file = auth_file
        self.visited_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()

    def interactive_login(self, url, wait_callback):
        """手動ログイン用"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            print(f"🔵 ブラウザを起動しました: {url}")
            try:
                page.goto(url, timeout=60000)
            except Exception as e:
                print(f"⚠️ ページ読み込み警告: {e}")

            wait_callback()
            self.save_session(context)

    def save_session(self, context):
        try:
            context.storage_state(path=self.auth_file)
            print(f"✅ Cookie情報を {self.auth_file} に保存しました。")
        except Exception as e:
            print(f"❌ 保存失敗: {e}")

    def _auto_scroll(self, page):
        """Lazy Loading対策: 少しずつスクロールして読み込ませる"""
        print("⏬ 画像読み込みのためスクロール中...")
        page.evaluate("""
            async () => {
                await new Promise((resolve) => {
                    var totalHeight = 0;
                    var distance = 200; // スクロール幅
                    var timer = setInterval(() => {
                        var scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;

                        if(totalHeight >= scrollHeight - window.innerHeight){
                            clearInterval(timer);
                            resolve();
                        }
                    }, 50); // スクロール速度
                });
            }
        """)
        # 読み込み待ち
        time.sleep(2)
        # 一番上に戻す
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

    def fetch_text(self, url, username=None, password=None):
        """
        テキストとスクリーンショットを取得
        - 全体画像: 容量オーバー防止のため 1.5倍画質
        - 1画面画像: 精密OCRのため 3.0倍画質
        """
        with sync_playwright() as p:
            context_options = {}
            if os.path.exists(self.auth_file):
                try:
                    with open(self.auth_file, 'r') as f: json.load(f)
                    context_options['storage_state'] = self.auth_file
                except: pass

            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }

            # ブラウザ起動
            browser = p.chromium.launch(headless=True)
            
            # --- 1. 高画質コンテキスト (OCR用・1画面分) ---
            # device_scale_factor=3.0 でくっきり撮影
            context_high = browser.new_context(
                **context_options, 
                viewport={'width': 1280, 'height': 800},
                device_scale_factor=3.0 
            )
            page_high = context_high.new_page()
            
            # context_fullをNoneで初期化（finallyブロックでのエラー防止）
            context_full = None
            
            try:
                print(f"🌍 アクセス中: {url}")
                page_high.goto(url, timeout=60000)
                page_high.wait_for_load_state("networkidle")

                # HTMLテキスト取得
                text_content = page_high.inner_text("body")
                title = page_high.title()

                # [高画質] 1画面分のスクショ
                view_bytes = page_high.screenshot(full_page=False)
                
                # バイトデータの検証
                if view_bytes and len(view_bytes) > 0:
                    try:
                        img_view = Image.open(io.BytesIO(view_bytes))
                    except Exception as e:
                        print(f"⚠️ 画像読み込みエラー: {str(e)}")
                        img_view = self._create_placeholder_image("1画面画像取得失敗")
                else:
                    print(f"⚠️ 画像データが空です")
                    img_view = self._create_placeholder_image("1画面画像取得失敗")
                
                # --- 2. 標準画質コンテキスト (全体表示用) ---
                # 全体スクショは長くなりすぎるので device_scale_factor=1.5 に抑える
                # これで「途切れ」を防ぐ
                context_full = browser.new_context(
                    **context_options, 
                    viewport={'width': 1280, 'height': 800},
                    device_scale_factor=1.5
                )
                page_full = context_full.new_page()
                page_full.goto(url, timeout=60000) # 同じページを開く
                page_full.wait_for_load_state("networkidle")

                # スクロールして全読み込み
                self._auto_scroll(page_full)

                # [中画質] 全体スクショ
                full_bytes = page_full.screenshot(full_page=True)
                
                # バイトデータの検証
                if full_bytes and len(full_bytes) > 0:
                    try:
                        img_full = Image.open(io.BytesIO(full_bytes))
                    except Exception as e:
                        print(f"⚠️ 画像読み込みエラー: {str(e)}")
                        img_full = self._create_placeholder_image("全体画像取得失敗")
                else:
                    print(f"⚠️ 画像データが空です")
                    img_full = self._create_placeholder_image("全体画像取得失敗")
                
                return title, text_content, img_full, img_view

            except Exception as e:
                raise Exception(f"取得失敗: {str(e)}")
            finally:
                if context_high:
                    context_high.close()
                if context_full:
                    context_full.close()
                if browser:
                    browser.close()
    
    def crawl_site(
        self,
        base_url: str,
        max_pages: int = 50,
        max_depth: int = 3,
        same_domain_only: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        サイト内をクローリング（下層ページも取得）
        
        Args:
            base_url: 開始URL
            max_pages: 最大取得ページ数
            max_depth: 最大深さ
            same_domain_only: 同一ドメインのみ
            username: Basic認証ユーザー名
            password: Basic認証パスワード
            progress_callback: 進捗コールバック関数
        
        Returns:
            [{"url": str, "title": str, "text": str, "full_image": Image, "viewport_image": Image, "error": str}, ...]
        """
        self.visited_urls = set()
        self.failed_urls = set()
        
        base_domain = urlparse(base_url).netloc
        to_visit = [(base_url, 0)]  # (url, depth)
        results = []
        
        print(f"🌐 クローリング開始: {base_url}")
        print(f"📋 設定: 最大{max_pages}ページ, 深さ{max_depth}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # コンテキスト設定
            context_options = {
                'viewport': {'width': 1280, 'height': 800},
                'device_scale_factor': 2.0
            }
            
            # 認証情報
            if os.path.exists(self.auth_file):
                try:
                    with open(self.auth_file, 'r') as f:
                        json.load(f)
                    context_options['storage_state'] = self.auth_file
                except:
                    pass
            
            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }
            
            context = browser.new_context(**context_options)
            page = context.new_page()
            
            try:
                while to_visit and len(results) < max_pages:
                    current_url, depth = to_visit.pop(0)
                    
                    # 訪問済みチェック
                    if current_url in self.visited_urls or current_url in self.failed_urls:
                        continue
                    
                    # ドメインチェック
                    if same_domain_only:
                        current_domain = urlparse(current_url).netloc
                        if current_domain != base_domain:
                            continue
                    
                    # 深さチェック
                    if depth > max_depth:
                        continue
                    
                    try:
                        print(f"📄 [{len(results) + 1}/{max_pages}] 深さ{depth}: {current_url}")
                        
                        # 進捗通知
                        if progress_callback:
                            progress_callback(len(results) + 1, max_pages, current_url)
                        
                        # ページにアクセス
                        page.goto(current_url, timeout=60000)
                        page.wait_for_load_state("networkidle")
                        
                        # Lazy Loading対応スクロール
                        self._auto_scroll(page)
                        
                        # データ取得
                        title = page.title()
                        text_content = page.inner_text("body")
                        
                        # スクリーンショット（1画面分）
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(0.3)
                        viewport_bytes = page.screenshot(full_page=False)
                        
                        # バイトデータの検証
                        if viewport_bytes and len(viewport_bytes) > 0:
                            try:
                                viewport_image = Image.open(io.BytesIO(viewport_bytes))
                            except Exception as e:
                                print(f"⚠️ 1画面画像変換エラー: {str(e)}")
                                viewport_image = self._create_placeholder_image("1画面画像取得失敗")
                        else:
                            viewport_image = self._create_placeholder_image("1画面画像取得失敗")
                        
                        # スクリーンショット（フルページ）
                        full_bytes = page.screenshot(full_page=True)
                        
                        # バイトデータの検証
                        if full_bytes and len(full_bytes) > 0:
                            try:
                                full_image = Image.open(io.BytesIO(full_bytes))
                            except Exception as e:
                                print(f"⚠️ 全体画像変換エラー: {str(e)}")
                                full_image = self._create_placeholder_image("全体画像取得失敗")
                        else:
                            full_image = self._create_placeholder_image("全体画像取得失敗")
                        
                        results.append({
                            "url": current_url,
                            "title": title,
                            "text": text_content,
                            "full_image": full_image,
                            "viewport_image": viewport_image,
                            "depth": depth,
                            "error": None
                        })
                        
                        self.visited_urls.add(current_url)
                        
                        # 次の深さのリンクを抽出（深さ制限内の場合のみ）
                        if depth < max_depth:
                            links = self._extract_links(page, current_url)
                            for link in links:
                                # フラグメント除去
                                link = link.split('#')[0]
                                if link and link not in self.visited_urls and link not in self.failed_urls:
                                    # 同じ深さのリンクはキューの後ろに追加
                                    to_visit.append((link, depth + 1))
                        
                        time.sleep(1.0)  # サーバー負荷軽減
                        
                    except Exception as e:
                        error_msg = str(e)
                        print(f"⚠️ エラー: {current_url} - {error_msg}")
                        self.failed_urls.add(current_url)
                        
                        # エラー情報を記録（プレースホルダー画像を使用）
                        error_placeholder = self._create_placeholder_image(f"取得失敗\n{error_msg[:30]}...")
                        
                        results.append({
                            "url": current_url,
                            "title": f"取得失敗: {current_url}",
                            "text": "",
                            "full_image": error_placeholder,
                            "viewport_image": error_placeholder,
                            "depth": depth,
                            "error": error_msg
                        })
                        continue
                
            finally:
                context.close()
                browser.close()
        
        print(f"✅ クローリング完了: {len(results)}ページ取得")
        return results
    
    def _create_placeholder_image(self, message: str = "画像なし", width: int = 1280, height: int = 800) -> Image.Image:
        """
        プレースホルダー画像を作成
        
        Args:
            message: 表示するメッセージ
            width: 画像幅
            height: 画像高さ
        
        Returns:
            PIL Image
        """
        # グレーの背景画像を作成
        img = Image.new('RGB', (width, height), color='#2B2B2B')
        draw = ImageDraw.Draw(img)
        
        # 中央に赤い枠を描画
        margin = 50
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline='#FF4444',
            width=5
        )
        
        # テキストを描画（フォントなしでシンプルに）
        text = f"⚠️ {message}"
        
        # テキストのバウンディングボックスを取得（簡易計算）
        text_width = len(text) * 10
        text_height = 20
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2
        
        draw.text((text_x, text_y), text, fill='#FF4444')
        
        return img
    
    def _extract_links(self, page, base_url: str) -> List[str]:
        """
        ページから有効なリンクを抽出
        
        Args:
            page: Playwrightのページオブジェクト
            base_url: ベースURL
        
        Returns:
            リンクのリスト
        """
        try:
            links = page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(href => href.startsWith('http'));
                }
            """)
            
            # 絶対URLに変換
            absolute_links = []
            for link in links:
                absolute_url = urljoin(base_url, link)
                
                # 除外パターン（画像、CSS、JSなど）
                if re.search(r'\.(jpg|jpeg|png|gif|css|js|pdf|zip)$', absolute_url, re.IGNORECASE):
                    continue
                
                absolute_links.append(absolute_url)
            
            return absolute_links
            
        except Exception as e:
            print(f"⚠️ リンク抽出エラー: {str(e)}")
            return []