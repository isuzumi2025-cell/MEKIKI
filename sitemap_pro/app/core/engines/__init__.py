"""
Engines Package
テキスト抽出・OCR・DOMハンドリングの統合エンジン

Contains:
- ocr_engine.py: Google Cloud Vision API OCR
- dom_handler.py: Playwright DOM/XPath extraction
- capture.py: Playwright screenshot capture
"""
from .ocr_engine import OCREngine
from .dom_handler import DomXPathHandler, quick_xpath_search, quick_get_dom
from .capture import PlaywrightCapture, quick_capture

__all__ = [
    'OCREngine',
    'DomXPathHandler',
    'PlaywrightCapture',
    'quick_xpath_search',
    'quick_get_dom',
    'quick_capture'
]
