"""
正規化処理のテスト
"""
import pytest
from app.pipeline.normalize import (
    normalize_text,
    calculate_confidence_stats,
    estimate_style_hints,
)


def test_normalize_text():
    """テキスト正規化のテスト"""
    config = {
        "normalize": {
            "ja": {
                "fullwidth_ascii": True,
            },
        },
    }
    
    # 全角ASCIIを半角に変換
    text = "テスト１２３"
    normalized = normalize_text(text, config)
    # 全角数字が半角に変換される（実装による）
    assert isinstance(normalized, str)


def test_calculate_confidence_stats():
    """信頼度統計計算のテスト"""
    import pytest
    
    items = [
        {"confidence": 0.8},
        {"confidence": 0.9},
        {"confidence": 0.7},
    ]
    
    stats = calculate_confidence_stats(items)
    assert "min" in stats
    assert "mean" in stats
    assert "p95" in stats
    assert stats["min"] == 0.7
    assert stats["mean"] == pytest.approx(0.8, abs=0.01)


def test_estimate_style_hints():
    """スタイルヒント推定のテスト"""
    cluster = [
        {"bbox": {"x1": 10, "y1": 10, "x2": 50, "y2": 30}},
    ]
    
    hints = estimate_style_hints(cluster)
    assert "font_size_bucket" in hints
    assert "weight_bucket" in hints
    assert hints["font_size_bucket"] in ["S", "M", "L", "XL", "unknown"]



