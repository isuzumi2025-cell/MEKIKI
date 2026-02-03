"""
BFS クローラー
親子関係追跡、並列処理、時間制限、監査統合
"""
import asyncio
import os
import time
from datetime import datetime
from typing import Set, List, Dict, Any, Optional
import uuid

from sqlalchemy.orm import Session
from app.db import models
from app.core.engine import PlaywrightEngine, FastEngine
from app.core.parser import URLParser
from app.core.auditor import Auditor
from app.core.robots import robots_checker
from app.core.config import settings
from app.core.interfaces import InMemoryQueue, QueueItem, CrawlerHooks


class Crawler:
    """
    BFS クローラー
    
    Features:
    - BFS探索（浅い階層優先）
    - 親子関係追跡
    - 並列処理（Semaphore制御）
    - 時間制限（必ず終わる）
    - 監査統合
    """
    
    def __init__(self, job_id: str, db: Session, hooks: Optional[CrawlerHooks] = None):
        self.job_id = job_id
        self.db = db
        self.job = db.query(models.Job).filter(models.Job.id == job_id).first()
        self.profile = self.job.profile
        self.hooks = hooks or CrawlerHooks()
        
        # ベースドメイン
        self.base_url = URLParser.normalize_url(
            self.job.start_url or self.profile.target_url,
            keep_params=self.profile.keep_params or []
        )
        from urllib.parse import urlparse
        self.base_domain = urlparse(self.base_url).netloc
        self.allowed_domains = [self.base_domain] + (self.profile.allow_domains or [])
        
        # エンジン選択
        if self.profile.mode == "fast":
            self.engine = FastEngine()
        else:
            self.engine = PlaywrightEngine()
        
        # 状態管理
        self.visited: Set[str] = set()
        self.url_to_id: Dict[str, int] = {}
        self.queue = InMemoryQueue()
        
        # 制限
        self.max_pages = self.profile.max_pages or settings.DEFAULT_MAX_PAGES
        self.max_depth = self.profile.max_depth or settings.DEFAULT_MAX_DEPTH
        self.max_time = self.profile.max_time_seconds or settings.DEFAULT_MAX_TIME_SECONDS
        self.concurrent_limit = self.profile.concurrent_limit or settings.DEFAULT_CONCURRENT_LIMIT
        
        # デフォルト除外拡張子（常に適用）
        self.DEFAULT_EXCLUDE_EXTENSIONS = {
            # ドキュメント
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            # 画像
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff',
            # 動画・音声
            '.mp4', '.mp3', '.avi', '.mov', '.wmv', '.flv', '.wav', '.ogg', '.webm',
            # アーカイブ
            '.zip', '.rar', '.tar', '.gz', '.7z',
            # その他
            '.exe', '.dmg', '.apk', '.ipa', '.css', '.js', '.json', '.xml', '.txt'
        }
        
        # 監査
        self.auditor = Auditor(db, job_id)
        
        # 開始時刻
        self.start_time: float = 0
    
    def get_excluded_extension(self, url: str) -> str:
        """URLが除外対象の拡張子を持つ場合、その拡張子を返す（なければNone）"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        for ext in self.DEFAULT_EXCLUDE_EXTENSIONS:
            if path.endswith(ext):
                return ext
        return None
    
    def should_exclude_by_extension(self, url: str) -> bool:
        """URLが除外対象の拡張子を持つかチェック（互換性用）"""
        return self.get_excluded_extension(url) is not None
    
    def _save_excluded_link(self, url: str, parent_id: int, extension: str):
        """除外されたリンクをDBに保存"""
        # 親ページのURLを取得
        source_url = None
        if parent_id:
            parent_page = self.db.query(models.Page).filter(models.Page.id == parent_id).first()
            if parent_page:
                source_url = parent_page.url
        
        excluded_link = models.ExcludedLink(
            job_id=self.job_id,
            url=url,
            source_url=source_url,
            extension=extension
        )
        self.db.add(excluded_link)
        self.db.commit()

    async def run(self):
        """クロール実行"""
        self.start_time = time.time()
        
        # ジョブステータス更新
        self.job.status = "running"
        self.db.commit()
        
        await self.hooks.on_job_start(self.job_id)
        
        # 初期URLをキューに追加
        await self.queue.enqueue(QueueItem(url=self.base_url, depth=0, parent_id=None))
        
        # 並列制御用セマフォ
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        all_findings = []
        
        try:
            while not await self.queue.is_empty():
                # 終了条件チェック
                if self._should_stop():
                    break
                
                # バッチ取得（並列処理用）
                batch = await self._get_batch(min(self.concurrent_limit, self.max_pages - self.job.pages_crawled))
                if not batch:
                    break
                
                # 並列処理
                tasks = [self._process_url(item, semaphore) for item in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 結果処理
                for result in results:
                    if isinstance(result, Exception):
                        print(f"Task error: {result}")
                    elif result:
                        page, page_findings = result
                        all_findings.extend(page_findings)
                
                # レート制限
                await asyncio.sleep(settings.DEFAULT_RATE_LIMIT_DELAY)
            
            # 重複チェック
            pages = self.db.query(models.Page).filter(models.Page.job_id == self.job_id).all()
            dup_findings = self.auditor.check_duplicates(pages)
            all_findings.extend(dup_findings)
            
            # Findings保存
            self.auditor.save_findings(all_findings)
            
            # サマリー生成
            self.job.status = "completed"
            self.job.result_summary = self._generate_summary(all_findings)
            
        except Exception as e:
            print(f"Crawl failed: {e}")
            import traceback
            traceback.print_exc()
            self.job.status = "failed"
            self.job.result_summary = {"error": str(e)}
            
        finally:
            self.job.completed_at = datetime.utcnow()
            self.db.commit()
            await self.hooks.on_job_complete(self.job_id, self.job.result_summary)
    
    async def _get_batch(self, count: int) -> List[QueueItem]:
        """キューからバッチ取得"""
        batch = []
        while len(batch) < count and not await self.queue.is_empty():
            item = await self.queue.dequeue()
            if item and item.url not in self.visited and item.depth <= self.max_depth:
                batch.append(item)
            elif item and item.url in self.visited:
                # クロスリンク処理
                await self._handle_cross_link(item)
        return batch
    
    async def _handle_cross_link(self, item: QueueItem):
        """既訪問URLへのリンク（クロスリンク）を処理"""
        target_id = self.url_to_id.get(item.url)
        if item.parent_id and target_id and item.parent_id != target_id:
            exists = self.db.query(models.Link).filter_by(
                job_id=self.job_id,
                source_page_id=item.parent_id,
                target_page_id=target_id
            ).first()
            if not exists:
                link = models.Link(
                    job_id=self.job_id,
                    source_page_id=item.parent_id,
                    target_page_id=target_id,
                    type="internal"
                )
                self.db.add(link)
                self.db.commit()
    
    async def _process_url(self, item: QueueItem, semaphore: asyncio.Semaphore):
        """単一URLを処理"""
        async with semaphore:
            url = item.url
            depth = item.depth
            parent_id = item.parent_id
            
            # 二重チェック
            if url in self.visited:
                return None
            
            # デフォルト拡張子除外チェック（PDF、画像等をスキップ）
            excluded_ext = self.get_excluded_extension(url)
            if excluded_ext:
                print(f"Excluded by extension: {url}")
                # 除外リンクをDBに記録
                self._save_excluded_link(url, parent_id, excluded_ext)
                return None
            
            # robots.txt チェック
            if self.profile.respect_robots:
                can_fetch = await robots_checker.can_fetch(url, respect_robots=True)
                if not can_fetch:
                    print(f"Blocked by robots.txt: {url}")
                    return None
            
            # 除外パターンチェック
            if self.profile.exclude_patterns:
                if URLParser.matches_exclude_pattern(url, self.profile.exclude_patterns):
                    print(f"Excluded by pattern: {url}")
                    return None
            
            # フッククエリ
            if await self.hooks.should_skip_page(url):
                return None
            
            self.visited.add(url)
            print(f"Crawling [{self.job.pages_crawled + 1}/{self.max_pages}]: {url}")
            
            # フェッチ
            data = await self.engine.fetch(
                url,
                auth_config=self.profile.auth_config,
                capture_sp=self.profile.capture_sp
            )
            
            # フック処理
            data = await self.hooks.on_page_crawled(data)
            
            # スクショ保存
            screenshot_path = None
            screenshot_sp_path = None
            
            if data.get("screenshot"):
                screenshot_path = await self._save_screenshot(data["screenshot"], "pc")
            
            if data.get("screenshot_sp"):
                screenshot_sp_path = await self._save_screenshot(data["screenshot_sp"], "sp")
            
            # Page保存
            page = models.Page(
                job_id=self.job_id,
                url=url,
                title=data.get("title"),
                status_code=data.get("status", 0),
                depth=depth,
                screenshot_path=screenshot_path,
                screenshot_sp_path=screenshot_sp_path,
                content_hash=data.get("content_hash"),
                metadata_info=data.get("metadata", {}),
                crawled_at=datetime.utcnow()
            )
            self.db.add(page)
            self.db.commit()
            
            self.url_to_id[url] = page.id
            self.job.pages_crawled += 1
            self.db.commit()
            
            # 親リンク作成
            if parent_id:
                link = models.Link(
                    job_id=self.job_id,
                    source_page_id=parent_id,
                    target_page_id=page.id,
                    type="internal"
                )
                self.db.add(link)
                self.db.commit()
            
            # 監査チェック
            findings = self.auditor.check_page(page)
            
            # 子リンクをキューに追加
            for link_url in data.get("links", []):
                # 正規化（keep_params適用）
                normalized = URLParser.normalize_url(
                    link_url,
                    keep_params=self.profile.keep_params or []
                )
                
                if not normalized:
                    continue
                
                # 内部リンクチェック
                if URLParser.is_internal_link(normalized, self.base_domain, self.allowed_domains):
                    # フックチェック
                    if await self.hooks.on_before_enqueue(normalized, depth + 1):
                        await self.queue.enqueue(QueueItem(
                            url=normalized,
                            depth=depth + 1,
                            parent_id=page.id
                        ))
            
            return (page, findings)
    
    async def _save_screenshot(self, data: bytes, suffix: str) -> str:
        """スクショを保存してパスを返す"""
        filename = f"{uuid.uuid4()}_{suffix}.{settings.SCREENSHOT_FORMAT}"
        save_dir = os.path.join(settings.OUTPUT_DIR, self.job_id, "screenshots")
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(data)
        
        # 相対パス返却（API経由でアクセス）
        return f"outputs/{self.job_id}/screenshots/{filename}"
    
    def _should_stop(self) -> bool:
        """停止条件チェック"""
        # ページ数上限
        if self.job.pages_crawled >= self.max_pages:
            print(f"Reached max pages limit: {self.max_pages}")
            return True
        
        # 時間制限
        elapsed = time.time() - self.start_time
        if elapsed >= self.max_time:
            print(f"Reached max time limit: {self.max_time}s")
            return True
        
        # ジョブステータス（停止リクエスト）
        self.db.refresh(self.job)
        if self.job.status == "stopped":
            print("Job stopped by user")
            return True
        
        return False
    
    def _generate_summary(self, findings: List[models.Finding]) -> Dict[str, Any]:
        """結果サマリーを生成"""
        pages = self.db.query(models.Page).filter(models.Page.job_id == self.job_id).all()
        
        status_200 = sum(1 for p in pages if p.status_code == 200)
        status_404 = sum(1 for p in pages if p.status_code == 404)
        status_5xx = sum(1 for p in pages if p.status_code and p.status_code >= 500)
        
        finding_summary = Auditor.summarize_findings(findings)
        
        return {
            "total_pages": len(pages),
            "status_200": status_200,
            "status_404": status_404,
            "status_5xx": status_5xx,
            "errors": finding_summary["errors"],
            "warnings": finding_summary["warnings"],
            "info": finding_summary["info"],
            "elapsed_seconds": round(time.time() - self.start_time, 2)
        }


# バックグラウンドタスク用ラッパー
def run_crawler_task(job_id: str, db_session_factory):
    """
    サブプロセスでクローラーを実行
    FastAPIのイベントループと完全に分離
    """
    import subprocess
    import sys
    import os
    
    # 作業ディレクトリを app の親ディレクトリ（sitemap_app）に設定
    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print(f"[CrawlerTask] Launching subprocess for job: {job_id}", flush=True)
    print(f"[CrawlerTask] Working directory: {app_dir}", flush=True)
    
    # 別プロセスでクローラー実行
    result = subprocess.run(
        [sys.executable, "-m", "app.crawler_runner", job_id],
        cwd=app_dir,
        capture_output=True,
        text=True
    )
    
    print(f"[CrawlerTask] Subprocess stdout: {result.stdout}", flush=True)
    if result.stderr:
        print(f"[CrawlerTask] Subprocess stderr: {result.stderr}", flush=True)
    
    if result.returncode != 0:
        print(f"[CrawlerTask] Subprocess failed with code: {result.returncode}", flush=True)




