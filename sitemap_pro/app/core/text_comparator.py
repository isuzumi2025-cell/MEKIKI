"""
テキスト比較・差分エンジン
2つのテキストソース間の差分計算、Sync Rate算出、サジェスト生成

Features:
- 文字レベル差分計算 (diff-match-patch)
- Sync Rate (一致率) 算出
- 差分ハイライトHTML生成
- 領域ごとの親和性マッピング
- LLM連携サジェスト (オプション)
"""
import re
import difflib
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime


class TextComparator:
    """
    テキスト比較エンジン
    
    Web vs PDF, 原稿 vs 掲載版 などの比較に対応
    """
    
    def __init__(self):
        self._dmp = None  # diff-match-patch インスタンス
        
    def _get_dmp(self):
        """diff-match-patch のインスタンスを取得（遅延初期化）"""
        if self._dmp is None:
            try:
                import diff_match_patch as dmp_module
                self._dmp = dmp_module.diff_match_patch()
            except ImportError:
                print("⚠️ diff-match-patch がインストールされていません。")
                print("   pip install diff-match-patch を実行してください。")
                print("   フォールバック: difflib を使用します。")
                self._dmp = None
        return self._dmp
    
    # =========================================================================
    # メイン比較機能
    # =========================================================================
    
    def compare(
        self,
        text_a: str,
        text_b: str,
        label_a: str = "Source A",
        label_b: str = "Source B",
        normalize: bool = True
    ) -> Dict[str, Any]:
        """
        2つのテキストを比較
        
        Args:
            text_a: ソーステキストA (例: Web)
            text_b: ソーステキストB (例: PDF)
            label_a: テキストAのラベル
            label_b: テキストBのラベル
            normalize: テキストを正規化するか
            
        Returns:
            {
                "sync_rate": float,  # 一致率 (0-100%)
                "diff_count": int,  # 差異箇所数
                "diffs": [
                    {"type": "equal/insert/delete", "text": str, "source": str},
                    ...
                ],
                "diff_html": str,  # 差分ハイライトHTML
                "summary": str  # 比較サマリー
            }
        """
        # テキスト正規化
        if normalize:
            text_a = self._normalize_text(text_a)
            text_b = self._normalize_text(text_b)
        
        # 差分計算
        diffs = self._calculate_diff(text_a, text_b)
        
        # Sync Rate 計算
        sync_rate = self._calculate_sync_rate(text_a, text_b)
        
        # 差分カウント
        diff_count = sum(1 for d in diffs if d["type"] != "equal")
        
        # HTML生成
        diff_html = self._generate_diff_html(diffs, label_a, label_b)
        
        # サマリー生成
        summary = self._generate_summary(sync_rate, diff_count, len(text_a), len(text_b))
        
        return {
            "sync_rate": sync_rate,
            "diff_count": diff_count,
            "diffs": diffs,
            "diff_html": diff_html,
            "summary": summary,
            "label_a": label_a,
            "label_b": label_b,
            "compared_at": datetime.utcnow().isoformat()
        }
    
    def compare_blocks(
        self,
        blocks_a: List[Dict],
        blocks_b: List[Dict]
    ) -> Dict[str, Any]:
        """
        ブロック単位で比較（領域親和性マッピング）
        
        Args:
            blocks_a: ソースAのブロックリスト [{"text": str, "bbox": [...], "area_id": int}, ...]
            blocks_b: ソースBのブロックリスト [{"text": str, "bbox": [...], "area_id": int}, ...]
            
        Returns:
            {
                "mappings": [
                    {
                        "source_a": {"area_id": int, "text": str},
                        "source_b": {"area_id": int, "text": str},
                        "similarity": float,
                        "diffs": [...]
                    },
                    ...
                ],
                "unmatched_a": [...],
                "unmatched_b": [...]
            }
        """
        mappings = []
        used_b = set()
        
        for block_a in blocks_a:
            best_match = None
            best_similarity = 0.0
            
            for i, block_b in enumerate(blocks_b):
                if i in used_b:
                    continue
                
                similarity = self._calculate_similarity(
                    block_a.get("text", ""),
                    block_b.get("text", "")
                )
                
                if similarity > best_similarity and similarity > 0.3:  # 30%以上で候補
                    best_similarity = similarity
                    best_match = (i, block_b)
            
            if best_match:
                i, matched_block = best_match
                used_b.add(i)
                
                # 詳細差分
                comparison = self.compare(
                    block_a.get("text", ""),
                    matched_block.get("text", ""),
                    normalize=True
                )
                
                mappings.append({
                    "source_a": {
                        "area_id": block_a.get("area_id"),
                        "text": block_a.get("text", ""),
                        "bbox": block_a.get("bbox", [])
                    },
                    "source_b": {
                        "area_id": matched_block.get("area_id"),
                        "text": matched_block.get("text", ""),
                        "bbox": matched_block.get("bbox", [])
                    },
                    "similarity": best_similarity,
                    "sync_rate": comparison["sync_rate"],
                    "diff_count": comparison["diff_count"]
                })
            else:
                # マッチなし
                mappings.append({
                    "source_a": {
                        "area_id": block_a.get("area_id"),
                        "text": block_a.get("text", ""),
                        "bbox": block_a.get("bbox", [])
                    },
                    "source_b": None,
                    "similarity": 0.0,
                    "sync_rate": 0.0,
                    "diff_count": 0
                })
        
        # マッチしなかったBのブロック
        unmatched_b = [blocks_b[i] for i in range(len(blocks_b)) if i not in used_b]
        
        return {
            "mappings": mappings,
            "unmatched_b": unmatched_b,
            "total_similarity": self._calculate_overall_similarity(mappings)
        }
    
    # =========================================================================
    # 差分計算
    # =========================================================================
    
    def _calculate_diff(self, text_a: str, text_b: str) -> List[Dict]:
        """差分を計算"""
        dmp = self._get_dmp()
        
        if dmp:
            # diff-match-patch を使用（高精度）
            diffs = dmp.diff_main(text_a, text_b)
            dmp.diff_cleanupSemantic(diffs)
            
            return [
                {
                    "type": self._dmp_op_to_type(op),
                    "text": text
                }
                for op, text in diffs
            ]
        else:
            # difflib フォールバック
            return self._difflib_diff(text_a, text_b)
    
    def _dmp_op_to_type(self, op: int) -> str:
        """diff-match-patch の操作を文字列に変換"""
        if op == 0:
            return "equal"
        elif op == 1:
            return "insert"
        else:
            return "delete"
    
    def _difflib_diff(self, text_a: str, text_b: str) -> List[Dict]:
        """difflib を使用した差分計算"""
        matcher = difflib.SequenceMatcher(None, text_a, text_b)
        result = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                result.append({"type": "equal", "text": text_a[i1:i2]})
            elif tag == "delete":
                result.append({"type": "delete", "text": text_a[i1:i2]})
            elif tag == "insert":
                result.append({"type": "insert", "text": text_b[j1:j2]})
            elif tag == "replace":
                result.append({"type": "delete", "text": text_a[i1:i2]})
                result.append({"type": "insert", "text": text_b[j1:j2]})
        
        return result
    
    # =========================================================================
    # Sync Rate 計算
    # =========================================================================
    
    def _calculate_sync_rate(self, text_a: str, text_b: str) -> float:
        """一致率を計算 (0-100%)"""
        if not text_a and not text_b:
            return 100.0
        if not text_a or not text_b:
            return 0.0
        
        matcher = difflib.SequenceMatcher(None, text_a, text_b)
        return round(matcher.ratio() * 100, 2)
    
    def _calculate_similarity(self, text_a: str, text_b: str) -> float:
        """2テキスト間の類似度を計算 (0-1)"""
        if not text_a and not text_b:
            return 1.0
        if not text_a or not text_b:
            return 0.0
        
        # 正規化
        text_a = self._normalize_text(text_a)
        text_b = self._normalize_text(text_b)
        
        matcher = difflib.SequenceMatcher(None, text_a, text_b)
        return matcher.ratio()
    
    def _calculate_overall_similarity(self, mappings: List[Dict]) -> float:
        """全体の類似度を計算"""
        if not mappings:
            return 0.0
        
        total_similarity = sum(m.get("similarity", 0) for m in mappings)
        return round(total_similarity / len(mappings) * 100, 2)
    
    # =========================================================================
    # HTML生成
    # =========================================================================
    
    def _generate_diff_html(
        self,
        diffs: List[Dict],
        label_a: str,
        label_b: str
    ) -> str:
        """差分をハイライトしたHTMLを生成"""
        html_parts = []
        
        for diff in diffs:
            text = self._escape_html(diff["text"])
            
            if diff["type"] == "equal":
                html_parts.append(f'<span class="diff-equal">{text}</span>')
            elif diff["type"] == "delete":
                html_parts.append(
                    f'<span class="diff-delete" title="削除: {label_a}">{text}</span>'
                )
            elif diff["type"] == "insert":
                html_parts.append(
                    f'<span class="diff-insert" title="追加: {label_b}">{text}</span>'
                )
        
        return "".join(html_parts)
    
    def _escape_html(self, text: str) -> str:
        """HTMLエスケープ"""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "<br>")
        )
    
    # =========================================================================
    # テキスト正規化
    # =========================================================================
    
    def _normalize_text(self, text: str) -> str:
        """比較用にテキストを正規化"""
        if not text:
            return ""
        
        # 全角→半角
        text = self._normalize_width(text)
        
        # 空白を正規化
        text = re.sub(r'\s+', ' ', text)
        
        # 前後の空白を除去
        text = text.strip()
        
        return text
    
    def _normalize_width(self, text: str) -> str:
        """全角英数字を半角に変換"""
        result = []
        for char in text:
            code = ord(char)
            # 全角英数字 → 半角
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            # 全角スペース → 半角
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(char)
        return ''.join(result)
    
    # =========================================================================
    # サマリー生成
    # =========================================================================
    
    def _generate_summary(
        self,
        sync_rate: float,
        diff_count: int,
        len_a: int,
        len_b: int
    ) -> str:
        """比較サマリーを生成"""
        if sync_rate >= 95:
            status = "✅ ほぼ一致"
        elif sync_rate >= 80:
            status = "⚠️ 軽微な差異あり"
        elif sync_rate >= 50:
            status = "⚠️ 中程度の差異"
        else:
            status = "❌ 大きな差異"
        
        return f"{status} | Sync Rate: {sync_rate}% | 差異: {diff_count}箇所 | A: {len_a}文字 / B: {len_b}文字"
    
    # =========================================================================
    # サジェスト生成 (LLM連携)
    # =========================================================================
    
    def generate_suggestions(
        self,
        comparison_result: Dict,
        mode: str = "proofread"
    ) -> List[Dict]:
        """
        差分に基づくサジェストを生成
        
        Args:
            comparison_result: compare() の結果
            mode: "proofread" (校正), "creative" (クリエイティブ評価)
            
        Returns:
            [
                {
                    "type": "spelling/grammar/style/creative",
                    "original": str,
                    "suggestion": str,
                    "reason": str
                },
                ...
            ]
        """
        suggestions = []
        diffs = comparison_result.get("diffs", [])
        
        # 差異箇所をサジェストに変換
        for i, diff in enumerate(diffs):
            if diff["type"] == "delete":
                # 次が insert なら置換として扱う
                next_diff = diffs[i + 1] if i + 1 < len(diffs) else None
                
                if next_diff and next_diff["type"] == "insert":
                    suggestions.append({
                        "type": "change",
                        "original": diff["text"],
                        "suggestion": next_diff["text"],
                        "reason": "変更箇所"
                    })
                else:
                    suggestions.append({
                        "type": "deletion",
                        "original": diff["text"],
                        "suggestion": "(削除)",
                        "reason": "削除箇所"
                    })
            
            elif diff["type"] == "insert" and (i == 0 or diffs[i-1]["type"] != "delete"):
                suggestions.append({
                    "type": "addition",
                    "original": "(なし)",
                    "suggestion": diff["text"],
                    "reason": "追加箇所"
                })
        
        return suggestions


# クイック比較関数
def quick_compare(text_a: str, text_b: str, **kwargs) -> Dict:
    """2テキストをクイック比較"""
    comparator = TextComparator()
    return comparator.compare(text_a, text_b, **kwargs)
