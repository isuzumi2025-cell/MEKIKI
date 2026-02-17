"""
PDF一括ローダー & グローバルマスク機能
指定フォルダ内の全PDFを再帰的に読み込み、マスクエリアを適用
PyMuPDF (fitz) を使用したテキスト抽出と画像生成
"""
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageDraw
import fitz  # PyMuPDF


class PDFLoader:
    """PDF一括ローダークラス"""
    
    def __init__(self, global_mask: Optional[Dict] = None, dpi: int = 400):
        """
        Args:
            global_mask: グローバルマスク {"x0": int, "y0": int, "x1": int, "y1": int}
            dpi: PDF変換時のDPI
        """
        self.global_mask = global_mask
        self.dpi = dpi
    
    def load_pdfs_from_folder(
        self,
        folder_path: str,
        recursive: bool = True
    ) -> List[Dict]:
        """
        フォルダ内の全PDFを読み込む
        
        Args:
            folder_path: フォルダパス
            recursive: 再帰的に検索するか
        
        Returns:
            [{"filename": str, "page_num": int, "text": str, "image_path": str}, ...]
        """
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"フォルダが見つかりません: {folder_path}")
        
        # PDFファイルを検索
        if recursive:
            pdf_files = list(folder.rglob("*.pdf"))
        else:
            pdf_files = list(folder.glob("*.pdf"))
        
        results = []
        
        for pdf_file in pdf_files:
            try:
                pages = self._load_pdf_with_mask(str(pdf_file))
                for page_num, (image, text, areas) in enumerate(pages, start=1):
                    results.append({
                        "filename": str(pdf_file),
                        "page_num": page_num,
                        "text": text,
                        "image_path": None,  # 必要に応じて保存パスを設定
                        "areas": areas,  # bbox付きテキスト領域
                        "page_image": image  # PIL Image
                    })
            except Exception as e:
                print(f"⚠️ PDF読み込みエラー: {pdf_file} - {str(e)}")
                continue
        
        return results
    
    def _load_pdf_with_mask(self, pdf_path: str) -> List[Tuple[Image.Image, str, List[Dict]]]:
        """
        PDFを読み込み、マスクを適用してテキストを抽出
        PyMuPDFを使用してテキスト抽出と画像生成を行う
        
        Returns:
            [(PIL.Image, text, areas), ...]
            areas: [{"text": str, "bbox": [x0, y0, x1, y1]}, ...]
        """
        results = []
        
        try:
            # PyMuPDFでPDFを開く
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # スケールファクターを計算（DPIから）
                scale = self.dpi / 72.0
                
                # テキストブロックを抽出（bbox付き）
                areas = []
                area_id_counter = 1
                try:
                    # get_text("dict")でブロック情報を取得
                    text_dict = page.get_text("dict")
                    blocks = text_dict.get("blocks", [])
                    
                    full_text_parts = []
                    
                    for block in blocks:
                        if block.get("type") == 0:  # テキストブロック
                            block_text = ""
                            bbox = block.get("bbox", [0, 0, 0, 0])
                            
                            # ブロック内の行を結合
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    block_text += span.get("text", "")
                                block_text += "\n"
                            
                            block_text = block_text.strip()
                            if block_text:
                                # 座標をスケーリング
                                scaled_bbox = [
                                    bbox[0] * scale,
                                    bbox[1] * scale,
                                    bbox[2] * scale,
                                    bbox[3] * scale
                                ]
                                areas.append({
                                    "text": block_text,
                                    "bbox": scaled_bbox,
                                    "area_id": area_id_counter
                                })
                                area_id_counter += 1
                                full_text_parts.append(block_text)
                    
                    text = "\n".join(full_text_parts).strip()
                    
                    # テキストが空の場合（スキャンデータ等）、空文字を返す
                    if not text:
                        text = ""
                        print(f"⚠️ PDFテキスト抽出不可: {pdf_path} (ページ {page_num + 1}) - スキャンデータの可能性があります")
                except Exception as e:
                    # エラー時も空文字を返す
                    text = ""
                    areas = []
                    print(f"⚠️ テキスト抽出エラー: {str(e)}")
                
                # ページを画像に変換（プレビュー用）
                try:
                    mat = fitz.Matrix(scale, scale)
                    pix = page.get_pixmap(matrix=mat)
                    
                    # PIL Imageに変換
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # マスクを適用
                    if self.global_mask:
                        masked_img = self._apply_mask(img, self.global_mask)
                    else:
                        masked_img = img
                    
                    results.append((masked_img, text, areas))
                    
                except Exception as e:
                    print(f"⚠️ 画像変換エラー: {str(e)}")
                    # 画像変換に失敗した場合、空の画像とテキストを返す
                    empty_img = Image.new("RGB", (800, 600), color="white")
                    results.append((empty_img, text, areas))
            
            doc.close()
            
        except Exception as e:
            raise RuntimeError(f"PDF読み込みエラー: {str(e)}")
        
        return results
    
    def _apply_mask(self, image: Image.Image, mask: Dict) -> Image.Image:
        """
        画像にマスク（除外矩形）を適用
        マスクエリアの文字を白で塗りつぶす
        """
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        
        x0 = mask.get("x0", 0)
        y0 = mask.get("y0", 0)
        x1 = mask.get("x1", img_copy.width)
        y1 = mask.get("y1", img_copy.height)
        
        # マスクエリアを白で塗りつぶし
        draw.rectangle([x0, y0, x1, y1], fill="white")
        
        return img_copy
    
    def set_global_mask(self, x0: int, y0: int, x1: int, y1: int):
        """グローバルマスクを設定"""
        self.global_mask = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    
    def clear_global_mask(self):
        """グローバルマスクをクリア"""
        self.global_mask = None

