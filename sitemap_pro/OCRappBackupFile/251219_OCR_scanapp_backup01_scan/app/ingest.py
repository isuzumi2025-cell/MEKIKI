"""
Phase 1: 取り込み処理
"""
from pathlib import Path
from typing import Optional


def ingest_file(
    input_path: Path,
    client: str,
    campaign: str,
    month: Optional[str] = None,
    preprocess_lines: bool = True,
    debug: bool = False,
) -> dict:
    """
    画像/PDFを取り込んでOCR処理を実行
    
    Args:
        input_path: 入力ファイルまたはディレクトリ
        client: クライアント名
        campaign: キャンペーン名
        month: 月（YYYY-MM形式）
        preprocess_lines: 線マスク処理を有効化
        debug: デバッグモード
    
    Returns:
        処理結果の辞書
    """
    # TODO: Phase 1で実装
    return {
        "status": "not_implemented",
        "message": "Phase 1の実装が必要です",
    }
