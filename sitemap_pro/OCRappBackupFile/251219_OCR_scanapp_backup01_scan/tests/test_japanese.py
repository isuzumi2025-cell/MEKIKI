"""
日本語チェックのテスト
"""
import pytest
from app.japanese.checker import (
    check_japanese,
    check_brackets,
    check_punctuation,
    check_whitespace,
    check_fullwidth,
    check_unit_consistency,
)


def test_check_brackets():
    """括弧チェックのテスト"""
    # 正常な括弧
    issues = check_brackets("（テスト）")
    assert len(issues) == 0
    
    # 開閉不整合
    issues = check_brackets("（テスト")
    assert len(issues) > 0
    assert issues[0]["type"] == "bracket_mismatch"


def test_check_punctuation():
    """句読点チェックのテスト"""
    # 連続する句読点
    issues = check_punctuation("テスト。。")
    assert len(issues) > 0
    assert issues[0]["type"] == "punctuation_repeat"


def test_check_whitespace():
    """空白チェックのテスト"""
    issues, suggestions = check_whitespace("日本語 の間")
    assert len(issues) > 0
    assert len(suggestions) > 0
    assert issues[0]["type"] == "unnatural_whitespace"


def test_check_fullwidth():
    """全半角チェックのテスト"""
    issues, suggestions = check_fullwidth("テスト123")
    # 混在がない場合は問題なし
    assert len(issues) == 0
    
    # 全半角混在
    issues, suggestions = check_fullwidth("テスト１２３abc")
    assert len(issues) > 0


def test_check_unit_consistency():
    """単位表記チェックのテスト"""
    issues, suggestions = check_unit_consistency("¥1000")
    assert len(issues) > 0
    assert len(suggestions) > 0
    assert suggestions[0]["after"] == "1000円"


def test_check_japanese_integration():
    """日本語チェックの統合テスト"""
    text = "（テスト）これは 日本語です。"
    rules = {
        "bracket_check": True,
        "punctuation_check": True,
        "whitespace_check": True,
        "fullwidth_check": True,
        "unit_check": True,
    }
    
    result = check_japanese(text, rules)
    assert "grammar_issues" in result
    assert "suggestions" in result



