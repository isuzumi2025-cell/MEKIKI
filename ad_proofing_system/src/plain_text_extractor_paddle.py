# src/plain_text_extractor_paddle.py
"""
【究極完全版】広告校正システム用 OCR
- CPUモード
- 画像処理: アンシャープマスク（鮮鋭化）
- 幾何学解析: 距離・整列・傾き
- 【新実装】視覚的推論: 文字のウエイト（太さ）と等級（サイズ）による厳密なグルーピング
"""

import os
import sys
from pathlib import Path
import math
import re
import logging

import fitz  # PyMuPDF
import numpy as np
import cv2
from paddleocr import PaddleOCR

# ログ抑制
logging.getLogger("ppocr").setLevel(logging.WARNING)

# ==========================================
# 設定
# ==========================================
RESCUE_KEYWORDS = re.compile(r"[0-9a-zA-Z]{2,}|円|税|Tel|Fax|http|OFF|%|検索|注文|届|送|込|期限")

# --- 類似性判定の許容範囲 ---
# 文字サイズ（高さ）の比率 (0.8倍〜1.25倍なら同じ等級とみなす)
SIZE_SIMILARITY_MIN = 0.8
SIZE_SIMILARITY_MAX = 1.25

# ウエイト（黒画素密度）の許容差 (0.0〜1.0)
# 差が 0.15 以内なら同じ太さとみなす（BoldとRegularの境界）
WEIGHT_DIFF_TOLERANCE = 0.15

# 行間（文字高さの何倍まで許容するか）
LINE_SPACING_LIMIT = 2.0

# 横方向の重なり（カラム判定）
HORIZONTAL_OVERLAP_LIMIT = 0.2

# ==========================================
# 画像処理 & 特徴量計算
# ==========================================

def preprocess_image_advanced(img_cv):
    """アンシャープマスクで文字をくっきりさせる"""
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_cv
    
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
    sharpened = float(3.0) * gray - float(2.0) * blurred
    sharpened = np.maximum(sharpened, 0)
    sharpened = np.minimum(sharpened, 255)
    sharpened = sharpened.astype(np.uint8)
    
    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

def calculate_visual_weight(img_full, box):
    """
    指定されたボックス領域の「黒画素密度（Weight）」を計算する
    Return: 0.0(真っ白) 〜 1.0(真っ黒)
    """
    # 座標を整数化
    xs = [int(p[0]) for p in box]
    ys = [int(p[1]) for p in box]
    x_min, x_max = max(0, min(xs)), min(img_full.shape[1], max(xs))
    y_min, y_max = max(0, min(ys)), min(img_full.shape[0], max(ys))
    
    if x_max <= x_min or y_max <= y_min:
        return 0.0

    # ROI（関心領域）切り出し
    roi = img_full[y_min:y_max, x_min:x_max]
    
    # グレースケール -> 二値化 (Otsu)
    if len(roi.shape) == 3:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    else:
        roi_gray = roi
        
    # 白背景・黒文字前提で二値化 (文字部分を0、背景を255にする)
    # THRESH_BINARY_INV で「文字(黒)を255」にする
    _, binary = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # 黒画素（実際は反転してるので白画素255）の数を数える
    ink_pixels = cv2.countNonZero(binary)
    total_pixels = binary.size
    
    if total_pixels == 0: return 0.0
    
    # 密度 = 文字部分の面積 / 矩形全体の面積
    density = ink_pixels / total_pixels
    return density

# ==========================================
# 自動推論ロジック
# ==========================================

def get_enhanced_metrics(img_cv, box, text, conf):
    """幾何学情報 + 視覚情報(Weight/Size) を取得"""
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    l, r, t, b = min(xs), max(xs), min(ys), max(ys)
    w, h = r - l, b - t
    
    # 視覚的ウエイト（太さ）を計算
    weight = calculate_visual_weight(img_cv, box)
    
    # 傾き
    dx = box[1][0] - box[0][0]
    dy = box[1][1] - box[0][1]
    angle = math.degrees(math.atan2(dy, dx))

    return {
        "text": text, "conf": conf, "box": box,
        "left": l, "right": r, "top": t, "bottom": b,
        "width": w, "height": h,
        "center_x": (l + r) / 2, "center_y": (t + b) / 2,
        "angle": angle,
        "weight": weight, # 0.0 ~ 1.0 (文字の太さ)
        "processed": False
    }

def are_semantically_connected(b1, b2):
    """
    2つのブロックが「意味的に同じグループ」か判定する
    判定基準: 幾何学配置 AND (サイズ類似 AND ウエイト類似)
    """
    upper, lower = (b1, b2) if b1["center_y"] < b2["center_y"] else (b2, b1)

    # 1. 傾きチェック
    adiff = abs(b1["angle"] - b2["angle"])
    if adiff > 180: adiff = 360 - adiff
    if adiff > 8: return False

    # 2. 文字サイズ（等級）チェック
    # 見出し(大) と 本文(小) は結合しない
    h_ratio = lower["height"] / max(upper["height"], 1)
    if not (SIZE_SIMILARITY_MIN <= h_ratio <= SIZE_SIMILARITY_MAX):
        return False

    # 3. 文字ウエイト（太さ）チェック
    # 見出し(Bold) と 本文(Regular) は結合しない
    w_diff = abs(upper["weight"] - lower["weight"])
    if w_diff > WEIGHT_DIFF_TOLERANCE:
        return False

    # 4. 垂直距離（行間）チェック
    avg_h = (upper["height"] + lower["height"]) / 2
    dist = lower["top"] - upper["bottom"]
    if dist > (avg_h * LINE_SPACING_LIMIT):
        return False

    # 5. 水平重なり（整列）チェック
    overlap_start = max(upper["left"], lower["left"])
    overlap_end = min(upper["right"], lower["right"])
    overlap = overlap_end - overlap_start
    
    min_w = min(upper["width"], lower["width"])
    if overlap / max(min_w, 1) < HORIZONTAL_OVERLAP_LIMIT:
        return False

    return True

def infer_and_cluster(ocr_engine, img_cv):
    """OCR実行 -> 視覚的推論 -> クラスタリング"""
    
    # 1. 前処理
    img_proc = preprocess_image_advanced(img_cv)
    res = ocr_engine.ocr(img_proc, cls=True)
    if res is None or res[0] is None: return ""
    
    dt_boxes = [l[0] for l in res[0]]
    rec_res = [l[1] for l in res[0]]

    # 2. 特徴量抽出
    items = []
    for i, box in enumerate(dt_boxes):
        txt, cnf = rec_res[i]
        # 閾値判定
        thresh = 0.5
        if RESCUE_KEYWORDS.search(txt): thresh = 0.4
        if cnf < thresh: continue
        
        # ★ここで太さ(Weight)などを計算
        items.append(get_enhanced_metrics(img_cv, box, txt, cnf))

    # 3. グラフベースのクラスタリング (連結成分探索)
    # 全ペア総当たりで「接続」を判定
    n = len(items)
    adj = [[] for _ in range(n)]
    
    for i in range(n):
        for j in range(i + 1, n):
            if are_semantically_connected(items[i], items[j]):
                adj[i].append(j)
                adj[j].append(i)
    
    # グループ化
    clusters = []
    visited = [False] * n
    for i in range(n):
        if not visited[i]:
            group = []
            stack = [i]
            visited[i] = True
            while stack:
                curr = stack.pop()
                group.append(items[curr])
                for neighbor in adj[curr]:
                    if not visited[neighbor]:
                        visited[neighbor] = True
                        stack.append(neighbor)
            clusters.append(group)

    # 4. テキスト生成 & 整列
    final_texts = []
    # クラスタの代表座標（最上部）でソート
    clusters.sort(key=lambda c: min([x["top"] for x in c]))
    
    for group in clusters:
        # グループ内は上から順にソート
        group.sort(key=lambda x: x["top"])
        
        # デバッグ用情報（必要ならコメントアウト解除）
        # avg_w = sum([x["weight"] for x in group]) / len(group)
        # txt_block = f"[Weight: {avg_w:.2f}]\n" + "\n".join([x["text"] for x in group])
        
        txt_block = "\n".join([x["text"] for x in group])
        final_texts.append(txt_block)

    return "\n\n".join(final_texts)

# ==========================================
# メイン処理
# ==========================================

def main():
    print("[INFO] Starting Visual Inference OCR (Size/Weight Analysis)...")
    
    # CPUモード
    ocr = PaddleOCR(use_angle_cls=True, lang='japan', use_gpu=False)

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    pdf_path = data_dir / "sample.pdf"
    txt_path = data_dir / "sample_plain_paddle.txt"

    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)
    all_pages = []

    for i, page in enumerate(doc):
        print(f"[INFO] Processing Page {i + 1}/{len(doc)} ...")
        
        # 解像度4倍
        zoom = 4.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_np = np.frombuffer(pix.tobytes("png"), dtype=np.uint8)
        img_cv = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        h, w, _ = img_cv.shape
        
        page_text = ""
        if i == 0: # Page 1 Split Logic
            print("   -> Split Layout Processing")
            mid = h // 2
            overlap = 100
            top = cv2.rotate(img_cv[0:mid+overlap, :], cv2.ROTATE_180)
            btm = img_cv[mid-overlap:h, :]
            
            t1 = infer_and_cluster(ocr, top)
            t2 = infer_and_cluster(ocr, btm)
            page_text = f"--- [TOP HALF] ---\n{t1}\n\n--- [BOTTOM HALF] ---\n{t2}"
        else:
            page_text = infer_and_cluster(ocr, img_cv)
            
        all_pages.append(f"===== PAGE {i+1} =====")
        all_pages.append(page_text)
        all_pages.append("")

    doc.close()
    txt_path.write_text("\n".join(all_pages), encoding="utf-8")
    print(f"[INFO] Done. Saved to {txt_path}")
    print("\n===== PREVIEW =====")
    print("\n".join(all_pages)[:1000])

if __name__ == "__main__":
    main()
