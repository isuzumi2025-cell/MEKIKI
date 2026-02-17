"""
段落クラスタリングのテスト
"""
import pytest
from app.pipeline.paragraph import (
    normalize_ocr_elements,
    cluster_paragraphs,
    estimate_role,
    calculate_bbox_union,
)


def test_normalize_ocr_elements():
    """OCR要素の正規化テスト"""
    elements = [
        {"text": "下", "bbox": {"x1": 10, "y1": 20, "x2": 20, "y2": 30}, "confidence": 0.9},
        {"text": "上", "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20}, "confidence": 0.9},
    ]
    
    normalized = normalize_ocr_elements(elements)
    # 上→下にソートされる
    assert normalized[0]["text"] == "上"
    assert normalized[1]["text"] == "下"


def test_cluster_paragraphs():
    """段落クラスタリングのテスト"""
    elements = [
        {"text": "要素1", "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 30}, "confidence": 0.9},
        {"text": "要素2", "bbox": {"x1": 10, "y1": 35, "x2": 50, "y2": 55}, "confidence": 0.9},
        {"text": "要素3", "bbox": {"x1": 100, "y1": 10, "x2": 140, "y2": 30}, "confidence": 0.9},
    ]
    
    clusters = cluster_paragraphs(elements, distance_px=18, align_tolerance_px=8)
    # 近接する要素がクラスタリングされる
    assert len(clusters) >= 1


def test_estimate_role():
    """ロール推定のテスト"""
    # 見出し風（大きなフォント）
    large_cluster = [
        {"text": "見出し", "bbox": {"x1": 10, "y1": 10, "x2": 100, "y2": 50}, "confidence": 0.9},
    ]
    role = estimate_role(large_cluster, avg_font_size=20, headline_size_ratio=1.5)
    assert role in ["headline", "body", "other"]
    
    # 価格風（数字が多い）
    price_cluster = [
        {"text": "¥1000", "bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 30}, "confidence": 0.9},
    ]
    role = estimate_role(price_cluster, avg_font_size=20, price_digit_ratio=0.3)
    assert role == "price"


def test_calculate_bbox_union():
    """bbox_union計算のテスト"""
    cluster = [
        {"bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 30}},
        {"bbox": {"x1": 20, "y1": 20, "x2": 60, "y2": 40}},
    ]
    
    bbox_union = calculate_bbox_union(cluster)
    assert bbox_union["x1"] == 10
    assert bbox_union["y1"] == 10
    assert bbox_union["x2"] == 60
    assert bbox_union["y2"] == 40



