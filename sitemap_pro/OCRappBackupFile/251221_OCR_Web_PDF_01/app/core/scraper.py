from playwright.sync_api import sync_playwright
from PIL import Image
import os
import json
import io
import time

# 巨大な画像を許可
Image.MAX_IMAGE_PIXELS = None

class WebScraper:
    def __init__(self, auth_file="auth.json"):
        self.auth_file = auth_file

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
            
            try:
                print(f"🌍 アクセス中: {url}")
                page_high.goto(url, timeout=60000)
                page_high.wait_for_load_state("networkidle")

                # HTMLテキスト取得
                text_content = page_high.inner_text("body")
                title = page_high.title()

                # [高画質] 1画面分のスクショ
                view_bytes = page_high.screenshot(full_page=False)
                img_view = Image.open(io.BytesIO(view_bytes))
                
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
                img_full = Image.open(io.BytesIO(full_bytes))
                
                return title, text_content, img_full, img_view

            except Exception as e:
                raise Exception(f"取得失敗: {str(e)}")
            finally:
                context_high.close()
                context_full.close()
                browser.close()