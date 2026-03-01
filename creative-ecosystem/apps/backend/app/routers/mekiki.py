"""
MEKIKI API Router — /api/v1/mekiki

Bridges the ICC gateway to the MEKIKI OCR proofing engine located at
../../../../OCR relative to the backend root.

Endpoints
---------
POST /ocr            — queue a web+PDF OCR job
GET  /jobs/{job_id}  — poll job status and results
GET  /sync-pairs     — list SyncPair objects from the latest completed job
POST /storyboard     — generate a storyboard plan via MEKIKI StoryboardPlanner
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# MEKIKI StoryboardPlanner — runtime import via sys.path
# ---------------------------------------------------------------------------
_OCR_ROOT = Path(__file__).parents[5] / "OCR"

def _import_storyboard_planner():
    """Import StoryboardPlanner lazily via importlib to avoid app/ name collision."""
    import importlib.util
    cache_key = "_mekiki_storyboard_planner"
    if cache_key in sys.modules:
        return sys.modules[cache_key].StoryboardPlanner
    planner_path = (_OCR_ROOT / "app/pipeline/storyboard/storyboard_planner.py").resolve()
    if not planner_path.exists():
        raise RuntimeError(f"StoryboardPlanner not found at {planner_path}")
    spec = importlib.util.spec_from_file_location(cache_key, planner_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[cache_key] = mod  # register before exec so @dataclass can resolve __module__
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.StoryboardPlanner


router = APIRouter(prefix="/mekiki", tags=["mekiki"])

# ---------------------------------------------------------------------------
# In-memory job store (replace with DB in production)
# ---------------------------------------------------------------------------
_JOBS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class OcrJobResponse(BaseModel):
    job_id: str
    status: str  # queued | running | completed | failed


class SyncPair(BaseModel):
    web_id: str
    pdf_id: str
    similarity: float
    web_text: str = ""
    pdf_text: str = ""


class JobResult(BaseModel):
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    sync_pairs: List[SyncPair] = []
    error: Optional[str] = None


class StoryboardRequest(BaseModel):
    brief: str
    duration_sec: int = 30


class StoryboardShotResponse(BaseModel):
    shot_no: int
    phase: str
    start_sec: float
    end_sec: float
    duration_sec: float
    copy_text: str
    narration_text: str
    narration_chars: int
    narration_words: int
    visual_hint: str
    source_excerpt: str


class StoryboardResponse(BaseModel):
    plan_id: str
    shots: List[StoryboardShotResponse]
    total_duration_sec: int
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/ocr",
    response_model=OcrJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an OCR comparison job",
)
async def start_ocr_job(
    web_url: str = Form(..., description="Web page URL to capture and OCR"),
    pdf_file: Optional[UploadFile] = File(None, description="PDF file to compare against"),
) -> OcrJobResponse:
    """Accept a web URL and optional PDF upload, queue an OCR job, and
    return a job_id that can be polled via GET /jobs/{job_id}.

    The actual OCR execution is handled by the MEKIKI engine (OCR/app/).
    This endpoint queues the request and returns immediately.
    """
    job_id = str(uuid.uuid4())
    pdf_bytes: Optional[bytes] = None
    pdf_filename: Optional[str] = None

    if pdf_file is not None:
        pdf_bytes = await pdf_file.read()
        pdf_filename = pdf_file.filename

    _JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "web_url": web_url,
        "pdf_filename": pdf_filename,
        "pdf_size": len(pdf_bytes) if pdf_bytes else 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "sync_pairs": [],
        "error": None,
    }

    # TODO: dispatch to background worker / MEKIKI engine
    return OcrJobResponse(job_id=job_id, status="queued")


@router.get(
    "/jobs/{job_id}",
    response_model=JobResult,
    summary="Poll job status and results",
)
def get_job(job_id: str) -> JobResult:
    """Return the current status of an OCR job and, if completed,
    the list of SyncPair objects produced by the MEKIKI engine.
    """
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return JobResult(
        job_id=job["job_id"],
        status=job["status"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        sync_pairs=[SyncPair(**sp) for sp in job.get("sync_pairs", [])],
        error=job.get("error"),
    )


@router.get(
    "/sync-pairs",
    response_model=List[SyncPair],
    summary="List SyncPair objects from the latest completed job",
)
def list_sync_pairs() -> List[SyncPair]:
    """Return all SyncPair objects from the most recently completed OCR job.

    SyncPair links a Web paragraph region (W-001) with a PDF paragraph
    region (P-001) and their similarity score.
    """
    completed = [
        j for j in _JOBS.values() if j.get("status") == "completed"
    ]
    if not completed:
        return []

    latest = sorted(completed, key=lambda j: j["created_at"], reverse=True)[0]
    return [SyncPair(**sp) for sp in latest.get("sync_pairs", [])]


@router.post(
    "/storyboard",
    response_model=StoryboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate storyboard plan via MEKIKI StoryboardPlanner",
)
def generate_storyboard(body: StoryboardRequest) -> StoryboardResponse:
    """Generate a multi-shot storyboard plan from a text brief using the
    MEKIKI StoryboardPlanner.

    The planner divides the requested duration into phases (Hook / Problem /
    Insight / Solution / Proof / CTA) and produces copy + narration text for
    each shot.
    """
    try:
        StoryboardPlanner = _import_storyboard_planner()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    planner = StoryboardPlanner()
    raw_shots = planner.generate(
        duration_sec=body.duration_sec,
        text_candidates=[body.brief],
        image_candidates=[],
    )

    shots = [
        StoryboardShotResponse(
            shot_no=s["shot_no"],
            phase=s["phase"],
            start_sec=s["start_sec"],
            end_sec=s["end_sec"],
            duration_sec=s["duration_sec"],
            copy_text=s["copy_text"],
            narration_text=s["narration_text"],
            narration_chars=s["narration_chars"],
            narration_words=s["narration_words"],
            visual_hint=s["visual_hint"],
            source_excerpt=s["source_excerpt"],
        )
        for s in raw_shots
    ]

    plan_id = str(uuid.uuid4())
    return StoryboardResponse(
        plan_id=plan_id,
        shots=shots,
        total_duration_sec=body.duration_sec,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
