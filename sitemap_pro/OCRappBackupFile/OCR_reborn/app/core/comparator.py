"""
比較エンジン
WebスクリーンショットとPDF画像の同一IDエリアを比較
差異検出とマッチング精度の評価
"""

from typing import List, Dict, Tuple, Optional
from PIL import Image, ImageChops, ImageDraw, ImageFont
import difflib
import os


class Comparator:
    """
    Web画像とPDF画像の比較エンジン
    
    機能:
    - テキスト差分検出（difflib使用）
    - 画像差分検出（ピクセル比較）
    - 領域単位の比較
    - マッチング精度の評価
    - 差分可視化
    """
    
    def __init__(self):
        self.web_clusters = []
        self.pdf_clusters = []
        self.comparison_results = []
    
    def set_data(
        self,
        web_clusters: List[Dict],
        pdf_clusters: List[Dict],
        web_image: Optional[Image.Image] = None,
        pdf_image: Optional[Image.Image] = None
    ):
        """
        比較対象のデータをセット
        
        Args:
            web_clusters: Webから検出されたクラスタ
            pdf_clusters: PDFから検出されたクラスタ
            web_image: Web画像（オプション）
            pdf_image: PDF画像（オプション）
        """
        self.web_clusters = web_clusters
        self.pdf_clusters = pdf_clusters
        self.web_image = web_image
        self.pdf_image = pdf_image
        self.comparison_results = []
    
    def compare_all(self) -> List[Dict]:
        """
        全エリアを比較
        
        Returns:
            比較結果のリスト
            [{
                "area_id": int,
                "web_text": str,
                "pdf_text": str,
                "similarity": float (0.0 - 1.0),
                "status": "match" | "mismatch" | "web_only" | "pdf_only",
                "diff_html": str,
                "web_rect": [x0, y0, x1, y1],
                "pdf_rect": [x0, y0, x1, y1]
            }, ...]
        """
        # IDでマッチング
        web_dict = {c['id']: c for c in self.web_clusters}
        pdf_dict = {c['id']: c for c in self.pdf_clusters}
        
        all_ids = set(web_dict.keys()) | set(pdf_dict.keys())
        
        results = []
        
        for area_id in sorted(all_ids):
            web_cluster = web_dict.get(area_id)
            pdf_cluster = pdf_dict.get(area_id)
            
            result = self._compare_single(area_id, web_cluster, pdf_cluster)
            results.append(result)
        
        self.comparison_results = results
        return results
    
    def _compare_single(
        self,
        area_id: int,
        web_cluster: Optional[Dict],
        pdf_cluster: Optional[Dict]
    ) -> Dict:
        """単一エリアの比較"""
        result = {
            "area_id": area_id,
            "web_text": "",
            "pdf_text": "",
            "similarity": 0.0,
            "status": "unknown",
            "diff_html": "",
            "web_rect": None,
            "pdf_rect": None
        }
        
        # Web only
        if web_cluster and not pdf_cluster:
            result["web_text"] = web_cluster.get("text", "")
            result["web_rect"] = web_cluster.get("rect")
            result["status"] = "web_only"
            result["similarity"] = 0.0
            return result
        
        # PDF only
        if pdf_cluster and not web_cluster:
            result["pdf_text"] = pdf_cluster.get("text", "")
            result["pdf_rect"] = pdf_cluster.get("rect")
            result["status"] = "pdf_only"
            result["similarity"] = 0.0
            return result
        
        # Both exist
        web_text = web_cluster.get("text", "")
        pdf_text = pdf_cluster.get("text", "")
        
        result["web_text"] = web_text
        result["pdf_text"] = pdf_text
        result["web_rect"] = web_cluster.get("rect")
        result["pdf_rect"] = pdf_cluster.get("rect")
        
        # テキスト類似度計算
        similarity = self._calculate_similarity(web_text, pdf_text)
        result["similarity"] = similarity
        
        # ステータス判定
        if similarity >= 0.95:
            result["status"] = "match"
        else:
            result["status"] = "mismatch"
        
        # 差分HTML生成
        result["diff_html"] = self._generate_diff_html(web_text, pdf_text)
        
        return result
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        テキスト類似度を計算（0.0 - 1.0）
        
        SequenceMatcher を使用した類似度判定
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # 正規化（空白・改行の統一）
        text1_normalized = " ".join(text1.split())
        text2_normalized = " ".join(text2.split())
        
        return difflib.SequenceMatcher(None, text1_normalized, text2_normalized).ratio()
    
    def _generate_diff_html(self, text1: str, text2: str) -> str:
        """
        差分をHTML形式で生成
        """
        diff = difflib.unified_diff(
            text1.splitlines(),
            text2.splitlines(),
            lineterm='',
            n=0
        )
        
        html_lines = []
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                html_lines.append(f'<span style="background-color: #90EE90;">{line}</span>')
            elif line.startswith('-') and not line.startswith('---'):
                html_lines.append(f'<span style="background-color: #FFB6C1;">{line}</span>')
            else:
                html_lines.append(line)
        
        return '<br>'.join(html_lines)
    
    def get_summary(self) -> Dict:
        """
        比較結果のサマリーを取得
        
        Returns:
            {
                "total": int,
                "match": int,
                "mismatch": int,
                "web_only": int,
                "pdf_only": int,
                "average_similarity": float
            }
        """
        if not self.comparison_results:
            return {
                "total": 0,
                "match": 0,
                "mismatch": 0,
                "web_only": 0,
                "pdf_only": 0,
                "average_similarity": 0.0
            }
        
        summary = {
            "total": len(self.comparison_results),
            "match": 0,
            "mismatch": 0,
            "web_only": 0,
            "pdf_only": 0,
            "average_similarity": 0.0
        }
        
        similarities = []
        
        for result in self.comparison_results:
            status = result["status"]
            if status == "match":
                summary["match"] += 1
            elif status == "mismatch":
                summary["mismatch"] += 1
            elif status == "web_only":
                summary["web_only"] += 1
            elif status == "pdf_only":
                summary["pdf_only"] += 1
            
            similarities.append(result["similarity"])
        
        if similarities:
            summary["average_similarity"] = sum(similarities) / len(similarities)
        
        return summary
    
    def generate_diff_image(
        self,
        area_id: int,
        output_path: str = None
    ) -> Optional[Image.Image]:
        """
        特定エリアの差分画像を生成
        
        Args:
            area_id: エリアID
            output_path: 保存先パス（指定した場合は保存）
        
        Returns:
            差分画像
        """
        if not self.web_image or not self.pdf_image:
            print("⚠️  画像が設定されていません")
            return None
        
        # エリア情報の取得
        web_cluster = next((c for c in self.web_clusters if c['id'] == area_id), None)
        pdf_cluster = next((c for c in self.pdf_clusters if c['id'] == area_id), None)
        
        if not web_cluster or not pdf_cluster:
            print(f"⚠️  Area {area_id} が見つかりません")
            return None
        
        # 領域の切り出し
        web_rect = web_cluster['rect']
        pdf_rect = pdf_cluster['rect']
        
        web_crop = self.web_image.crop(web_rect)
        pdf_crop = self.pdf_image.crop(pdf_rect)
        
        # サイズを合わせる（大きい方に統一）
        max_width = max(web_crop.width, pdf_crop.width)
        max_height = max(web_crop.height, pdf_crop.height)
        
        web_resized = Image.new('RGB', (max_width, max_height), (255, 255, 255))
        pdf_resized = Image.new('RGB', (max_width, max_height), (255, 255, 255))
        
        web_resized.paste(web_crop, (0, 0))
        pdf_resized.paste(pdf_crop, (0, 0))
        
        # 差分画像作成
        diff = ImageChops.difference(web_resized, pdf_resized)
        
        # 横に並べて表示
        combined_width = max_width * 3 + 40
        combined_height = max_height + 60
        combined = Image.new('RGB', (combined_width, combined_height), (240, 240, 240))
        
        # 画像配置
        combined.paste(web_resized, (10, 50))
        combined.paste(pdf_resized, (max_width + 20, 50))
        combined.paste(diff, (max_width * 2 + 30, 50))
        
        # ラベル追加
        draw = ImageDraw.Draw(combined)
        try:
            # Windows環境でのフォント
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        draw.text((10, 10), "Web", fill=(0, 0, 0), font=font)
        draw.text((max_width + 20, 10), "PDF", fill=(0, 0, 0), font=font)
        draw.text((max_width * 2 + 30, 10), "Diff", fill=(255, 0, 0), font=font)
        
        if output_path:
            combined.save(output_path)
            print(f"✅ 差分画像を保存: {output_path}")
        
        return combined
    
    def export_to_csv(self, output_path: str):
        """
        比較結果をCSVにエクスポート
        
        Args:
            output_path: 出力CSVパス
        """
        import csv
        
        if not self.comparison_results:
            print("⚠️  比較結果がありません")
            return
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                "Area ID",
                "Status",
                "Similarity",
                "Web Text",
                "PDF Text"
            ])
            
            # データ
            for result in self.comparison_results:
                writer.writerow([
                    result["area_id"],
                    result["status"],
                    f"{result['similarity']:.2%}",
                    result["web_text"],
                    result["pdf_text"]
                ])
        
        print(f"✅ CSVを出力しました: {output_path}")
    
    def export_to_html(self, output_path: str):
        """
        比較結果をHTML形式でエクスポート
        
        Args:
            output_path: 出力HTMLパス
        """
        if not self.comparison_results:
            print("⚠️  比較結果がありません")
            return
        
        summary = self.get_summary()
        
        html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>Web vs PDF 比較結果</title>
    <style>
        body {{ font-family: 'Meiryo', 'Yu Gothic', sans-serif; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .summary {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .summary-item {{ display: inline-block; margin-right: 30px; }}
        .result-item {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #ccc; }}
        .match {{ border-left-color: #4CAF50; }}
        .mismatch {{ border-left-color: #FF5722; }}
        .web-only {{ border-left-color: #2196F3; }}
        .pdf-only {{ border-left-color: #FF9800; }}
        .status {{ font-weight: bold; padding: 5px 10px; border-radius: 4px; color: white; }}
        .status.match {{ background: #4CAF50; }}
        .status.mismatch {{ background: #FF5722; }}
        .status.web-only {{ background: #2196F3; }}
        .status.pdf-only {{ background: #FF9800; }}
        .text-box {{ background: #f9f9f9; padding: 10px; margin: 10px 0; border-radius: 4px; }}
        .diff {{ font-family: monospace; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>🔍 Web vs PDF 比較結果</h1>
    
    <div class="summary">
        <h2>📊 サマリー</h2>
        <div class="summary-item">総数: <strong>{summary['total']}</strong></div>
        <div class="summary-item">✅ 一致: <strong>{summary['match']}</strong></div>
        <div class="summary-item">⚠️ 不一致: <strong>{summary['mismatch']}</strong></div>
        <div class="summary-item">🌐 Web専用: <strong>{summary['web_only']}</strong></div>
        <div class="summary-item">📄 PDF専用: <strong>{summary['pdf_only']}</strong></div>
        <div class="summary-item">平均類似度: <strong>{summary['average_similarity']:.2%}</strong></div>
    </div>
    
    <h2>📝 詳細</h2>
"""
        
        for result in self.comparison_results:
            status_class = result['status']
            area_id = result['area_id']
            similarity = result['similarity']
            web_text = result['web_text'].replace('\n', '<br>')
            pdf_text = result['pdf_text'].replace('\n', '<br>')
            
            html += f"""
    <div class="result-item {status_class}">
        <h3>Area {area_id} <span class="status {status_class}">{status_class.upper()}</span></h3>
        <p>類似度: <strong>{similarity:.2%}</strong></p>
        
        <div class="text-box">
            <strong>🌐 Web:</strong><br>
            {web_text or '<i>(なし)</i>'}
        </div>
        
        <div class="text-box">
            <strong>📄 PDF:</strong><br>
            {pdf_text or '<i>(なし)</i>'}
        </div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ HTMLレポートを出力しました: {output_path}")

