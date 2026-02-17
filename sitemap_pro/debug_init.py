"""Debug crawler initialization"""
import asyncio

async def debug_crawler():
    from app.db.database import SessionLocal
    from app.db import models
    from app.core.parser import URLParser
    from app.core.robots import robots_checker
    
    db = SessionLocal()
    
    # Get latest job
    job = db.query(models.Job).order_by(models.Job.started_at.desc()).first()
    profile = job.profile
    
    print(f"=== Job Debug ===")
    print(f"Job ID: {job.id}")
    print(f"Start URL: {job.start_url}")
    print(f"Profile: {profile.name}")
    print(f"Auth config: {profile.auth_config}")
    print(f"Respect robots: {profile.respect_robots}")
    
    # Test URL normalization
    base_url = URLParser.normalize_url(
        job.start_url or profile.target_url,
        keep_params=profile.keep_params or []
    )
    print(f"\nNormalized base URL: {base_url}")
    
    from urllib.parse import urlparse
    base_domain = urlparse(base_url).netloc
    print(f"Base domain: {base_domain}")
    
    # Test robots.txt
    if profile.respect_robots:
        print(f"\nTesting robots.txt for: {base_url}")
        can_fetch = await robots_checker.can_fetch(base_url, respect_robots=True)
        print(f"Can fetch: {can_fetch}")
    else:
        print("\nRobots.txt check disabled")
    
    # Test actual engine fetch
    print("\n=== Engine Fetch Test ===")
    from app.core.engine import PlaywrightEngine
    engine = PlaywrightEngine(headless=True)
    
    result = await engine.fetch(
        base_url,
        auth_config=profile.auth_config
    )
    
    print(f"Status: {result.get('status')}")
    print(f"Title: {result.get('title')}")
    print(f"Error: {result.get('error')}")
    print(f"Links found: {len(result.get('links', []))}")
    print(f"Screenshot size: {len(result.get('screenshot') or b'')} bytes")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(debug_crawler())
