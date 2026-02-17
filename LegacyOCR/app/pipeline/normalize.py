"""
正規化JSON生成
"""
from typing import Dict, Any, List
from datetime import datetime
import hashlib
import json


def generate_normalized_json(
    doc_id: str,
    source_type: str,
    original_path: str,
    pages: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    正規化JSONを生成
    
    Args:
        doc_id: ドキュメントID
        source_type: "file", "pdf", "web"
        original_path: 元のパスまたはURL
        pages: ページデータのリスト
        config: 設定辞書（config_fingerprint生成用）
    
    Returns:
        正規化JSON辞書
    """
    # 設定のフィンガープリントを生成（再現性のため）
    config_str = json.dumps(config, sort_keys=True)
    config_fingerprint = hashlib.md5(config_str.encode()).hexdigest()[:8]
    
    normalized = {
        "doc_id": doc_id,
        "source": {
            "type": source_type,
            "original_path_or_url": original_path,
            "fetched_at": None,  # Phase 3で使用
        },
        "config_fingerprint": config_fingerprint,
        "pages": pages,
    }
    
    return normalized


def normalize_text(text: str, config: Dict[str, Any]) -> str:
    """
    テキストを正規化
    
    Args:
        text: 元のテキスト
        config: 設定辞書
    
    Returns:
        正規化されたテキスト
    """
    normalized = text
    
    # ASCIIの全半角統一
    if config.get("normalize", {}).get("ja", {}).get("fullwidth_ascii", True):
        # 全角ASCIIを半角に変換
        for char in normalized:
            if ord(char) >= 0xFF00 and ord(char) <= 0xFFEF:
                # 全角文字を半角に変換
                normalized = normalized.replace(char, chr(ord(char) - 0xFEE0))
    
    return normalized


def calculate_confidence_stats(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    信頼度統計を計算
    
    Args:
        items: 要素のリスト（confidence を持つ）
    
    Returns:
        {"min": float, "mean": float, "p95": float}
    """
    confidences = [item.get("confidence", 0.0) for item in items if item.get("confidence") is not None]
    
    if not confidences:
        return {"min": 0.0, "mean": 0.0, "p95": 0.0}
    
    confidences_sorted = sorted(confidences)
    n = len(confidences_sorted)
    
    return {
        "min": min(confidences),
        "mean": sum(confidences) / n,
        "p95": confidences_sorted[int(n * 0.95)] if n > 0 else 0.0,
    }


def estimate_style_hints(cluster: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    スタイルヒントを推定
    
    Args:
        cluster: 要素のリスト
    
    Returns:
        {"font_size_bucket": "S|M|L|XL", "weight_bucket": "light|regular|bold|unknown"}
    """
    if not cluster:
        return {"font_size_bucket": "unknown", "weight_bucket": "unknown"}
    
    # フォントサイズ（bboxの高さから推定）
    heights = []
    for elem in cluster:
        bbox = elem.get("bbox", {})
        height = bbox.get("y2", 0) - bbox.get("y1", 0)
        if height > 0:
            heights.append(height)
    
    if not heights:
        return {"font_size_bucket": "unknown", "weight_bucket": "unknown"}
    
    avg_height = sum(heights) / len(heights)
    
    # バケット分類（簡易版）
    if avg_height < 20:
        size_bucket = "S"
    elif avg_height < 30:
        size_bucket = "M"
    elif avg_height < 50:
        size_bucket = "L"
    else:
        size_bucket = "XL"
    
    # フォントウェイトは推定困難（OCR結果からは取得できない）
    weight_bucket = "unknown"
    
    return {
        "font_size_bucket": size_bucket,
        "weight_bucket": weight_bucket,
    }



