"""
PDF高解像度ローダー
PDFを高品質な画像に変換し、OCRに最適化する
"""

from typing import List, Tuple
from PIL import Image
import fitz  # PyMuPDF
from pathlib import Path
import io


class PDFLoader:
    """
    PDFを高解像度画像に変換するクラス
    
    PyMuPDFを使用し、既存ツールで使われていた
    pdf2imageよりも高速かつ高品質な変換を実現
    """
    
    def __init__(self, dpi: int = 300, zoom: float = None):
        """
        Args:
            dpi: 解像度（デフォルト: 300）
            zoom: ズーム倍率（dpiの代わりに指定可能）
                  None の場合、dpiから自動計算
        """
        self.dpi = dpi
        if zoom is None:
            # DPI 72 が基準なので、zoom = dpi / 72
            self.zoom = dpi / 72.0
        else:
            self.zoom = zoom
    
    def load(self, pdf_path: str, page_numbers: List[int] = None) -> List[Image.Image]:
        """
        PDFを画像リストに変換
        
        Args:
            pdf_path: PDFファイルパス
            page_numbers: 変換するページ番号リスト（1-indexed）
                         None の場合は全ページ
        
        Returns:
            PIL.Image オブジェクトのリスト
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDFが見つかりません: {pdf_path}")
        
        if pdf_path.suffix.lower() != '.pdf':
            raise ValueError(f"PDFファイルではありません: {pdf_path}")
        
        images = []
        
        try:
            # PyMuPDFでPDFを開く
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            
            # ページ番号の処理
            if page_numbers is None:
                page_numbers = list(range(1, total_pages + 1))
            
            print(f"📄 PDF読み込み: {pdf_path.name}")
            print(f"   総ページ数: {total_pages}")
            print(f"   解像度: {self.dpi} DPI (zoom: {self.zoom:.2f}x)")
            
            # 各ページを画像化
            for page_num in page_numbers:
                if page_num < 1 or page_num > total_pages:
                    print(f"⚠️  ページ {page_num} はスキップされました（範囲外）")
                    continue
                
                # ページ取得（0-indexed）
                page = doc[page_num - 1]
                
                # 変換行列（ズーム倍率）
                mat = fitz.Matrix(self.zoom, self.zoom)
                
                # ピクスマップ取得（RGB）
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # PIL Image に変換
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                images.append(img)
                
                print(f"   ✅ ページ {page_num}: {img.size[0]}x{img.size[1]}px")
            
            doc.close()
            print(f"✅ 完了: {len(images)} ページを変換しました")
            
        except Exception as e:
            raise RuntimeError(f"PDF読み込みエラー: {e}")
        
        return images
    
    def load_single_page(self, pdf_path: str, page_number: int = 1) -> Image.Image:
        """
        PDFの特定ページを1枚だけ読み込む
        
        Args:
            pdf_path: PDFファイルパス
            page_number: ページ番号（1-indexed）
        
        Returns:
            PIL.Image オブジェクト
        """
        images = self.load(pdf_path, [page_number])
        if not images:
            raise ValueError(f"ページ {page_number} の読み込みに失敗しました")
        return images[0]
    
    def get_page_count(self, pdf_path: str) -> int:
        """
        PDFの総ページ数を取得
        
        Args:
            pdf_path: PDFファイルパス
        
        Returns:
            総ページ数
        """
        try:
            doc = fitz.open(str(pdf_path))
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            raise RuntimeError(f"PDF情報取得エラー: {e}")
    
    def get_page_info(self, pdf_path: str, page_number: int = 1) -> dict:
        """
        PDFページの詳細情報を取得
        
        Args:
            pdf_path: PDFファイルパス
            page_number: ページ番号（1-indexed）
        
        Returns:
            {
                "page_number": int,
                "width": float (pt),
                "height": float (pt),
                "rotation": int (degrees),
                "image_width": int (px),
                "image_height": int (px)
            }
        """
        try:
            doc = fitz.open(str(pdf_path))
            
            if page_number < 1 or page_number > len(doc):
                raise ValueError(f"ページ番号が範囲外です: {page_number}")
            
            page = doc[page_number - 1]
            rect = page.rect
            
            info = {
                "page_number": page_number,
                "width": rect.width,
                "height": rect.height,
                "rotation": page.rotation,
                "image_width": int(rect.width * self.zoom),
                "image_height": int(rect.height * self.zoom)
            }
            
            doc.close()
            return info
            
        except Exception as e:
            raise RuntimeError(f"ページ情報取得エラー: {e}")


class ImageOptimizer:
    """
    OCR精度向上のための画像最適化
    既存ツールのpreprocessor.pyの機能を取り込み
    """
    
    @staticmethod
    def optimize_for_ocr(image: Image.Image, upscale: bool = True) -> Image.Image:
        """
        OCR用に画像を最適化
        
        Args:
            image: 入力画像
            upscale: 小さい画像を拡大するか
        
        Returns:
            最適化された画像
        """
        import cv2
        import numpy as np
        
        # PIL -> OpenCV
        img_np = np.array(image)
        
        if img_np.ndim == 3:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 拡大（Tesseractは文字高さ30px以上を好む）
        height, width = img_np.shape[:2]
        if upscale and (height < 2000 or width < 2000):
            img_np = cv2.resize(img_np, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)
        
        # グレースケール化
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY) if img_np.ndim == 3 else img_np
        
        # ノイズ除去
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # ガンマ補正（薄い文字を濃くする）
        gamma = 0.5
        look_up_table = np.array([
            ((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)
        ]).astype("uint8")
        gamma_corrected = cv2.LUT(denoised, look_up_table)
        
        # 二値化（大津の二値化）
        _, binary = cv2.threshold(
            gamma_corrected, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        
        # OpenCV -> PIL
        return Image.fromarray(binary)
    
    @staticmethod
    def resize_if_needed(image: Image.Image, max_size: Tuple[int, int] = (4000, 4000)) -> Image.Image:
        """
        画像が大きすぎる場合にリサイズ
        
        Args:
            image: 入力画像
            max_size: 最大サイズ (width, height)
        
        Returns:
            リサイズされた画像（必要な場合）
        """
        width, height = image.size
        max_width, max_height = max_size
        
        if width <= max_width and height <= max_height:
            return image
        
        # アスペクト比を維持してリサイズ
        ratio = min(max_width / width, max_height / height)
        new_size = (int(width * ratio), int(height * ratio))
        
        return image.resize(new_size, Image.Resampling.LANCZOS)

