"""
Analyzer Module
コア分析エンジン - テキスト比較、類似度計算、自動マッチング
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from pathlib import Path
import difflib
import uuid


@dataclass
class DetectedArea:
    """
    検出されたテキストエリア
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    bbox: List[int] = field(default_factory=lambda: [0, 0, 0, 0])  # [x0, y0, x1, y1]
    confidence: float = 0.0
    source_type: str = ""  # "web" or "pdf"
    source_id: str = ""  # URL or PDF filename
    page_num: Optional[int] = None  # PDFの場合はページ番号
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "page_num": self.page_num
        }


@dataclass
class MatchedPair:
    """
    マッチングされたWebエリアとPDFエリアのペア
    """
    web_area: DetectedArea
    pdf_area: DetectedArea
    similarity_score: float
    match_type: str = "auto"  # "auto" or "manual"
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "web_area": self.web_area.to_dict(),
            "pdf_area": self.pdf_area.to_dict(),
            "similarity_score": self.similarity_score,
            "match_type": self.match_type
        }


class ContentAnalyzer:
    """
    コンテンツ分析エンジン
    OCR結果の管理、自動マッチング、類似度計算
    """
    
    def __init__(self, ocr_engine=None):
        """
        Args:
            ocr_engine: OCREngineインスタンス（オプション）
        """
        self.ocr_engine = ocr_engine
        self.web_areas: List[DetectedArea] = []
        self.pdf_areas: List[DetectedArea] = []
        self.matched_pairs: List[MatchedPair] = []
    
    def analyze_image(
        self,
        image_path: str,
        source_type: str,
        source_id: str,
        page_num: Optional[int] = None
    ) -> List[DetectedArea]:
        """
        画像をOCRにかけ、結果をDetectedAreaのリストに変換して保存
        
        Args:
            image_path: 画像ファイルのパス
            source_type: "web" or "pdf"
            source_id: URL or PDF filename
            page_num: PDFの場合はページ番号
        
        Returns:
            DetectedAreaのリスト
        """
        # ファイル存在確認
        if not Path(image_path).exists():
            print(f"⚠️ 画像ファイルが見つかりません: {image_path}")
            return []
        
        # OCRエンジンの確認
        if not self.ocr_engine:
            print("⚠️ OCRエンジンが初期化されていません")
            return []
        
        try:
            # OCR実行
            print(f"🔍 OCR実行中: {Path(image_path).name}")
            result = self.ocr_engine.detect_document_text(image_path)
            
            if not result:
                print(f"⚠️ OCR結果が取得できませんでした: {image_path}")
                return []
            
            # DetectedAreaに変換
            areas = []
            for block in result.get("blocks", []):
                area = DetectedArea(
                    text=block["text"],
                    bbox=block["bbox"],
                    confidence=block["confidence"],
                    source_type=source_type,
                    source_id=source_id,
                    page_num=page_num
                )
                areas.append(area)
            
            # リストに追加
            if source_type == "web":
                self.web_areas.extend(areas)
            elif source_type == "pdf":
                self.pdf_areas.extend(areas)
            
            print(f"✅ {len(areas)} エリア検出: {Path(image_path).name}")
            return areas
            
        except Exception as e:
            print(f"⚠️ 画像分析エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def compute_auto_matches(
        self,
        threshold: float = 0.3,
        method: str = "hybrid"
    ) -> List[MatchedPair]:
        """
        WebエリアとPDFエリアのテキスト類似度を計算し、自動ペアリング
        
        Args:
            threshold: マッチング閾値
            method: 類似度計算方法 ("difflib", "jaccard", "hybrid")
        
        Returns:
            MatchedPairのリスト
        """
        if not self.web_areas:
            print("⚠️ Webエリアがありません")
            return []
        
        if not self.pdf_areas:
            print("⚠️ PDFエリアがありません")
            return []
        
        print(f"🔄 自動マッチング開始: Web {len(self.web_areas)} × PDF {len(self.pdf_areas)}")
        
        self.matched_pairs.clear()
        
        try:
            # 各Webエリアに対して最適なPDFエリアを探す
            for web_area in self.web_areas:
                best_match = None
                best_score = 0.0
                
                for pdf_area in self.pdf_areas:
                    # 類似度を計算
                    if method == "difflib":
                        score = self._calculate_similarity(web_area.text, pdf_area.text)
                    elif method == "jaccard":
                        score = self._calculate_jaccard(web_area.text, pdf_area.text)
                    else:  # hybrid
                        score1 = self._calculate_similarity(web_area.text, pdf_area.text)
                        score2 = self._calculate_jaccard(web_area.text, pdf_area.text)
                        score = (score1 + score2) / 2
                    
                    # 最高スコアを記録
                    if score > best_score:
                        best_score = score
                        best_match = pdf_area
                
                # 閾値を超えていればペアとして追加
                if best_match and best_score >= threshold:
                    pair = MatchedPair(
                        web_area=web_area,
                        pdf_area=best_match,
                        similarity_score=best_score,
                        match_type="auto"
                    )
                    self.matched_pairs.append(pair)
            
            print(f"✅ {len(self.matched_pairs)} ペアが見つかりました")
            return self.matched_pairs
            
        except Exception as e:
            print(f"⚠️ マッチング処理エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        difflib を使用した類似度計算
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            類似度 (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    def _calculate_jaccard(self, text1: str, text2: str) -> float:
        """
        Jaccard係数を計算（単語ベース）
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            Jaccard係数 (0.0-1.0)
        """
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_differences(self, text1: str, text2: str) -> List[Dict]:
        """
        2つのテキスト間の差分を検出
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            差分リスト [{"type": "add/delete/change", "text": str, "line": int}, ...]
        """
        differences = []
        
        # 行ごとに分割
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        # ndiff で差分を取得
        diff = difflib.ndiff(lines1, lines2)
        
        line_num = 0
        for item in diff:
            if item.startswith('+ '):  # 追加
                differences.append({
                    "type": "add",
                    "text": item[2:],
                    "line": line_num
                })
            elif item.startswith('- '):  # 削除
                differences.append({
                    "type": "delete",
                    "text": item[2:],
                    "line": line_num
                })
            elif item.startswith('? '):  # 変更インジケータ
                pass  # スキップ
            else:  # 同一行
                line_num += 1
        
        return differences
    
    def add_manual_pair(
        self,
        web_area: DetectedArea,
        pdf_area: DetectedArea
    ) -> MatchedPair:
        """
        手動でペアを追加
        
        Args:
            web_area: Webエリア
            pdf_area: PDFエリア
        
        Returns:
            作成されたMatchedPair
        """
        # 類似度を計算
        score = self._calculate_similarity(web_area.text, pdf_area.text)
        
        pair = MatchedPair(
            web_area=web_area,
            pdf_area=pdf_area,
            similarity_score=score,
            match_type="manual"
        )
        
        self.matched_pairs.append(pair)
        print(f"✅ 手動ペア追加: スコア {score:.2%}")
        
        return pair
    
    def clear_all(self):
        """全データをクリア"""
        self.web_areas.clear()
        self.pdf_areas.clear()
        self.matched_pairs.clear()
        print("🗑️ 全データをクリアしました")
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        return {
            "web_areas_count": len(self.web_areas),
            "pdf_areas_count": len(self.pdf_areas),
            "matched_pairs_count": len(self.matched_pairs),
            "average_similarity": sum(p.similarity_score for p in self.matched_pairs) / len(self.matched_pairs) if self.matched_pairs else 0.0
        }

