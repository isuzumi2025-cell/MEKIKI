"""
マクロビュー
Web vs PDF の全体比較ビュー
サイドバイサイドでの表示と差分ハイライト
"""

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
from typing import List, Dict, Optional, Callable


class MacroView:
    """
    Web画像とPDF画像を並べて表示し、
    比較結果をビジュアルに確認できるビュー
    
    機能:
    - サイドバイサイド表示
    - 差分エリアのハイライト
    - エリア選択による詳細表示
    - スクロール同期
    """
    
    def __init__(
        self,
        parent,
        on_area_click: Optional[Callable] = None
    ):
        """
        Args:
            parent: 親ウィジェット
            on_area_click: エリアクリック時のコールバック(area_id)
        """
        self.parent = parent
        self.on_area_click = on_area_click
        
        # データ
        self.web_image = None
        self.pdf_image = None
        self.web_clusters = []
        self.pdf_clusters = []
        self.comparison_results = []
        
        # 表示制御
        self.display_scale = 0.5
        self.show_matched = True
        self.show_mismatched = True
        self.show_web_only = True
        self.show_pdf_only = True
        
        # UI構築
        self._build_ui()
    
    def _build_ui(self):
        """UIの構築"""
        # メインコンテナ
        self.container = ctk.CTkFrame(self.parent)
        self.container.pack(fill="both", expand=True)
        
        # ツールバー
        self._build_toolbar()
        
        # コンテンツエリア（左右分割）
        self.content = tk.PanedWindow(
            self.container,
            orient="horizontal",
            bg="#2B2B2B",
            sashwidth=4
        )
        self.content.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 左側: Web画像
        self.web_frame = self._create_image_panel("🌐 Web", "left")
        self.content.add(self.web_frame, width=600)
        
        # 右側: PDF画像
        self.pdf_frame = self._create_image_panel("📄 PDF", "right")
        self.content.add(self.pdf_frame, width=600)
    
    def _build_toolbar(self):
        """ツールバーの構築"""
        toolbar = ctk.CTkFrame(self.container, height=50, corner_radius=0)
        toolbar.pack(side="top", fill="x", padx=5, pady=5)
        
        # タイトル
        ctk.CTkLabel(
            toolbar,
            text="📊 全体比較ビュー",
            font=("Arial", 14, "bold")
        ).pack(side="left", padx=10)
        
        # セパレータ
        ctk.CTkLabel(toolbar, text="|", text_color="gray").pack(side="left", padx=5)
        
        # フィルター
        ctk.CTkLabel(toolbar, text="表示:").pack(side="left", padx=5)
        
        self.check_matched = ctk.CTkCheckBox(
            toolbar,
            text="✅ 一致",
            command=self._on_filter_change
        )
        self.check_matched.select()
        self.check_matched.pack(side="left", padx=5)
        
        self.check_mismatched = ctk.CTkCheckBox(
            toolbar,
            text="⚠️ 不一致",
            command=self._on_filter_change
        )
        self.check_mismatched.select()
        self.check_mismatched.pack(side="left", padx=5)
        
        self.check_web_only = ctk.CTkCheckBox(
            toolbar,
            text="🌐 Web専用",
            command=self._on_filter_change
        )
        self.check_web_only.select()
        self.check_web_only.pack(side="left", padx=5)
        
        self.check_pdf_only = ctk.CTkCheckBox(
            toolbar,
            text="📄 PDF専用",
            command=self._on_filter_change
        )
        self.check_pdf_only.select()
        self.check_pdf_only.pack(side="left", padx=5)
        
        # ズーム
        ctk.CTkLabel(toolbar, text="|", text_color="gray").pack(side="left", padx=10)
        ctk.CTkLabel(toolbar, text="Zoom:").pack(side="left", padx=5)
        
        self.zoom_slider = ctk.CTkSlider(
            toolbar,
            from_=0.2,
            to=1.5,
            command=self._on_zoom_change,
            width=150
        )
        self.zoom_slider.set(0.5)
        self.zoom_slider.pack(side="left", padx=5)
        
        self.zoom_label = ctk.CTkLabel(toolbar, text="50%", width=50)
        self.zoom_label.pack(side="left")
    
    def _create_image_panel(self, title: str, side: str):
        """画像パネルの作成"""
        frame = ctk.CTkFrame(self.content)
        
        # ヘッダー
        header = ctk.CTkLabel(
            frame,
            text=title,
            font=("Arial", 12, "bold"),
            anchor="w"
        )
        header.pack(fill="x", padx=5, pady=5)
        
        # Canvas コンテナ
        canvas_container = tk.Frame(frame, bg="#202020")
        canvas_container.pack(fill="both", expand=True)
        
        # スクロールバー
        v_scroll = tk.Scrollbar(canvas_container, orient="vertical")
        h_scroll = tk.Scrollbar(canvas_container, orient="horizontal")
        
        # Canvas
        canvas = tk.Canvas(
            canvas_container,
            bg="#202020",
            highlightthickness=0,
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set
        )
        
        v_scroll.config(command=canvas.yview)
        h_scroll.config(command=canvas.xview)
        
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        
        # イベント
        canvas.bind("<Button-1>", lambda e: self._on_canvas_click(e, side))
        
        # 保存
        if side == "left":
            self.web_canvas = canvas
        else:
            self.pdf_canvas = canvas
        
        return frame
    
    def load_data(
        self,
        web_image: Image.Image,
        pdf_image: Image.Image,
        web_clusters: List[Dict],
        pdf_clusters: List[Dict],
        comparison_results: List[Dict]
    ):
        """
        比較データをロード
        
        Args:
            web_image: Web画像
            pdf_image: PDF画像
            web_clusters: Webクラスタ
            pdf_clusters: PDFクラスタ
            comparison_results: 比較結果
        """
        self.web_image = web_image
        self.pdf_image = pdf_image
        self.web_clusters = web_clusters
        self.pdf_clusters = pdf_clusters
        self.comparison_results = comparison_results
        
        self.redraw()
    
    def redraw(self):
        """全体を再描画"""
        if not self.web_image or not self.pdf_image:
            return
        
        # Web側の描画
        self._draw_side(
            self.web_canvas,
            self.web_image,
            self.web_clusters,
            "web"
        )
        
        # PDF側の描画
        self._draw_side(
            self.pdf_canvas,
            self.pdf_image,
            self.pdf_clusters,
            "pdf"
        )
    
    def _draw_side(
        self,
        canvas: tk.Canvas,
        image: Image.Image,
        clusters: List[Dict],
        side: str
    ):
        """片側の描画"""
        canvas.delete("all")
        
        # 画像のリサイズ
        img_w, img_h = image.size
        display_w = int(img_w * self.display_scale)
        display_h = int(img_h * self.display_scale)
        
        resized_image = image.resize(
            (display_w, display_h),
            Image.Resampling.LANCZOS
        )
        
        # クラスタ枠を描画した画像を作成
        annotated_image = self._annotate_image(
            resized_image.copy(),
            clusters,
            side
        )
        
        # Canvas に表示
        tk_img = ImageTk.PhotoImage(annotated_image)
        
        # 参照を保持（ガベージコレクション防止）
        if side == "web":
            self.web_tk_img = tk_img
        else:
            self.pdf_tk_img = tk_img
        
        canvas.config(scrollregion=(0, 0, display_w, display_h))
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
    
    def _annotate_image(
        self,
        image: Image.Image,
        clusters: List[Dict],
        side: str
    ) -> Image.Image:
        """
        画像にクラスタ枠を描画
        
        Args:
            image: ベース画像
            clusters: クラスタリスト
            side: "web" or "pdf"
        
        Returns:
            アノテーション付き画像
        """
        draw = ImageDraw.Draw(image, 'RGBA')
        
        for cluster in clusters:
            area_id = cluster.get('id')
            rect = cluster.get('rect', [0, 0, 0, 0])
            
            # スケール適用
            x0, y0, x1, y1 = [int(v * self.display_scale) for v in rect]
            
            # 比較結果から色を決定
            status = self._get_status_for_area(area_id, side)
            
            # フィルタチェック
            if not self._should_show(status):
                continue
            
            color, fill_alpha = self._get_color_for_status(status)
            
            # 塗りつぶし（半透明）
            fill_color = color + (fill_alpha,)
            draw.rectangle([x0, y0, x1, y1], fill=fill_color, outline=None)
            
            # 枠線
            draw.rectangle([x0, y0, x1, y1], outline=color, width=2)
            
            # ラベル
            label = f"Area {area_id}"
            label_bbox = draw.textbbox((x0, y0), label)
            label_w = label_bbox[2] - label_bbox[0] + 10
            label_h = label_bbox[3] - label_bbox[1] + 5
            
            draw.rectangle(
                [x0, y0 - label_h - 2, x0 + label_w, y0],
                fill=color
            )
            draw.text((x0 + 5, y0 - label_h), label, fill="white")
        
        return image
    
    def _get_status_for_area(self, area_id: int, side: str) -> str:
        """エリアIDから比較ステータスを取得"""
        for result in self.comparison_results:
            if result["area_id"] == area_id:
                status = result["status"]
                
                # Web/PDF専用の場合、side によって扱いを変える
                if status == "web_only" and side == "pdf":
                    return "not_shown"
                if status == "pdf_only" and side == "web":
                    return "not_shown"
                
                return status
        
        return "unknown"
    
    def _get_color_for_status(self, status: str) -> Tuple[str, int]:
        """
        ステータスから色を取得
        
        Returns:
            (color, fill_alpha): RGB色コードと塗りつぶしアルファ値
        """
        color_map = {
            "match": ("#4CAF50", 30),       # 緑
            "mismatch": ("#FF5722", 50),    # 赤
            "web_only": ("#2196F3", 50),    # 青
            "pdf_only": ("#FF9800", 50),    # オレンジ
            "unknown": ("#999999", 30),     # グレー
            "not_shown": ("#000000", 0)     # 非表示
        }
        return color_map.get(status, ("#999999", 30))
    
    def _should_show(self, status: str) -> bool:
        """ステータスを表示すべきか判定"""
        if status == "match" and not self.show_matched:
            return False
        if status == "mismatch" and not self.show_mismatched:
            return False
        if status == "web_only" and not self.show_web_only:
            return False
        if status == "pdf_only" and not self.show_pdf_only:
            return False
        if status == "not_shown":
            return False
        return True
    
    def _on_filter_change(self):
        """フィルター変更時の処理"""
        self.show_matched = self.check_matched.get()
        self.show_mismatched = self.check_mismatched.get()
        self.show_web_only = self.check_web_only.get()
        self.show_pdf_only = self.check_pdf_only.get()
        
        self.redraw()
    
    def _on_zoom_change(self, value):
        """ズーム変更時の処理"""
        self.display_scale = float(value)
        self.zoom_label.configure(text=f"{int(value * 100)}%")
        self.redraw()
    
    def _on_canvas_click(self, event, side: str):
        """Canvas クリック時の処理"""
        canvas = self.web_canvas if side == "web" else self.pdf_canvas
        clusters = self.web_clusters if side == "web" else self.pdf_clusters
        
        # クリック座標
        cx = canvas.canvasx(event.x)
        cy = canvas.canvasy(event.y)
        
        # 元画像の座標に変換
        img_x = cx / self.display_scale
        img_y = cy / self.display_scale
        
        # クリックされたエリアを検索
        for cluster in clusters:
            rect = cluster.get("rect", [0, 0, 0, 0])
            x0, y0, x1, y1 = rect
            
            if x0 <= img_x <= x1 and y0 <= img_y <= y1:
                area_id = cluster.get("id")
                
                if self.on_area_click:
                    self.on_area_click(area_id)
                
                return
    
    def highlight_area(self, area_id: int):
        """特定エリアをハイライト"""
        # TODO: 実装（選択状態の表示など）
        pass
    
    def clear(self):
        """全てクリア"""
        self.web_image = None
        self.pdf_image = None
        self.web_clusters = []
        self.pdf_clusters = []
        self.comparison_results = []
        
        if hasattr(self, 'web_canvas'):
            self.web_canvas.delete("all")
        if hasattr(self, 'pdf_canvas'):
            self.pdf_canvas.delete("all")

