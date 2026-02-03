# src/pdf_ingest.py
print("<<< HELLO_FROM_PDF_INGEST_v2_OCR_ENABLED >>>")

from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF
import pandas as pd
import pytesseract
from PIL import Image
import numpy as np


def extract_blocks_with_pymupdf(pdf_path: Path) -> List[Dict[str, Any]]:
    """通常のテキストPDF用：PyMuPDFのテキストブロック抽出"""
    blocks: List[Dict[str, Any]] = []

    doc = fitz.open(pdf_path)
    for page_idx, page in enumerate(doc):
        for b in page.get_text("blocks"):
            if len(b) < 5:
                continue
            x0, y0, x1, y1, text = b[:5]
            text = (text or "").strip()
            if not text:
                continue
            blocks.append(
                {
                    "page": page_idx + 1,
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "text": text,
                }
            )
    doc.close()
    return blocks


def extract_blocks_with_ocr(pdf_path: Path) -> List[Dict[str, Any]]:
    """スキャンPDF用：ページ画像を Tesseract OCR で解析"""
    blocks: List[Dict[str, Any]] = []

    doc = fitz.open(pdf_path)
    for page_idx, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_np = np.array(img)

        data = pytesseract.image_to_data(
            img_np,
            lang="jpn+eng",
            output_type=pytesseract.Output.DICT,
        )

        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = (data["text"][i] or "").strip()
            conf_str = data.get("conf", ["-1"] * n_boxes)[i]
            try:
                conf = float(conf_str)
            except ValueError:
                conf = -1.0

            if not text:
                continue
            if conf < 40:  # 認識精度が低いものは捨てる
                continue

            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]

            blocks.append(
                {
                    "page": page_idx + 1,
                    "x0": float(x),
                    "y0": float(y),
                    "x1": float(x + w),
                    "y1": float(y + h),
                    "text": text,
                }
            )

    doc.close()
    return blocks


def extract_to_blocks(pdf_path: Path) -> pd.DataFrame:
    """
    1. まず PyMuPDF でテキスト抽出
    2. それで 0ブロックなら OCR(Tesseract) にフォールバック
    """
    print(f"[DEBUG] extract_to_blocks: {pdf_path}")

    blocks = extract_blocks_with_pymupdf(pdf_path)
    print(f"[DEBUG] PyMuPDF blocks: {len(blocks)}")

    if not blocks:
        print("[WARN] PyMuPDF でテキストブロックが見つかりません。OCR に切り替えます。")
        blocks = extract_blocks_with_ocr(pdf_path)
        print(f"[DEBUG] OCR blocks: {len(blocks)}")

    if not blocks:
        print("[ERROR] OCR でもテキストが抽出できませんでした。PDF 内容を確認してください。")
        return pd.DataFrame(columns=["page", "x0", "y0", "x1", "y1", "text"])

    df = (
        pd.DataFrame(blocks)
        .sort_values(["page", "y0", "x0"])
        .reset_index(drop=True)
    )
    print(f"[INFO] 抽出ブロック数: {len(df)}")
    return df


def main():
    base_dir = Path(__file__).resolve().parent.parent
    print(f"[DEBUG] 実行中ディレクトリ: {base_dir}")

    pdf_path = base_dir / "data" / "sample.pdf"
    out_csv = base_dir / "data" / "sample_blocks.csv"

    print(f"[DEBUG] 入力PDF: {pdf_path}")
    print(f"[DEBUG] 出力CSV: {out_csv}")

    if not pdf_path.exists():
        print(f"[ERROR] PDF が見つかりません: {pdf_path}")
        return

    df = extract_to_blocks(pdf_path)

    if df.empty:
        print("[WARN] データフレームが空です。PDFかパス、OCR設定を確認してください。")
        return

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"[INFO] CSV に書き出しました: {out_csv}")


if __name__ == "__main__":
    main()
