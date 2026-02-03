# src/plain_text_extractor_paddle.py
"""
【決定版】広告校正システム用 OCR（PaddleOCR採用）
- Tesseract(ルールベース)から DeepLearningベースへ変更
- 物体検出技術により、散らばった文字・逆さ文字・袋文字を正確に捕捉
- 広告特有の「デザインレイアウト」を崩さずにテキスト化
"""
# src/plain_text_extractor_paddle.py の main関数内

import paddle # 追加

def main():
    # ==========================================
    # 0. GPUチェック
    # ==========================================
    paddle.utils.run_check() # インストール成功判定
    gpu_available = paddle.device.is_compiled_with_cuda()
    print(f"[INFO] GPU Available: {gpu_available}")
    
    if gpu_available:
        print(f"[INFO] Using GPU: {paddle.device.get_device()}")
    else:
        print("[WARN] GPU not found. Using CPU (Slow).")

    # ==========================================
    # 1. 初期化
    # ==========================================
    print("[INFO] Initializing PaddleOCR...")
    
    # use_gpu=True を明示的に指定
    ocr = PaddleOCR(
        use_angle_cls=True, 
        lang='japan', 
        use_gpu=gpu_available,  # GPUがあればTrue
        show_log=False
    )

    # ... (以下、前回と同じコード) ...
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import cv2
from paddleocr import PaddleOCR
import logging

# PaddleOCRのログを抑制（うるさいので）
logging.getLogger("ppocr").setLevel(logging.WARNING)

def main():
    # ==========================================
    # 1. 初期化 (初回のみモデルDLが走ります)
    # ==========================================
    print("[INFO] Initializing PaddleOCR (Deep Learning Model)...")
    
    # use_angle_cls=True : 文字の回転（逆さまなど）を自動補正する
    # lang='japan'       : 日本語モデル
    ocr = PaddleOCR(use_angle_cls=True, lang='japan', show_log=False)

    # ==========================================
    # 2. パス設定
    # ==========================================
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    pdf_path = data_dir / "sample.pdf"
    txt_path = data_dir / "sample_plain_paddle.txt"

    print(f"[DEBUG] Reading: {pdf_path}")
    if not pdf_path.exists():
        print("[ERROR] PDF not found.")
        return

    # ==========================================
    # 3. PDF読み込み & OCR実行
    # ==========================================
    doc = fitz.open(pdf_path)
    all_text_results = []

    for i, page in enumerate(doc):
        print(f"[INFO] Processing Page {i + 1}/{len(doc)} ...")

        # 高解像度で画像化 (Zoom x3 程度で十分精度が出ます)
        zoom = 3.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # PyMuPDF -> numpy array (OpenCV形式) に変換
        # PaddleOCRはファイルパスかnumpy配列を受け取れます
        img_data = pix.tobytes("png")
        img_np = np.frombuffer(img_data, dtype=np.uint8)
        img_cv = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

        # --- PaddleOCR 実行 ---
        # result = [ [ [[x,y],...], (text, score) ], ... ]
        result = ocr.ocr(img_cv, cls=True)

        # 結果がNoneの場合のガード
        if result is None or result[0] is None:
            all_text_results.append(f"===== PAGE {i+1} (No Text Found) =====")
            continue

        # --- 結果の整形 ---
        # PaddleOCRは「検出された順」にリストで返ってきますが、
        # 広告の場合、座標(Y軸)順に並べ替えたほうが人間にとって自然です。
        
        # result[0] に各行のリストが入っている
        lines = result[0]
        
        # Y座標(左上のy)でソート
        # line[0][0][1] -> バウンディングボックスの左上のY座標
        lines.sort(key=lambda x: x[0][0][1])

        page_text = []
        for line in lines:
            text_body = line[1][0] # テキスト本体
            confidence = line[1][1] # 確信度 (0.0 ~ 1.0)

            # 確信度が低すぎるゴミ（0.5未満など）は捨てる
            if confidence < 0.6:
                continue

            page_text.append(text_body)

        # ページ結合
        joined_text = "\n".join(page_text)
        all_text_results.append(f"===== PAGE {i + 1} =====")
        all_text_results.append(joined_text)
        all_text_results.append("")

    doc.close()

    # ==========================================
    # 4. 書き出し
    # ==========================================
    final_output = "\n".join(all_text_results)
    txt_path.write_text(final_output, encoding="utf-8")

    print(f"[INFO] OCR Complete! Saved to: {txt_path}")
    print("\n===== PREVIEW (PaddleOCR Result) =====")
    print(final_output[:1000])
    print("======================================")

if __name__ == "__main__":
    main()