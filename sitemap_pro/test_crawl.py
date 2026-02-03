import sys
sys.path.insert(0, '.')
import traceback
import logging
import time

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log', encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from app.db.database import SessionLocal
from app.db import models
import uuid
import asyncio

def main():
    db = SessionLocal()
    profile = db.query(models.Profile).first()
    job = models.Job(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        start_url='https://example.com',
        status='pending'
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    logger.info(f'Created job: {job_id}')

    # 直接asyncio.run()で実行
    from app.core.crawler import Crawler
    
    async def run_crawl():
        db2 = SessionLocal()
        try:
            crawler = Crawler(job_id, db2)
            logger.info('Starting crawler')
            await crawler.run()
            logger.info('Crawler complete')
        except Exception as e:
            logger.error(f'Error: {e}', exc_info=True)
        finally:
            db2.close()
    
    asyncio.run(run_crawl())

    db3 = SessionLocal()
    j = db3.query(models.Job).filter(models.Job.id == job_id).first()
    logger.info(f'Status: {j.status}')
    logger.info(f'Pages: {j.pages_crawled}')
    logger.info(f'Summary: {j.result_summary}')
    db3.close()

if __name__ == '__main__':
    main()
