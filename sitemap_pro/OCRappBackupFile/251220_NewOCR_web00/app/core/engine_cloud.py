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
    # --- Dynamic Clustering 2.0 Logic ---
    def _vertical_stack_clustering(self, blocks):
        if not blocks: return []
        
        # 1. Coordinate Normalization & Sorting
        # Y coordinate is rounded to 'row unit' to handle slight skew
        blocks.sort(key=lambda b: (round(b["rect"][1] / 10), b["rect"][0]))

        # 2. Dynamic Threshold Calculation
        # Calculate the median font size to determine "Body Text" size
        font_sizes = [b["font_size"] for b in blocks]
        median_font = statistics.median(font_sizes) if font_sizes else 10
        
        clusters = [] 
        visited = set()

        for i, block in enumerate(blocks):
            if i in visited: continue
            
            # Start a new cluster
            current_cluster = {
                "rect": block["rect"],
                "texts": [block["text"]],
                "width": block["width"],
                "center_x": block["center_x"],
                "avg_font_size": block["font_size"],
                "role": "title" if block["font_size"] > median_font * 1.5 else "body"
            }
            visited.add(i)
            
            # Greedy merge with subsequent blocks
            has_merged = True
            while has_merged:
                has_merged = False
                best_match_idx = -1
                best_distance = float('inf')

                # Search for the next vertical neighbor
                for j, target in enumerate(blocks):
                    if j in visited: continue
                    
                    # Vertical Distance Check
                    # Distance between "Bottom of Current" and "Top of Target"
                    v_dist = target["rect"][1] - current_cluster["rect"][3]
                    
                    # Horizontal Overlap Check
                    min_w = min(current_cluster["width"], target["width"])
                    x_overlap = min(current_cluster["rect"][2], target["rect"][2]) - max(current_cluster["rect"][0], target["rect"][0])
                    overlap_ratio = x_overlap / min_w if min_w > 0 else 0
                    
                    # Left alignment check (crucial for paragraphs)
                    left_diff = abs(current_cluster["rect"][0] - target["rect"][0])

                    # --- DECISION RULES ---
                    # Rule 1: Must be below (allow small margin for side-by-side chunks that should be one line)
                    if v_dist < -10: continue 

                    # Rule 2: Dynamic Vertical Gap Threshold
                    # If it's a Title -> Body transition, allow larger gap.
                    gap_limit = median_font * 3.0
                    if current_cluster["role"] == "title":
                        gap_limit = median_font * 5.0
                    
                    if v_dist > gap_limit: continue

                    # Rule 3: Alignment
                    # Strictly require alignment for Body text. Looser for Title->Body.
                    is_aligned = overlap_ratio > 0.4 or left_diff < median_font * 2
                    if not is_aligned: continue

                    # Rule 4: Column Separation
                    # If there's another block *between* them horizontally, likely a different column. 
                    # (Simplified: check horizontal distance if not overlapping)
                    if overlap_ratio <= 0 and left_diff > median_font * 5: continue

                    # If valid, pick the closest one
                    if v_dist < best_distance:
                        best_distance = v_dist
                        best_match_idx = j

                if best_match_idx != -1:
                    target = blocks[best_match_idx]
                    visited.add(best_match_idx)
                    
                    # Update Cluster
                    current_cluster["rect"] = [
                        min(current_cluster["rect"][0], target["rect"][0]),
                        min(current_cluster["rect"][1], target["rect"][1]),
                        max(current_cluster["rect"][2], target["rect"][2]),
                        max(current_cluster["rect"][3], target["rect"][3])
                    ]
                    current_cluster["texts"].append(target["text"])
                    current_cluster["width"] = current_cluster["rect"][2] - current_cluster["rect"][0]
                    # Update font size (weighted average could be better, but max ensures we keep 'Title' status if mixed)
                    current_cluster["avg_font_size"] = max(current_cluster["avg_font_size"], target["font_size"])
                    has_merged = True

            clusters.append(current_cluster)

        return clusters

    def _orphan_absorption(self, clusters):
        # With Dynamic Clustering, orphans are usually legitimate noise or small captions.
        # We will just filter out extreme noise.
        final_clusters = []
        for c in clusters:
            # 1. Text Length Filter
            full_text = "".join(c["texts"])
            if len(full_text) < 2: continue # Remove single char noise
            
            # 2. Header/Footer Filter (Simple heuristic based on page position not available here without page size, skip)
            
            final_clusters.append(c)
            
        return final_clusters
