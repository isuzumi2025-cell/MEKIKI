"""
Sitemap Router — /api/v1/sitemap

Thin adapter / proxy layer over the existing sitemap_pro FastAPI application.
Rather than duplicating SQLAlchemy models, this router re-uses the sitemap_pro
database session and model layer via a sys.path insertion.

Endpoints
---------
POST /jobs           — start a new crawl job
GET  /jobs           — list all crawl jobs (newest first)
GET  /jobs/{job_id}  — poll a specific job's status and result
GET  /profiles       — list crawl profiles
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# sitemap_pro runtime import
# ---------------------------------------------------------------------------
_SITEMAP_PRO_ROOT = Path(__file__).parent / "../../../../sitemap_pro"


def _sitemap_sys_path() -> str:
    resolved = str(_SITEMAP_PRO_ROOT.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    return resolved


def _try_import_sitemap_db():
    """Attempt to import sitemap_pro database session and models.

    Returns (SessionLocal, models) or (None, None) if unavailable.
    """
    try:
        _sitemap_sys_path()
        from app.db.database import SessionLocal  # noqa: PLC0415
        from app.db import models  # noqa: PLC0415
        return SessionLocal, models
    except Exception:  # pragma: no cover
        return None, None


router = APIRouter(prefix="/sitemap", tags=["sitemap"])

# ---------------------------------------------------------------------------
# Pydantic schemas (mirror sitemap_pro schemas for ICC API surface)
# ---------------------------------------------------------------------------

class CrawlJobCreate(BaseModel):
    profile_id: Optional[int] = None
    start_url: str
    max_pages: int = 100


class CrawlJobResponse(BaseModel):
    job_id: str
    profile_id: Optional[int] = None
    start_url: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    pages_crawled: int = 0
    error: Optional[str] = None


class CrawlProfile(BaseModel):
    id: int
    name: str
    start_url: str
    max_pages: int
    created_at: str


# ---------------------------------------------------------------------------
# In-memory fallback store (used when sitemap_pro DB is unavailable)
# ---------------------------------------------------------------------------
_FALLBACK_JOBS: Dict[str, Dict[str, Any]] = {}


def _db_available() -> bool:
    SessionLocal, _ = _try_import_sitemap_db()
    return SessionLocal is not None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/jobs",
    response_model=CrawlJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new sitemap crawl job",
)
async def create_job(
    body: CrawlJobCreate,
    background_tasks: BackgroundTasks,
) -> CrawlJobResponse:
    """Queue a sitemap crawl job.

    If the sitemap_pro database is reachable, the job is delegated to the
    sitemap_pro crawler (run_crawler_task).  Otherwise the job is queued in
    an in-memory fallback store and returns 'queued'.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    SessionLocal, models = _try_import_sitemap_db()

    if SessionLocal is not None and models is not None:
        # Delegate to sitemap_pro engine
        try:
            from app.core.crawler import run_crawler_task  # noqa: PLC0415
            from app.schemas import schemas  # noqa: PLC0415

            db = SessionLocal()
            try:
                job_in = schemas.JobCreate(
                    profile_id=body.profile_id,
                    start_url=body.start_url,
                    max_pages=body.max_pages,
                )
                db_job = models.Job(
                    id=job_id,
                    profile_id=body.profile_id,
                    start_url=body.start_url,
                    max_pages=body.max_pages,
                    status="queued",
                    started_at=datetime.now(timezone.utc),
                )
                db.add(db_job)
                db.commit()
                db.refresh(db_job)
                background_tasks.add_task(run_crawler_task, job_id, body.start_url, body.max_pages)
                return CrawlJobResponse(
                    job_id=str(db_job.id),
                    profile_id=db_job.profile_id,
                    start_url=body.start_url,
                    status="queued",
                    started_at=now,
                )
            finally:
                db.close()
        except Exception as exc:  # pragma: no cover
            # Fall through to in-memory store on any sitemap_pro error
            pass

    # Fallback: in-memory
    _FALLBACK_JOBS[job_id] = {
        "job_id": job_id,
        "profile_id": body.profile_id,
        "start_url": body.start_url,
        "status": "queued",
        "started_at": now,
        "completed_at": None,
        "pages_crawled": 0,
        "error": None,
    }
    return CrawlJobResponse(
        job_id=job_id,
        profile_id=body.profile_id,
        start_url=body.start_url,
        status="queued",
        started_at=now,
    )


@router.get(
    "/jobs",
    response_model=List[CrawlJobResponse],
    summary="List all crawl jobs, newest first",
)
def list_jobs() -> List[CrawlJobResponse]:
    """Return all crawl jobs ordered by start time descending.

    Reads from sitemap_pro SQLite database when available; falls back to the
    in-memory store otherwise.
    """
    SessionLocal, models = _try_import_sitemap_db()

    if SessionLocal is not None and models is not None:
        db = SessionLocal()
        try:
            rows = (
                db.query(models.Job)
                .order_by(models.Job.started_at.desc())
                .limit(200)
                .all()
            )
            return [
                CrawlJobResponse(
                    job_id=str(r.id),
                    profile_id=getattr(r, "profile_id", None),
                    start_url=getattr(r, "start_url", ""),
                    status=r.status,
                    started_at=r.started_at.isoformat() if r.started_at else "",
                    completed_at=(
                        r.completed_at.isoformat() if getattr(r, "completed_at", None) else None
                    ),
                    pages_crawled=getattr(r, "pages_crawled", 0) or 0,
                    error=getattr(r, "error", None),
                )
                for r in rows
            ]
        finally:
            db.close()

    # Fallback
    jobs = sorted(_FALLBACK_JOBS.values(), key=lambda j: j["started_at"], reverse=True)
    return [CrawlJobResponse(**j) for j in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=CrawlJobResponse,
    summary="Get status and result of a specific crawl job",
)
def get_job(job_id: str) -> CrawlJobResponse:
    """Return the current status of a crawl job identified by job_id."""
    SessionLocal, models = _try_import_sitemap_db()

    if SessionLocal is not None and models is not None:
        db = SessionLocal()
        try:
            row = db.query(models.Job).filter(models.Job.id == job_id).first()
            if row:
                return CrawlJobResponse(
                    job_id=str(row.id),
                    profile_id=getattr(row, "profile_id", None),
                    start_url=getattr(row, "start_url", ""),
                    status=row.status,
                    started_at=row.started_at.isoformat() if row.started_at else "",
                    completed_at=(
                        row.completed_at.isoformat()
                        if getattr(row, "completed_at", None)
                        else None
                    ),
                    pages_crawled=getattr(row, "pages_crawled", 0) or 0,
                    error=getattr(row, "error", None),
                )
        finally:
            db.close()

    job = _FALLBACK_JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return CrawlJobResponse(**job)


@router.get(
    "/profiles",
    response_model=List[CrawlProfile],
    summary="List available crawl profiles",
)
def list_profiles() -> List[CrawlProfile]:
    """Return all configured crawl profiles from the sitemap_pro database."""
    SessionLocal, models = _try_import_sitemap_db()

    if SessionLocal is not None and models is not None:
        db = SessionLocal()
        try:
            rows = (
                db.query(models.Profile)
                .order_by(models.Profile.created_at.desc())
                .all()
            )
            return [
                CrawlProfile(
                    id=r.id,
                    name=r.name,
                    start_url=r.start_url,
                    max_pages=getattr(r, "max_pages", 100),
                    created_at=r.created_at.isoformat() if r.created_at else "",
                )
                for r in rows
            ]
        finally:
            db.close()

    # No sitemap_pro DB — return empty list
    return []
