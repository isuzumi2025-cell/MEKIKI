"""
Macro View Module
全体マップビュー - WebとPDFのグリッド配置、マッチング線描画
"""
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from typing import List, Dict, Optional, Callable, Tuple
from PIL import Image, ImageTk, ImageDraw, ImageFont
import math


class MacroView(ctk.CTkFrame):
    """
    全体マップビュー（Canvas版）
    Webサムネイルとマッチング線を描画
    """
    
    def __init__(
        self,
        master,
        analyzer=None,
        on_detail_click: Optional[Callable] = None,
        **kwargs
    ):
        """
        Args:
            master: 親ウィジェット
            analyzer: ContentAnalyzerインスタンス
            on_detail_click: 詳細比較ボタンのコールバック
        """
        super().__init__(master, **kwargs)
        
        self.analyzer = analyzer
        self.on_detail_click = on_detail_click
        
        # データ
        self.web_areas: List = []  # DetectedArea
        self.pdf_areas: List = []
        self.matched_pairs: List = []  # MatchedPair
        
        # UI設定
        self.thumbnail_size = (200, 150)
        self.grid_padding = 20
        self.grid_columns = 3
        
        # Canvas上のアイテムID管理
        self.web_items: Dict[str, Dict] = {}  # area.id -> {"rect": id, "text": id, "image": id}
        self.pdf_items: Dict[str, Dict] = {}
        self.line_items: List[int] = []
        
        self._build_ui()
    
    def _build_ui(self):
        """UI構築"""
        # ヘッダー
        header = ctk.CTkFrame(self, fg_color="#1A1A1A", height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="🗺️ 全体マッピングビュー",
            font=("Meiryo", 18, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=20, pady=10)
        
        # ツールバー
        toolbar = ctk.CTkFrame(header, fg_color="transparent")
        toolbar.pack(side="right", padx=20, pady=10)
        
        ctk.CTkButton(
            toolbar,
            text="🔄 再描画",
            command=self.refresh_canvas,
            width=100,
            height=30
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="📂 画像検索",
            command=self._open_image_search,
            width=120,
            height=30,
            fg_color="#9C27B0"
        ).pack(side="left", padx=5)
        
        # メインキャンバスエリア
        canvas_frame = ctk.CTkFrame(self)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # スクロールバー
        self.v_scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="vertical")
        self.v_scrollbar.pack(side="right", fill="y")
        
        self.h_scrollbar = ctk.CTkScrollbar(canvas_frame, orientation="horizontal")
        self.h_scrollbar.pack(side="bottom", fill="x")
        
        # Canvas
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#2B2B2B",
            highlightthickness=0,
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.v_scrollbar.configure(command=self.canvas.yview)
        self.h_scrollbar.configure(command=self.canvas.xview)
        
        # ドラッグ&ドロップエリア（右下）
        self.drop_zone = ctk.CTkFrame(
            self,
            fg_color="#3A3A3A",
            border_width=2,
            border_color="#9C27B0",
            corner_radius=10,
            width=250,
            height=150
        )
        self.drop_zone.place(relx=0.98, rely=0.95, anchor="se")
        self.drop_zone.pack_propagate(False)
        
        ctk.CTkLabel(
            self.drop_zone,
            text="📸 画像検索\n\n画像をドロップまたは\nボタンから選択",
            font=("Meiryo", 11),
            text_color="#9C27B0"
        ).pack(expand=True)
        
        # 統計情報（左下）
        self.stats_label = ctk.CTkLabel(
            self,
            text="Web: 0 | PDF: 0 | ペア: 0",
            font=("Meiryo", 10),
            text_color="gray"
        )
        self.stats_label.place(relx=0.02, rely=0.98, anchor="sw")
    
    def load_from_analyzer(self):
        """Analyzerからデータを読み込んで描画"""
        if not self.analyzer:
            print("⚠️ Analyzerが設定されていません")
            return
        
        self.web_areas = self.analyzer.web_areas
        self.pdf_areas = self.analyzer.pdf_areas
        self.matched_pairs = self.analyzer.matched_pairs
        
        self.refresh_canvas()
    
    def refresh_canvas(self):
        """Canvas全体を再描画"""
        # クリア
        self.canvas.delete("all")
        self.web_items.clear()
        self.pdf_items.clear()
        self.line_items.clear()
        
        if not self.web_areas and not self.pdf_areas:
            # プレースホルダー
            self.canvas.create_text(
                400, 300,
                text="データがありません\n\nナビゲーションから\n「Web一括クロール」または「PDF一括読込」を実行してください",
                font=("Meiryo", 14),
                fill="gray",
                justify="center"
            )
            return
        
        # 左側: Webエリア描画
        web_x_start = 50
        web_y_start = 50
        self._draw_grid(
            self.web_areas,
            web_x_start,
            web_y_start,
            "🌐 Web Pages",
            "#E08E00",
            self.web_items
        )
        
        # 右側: PDFエリア描画
        canvas_width = 1600  # 仮想キャンバス幅
        pdf_x_start = canvas_width // 2 + 50
        pdf_y_start = 50
        self._draw_grid(
            self.pdf_areas,
            pdf_x_start,
            pdf_y_start,
            "📁 PDF Pages",
            "#4CAF50",
            self.pdf_items
        )
        
        # マッチング線を描画
        self._draw_matching_lines()
        
        # スクロール領域を設定
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # 統計情報を更新
        self._update_stats()
    
    def _draw_grid(
        self,
        areas: List,
        start_x: int,
        start_y: int,
        title: str,
        color: str,
        items_dict: Dict
    ):
        """グリッド状にエリアを描画"""
        # タイトル
        self.canvas.create_text(
            start_x, start_y - 20,
            text=title,
            font=("Meiryo", 14, "bold"),
            fill=color,
            anchor="w"
        )
        
        # グリッド配置
        for i, area in enumerate(areas):
            row = i // self.grid_columns
            col = i % self.grid_columns
            
            x = start_x + col * (self.thumbnail_size[0] + self.grid_padding)
            y = start_y + row * (self.thumbnail_size[1] + self.grid_padding)
            
            # サムネイル枠
            rect_id = self.canvas.create_rectangle(
                x, y,
                x + self.thumbnail_size[0],
                y + self.thumbnail_size[1],
                outline=color,
                width=3,
                fill="#1A1A1A"
            )
            
            # テキスト情報
            text_preview = area.text[:30] + "..." if len(area.text) > 30 else area.text
            text_id = self.canvas.create_text(
                x + self.thumbnail_size[0] // 2,
                y + self.thumbnail_size[1] // 2,
                text=text_preview,
                font=("Meiryo", 9),
                fill="white",
                width=self.thumbnail_size[0] - 20,
                justify="center"
            )
            
            # バウンディングボックスを小さく描画
            if area.bbox:
                bbox_scale = 0.3
                bbox_x = x + 10
                bbox_y = y + 10
                bbox_w = area.bbox[2] - area.bbox[0]
                bbox_h = area.bbox[3] - area.bbox[1]
                
                self.canvas.create_rectangle(
                    bbox_x,
                    bbox_y,
                    bbox_x + bbox_w * bbox_scale,
                    bbox_y + bbox_h * bbox_scale,
                    outline="red",
                    width=1
                )
            
            # アイテムIDを保存
            items_dict[area.id] = {
                "rect": rect_id,
                "text": text_id,
                "x": x + self.thumbnail_size[0] // 2,
                "y": y + self.thumbnail_size[1] // 2
            }
    
    def _draw_matching_lines(self):
        """マッチング線を描画"""
        for pair in self.matched_pairs:
            web_id = pair.web_area.id
            pdf_id = pair.pdf_area.id
            
            if web_id not in self.web_items or pdf_id not in self.pdf_items:
                continue
            
            # 座標を取得
            x1 = self.web_items[web_id]["x"]
            y1 = self.web_items[web_id]["y"]
            x2 = self.pdf_items[pdf_id]["x"]
            y2 = self.pdf_items[pdf_id]["y"]
            
            # 類似度に応じた色
            score = pair.similarity_score
            if score >= 0.7:
                line_color = "#4CAF50"  # 緑
            elif score >= 0.4:
                line_color = "#FFC107"  # 黄
            else:
                line_color = "#FF5722"  # 赤
            
            # ベジェ曲線風に描画
            line_id = self._draw_bezier_line(
                x1, y1, x2, y2,
                color=line_color,
                width=2
            )
            
            self.line_items.append(line_id)
            
            # スコアラベル
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            self.canvas.create_text(
                mid_x, mid_y - 10,
                text=f"{score:.0%}",
                font=("Meiryo", 9, "bold"),
                fill=line_color
            )
    
    def _draw_bezier_line(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        color: str = "white",
        width: int = 2
    ) -> int:
        """ベジェ曲線風の線を描画"""
        # 制御点を計算
        cx = (x1 + x2) // 2
        cy = min(y1, y2) - 50
        
        # 簡易的な曲線（複数の直線で近似）
        points = []
        steps = 20
        for i in range(steps + 1):
            t = i / steps
            # 2次ベジェ曲線
            x = (1-t)**2 * x1 + 2*(1-t)*t * cx + t**2 * x2
            y = (1-t)**2 * y1 + 2*(1-t)*t * cy + t**2 * y2
            points.extend([x, y])
        
        return self.canvas.create_line(
            *points,
            fill=color,
            width=width,
            smooth=True
        )
    
    def _update_stats(self):
        """統計情報を更新"""
        web_count = len(self.web_areas)
        pdf_count = len(self.pdf_areas)
        pair_count = len(self.matched_pairs)
        
        self.stats_label.configure(
            text=f"Web: {web_count} | PDF: {pdf_count} | ペア: {pair_count}"
        )
    
    def _open_image_search(self):
        """画像検索ダイアログを開く"""
        file_path = filedialog.askopenfilename(
            title="検索する画像を選択",
            filetypes=[
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp"),
                ("全てのファイル", "*.*")
            ]
        )
        
        if file_path:
            print(f"🔍 画像検索: {file_path}")
            # TODO: VisualSearchEngineを使用した逆引き検索
            # 今は未実装メッセージ
            self.canvas.create_text(
                800, 400,
                text=f"画像検索機能は実装予定です\n選択された画像: {file_path}",
                font=("Meiryo", 12),
                fill="#9C27B0",
                justify="center",
                tags="search_message"
            )
            self.after(3000, lambda: self.canvas.delete("search_message"))

