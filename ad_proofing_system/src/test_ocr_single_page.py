# src/test_ocr_single_page.py
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from pathlib import Path


def extract_text_mixed(pdf_path: Path, page_num: int = 0) -> str:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)

    # まず PyMuPDF の通常テキスト抽出を試す
    text = page.get_text()

    if text and text.strip():
        print("[INFO] PyMuPDF でテキスト抽出成功")
        return text

    print("[WARN] PyMuPDF は文字を検出できません。OCR に切り替えます。")

    # ページを画像化 → OCR
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))

    ocr_text = pytesseract.image_to_string(img, lang="jpn+eng")
    return ocr_text


def main():
    base_dir = Path(__file__).resolve().parent.parent
    pdf_path = base_dir / "data" / "sample.pdf"

    if not pdf_path.exists():
        print("[ERROR] sample.pdf が data フォルダにありません")
        return

    print(f"[DEBUG] PDF: {pdf_path}")

    text = extract_text_mixed(pdf_path, page_num=0)

    print("\n===== OCR RESULT =====")
    print(text)


if __name__ == "__main__":
    main()
