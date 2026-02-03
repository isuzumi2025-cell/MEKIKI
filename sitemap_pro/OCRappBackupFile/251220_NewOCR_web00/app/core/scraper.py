from playwright.sync_api import sync_playwright
import os
import json
import time
from urllib.parse import urljoin, urlparse

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
            browser, context, page = self._setup_browser(p, username, password)
            try:
                print(f"🌍 アクセス中: {url}")
                page.goto(url, timeout=60000)
                page.wait_for_load_state("networkidle")

                text_content = page.inner_text("body")
                title = page.title()
                
                return title, text_content
            except Exception as e:
                raise Exception(f"取得失敗: {str(e)}")
            finally:
                context.close()
                browser.close()

    def recursive_crawl(self, root_url, max_depth=2, max_pages=10, username=None, password=None):
        """
        指定されたURLから再帰的にリンクを辿り、サイトマップデータを作成する
        Returns:
            nodes (list): [{"url": str, "title": str, "screenshot": path, "text": str, "depth": int}]
            edges (list): [{"from": url, "to": url}]
        """
        visited = set()
        queue = [(root_url, 0)]
        nodes = []
        edges = []
        
        # 保存先
        img_dir = os.path.join("output_data", "sitemap_images")
        os.makedirs(img_dir, exist_ok=True)

        with sync_playwright() as p:
            browser, context, page = self._setup_browser(p, username, password)
            
            try:
                while queue and len(visited) < max_pages:
                    url, depth = queue.pop(0)
                    if url in visited or depth > max_depth:
                        continue
                    
                    visited.add(url)
                    print(f"🕷️ Crawling: {url} (Depth: {depth})")
                    
                    try:
                        page.goto(url, timeout=30000, wait_until="networkidle")
                        page.wait_for_timeout(1000) # レンダリング安定待ち
                        
                        # データ取得
                        title = page.title()
                        text_content = page.inner_text("body")
                        
                        # スクリーンショット
                        filename = f"node_{len(visited)}.png"
                        screenshot_path = os.path.join(img_dir, filename)
                        page.screenshot(path=screenshot_path, full_page=False)
                        
                        nodes.append({
                            "id": len(visited),
                            "url": url,
                            "title": title,
                            "screenshot": screenshot_path,
                            "text": text_content[:200] + "...", # プレビュー用
                            "full_text": text_content,
                            "depth": depth
                        })

                        # 次のリンクを取得
                        if depth < max_depth:
                            hrefs = page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
                            root_domain = urlparse(root_url).netloc
                            
                            for href in hrefs:
                                # URL正規化とドメインチェック
                                parsed = urlparse(href)
                                if parsed.netloc == root_domain and href not in visited:
                                    queue.append((href, depth + 1))
                                    edges.append({"from": url, "to": href})
                                    
                    except Exception as e:
                        print(f"⚠️ Skip {url}: {e}")
                        continue
                        
            finally:
                context.close()
                browser.close()
                
        return nodes, edges

    def _setup_browser(self, p, username, password):
        context_options = {}
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, 'r') as f: json.load(f)
                context_options['storage_state'] = self.auth_file
            except: pass

        if username and password:
            context_options['http_credentials'] = {'username': username, 'password': password}

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**context_options)
        page = context.new_page()
        return browser, context, page