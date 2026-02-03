"""Debug script to run a complete crawl with verbose logging"""
import asyncio

async def run_test_crawl():
    from app.db.database import SessionLocal
    from app.db import models
    from app.core.crawler import Crawler
    
    db = SessionLocal()
    try:
        # Create a test profile
        profile = models.Profile(
            name="Debug Test Profile",
            target_url="https://example.com",
            mode="render",
            max_pages=5,
            max_depth=2,
            max_time_seconds=60,
            respect_robots=False
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        print(f"Created profile: {profile.id}")
        
        # Create a test job
        from datetime import datetime
        job = models.Job(
            profile_id=profile.id,
            start_url="https://example.com",
            status="pending",
            started_at=datetime.utcnow()
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        print(f"Created job: {job.id}")
        
        # Run crawler
        print("Starting crawler...")
        crawler = Crawler(job.id, db)
        
        print(f"Queue initialized. Base URL: {crawler.base_url}")
        print(f"Max pages: {crawler.max_pages}")
        
        await crawler.run()
        
        # Check results
        db.refresh(job)
        print(f"\n=== Results ===")
        print(f"Job status: {job.status}")
        print(f"pages_crawled: {job.pages_crawled}")
        print(f"Result summary: {job.result_summary}")
        
        # Check pages table
        pages = db.query(models.Page).filter(models.Page.job_id == job.id).all()
        print(f"Pages in DB: {len(pages)}")
        for p in pages:
            print(f"  - {p.url} (status: {p.status_code})")
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test_crawl())
