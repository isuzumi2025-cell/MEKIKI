import os
import io
import math
import statistics
from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account
from app.core.interface import OCREngineStrategy

class CloudOCREngine(OCREngineStrategy):
    """
    Google Cloud Vision API (Raw Data Return Mode)
    GUI側で編集可能にするため、画像への描画は行わず、
    「クラスタリング結果」と「全文字の生データ」を返します。
    """

    def __init__(self):
        key_path = "service_account.json"
        if os.path.exists(key_path):
            credentials = service_account.Credentials.from_service_account_file(key_path)
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
        else:
            self.client = vision.ImageAnnotatorClient()

    def extract_text(self, image: Image.Image):
        """
        Returns: 
            clusters (list): 自動解析されたエリア情報のリスト
            raw_words (list): 全文字の生データ（手動修正時の再計算用）
        """
        try:
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            content = img_byte_arr.getvalue()
            vision_image = vision.Image(content=content)
            response = self.client.document_text_detection(image=vision_image)
            
            if response.error.message:
                raise RuntimeError(f"Cloud Vision API Error: {response.error.message}")

            # --- 1. 生データの取得 ---
            raw_blocks = [] # クラスタリング用
            raw_words = []  # 手動編集用（全単語の座標とテキスト）

            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    # クラスタリング用のブロック情報構築
                    block_text_parts = []
                    symbol_heights = []
                    
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join([symbol.text for symbol in word.symbols])
                            block_text_parts.append(word_text)
                            
                            # 単語単位の情報を保存（手動編集用）
                            wv = word.bounding_box.vertices
                            wx = [v.x for v in wv]
                            wy = [v.y for v in wv]
                            raw_words.append({
                                "text": word_text,
                                "rect": [min(wx), min(wy), max(wx), max(wy)],
                                "center": ((min(wx)+max(wx))/2, (min(wy)+max(wy))/2)
                            })

                            for symbol in word.symbols:
                                v = symbol.bounding_box.vertices
                                h = v[3].y - v[0].y
                                symbol_heights.append(h)
                    
                    # ブロック情報
                    v = block.bounding_box.vertices
                    x_coords = [vertex.x for vertex in v]
                    y_coords = [vertex.y for vertex in v]
                    
                    raw_blocks.append({
                        "text": "".join(block_text_parts),
                        "rect": [min(x_coords), min(y_coords), max(x_coords), max(y_coords)],
                        "center_x": (min(x_coords) + max(x_coords)) / 2,
                        "width": max(x_coords) - min(x_coords),
                        "font_size": statistics.mean(symbol_heights) if symbol_heights else 10
                    })

            # --- 2. 自動クラスタリング実行 ---
            vertical_clusters = self._vertical_stack_clustering(raw_blocks)
            final_clusters = self._orphan_absorption(vertical_clusters)

            # ソート
            def sort_key(cluster):
                x0, y0, _, _ = cluster["rect"]
                row = round(y0 / 60) * 60
                return (row, x0)
            final_clusters.sort(key=sort_key)

            # 辞書形式で整形して返す
            # GUI側で扱いやすいように ID を付与
            formatted_clusters = []
            for i, c in enumerate(final_clusters):
                formatted_clusters.append({
                    "id": i + 1,
                    "rect": list(map(int, c["rect"])),
                    "text": "\n".join(c["texts"])
                })

            return formatted_clusters, raw_words

        except Exception as e:
            raise RuntimeError(str(e))

    # --- 以下、前回のロジック（そのまま利用） ---
    def _vertical_stack_clustering(self, blocks):
        if not blocks: return []
        blocks.sort(key=lambda b: b["rect"][1])
        
        clusters = [{
            "rect": b["rect"], 
            "texts": [b["text"]],
            "width": b["width"],
            "center_x": b["center_x"],
            "avg_font_size": b["font_size"]
        } for b in blocks]
        
        has_merged = True
        while has_merged:
            has_merged = False
            new_clusters = []
            skip_indices = set()

            for i in range(len(clusters)):
                if i in skip_indices: continue
                current = clusters[i]
                
                for j in range(i + 1, len(clusters)):
                    if j in skip_indices: continue
                    target = clusters[j]
                    
                    # 結合判定
                    x_overlap = min(current["rect"][2], target["rect"][2]) - max(current["rect"][0], target["rect"][0])
                    min_width = min(current["width"], target["width"])
                    overlap_ratio = x_overlap / min_width if min_width > 0 else 0
                    left_diff = abs(current["rect"][0] - target["rect"][0])
                    is_aligned = overlap_ratio > 0.7 or left_diff < 20
                    
                    if not is_aligned: continue

                    gap_y = target["rect"][1] - current["rect"][3]
                    base_size = max(current["avg_font_size"], target["avg_font_size"])
                    threshold_y = max(base_size * 2.5, 80)

                    if gap_y > threshold_y: continue
                    if current["avg_font_size"] > target["avg_font_size"] * 2.0: continue
                    if target["avg_font_size"] > current["avg_font_size"] * 1.5: continue
                    
                    gap_x = max(0, target["rect"][0] - current["rect"][2]) if current["rect"][0] < target["rect"][0] else max(0, current["rect"][0] - target["rect"][2])
                    if gap_x > 10: continue

                    new_rect = [
                        min(current["rect"][0], target["rect"][0]),
                        min(current["rect"][1], target["rect"][1]),
                        max(current["rect"][2], target["rect"][2]),
                        max(current["rect"][3], target["rect"][3])
                    ]
                    
                    new_texts = current["texts"] + target["texts"] if current["rect"][1] < target["rect"][1] else target["texts"] + current["texts"]
                    new_avg = max(current["avg_font_size"], target["avg_font_size"])

                    current = {
                        "rect": new_rect, "texts": new_texts,
                        "width": new_rect[2] - new_rect[0],
                        "center_x": (new_rect[0] + new_rect[2]) / 2,
                        "avg_font_size": new_avg
                    }
                    skip_indices.add(j)
                    has_merged = True
                
                new_clusters.append(current)
            clusters = new_clusters
        return clusters

    def _orphan_absorption(self, clusters):
        if not clusters: return []
        areas = [(c["rect"][2]-c["rect"][0]) * (c["rect"][3]-c["rect"][1]) for c in clusters]
        avg_area = statistics.mean(areas) if areas else 0
        orphan_threshold = avg_area * 0.1 
        
        final_clusters = []
        orphans = []
        
        for c in clusters:
            area = (c["rect"][2]-c["rect"][0]) * (c["rect"][3]-c["rect"][1])
            text_len = sum(len(t) for t in c["texts"])
            if area < orphan_threshold or text_len < 3:
                orphans.append(c)
            else:
                final_clusters.append(c)

        if not final_clusters: return clusters

        for orphan in orphans:
            best_parent = None
            min_dist = float('inf')
            r1 = orphan["rect"]
            for parent in final_clusters:
                r2 = parent["rect"]
                dx = max(0, r2[0] - r1[2]) if r1[0] < r2[0] else max(0, r1[0] - r2[2])
                dy = max(0, r2[1] - r1[3]) if r1[1] < r2[1] else max(0, r1[1] - r2[3])
                dist = dx + dy
                if dist < 200 and dist < min_dist:
                    min_dist = dist
                    best_parent = parent
            
            if best_parent:
                r_p = best_parent["rect"]
                r_o = orphan["rect"]
                best_parent["rect"] = [min(r_p[0], r_o[0]), min(r_p[1], r_o[1]), max(r_p[2], r_o[2]), max(r_p[3], r_o[3])]
                best_parent["texts"].extend(orphan["texts"])
                best_parent["width"] = best_parent["rect"][2] - best_parent["rect"][0]
                best_parent["center_x"] = (best_parent["rect"][0] + best_parent["rect"][2]) / 2
            else:
                final_clusters.append(orphan)
        return final_clusters
