"""
Storyboard Bridge Router — /api/v1/storyboard

Provides the ICC storyboard planning, segmentation, and export pipeline.
Bridges the MEKIKI StoryboardPlanner (Python) with the FlowForge rendering
server (Node/TypeScript).

Endpoints
---------
POST /plan           — create storyboard plan (calls MEKIKI StoryboardPlanner)
POST /segment        — analyse URL / PDF layers (stub, returns empty segments)
POST /generate       — proxy to FlowForge render server
GET  /shots          — retrieve stored shots for a plan
GET  /export/{id}    — export plan as JSON or XLSX via MEKIKI StoryboardExporter
"""
from __future__ import annotations

import io
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import settings

# ---------------------------------------------------------------------------
# MEKIKI runtime imports
# ---------------------------------------------------------------------------
_OCR_ROOT = Path(__file__).parents[5] / "OCR"


def _import_storyboard_planner():
    """Lazily import StoryboardPlanner from the MEKIKI OCR subtree via importlib."""
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


def _import_storyboard_exporter():
    """Lazily import StoryboardExporter from the MEKIKI OCR subtree via importlib."""
    import importlib.util
    cache_key = "_mekiki_storyboard_exporter"
    if cache_key in sys.modules:
        return sys.modules[cache_key].StoryboardExporter
    exporter_path = (_OCR_ROOT / "app/pipeline/storyboard/storyboard_exporter.py").resolve()
    if not exporter_path.exists():
        raise RuntimeError(f"StoryboardExporter not found at {exporter_path}")
    spec = importlib.util.spec_from_file_location(cache_key, exporter_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[cache_key] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.StoryboardExporter


router = APIRouter(prefix="/storyboard", tags=["storyboard"])

# ---------------------------------------------------------------------------
# In-memory plan store (keyed by plan_id → list[dict])
# ---------------------------------------------------------------------------
_PLANS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StoryboardPlanRequest(BaseModel):
    brief: str
    duration_sec: int = 30  # 15 | 30 | 60
    style: str = "realistic"
    source_url: Optional[str] = None


class ShotProposal(BaseModel):
    shot_no: int
    phase: str  # Hook / Problem / Insight / Solution / Proof / CTA
    start_sec: float
    end_sec: float
    duration_sec: float
    copy_text: str
    narration_text: str
    visual_hint: str
    source_excerpt: str
    # TBEX extended fields
    scene_description: Optional[str] = None
    telop: Optional[str] = None
    audio: Optional[str] = None


class PatternShotData(BaseModel):
    time: str
    phase: str
    scene_description: str
    telop: str
    audio: str


class PatternPreset(BaseModel):
    id: str
    label: str
    duration: str           # '15s' | '30s' | '60s'
    duration_sec: int
    description: str
    shots: List[PatternShotData]


class FromPatternRequest(BaseModel):
    pattern_id: str
    brief: str = ""


class StoryboardPlanResponse(BaseModel):
    plan_id: str
    shots: List[ShotProposal]
    total_duration_sec: int
    created_at: str


class SegmentRequest(BaseModel):
    url: Optional[str] = None
    pdf_path: Optional[str] = None


class SegmentResult(BaseModel):
    segments: List[Dict[str, Any]] = []
    page_count: int = 0
    source: str = ""


class GenerateRequest(BaseModel):
    plan_id: str


class FlowStoryboardData(BaseModel):
    """TypeScript FlowForge format."""

    title: str
    globalStyle: Optional[str] = None
    shots: List[Dict[str, Any]]  # shot_no, phase, copy, narration, visual_hint, start_sec, end_sec


# ---------------------------------------------------------------------------
# TBEX Pattern presets (seed data from real TBEX storyboard CSVs)
# ---------------------------------------------------------------------------

_TBEX_PATTERNS: List[PatternPreset] = [
    PatternPreset(
        id="p1_sns_15s",
        label="パターン1: SNS 15秒",
        duration="15s",
        duration_sec=15,
        description="SNS向け短尺。インパクトのあるキャッチから素早くデモ→判定→オファーに誘導。",
        shots=[
            PatternShotData(
                time="0-5", phase="キャッチ",
                scene_description="画面いっぱいに「録るだけ！簡単本格診断」の文字。背景で作業員がスマホをかざす。インパクトのあるタイポグラフィ。",
                telop="録るだけ！\n簡単本格診断アプリ",
                audio="[SE] 「バン！」（インパクト音）",
            ),
            PatternShotData(
                time="5-9", phase="デモ",
                scene_description="アプリ画面がスピーディーに動く。録音→波形→OK判定。手軽さをスピード感で表現。早回しのデモ映像。",
                telop="東芝の技術が\nスマホに入った！",
                audio="[SE] ギュイーン（加速音）",
            ),
            PatternShotData(
                time="9-12", phase="判定",
                scene_description="大きな「OK（正常）」マーク、または「Caution（注意）」マーク。スタンプアニメーション。",
                telop="結果が、\nすぐ分かる！",
                audio="[SE] ピンポン！（正解音）/ ブッブー（警告音）",
            ),
            PatternShotData(
                time="12-15", phase="オファー",
                scene_description="「今だけ無料」の赤帯とダウンロードボタン。「iOS版 公開中」のバッジ。クリックを促す広告エンド。",
                telop="今だけ無料！\nダウンロードはこちら",
                audio="[SE] チャリーン（成功音）",
            ),
        ],
    ),
    PatternPreset(
        id="p2_feature_15s",
        label="パターン2: 機能特化 15秒",
        duration="15s",
        duration_sec=15,
        description="HP・LP向け機能紹介。3大機能（基本情報・詳細分析・傾向管理）を順番に見せてQRへ誘導。",
        shots=[
            PatternShotData(
                time="0-5", phase="基本情報",
                scene_description="チラシ右端のスクリーンショット1枚目。「基本情報」画面がポップアップ。モーター名や点検日時がクリアに見える。",
                telop="1. 基本情報\n現場の情報を、デジタル化。",
                audio="[SE] ポップアップ音",
            ),
            PatternShotData(
                time="5-10", phase="分析詳細",
                scene_description="オクターブ分析、スペクトル画面の切り替え。「分析」タブの機能を網羅。",
                telop="2. 詳細分析\nオクターブ分析も、スペクトルも。",
                audio="[SE] スワイプ操作音（シャッ、シャッ）",
            ),
            PatternShotData(
                time="9-12", phase="傾向管理",
                scene_description="棒グラフで推移を確認。「写真/動画」タブもちらっと見せる。",
                telop="3. 傾向管理\n履歴が見える。変化に気づく。",
                audio="[SE] 完了音（ピンポン！）",
            ),
            PatternShotData(
                time="12-15", phase="アクション",
                scene_description="右下のQRコードがアップになる。「無料」の文字が弾む。QRコード + ダウンロードアイコン。",
                telop="今すぐ無料で\nダウンロード！",
                audio="[SE] チャイム + [VO] 「ダウンロード！」",
            ),
        ],
    ),
    PatternPreset(
        id="p3_main_40s",
        label="パターン3: メイン 40秒",
        duration="60s",
        duration_sec=40,
        description="HP・LP向けブランドストーリー。リリース→機能→体験→比較→信頼→タグラインで東芝ブランドを訴求。",
        shots=[
            PatternShotData(
                time="0-6", phase="リリース",
                scene_description="ホワイトバックに東芝ロゴと「新アプリ」のパッケージが回転して登場。チラシのキービジュアルが動く。",
                telop="モーター音響分析アプリ\nついに登場。",
                audio="[SE] ニュースのイントロ音 → ファンファーレ",
            ),
            PatternShotData(
                time="6-16", phase="機能",
                scene_description="チラシ右側のスマホ画面（スペクトル分析）が拡大。波形がリアルタイムに動き精密さをアピール。「無料」のスタンプが押される。",
                telop="この本格分析が、\n無料で。",
                audio="[SE] アプリ起動音 → 解析音",
            ),
            PatternShotData(
                time="16-24", phase="体験",
                scene_description="作業員がポケットからスマホを取り出し、モーターにかざす。「プロの耳」がポケットに入っているようなアイコンアニメーション。",
                telop="現場のポケットに、\nプロの技術を。",
                audio="[SE] シュッ（ポケットから出す音）+ 信頼感のあるBGM",
            ),
            PatternShotData(
                time="24-30", phase="比較",
                scene_description="「正常」と「異常」の波形を比較表示。違いが一目瞭然であることを示す。Split Screen, Blue vs Red。",
                telop="正常も、異常も、\n視覚的に判別。",
                audio="[SE] 比較音「ピン、ピン」 → 納得のチャイム",
            ),
            PatternShotData(
                time="30-36", phase="信頼",
                scene_description="東芝の技術ロゴと精密なデータ画面。バックグラウンドで「0次点検」の文字が浮かび上がる。信頼感のある白と青のモーショングラフィックス。",
                telop="東芝の技術が\nあなたをサポート。",
                audio="[SE] 重厚なオーケストラSE",
            ),
            PatternShotData(
                time="36-40", phase="タグライン",
                scene_description="「ポケットにプロを。」のタグラインと東芝ロゴ。ダウンロードQRが表示。",
                telop="ポケットにプロを。\n今すぐ無料ダウンロード",
                audio="[音楽] ブランドジングル",
            ),
        ],
    ),
    PatternPreset(
        id="p4_hybrid_40s",
        label="パターン4: ハイブリッド 40秒",
        duration="60s",
        duration_sec=40,
        description="課題提示→ステップ解説型。現場担当者の「不安」を起点にSTEP1〜3でソリューションを展開、最後にオファー。",
        shots=[
            PatternShotData(
                time="0-5", phase="課題",
                scene_description="「音」の変化は耳だけでは分からない不安。暗いトーンで潜在リスクを提示。困り顔の作業員、「？」マーク。",
                telop="その異音、\n聞き分けられますか？",
                audio="[SE] ノイズ音・環境音 不安を煽る低音",
            ),
            PatternShotData(
                time="5-12", phase="録音",
                scene_description="「録音するだけ」の手軽さ。マイクアイコンが波形を吸い込む。チラシのStep1アイコン。",
                telop="STEP 1\nモーター音を、\n録音するだけ。",
                audio="[SE] 録音ボタン音 → 吸い込み音",
            ),
            PatternShotData(
                time="12-20", phase="検査",
                scene_description="データが瞬時にグラフ化される。「本格的」な解析画面。チラシのStep2分析画面。",
                telop="STEP 2\nこれだけで\n本格的な検査が可能。",
                audio="[SE] デジタル解析音 キラリと光るエフェクト",
            ),
            PatternShotData(
                time="20-30", phase="管理",
                scene_description="複数のデータがクラウド（中央）に集まる。「一元管理」のアイコン。チラシのStep3データ連携図。",
                telop="STEP 3\n結果をデータで\n一元管理。",
                audio="[SE] データ集合音 組織的なイメージのSE",
            ),
            PatternShotData(
                time="30-40", phase="オファー",
                scene_description="「今だけ無料」の帯リボン。ダウンロードボタン。チラシの「NEW」「無料」強調デザイン。",
                telop="このアプリが、\n今だけ無料。\nまずは体験！",
                audio="[音楽] アップテンポな終了音",
            ),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/plan",
    response_model=StoryboardPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a storyboard plan from a brief",
)
def create_plan(body: StoryboardPlanRequest) -> StoryboardPlanResponse:
    """Generate a multi-shot storyboard plan using the MEKIKI StoryboardPlanner.

    The planner segments the requested duration into directorial phases
    (Hook / Problem / Insight / Solution / Proof / CTA) and synthesises
    copy text, narration text, and a visual hint for each shot.

    The resulting plan is stored in memory and retrievable via GET /shots.
    """
    try:
        StoryboardPlanner = _import_storyboard_planner()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    planner = StoryboardPlanner()
    text_candidates = [body.brief]
    if body.source_url:
        text_candidates.append(body.source_url)

    raw_shots: List[Dict[str, Any]] = planner.generate(
        duration_sec=body.duration_sec,
        text_candidates=text_candidates,
        image_candidates=[],
    )

    shots = [
        ShotProposal(
            shot_no=s["shot_no"],
            phase=s["phase"],
            start_sec=s["start_sec"],
            end_sec=s["end_sec"],
            duration_sec=s["duration_sec"],
            copy_text=s["copy_text"],
            narration_text=s["narration_text"],
            visual_hint=s["visual_hint"],
            source_excerpt=s["source_excerpt"],
        )
        for s in raw_shots
    ]

    plan_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    _PLANS[plan_id] = {
        "plan_id": plan_id,
        "brief": body.brief,
        "style": body.style,
        "source_url": body.source_url,
        "total_duration_sec": body.duration_sec,
        "created_at": created_at,
        "shots": [s.model_dump() for s in shots],
    }

    return StoryboardPlanResponse(
        plan_id=plan_id,
        shots=shots,
        total_duration_sec=body.duration_sec,
        created_at=created_at,
    )


@router.post(
    "/segment",
    response_model=SegmentResult,
    summary="Analyse URL or PDF for layer segmentation (stub)",
)
def segment_source(body: SegmentRequest) -> SegmentResult:
    """Accepts a URL or PDF path and returns object-level layer segments.

    This endpoint is a stub — the full ObjectSegmentationSDK integration
    requires the MEKIKI OCR engine to run a document capture pass first.
    Returns an empty segment list until a capture job is linked.
    """
    source = body.url or body.pdf_path or ""
    # Stub: return empty segments
    return SegmentResult(segments=[], page_count=0, source=source)


@router.post(
    "/generate",
    summary="Proxy render request to FlowForge server",
)
async def generate_shots(body: GenerateRequest) -> Any:
    """Retrieve a stored plan and proxy a render request to the FlowForge
    server (POST /api/storyboard/generate).

    Returns the ShotResult array produced by FlowForge.
    """
    plan = _PLANS.get(body.plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{body.plan_id}' not found. Call POST /plan first.",
        )

    flowforge_url = f"{settings.flowforge_server_url.rstrip('/')}/api/storyboard/generate"
    payload = FlowStoryboardData(
        title=plan.get("brief", "")[:80],
        globalStyle=plan.get("style"),
        shots=[
            {
                "shot_no": s["shot_no"],
                "phase": s["phase"],
                "copy": s["copy_text"],
                "narration": s["narration_text"],
                "visual_hint": s["visual_hint"],
                "start_sec": s["start_sec"],
                "end_sec": s["end_sec"],
            }
            for s in plan.get("shots", [])
        ],
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                flowforge_url,
                json=payload.model_dump(),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Cannot reach FlowForge server at {settings.flowforge_server_url}. "
                "Ensure the FlowForge server is running."
            ),
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"FlowForge returned an error: {exc.response.text}",
        ) from exc


@router.get(
    "/shots",
    response_model=List[ShotProposal],
    summary="Retrieve stored shots for a plan",
)
def get_shots(plan_id: str = Query(..., description="Plan ID returned by POST /plan")) -> List[ShotProposal]:
    """Return the list of ShotProposal objects previously generated for the
    given plan_id.
    """
    plan = _PLANS.get(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )
    return [ShotProposal(**s) for s in plan.get("shots", [])]


@router.get(
    "/export/{plan_id}",
    summary="Export storyboard plan as JSON or XLSX",
)
def export_plan(
    plan_id: str,
    format: str = Query("json", description="Output format: json | xlsx"),
) -> Response:
    """Export a stored storyboard plan.

    - format=json  → returns the plan as a JSON file download.
    - format=xlsx  → calls MEKIKI StoryboardExporter to build an Excel workbook.

    The XLSX export requires openpyxl to be installed in the OCR environment.
    """
    plan = _PLANS.get(plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan '{plan_id}' not found.",
        )

    if format == "json":
        content = json.dumps(plan, ensure_ascii=False, indent=2)
        return Response(
            content=content.encode("utf-8"),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="storyboard_{plan_id[:8]}.json"'
            },
        )

    if format == "xlsx":
        try:
            StoryboardExporter = _import_storyboard_exporter()
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        try:
            exporter = StoryboardExporter()
            # StoryboardExporter.export() may accept a list of shot dicts.
            # Adapt to whatever signature the exporter exposes.
            shots_dicts = plan.get("shots", [])
            buf = io.BytesIO()
            exporter.export(shots=shots_dicts, output=buf)
            buf.seek(0)
            return Response(
                content=buf.read(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="storyboard_{plan_id[:8]}.xlsx"'
                    )
                },
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"XLSX export failed: {exc}",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown format '{format}'. Use json or xlsx.",
    )


@router.get(
    "/patterns",
    response_model=List[PatternPreset],
    summary="List TBEX storyboard pattern presets",
)
def list_patterns() -> List[PatternPreset]:
    """Return the 4 TBEX pattern presets (SNS 15s / Feature 15s / Main 40s / Hybrid 40s).

    Each preset contains pre-filled shot data (phase, scene_description, telop, audio)
    that can be used as a starting point for storyboard planning.
    """
    return _TBEX_PATTERNS


@router.post(
    "/from-pattern",
    response_model=StoryboardPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create storyboard plan from a TBEX pattern preset",
)
def create_from_pattern(body: FromPatternRequest) -> StoryboardPlanResponse:
    """Create a storyboard plan directly from one of the 4 TBEX pattern presets.

    The preset shots are used as-is (scene_description, telop, audio pre-filled),
    and the StoryboardPlanner is invoked with the pattern's duration to fill in
    the standard fields (copy_text, narration_text, visual_hint).
    """
    preset = next((p for p in _TBEX_PATTERNS if p.id == body.pattern_id), None)
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern '{body.pattern_id}' not found. "
                   f"Available: {[p.id for p in _TBEX_PATTERNS]}",
        )

    # Use brief from request or generate one from pattern description
    brief = body.brief.strip() or preset.description

    # Try to enrich with StoryboardPlanner (optional — falls back to preset data)
    planner_shots: List[Dict[str, Any]] = []
    try:
        StoryboardPlanner = _import_storyboard_planner()
        planner = StoryboardPlanner()
        planner_shots = planner.generate(
            duration_sec=preset.duration_sec,
            text_candidates=[brief],
            image_candidates=[],
        )
    except Exception:
        pass  # Fall back to pure preset shots

    shots: List[ShotProposal] = []
    for i, preset_shot in enumerate(preset.shots):
        # Parse time range from preset (e.g. "0-5" → start=0.0, end=5.0)
        parts = preset_shot.time.split("-")
        try:
            start_sec = float(parts[0])
            end_sec = float(parts[1])
        except (IndexError, ValueError):
            start_sec = float(i * 5)
            end_sec = float((i + 1) * 5)
        duration_sec = end_sec - start_sec

        # Merge planner output with preset TBEX fields
        planner_shot = planner_shots[i] if i < len(planner_shots) else {}
        shots.append(ShotProposal(
            shot_no=i + 1,
            phase=preset_shot.phase,
            start_sec=start_sec,
            end_sec=end_sec,
            duration_sec=duration_sec,
            copy_text=planner_shot.get("copy_text", preset_shot.telop.split("\n")[0]),
            narration_text=planner_shot.get("narration_text", preset_shot.scene_description[:80]),
            visual_hint=planner_shot.get("visual_hint", preset_shot.scene_description),
            source_excerpt=brief[:120],
            # TBEX-specific fields
            scene_description=preset_shot.scene_description,
            telop=preset_shot.telop,
            audio=preset_shot.audio,
        ))

    plan_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    _PLANS[plan_id] = {
        "plan_id": plan_id,
        "brief": brief,
        "style": "realistic",
        "pattern_id": body.pattern_id,
        "total_duration_sec": preset.duration_sec,
        "created_at": created_at,
        "shots": [s.model_dump() for s in shots],
    }

    return StoryboardPlanResponse(
        plan_id=plan_id,
        shots=shots,
        total_duration_sec=preset.duration_sec,
        created_at=created_at,
    )
