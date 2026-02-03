"""
API Endpoints
プロファイル管理、ジョブ管理、エクスポート機能を提供
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import HTMLResponse, FileResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import json

from app.db import models, database
from app.schemas import schemas
from app.core.crawler import run_crawler_task
from app.core.exporter import Exporter
from app.core.config import settings

router = APIRouter()


# ==============================================================================
# Profiles
# ==============================================================================

@router.post("/profiles", response_model=schemas.Profile)
def create_profile(profile: schemas.ProfileCreate, db: Session = Depends(database.get_db)):
    """プロファイル作成"""
    db_profile = models.Profile(**profile.model_dump())
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


@router.get("/profiles", response_model=List[schemas.Profile])
def list_profiles(db: Session = Depends(database.get_db)):
    """プロファイル一覧"""
    return db.query(models.Profile).order_by(models.Profile.created_at.desc()).all()


@router.get("/profiles/{profile_id}", response_model=schemas.Profile)
def get_profile(profile_id: int, db: Session = Depends(database.get_db)):
    """プロファイル詳細"""
    profile = db.query(models.Profile).filter(models.Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profiles/{profile_id}", response_model=schemas.Profile)
def update_profile(
    profile_id: int, 
    profile_update: schemas.ProfileUpdate, 
    db: Session = Depends(database.get_db)
):
    """プロファイル更新"""
    profile = db.query(models.Profile).filter(models.Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    update_data = profile_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(database.get_db)):
    """プロファイル削除"""
    profile = db.query(models.Profile).filter(models.Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db.delete(profile)
    db.commit()
    return {"status": "deleted", "id": profile_id}


# ==============================================================================
# Jobs
# ==============================================================================

@router.get("/jobs", response_model=List[schemas.Job])
def list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """ジョブ一覧（新しい順）"""
    return db.query(models.Job).order_by(models.Job.started_at.desc()).offset(skip).limit(limit).all()


@router.post("/jobs", response_model=schemas.Job)
async def create_job(
    job_in: schemas.JobCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(database.get_db)
):
    """ジョブ作成・開始"""
    profile = db.query(models.Profile).filter(models.Profile.id == job_in.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Start URL: Job Override > Profile Target
    start_url = job_in.start_url or profile.target_url
    if not start_url:
        raise HTTPException(status_code=400, detail="Start URL is required (in profile or job)")
    
    db_job = models.Job(
        profile_id=job_in.profile_id,
        start_url=start_url,
        status="pending"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # バックグラウンドでクローラー起動
    background_tasks.add_task(run_crawler_task, db_job.id, database.SessionLocal)
    
    return db_job


@router.get("/jobs/{job_id}", response_model=schemas.Job)
def get_job(job_id: str, db: Session = Depends(database.get_db)):
    """ジョブステータス取得"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(database.get_db)):
    """ジョブ削除（関連データも含む）"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 関連データを削除（カスケード）
    db.query(models.ExcludedLink).filter(models.ExcludedLink.job_id == job_id).delete()
    db.query(models.Finding).filter(models.Finding.job_id == job_id).delete()
    db.query(models.Link).filter(models.Link.job_id == job_id).delete()
    db.query(models.Page).filter(models.Page.job_id == job_id).delete()
    
    # ジョブ本体を削除
    db.delete(job)
    db.commit()
    
    return {"status": "deleted", "job_id": job_id}


@router.post("/jobs/{job_id}/stop")
def stop_job(job_id: str, db: Session = Depends(database.get_db)):
    """ジョブ停止"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in ["running", "pending"]:
        raise HTTPException(status_code=400, detail=f"Cannot stop job with status: {job.status}")
    
    job.status = "stopped"
    db.commit()
    return {"status": "stopped", "job_id": job_id}


@router.post("/jobs/{job_id}/resume")
def resume_job(job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    """ジョブ再開（手動介入後）"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume job with status: {job.status}")
    
    job.status = "running"
    db.commit()
    
    # 注: 実際の再開ロジックはクローラー側で実装が必要
    # MVPでは状態変更のみ
    
    return {"status": "resumed", "job_id": job_id}


@router.get("/jobs/{job_id}/results", response_model=schemas.JobDetail)
def get_job_results(job_id: str, db: Session = Depends(database.get_db)):
    """ジョブ結果詳細（Pages/Links/Findings含む）"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ==============================================================================
# Exports
# ==============================================================================

@router.get("/jobs/{job_id}/export/html", response_class=HTMLResponse)
def export_html(job_id: str, db: Session = Depends(database.get_db)):
    """HTMLサイトマップエクスポート"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    
    exporter = Exporter(db, job_id)
    html_content = exporter.export_html()
    return HTMLResponse(content=html_content)


@router.get("/jobs/{job_id}/export/csv")
def export_csv(job_id: str, db: Session = Depends(database.get_db)):
    """CSVエクスポート"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    exporter = Exporter(db, job_id)
    csv_content = exporter.export_csv()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sitemap_{job_id}.csv"}
    )


@router.get("/jobs/{job_id}/export/json")
def export_json(job_id: str, db: Session = Depends(database.get_db)):
    """JSONエクスポート（ノード＆エッジ）"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    exporter = Exporter(db, job_id)
    json_data = exporter.export_json()
    
    return Response(
        content=json.dumps(json_data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=sitemap_{job_id}.json"}
    )


@router.get("/jobs/{job_id}/audit")
def get_audit_report(job_id: str, format: str = "json", db: Session = Depends(database.get_db)):
    """
    監査レポート取得
    format: json または html
    """
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    exporter = Exporter(db, job_id)
    
    if format == "html":
        html_content = exporter.export_audit_html()
        return HTMLResponse(content=html_content)
    else:
        return exporter.export_audit_report()


# ==============================================================================
# Screenshots
# ==============================================================================

@router.get("/jobs/{job_id}/screenshots/{filename}")
def get_screenshot(job_id: str, filename: str):
    """スクリーンショット取得"""
    file_path = os.path.join(settings.OUTPUT_DIR, job_id, "screenshots", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return HTMLResponse("Not found", status_code=404)


# ==============================================================================
# Excluded Links
# ==============================================================================

@router.get("/jobs/{job_id}/excluded-links")
def get_excluded_links(job_id: str, db: Session = Depends(database.get_db)):
    """除外されたリンク一覧を取得（PDF、画像等）"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    excluded_links = db.query(models.ExcludedLink).filter(
        models.ExcludedLink.job_id == job_id
    ).all()
    
    # 拡張子別にグループ化
    by_extension = {}
    for link in excluded_links:
        ext = link.extension
        if ext not in by_extension:
            by_extension[ext] = []
        by_extension[ext].append({
            "url": link.url,
            "source_url": link.source_url,
            "excluded_at": link.excluded_at.isoformat() if link.excluded_at else None
        })
    
    return {
        "job_id": job_id,
        "total_excluded": len(excluded_links),
        "by_extension": by_extension
    }


# ==============================================================================
# Text Extraction & Comparison
# ==============================================================================

from pydantic import BaseModel
from typing import List as ListType

class WebExtractRequest(BaseModel):
    url: str
    mode: str = "text"  # text, html, structure
    xpath: str = None
    wait_time: int = 2000

class RegionExtractRequest(BaseModel):
    image_path: str
    bbox: ListType[int]  # [x0, y0, x1, y1]

class CompareRequest(BaseModel):
    text_a: str
    text_b: str
    label_a: str = "Source A"
    label_b: str = "Source B"
    normalize: bool = True

class BlockCompareRequest(BaseModel):
    blocks_a: ListType[dict]
    blocks_b: ListType[dict]


@router.post("/extract/web")
async def extract_from_web(request: WebExtractRequest):
    """
    Web URLからテキストを抽出
    
    - mode: text (プレーンテキスト), html (HTML), structure (DOM構造)
    - xpath: 特定要素を抽出する場合のXPath式
    """
    try:
        from app.core.text_extractor import TextExtractor
        extractor = TextExtractor()
        result = extractor.extract_from_web(
            url=request.url,
            mode=request.mode,
            xpath=request.xpath,
            wait_time=request.wait_time
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/pdf")
async def extract_from_pdf(pdf_path: str, pages: str = None, use_ocr: bool = True):
    """
    PDFからテキストを抽出（OCRフォールバック付き）
    
    - pages: カンマ区切りのページ番号 (例: "1,2,3")
    - use_ocr: テキストが少ない場合にOCRを使用
    """
    try:
        from app.core.text_extractor import TextExtractor
        extractor = TextExtractor()
        
        page_list = None
        if pages:
            page_list = [int(p.strip()) - 1 for p in pages.split(",")]
        
        result = extractor.extract_from_pdf(
            pdf_path=pdf_path,
            pages=page_list,
            use_ocr=use_ocr
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/image")
async def extract_from_image(image_path: str, granularity: str = "paragraph"):
    """
    画像からOCRでテキストを抽出
    
    - granularity: block (大きな塊), paragraph (段落), word (単語)
    """
    try:
        from app.core.text_extractor import TextExtractor
        extractor = TextExtractor()
        result = extractor.extract_from_image(
            image_path=image_path,
            granularity=granularity
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/region")
async def extract_from_region(request: RegionExtractRequest):
    """
    画像の指定領域からテキストを抽出
    
    - bbox: [x0, y0, x1, y1] 抽出領域
    """
    try:
        from app.core.text_extractor import TextExtractor
        extractor = TextExtractor()
        result = extractor.extract_from_region(
            image_path=request.image_path,
            bbox=request.bbox
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_texts(request: CompareRequest):
    """
    2つのテキストを比較
    
    Returns:
    - sync_rate: 一致率 (0-100%)
    - diff_count: 差異箇所数
    - diffs: 差分リスト
    - diff_html: 差分ハイライトHTML
    - summary: 比較サマリー
    """
    try:
        from app.core.text_comparator import TextComparator
        comparator = TextComparator()
        result = comparator.compare(
            text_a=request.text_a,
            text_b=request.text_b,
            label_a=request.label_a,
            label_b=request.label_b,
            normalize=request.normalize
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare/blocks")
async def compare_blocks(request: BlockCompareRequest):
    """
    ブロック単位で比較（領域親和性マッピング）
    
    各ブロックは {"text": str, "bbox": [x0,y0,x1,y1], "area_id": int} 形式
    """
    try:
        from app.core.text_comparator import TextComparator
        comparator = TextComparator()
        result = comparator.compare_blocks(
            blocks_a=request.blocks_a,
            blocks_b=request.blocks_b
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare/suggestions")
async def generate_suggestions(comparison_result: dict, mode: str = "proofread"):
    """
    差分に基づくサジェストを生成
    
    - mode: proofread (校正), creative (クリエイティブ評価)
    """
    try:
        from app.core.text_comparator import TextComparator
        comparator = TextComparator()
        suggestions = comparator.generate_suggestions(
            comparison_result=comparison_result,
            mode=mode
        )
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ViewerRequest(BaseModel):
    web_url: str = None
    pdf_path: str = None
    web_text: str = ""
    pdf_text: str = ""
    title: str = "テキスト比較"


@router.post("/compare/viewer", response_class=HTMLResponse)
async def generate_comparison_viewer(request: ViewerRequest):
    """
    テキスト比較ビューワーHTMLを生成
    
    Web URLとPDFパスを指定すると、テキスト抽出→比較→HTML生成を自動で行う
    """
    try:
        from app.core.text_extractor import TextExtractor
        from app.core.text_comparator import TextComparator
        from app.core.comparison_viewer import ComparisonViewer
        
        extractor = TextExtractor()
        comparator = TextComparator()
        viewer = ComparisonViewer()
        
        web_text = request.web_text
        pdf_text = request.pdf_text
        web_capture = None
        pdf_preview = None
        
        # Web テキスト抽出
        if request.web_url and not web_text:
            result = extractor.extract_from_web(request.web_url)
            web_text = result.get("full_text", "")
            
            # スクリーンショット撮影
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                web_capture = extractor.capture_screenshot(request.web_url, tmp.name)
        
        # PDF テキスト抽出
        if request.pdf_path and not pdf_text:
            result = extractor.extract_from_pdf(request.pdf_path)
            pdf_text = result.get("full_text", "")
        
        # 比較
        comparison_result = None
        suggestions = []
        if web_text and pdf_text:
            comparison_result = comparator.compare(
                web_text, pdf_text, 
                label_a="Web", label_b="PDF"
            )
            suggestions = comparator.generate_suggestions(comparison_result)
        
        # HTML生成
        html = viewer.generate_comparison_html(
            web_capture=web_capture,
            pdf_preview=pdf_preview,
            web_text=web_text,
            pdf_text=pdf_text,
            comparison_result=comparison_result,
            suggestions=suggestions,
            title=request.title
        )
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
