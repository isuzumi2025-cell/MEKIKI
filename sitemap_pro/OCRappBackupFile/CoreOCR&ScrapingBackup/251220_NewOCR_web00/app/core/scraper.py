from playwright.sync_api import sync_playwright
import os
import json

class WebScraper:
    def __init__(self, auth_file="auth.json"):
        self.auth_file = auth_file

    def interactive_login(self, url, wait_callback):
        """
        手動ログイン用（Basic認証以外の、画面操作が必要なサイト用）
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            print(f"🔵 ブラウザを起動しました: {url}")
            try:
                page.goto(url, timeout=60000)
            except Exception as e:
                print(f"⚠️ ページ読み込み警告: {e}")

            # GUI側のOK待機
            wait_callback()
            
            # Cookie保存
            self.save_session(context)
            # Basic認証情報はここからは取れないため、GUI入力に頼る

    def save_session(self, context):
        try:
            context.storage_state(path=self.auth_file)
            print(f"✅ Cookie情報を {self.auth_file} に保存しました。")
        except Exception as e:
            print(f"❌ 保存失敗: {e}")

    def fetch_text(self, url, username=None, password=None):
        """
        保存されたCookie、または指定されたID/PASSを使ってテキストを取得する
        """
        with sync_playwright() as p:
            # コンテキスト作成オプションの準備
            context_options = {}
            
            # 1. 以前のCookieがあれば読み込む
            if os.path.exists(self.auth_file):
                try:
                    # 読み込んでみて、壊れていなければ採用
                    with open(self.auth_file, 'r') as f: json.load(f)
                    context_options['storage_state'] = self.auth_file
                    print("🔓 保存されたCookieを使用します...")
                except:
                    print("⚠️ Cookieファイルが無効です。")

            # 2. ★Basic認証情報があればセットする
            if username and password:
                context_options['http_credentials'] = {
                    'username': username,
                    'password': password
                }
                print(f"🔑 Basic認証情報({username})を使用します...")

            # ブラウザ起動
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(**context_options)

            page = context.new_page()
            try:
                print(f"🌍 アクセス中: {url}")
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle") # 読み込み完了まで待つ

                text_content = page.inner_text("body")
                title = page.title()
                
                return title, text_content
            except Exception as e:
                # エラー詳細を表示
                raise Exception(f"取得失敗: {str(e)}")
            finally:
                context.close()
                browser.close()