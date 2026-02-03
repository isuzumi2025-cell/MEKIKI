"""
統合テキスト抽出モジュール
Web DOM, PDF OCR, 画像OCRからテキストを抽出

統合元:
- Scraper/dom_xpath_handler.py: DOM/XPath テキスト抽出
- OCR/app/core/ocr_engine.py: Google Vision OCR
"""
import os
import io
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

# Scraperモジュールへのパス追加
SCRAPER_PATH = Path(__file__).parent.parent.parent.parent / "Scraper"
OCR_PATH = Path(__file__).parent.parent.parent.parent / "OCR"
if str(SCRAPER_PATH) not in sys.path:
    sys.path.insert(0, str(SCRAPER_PATH))
if str(OCR_PATH) not in sys.path:
    sys.path.insert(0, str(OCR_PATH))


class TextExtractor:
    """
    統合テキスト抽出エンジン
    
    Features:
    - Web DOM テキスト抽出 (Playwright + XPath)
    - PDF テキスト抽出 (PyMuPDF + OCR)
    - 画像 OCR (Google Cloud Vision API)
    - パラグラフ自動検出 + bbox
    - 領域指定テキスト抽出
    """
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Args:
            credentials_path: Google Cloud認証情報のパス
        """
        self.credentials_path = credentials_path or str(
            OCR_PATH / "service_account.json"
        )
        self._ocr_engine = None
        self._dom_handler = None
        
    # =========================================================================
    # Web DOM テキスト抽出
    # =========================================================================
    
    def extract_from_web(
        self,
        url: str,
        mode: str = "text",
        xpath: Optional[str] = None,
        wait_time: int = 2000
    ) -> Dict[str, Any]:
        """
        Web URLからテキストを抽出
        
        Args:
            url: 対象URL
            mode: "text" (プレーンテキスト), "html" (HTML), "structure" (DOM構造)
            xpath: XPath式（特定要素を抽出する場合）
            wait_time: 読み込み待機時間(ミリ秒)
            
        Returns:
            {
                "source": "web",
                "url": str,
                "full_text": str,
                "blocks": [{"text": str, "bbox": [x0,y0,x1,y1], "type": str}, ...]
            }
        """
        try:
            from dom_xpath_handler import DomXPathHandler
        except ImportError:
            # フォールバック: Playwright直接使用
            return self._extract_web_fallback(url, mode, xpath, wait_time)
        
        result = {
            "source": "web",
            "url": url,
            "full_text": "",
            "blocks": [],
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        with DomXPathHandler(headless=True) as handler:
            if xpath:
                # XPath指定で特定要素を抽出
                elements = handler.find_elements_by_xpath(url, xpath, wait_time)
                for i, elem in enumerate(elements):
                    result["blocks"].append({
                        "text": elem.get("text", ""),
                        "html": elem.get("html", ""),
                        "tag": elem.get("tag", ""),
                        "type": "XPATH_MATCH",
                        "area_id": i + 1
                    })
                result["full_text"] = "\n\n".join([b["text"] for b in result["blocks"]])
            
            elif mode == "structure":
                # DOM構造を抽出
                structure = handler.extract_dom_structure(url, wait_time)
                result["structure"] = structure
                result["full_text"] = self._extract_text_from_structure(structure)
                
            else:
                # 全体テキスト抽出
                output_format = "text" if mode == "text" else "html"
                content = handler.get_page_dom(url, wait_time, output_format=output_format)
                result["full_text"] = content
                
                # パラグラフ抽出
                paragraphs = handler.find_elements_by_xpath(url, "//p | //h1 | //h2 | //h3 | //h4 | //li | //td | //th", wait_time)
                for i, elem in enumerate(paragraphs):
                    text = elem.get("text", "").strip()
                    if text:
                        result["blocks"].append({
                            "text": text,
                            "tag": elem.get("tag", ""),
                            "type": "PARAGRAPH",
                            "area_id": i + 1
                        })
        
        return result
    
    def _extract_web_fallback(self, url: str, mode: str, xpath: str, wait_time: int) -> Dict:
        """Playwrightを直接使用するフォールバック"""
        from playwright.sync_api import sync_playwright
        
        result = {
            "source": "web",
            "url": url,
            "full_text": "",
            "blocks": [],
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_time)
            
            if mode == "text":
                result["full_text"] = page.inner_text("body")
            else:
                result["full_text"] = page.content()
            
            browser.close()
        
        return result
    
    def _extract_text_from_structure(self, structure: Dict) -> str:
        """DOM構造からテキストを再帰的に抽出"""
        texts = []
        
        def extract_recursive(node):
            if isinstance(node, dict):
                if node.get("text"):
                    texts.append(node["text"])
                for child in node.get("children", []):
                    extract_recursive(child)
        
        extract_recursive(structure)
        return "\n".join(texts)
    
    # =========================================================================
    # PDF テキスト抽出
    # =========================================================================
    
    def extract_from_pdf(
        self,
        pdf_path: str,
        pages: Optional[List[int]] = None,
        use_ocr: bool = True
    ) -> Dict[str, Any]:
        """
        PDFからテキストを抽出
        
        Args:
            pdf_path: PDFファイルのパス
            pages: 抽出するページ番号リスト (None=全ページ)
            use_ocr: テキストが少ない場合にOCRを使用するか
            
        Returns:
            {
                "source": "pdf",
                "path": str,
                "pages_count": int,
                "full_text": str,
                "pages": [{
                    "page_num": int,
                    "text": str,
                    "blocks": [{"text": str, "bbox": [x0,y0,x1,y1], "type": str}, ...]
                }, ...]
            }
        """
        result = {
            "source": "pdf",
            "path": pdf_path,
            "pages_count": 0,
            "full_text": "",
            "pages": [],
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("⚠️ PyMuPDF がインストールされていません。pip install PyMuPDF を実行してください。")
            return result
        
        doc = fitz.open(pdf_path)
        result["pages_count"] = len(doc)
        
        page_nums = pages if pages else range(len(doc))
        full_texts = []
        
        for page_num in page_nums:
            if page_num >= len(doc):
                continue
                
            page = doc[page_num]
            page_text = page.get_text()
            
            page_data = {
                "page_num": page_num + 1,
                "text": page_text,
                "blocks": []
            }
            
            # テキストブロックを抽出（bbox付き）
            blocks = page.get_text("dict")["blocks"]
            for i, block in enumerate(blocks):
                if block.get("type") == 0:  # テキストブロック
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"
                    
                    if block_text.strip():
                        bbox = block.get("bbox", [0, 0, 0, 0])
                        page_data["blocks"].append({
                            "text": block_text.strip(),
                            "bbox": [int(b) for b in bbox],
                            "type": "PDF_BLOCK",
                            "area_id": i + 1
                        })
            
            # テキストが少ない場合はOCRにフォールバック
            if use_ocr and len(page_text.strip()) < 50:
                # ページを画像に変換してOCR
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_data)
                    tmp_path = tmp.name
                
                try:
                    ocr_result = self.extract_from_image(tmp_path)
                    if ocr_result and ocr_result.get("full_text"):
                        page_data["text"] = ocr_result["full_text"]
                        page_data["blocks"] = ocr_result.get("blocks", [])
                        page_data["ocr_used"] = True
                finally:
                    os.unlink(tmp_path)
            
            result["pages"].append(page_data)
            full_texts.append(page_data["text"])
        
        doc.close()
        result["full_text"] = "\n\n---\n\n".join(full_texts)
        
        return result
    
    # =========================================================================
    # 画像 OCR テキスト抽出
    # =========================================================================
    
    def extract_from_image(
        self,
        image_path: str,
        granularity: str = "paragraph"
    ) -> Dict[str, Any]:
        """
        画像からOCRでテキストを抽出
        
        Args:
            image_path: 画像ファイルのパス
            granularity: "block", "paragraph", "word"
            
        Returns:
            {
                "source": "ocr",
                "path": str,
                "full_text": str,
                "blocks": [{"text": str, "bbox": [x0,y0,x1,y1], "confidence": float, "type": str}, ...]
            }
        """
        result = {
            "source": "ocr",
            "path": image_path,
            "full_text": "",
            "blocks": [],
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        # OCRエンジンを初期化
        if not self._ocr_engine:
            try:
                sys.path.insert(0, str(OCR_PATH / "app" / "core"))
                from ocr_engine import OCREngine
                self._ocr_engine = OCREngine(self.credentials_path)
            except ImportError as e:
                print(f"⚠️ OCREngine インポートエラー: {e}")
                return result
        
        # OCR実行
        ocr_result = self._ocr_engine.detect_document_text(image_path)
        
        if ocr_result:
            result["full_text"] = ocr_result.get("full_text", "")
            
            for i, block in enumerate(ocr_result.get("blocks", [])):
                result["blocks"].append({
                    "text": block.get("text", ""),
                    "bbox": block.get("bbox", [0, 0, 0, 0]),
                    "confidence": block.get("confidence", 0.0),
                    "type": block.get("type", "PARAGRAPH"),
                    "area_id": i + 1
                })
        
        return result
    
    # =========================================================================
    # 領域指定テキスト抽出
    # =========================================================================
    
    def extract_from_region(
        self,
        image_path: str,
        bbox: List[int]
    ) -> Dict[str, Any]:
        """
        画像の指定領域からテキストを抽出
        
        Args:
            image_path: 画像ファイルのパス
            bbox: [x0, y0, x1, y1] 抽出領域
            
        Returns:
            {
                "source": "region",
                "path": str,
                "bbox": [x0, y0, x1, y1],
                "text": str,
                "confidence": float
            }
        """
        from PIL import Image
        import tempfile
        
        # 画像を読み込み、領域を切り抜き
        img = Image.open(image_path)
        x0, y0, x1, y1 = bbox
        cropped = img.crop((x0, y0, x1, y1))
        
        # 切り抜き画像を一時保存
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cropped.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # OCR実行
            ocr_result = self.extract_from_image(tmp_path)
            
            return {
                "source": "region",
                "path": image_path,
                "bbox": bbox,
                "text": ocr_result.get("full_text", ""),
                "confidence": self._calculate_avg_confidence(ocr_result.get("blocks", [])),
                "extracted_at": datetime.utcnow().isoformat()
            }
        finally:
            os.unlink(tmp_path)
    
    def _calculate_avg_confidence(self, blocks: List[Dict]) -> float:
        """ブロックの平均信頼度を計算"""
        if not blocks:
            return 0.0
        confidences = [b.get("confidence", 0.0) for b in blocks]
        return sum(confidences) / len(confidences)
    
    # =========================================================================
    # ユーティリティ
    # =========================================================================
    
    def capture_screenshot(
        self,
        url: str,
        output_path: str,
        full_page: bool = True,
        wait_time: int = 2000
    ) -> str:
        """
        Webページのスクリーンショットを撮影
        
        Args:
            url: 対象URL
            output_path: 保存先パス
            full_page: 全ページを撮影するか
            wait_time: 待機時間(ミリ秒)
            
        Returns:
            保存されたファイルパス
        """
        from playwright.sync_api import sync_playwright
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_time)
            page.screenshot(path=output_path, full_page=full_page)
            browser.close()
        
        return output_path


# クイックアクセス関数
def quick_extract_web(url: str, **kwargs) -> Dict:
    """WebからテキストをクイックExtraction"""
    extractor = TextExtractor()
    return extractor.extract_from_web(url, **kwargs)


def quick_extract_pdf(pdf_path: str, **kwargs) -> Dict:
    """PDFからテキストをクイックExtraction"""
    extractor = TextExtractor()
    return extractor.extract_from_pdf(pdf_path, **kwargs)


def quick_extract_image(image_path: str, **kwargs) -> Dict:
    """画像からテキストをクイックExtraction"""
    extractor = TextExtractor()
    return extractor.extract_from_image(image_path, **kwargs)
