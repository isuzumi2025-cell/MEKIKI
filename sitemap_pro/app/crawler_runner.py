"""
クローラー実行スクリプト
サブプロセスから呼び出される
"""
import sys
import asyncio

def main(job_id: str):
    from app.db.database import SessionLocal
    from app.core.crawler import Crawler
    
    db = SessionLocal()
    try:
        print(f"[CrawlerRunner] Starting job: {job_id}", flush=True)
        crawler = Crawler(job_id, db)
        asyncio.run(crawler.run())
        print(f"[CrawlerRunner] Completed job: {job_id}", flush=True)
    except Exception as e:
        import traceback
        print(f"[CrawlerRunner] Error: {e}", flush=True)
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.crawler_runner <job_id>")
        sys.exit(1)
    
    job_id = sys.argv[1]
    main(job_id)
