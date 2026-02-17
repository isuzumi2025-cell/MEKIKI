"""Non-interactive test crawl with Basic Auth"""
import asyncio

async def run_auth_crawl():
    from app.db.database import SessionLocal
    from app.db import models
    from app.core.crawler import Crawler
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Basic認証付きプロファイルを作成
        profile = models.Profile(
            name="PortCafe Auth Test",
            target_url="https://www.portcafe.net/demo/jrkyushu/jisha-meguri/",
            mode="render",
            max_pages=10,
            max_depth=2,
            max_time_seconds=120,
            respect_robots=False,
            auth_config={
                "mode": "basic",
                "user": "jrq",
                "pass": "testga"
            }
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        print(f"Created profile: {profile.id}")
        
        # ジョブ作成
        job = models.Job(
            profile_id=profile.id,
            start_url="https://www.portcafe.net/demo/jrkyushu/jisha-meguri/",
            status="pending",
            started_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        print(f"Created job: {job.id}")
        
        # フェッチテスト
        print("Testing fetch with auth...")
        crawler = Crawler(job.id, db)
        
        data = await crawler.engine.fetch(
            "https://www.portcafe.net/demo/jrkyushu/jisha-meguri/",
            auth_config=profile.auth_config
        )
        
        print(f"Status: {data.get('status')}")
        print(f"Title: {data.get('title', '')[:80] if data.get('title') else 'None'}")
        print(f"Error: {data.get('error')}")
        print(f"Links found: {len(data.get('links', []))}")
        print(f"Has screenshot: {bool(data.get('screenshot'))}")
        
        if data.get('links'):
            print("First 5 links:")
            for link in data.get('links', [])[:5]:
                print(f"  - {link}")
        
        # フルクロール実行
        print("\nRunning full crawl...")
        await crawler.run()
        
        db.refresh(job)
        print(f"\n=== Results ===")
        print(f"Job status: {job.status}")
        print(f"pages_crawled: {job.pages_crawled}")
        
        pages = db.query(models.Page).filter(models.Page.job_id == job.id).all()
        print(f"Pages in DB: {len(pages)}")
        for p in pages[:10]:
            print(f"  - {p.url[:60]}... (status: {p.status_code})")
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_auth_crawl())
