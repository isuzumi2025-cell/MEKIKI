"""
日本語チェック（ルールベース）
"""
from typing import List, Dict, Any, Tuple
import re


def check_japanese(text: str, rules: Dict[str, bool]) -> Dict[str, Any]:
    """
    Step D: 日本語整合チェック
    
    Args:
        text: チェック対象テキスト
        rules: チェックルールの有効/無効
    
    Returns:
        {"grammar_issues": [...], "suggestions": [...]}
    """
    issues = []
    suggestions = []
    
    if rules.get("bracket_check", True):
        bracket_issues = check_brackets(text)
        issues.extend(bracket_issues)
    
    if rules.get("punctuation_check", True):
        punct_issues = check_punctuation(text)
        issues.extend(punct_issues)
    
    if rules.get("whitespace_check", True):
        whitespace_issues, whitespace_suggestions = check_whitespace(text)
        issues.extend(whitespace_issues)
        suggestions.extend(whitespace_suggestions)
    
    if rules.get("fullwidth_check", True):
        fullwidth_issues, fullwidth_suggestions = check_fullwidth(text)
        issues.extend(fullwidth_issues)
        suggestions.extend(fullwidth_suggestions)
    
    if rules.get("unit_check", True):
        unit_issues, unit_suggestions = check_unit_consistency(text)
        issues.extend(unit_issues)
        suggestions.extend(unit_suggestions)
    
    return {
        "grammar_issues": issues,
        "suggestions": suggestions,
    }


def check_brackets(text: str) -> List[Dict[str, Any]]:
    """括弧の開閉不整合チェック"""
    issues = []
    
    bracket_pairs = [
        ("（", "）"),
        ("(", ")"),
        ("「", "」"),
        ("『", "』"),
        ("【", "】"),
        ("［", "］"),
    ]
    
    for open_bracket, close_bracket in bracket_pairs:
        open_count = text.count(open_bracket)
        close_count = text.count(close_bracket)
        
        if open_count != close_count:
            issues.append({
                "type": "bracket_mismatch",
                "span": [0, len(text)],
                "message": f"括弧の開閉不整合: {open_bracket} ({open_count}個) vs {close_bracket} ({close_count}個)",
                "severity": "warn",
            })
    
    return issues


def check_punctuation(text: str) -> List[Dict[str, Any]]:
    """句読点連続チェック"""
    issues = []
    
    # 連続する句読点
    patterns = [
        (r"。。+", "句点の連続"),
        (r"，，+", "読点の連続"),
        (r"！！+", "感嘆符の連続"),
        (r"？？+", "疑問符の連続"),
    ]
    
    for pattern, desc in patterns:
        matches = list(re.finditer(pattern, text))
        for match in matches:
            issues.append({
                "type": "punctuation_repeat",
                "span": [match.start(), match.end()],
                "message": f"{desc}を検出",
                "severity": "info",
            })
    
    return issues


def check_whitespace(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """不自然な空白チェック"""
    issues = []
    suggestions = []
    
    # 日本語中の半角空白（全角文字の間の半角空白）
    pattern = r"([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF])\s+([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF])"
    matches = list(re.finditer(pattern, text))
    
    for match in matches:
        issues.append({
            "type": "unnatural_whitespace",
            "span": [match.start(), match.end()],
            "message": "日本語中の不自然な空白",
            "severity": "info",
        })
        suggestions.append({
            "before": match.group(0),
            "after": match.group(1) + match.group(2),
            "reason": "日本語中の半角空白は通常不要",
            "confidence": "mid",
        })
    
    return issues, suggestions


def check_fullwidth(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """全角/半角の混在チェック"""
    issues = []
    suggestions = []
    
    # 英数字の全半角混在
    pattern = r"[0-9A-Za-z]+[０-９Ａ-Ｚａ-ｚ]+|[０-９Ａ-Ｚａ-ｚ]+[0-9A-Za-z]+"
    matches = list(re.finditer(pattern, text))
    
    for match in matches:
        issues.append({
            "type": "fullwidth_mix",
            "span": [match.start(), match.end()],
            "message": "全角/半角の混在",
            "severity": "info",
        })
        # 半角に統一する提案
        normalized = match.group(0)
        for char in normalized:
            if ord(char) >= 0xFF00 and ord(char) <= 0xFFEF:
                # 全角文字を半角に変換
                normalized = normalized.replace(char, chr(ord(char) - 0xFEE0))
        
        if normalized != match.group(0):
            suggestions.append({
                "before": match.group(0),
                "after": normalized,
                "reason": "全角/半角の統一（半角推奨）",
                "confidence": "mid",
            })
    
    return issues, suggestions


def check_unit_consistency(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """単位表記揺れチェック"""
    issues = []
    suggestions = []
    
    # 単位表記の統一ルール
    unit_rules = [
        (r"¥(\d+)", r"\1円", "円マークを「円」に統一"),
        (r"\\\s*(\d+)", r"\1円", "バックスラッシュを「円」に統一"),
    ]
    
    for pattern, replacement, reason in unit_rules:
        matches = list(re.finditer(pattern, text))
        for match in matches:
            issues.append({
                "type": "unit_inconsistency",
                "span": [match.start(), match.end()],
                "message": f"単位表記の揺れ: {match.group(0)}",
                "severity": "info",
            })
            normalized = re.sub(pattern, replacement, match.group(0))
            suggestions.append({
                "before": match.group(0),
                "after": normalized,
                "reason": reason,
                "confidence": "high",
            })
    
    return issues, suggestions



