"""
Canvas編集UI
既存OCRツールの編集機能を移植
検出枠のドラッグ操作、リサイズ、削除、新規作成機能
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from typing import List, Dict, Optional, Callable
import threading


class CanvasEditor:
    """
    画像とクラスタ情報を編集可能なCanvasを提供するクラス
    
    機能:
    - 画像の表示とスクロール
    - クラスタ枠の描画
    - ドラッグで新規エリア作成
    - クリックでエリア選択
    - 右クリックでエリア削除
    - リサイズ対応（自動スケーリング）
    """
    
    def __init__(
        self,
        parent,
        on_cluster_change: Optional[Callable] = None,
        on_selection_change: Optional[Callable] = None
    ):
        """
        Args:
            parent: 親ウィジェット
            on_cluster_change: クラスタ変更時のコールバック
            on_selection_change: 選択変更時のコールバック
        """
        self.parent = parent
        self.on_cluster_change = on_cluster_change
        self.on_selection_change = on_selection_change
        
        # データ
        self.original_image = None
        self.clusters = []
        self.raw_words = []  # 手動エリア作成時のテキスト抽出用
        
        # 表示制御
        self.display_scale = 1.0
        self._cached_image_size = None
        self._resized_image = None
        self.tk_img = None
        
        # 編集状態
        self.selected_cluster_index = None
        self.start_x = None
        self.start_y = None
        self.current_rect_id = None
        self.is_dragging = False
        
        # UI構築
        self._build_ui()
    
    def _build_ui(self):
        """UIの構築"""
        # コンテナフレーム
        self.container = tk.Frame(self.parent, bg="#202020")
        self.container.pack(fill="both", expand=True)
        
        # スクロールバー
        self.v_scroll = tk.Scrollbar(self.container, orient="vertical")
        self.h_scroll = tk.Scrollbar(self.container, orient="horizontal")
        
        # Canvas
        self.canvas = tk.Canvas(
            self.container,
            bg="#202020",
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set
        )
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        # 配置
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # イベントバインディング
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
    
    def load_image(self, image: Image.Image):
        """
        画像を読み込む
        
        Args:
            image: PIL.Image オブジェクト
        """
        self.original_image = image
        self._cached_image_size = None
        self.redraw()
    
    def set_clusters(self, clusters: List[Dict], raw_words: List[Dict] = None):
        """
        クラスタ情報をセット
        
        Args:
            clusters: クラスタリスト
            raw_words: 単語レベルのデータ（手動エリア作成用）
        """
        self.clusters = clusters
        self.raw_words = raw_words or []
        self.selected_cluster_index = None
        self.redraw()
    
    def get_clusters(self) -> List[Dict]:
        """現在のクラスタ情報を取得"""
        return self.clusters
    
    def redraw(self):
        """Canvas全体を再描画"""
        self.canvas.delete("all")
        
        if not self.original_image:
            return
        
        # Canvas幅の取得
        canvas_w = self.canvas.winfo_width()
        if canvas_w < 100:  # 初期化前
            return
        
        # スケール計算
        img_w, img_h = self.original_image.size
        self.display_scale = canvas_w / img_w
        display_w = int(img_w * self.display_scale)
        display_h = int(img_h * self.display_scale)
        
        # 画像のリサイズ（キャッシュを使用）
        if self._cached_image_size != (display_w, display_h):
            self._resized_image = self.original_image.resize(
                (display_w, display_h),
                Image.Resampling.LANCZOS
            )
            self._cached_image_size = (display_w, display_h)
            self.tk_img = ImageTk.PhotoImage(self._resized_image)
        
        # スクロール領域の設定
        self.canvas.config(scrollregion=(0, 0, display_w, display_h))
        
        # 画像の描画
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        # クラスタ枠の描画
        for idx, cluster in enumerate(self.clusters):
            self._draw_cluster(idx, cluster)
    
    def _draw_cluster(self, idx: int, cluster: Dict):
        """クラスタ枠を描画"""
        rect = cluster.get("rect", [0, 0, 0, 0])
        x0, y0, x1, y1 = [v * self.display_scale for v in rect]
        
        # 選択状態に応じて色を変える
        is_selected = (idx == self.selected_cluster_index)
        color = "#00FFFF" if is_selected else "#FF4444"
        width = 3 if is_selected else 2
        
        # 矩形
        self.canvas.create_rectangle(
            x0, y0, x1, y1,
            outline=color,
            width=width,
            tags=f"box_{idx}"
        )
        
        # ラベル背景
        label_text = f"Area {cluster.get('id', idx+1)}"
        label_width = len(label_text) * 7 + 10
        self.canvas.create_rectangle(
            x0, y0 - 20, x0 + label_width, y0,
            fill=color,
            outline=color,
            tags=f"box_{idx}"
        )
        
        # ラベルテキスト
        self.canvas.create_text(
            x0 + label_width / 2, y0 - 10,
            text=label_text,
            fill="white",
            font=("Arial", 9, "bold"),
            tags=f"box_{idx}"
        )
    
    def _on_mouse_down(self, event):
        """マウス押下時の処理"""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # 既存のクラスタをクリックしたか判定
        clicked_index = self._find_cluster_at(cx, cy)
        
        if clicked_index is not None:
            # 既存クラスタを選択
            self.selected_cluster_index = clicked_index
            self.redraw()
            
            if self.on_selection_change:
                self.on_selection_change(clicked_index)
            return
        
        # 新規エリア作成モード
        self.selected_cluster_index = None
        self.start_x = cx
        self.start_y = cy
        self.is_dragging = True
        
        # 仮の矩形を描画
        self.current_rect_id = self.canvas.create_rectangle(
            cx, cy, cx, cy,
            outline="#00FF00",
            width=2,
            dash=(4, 4)
        )
    
    def _on_mouse_drag(self, event):
        """マウスドラッグ時の処理"""
        if not self.is_dragging or self.start_x is None:
            return
        
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # 仮の矩形を更新
        self.canvas.coords(
            self.current_rect_id,
            self.start_x, self.start_y, cx, cy
        )
    
    def _on_mouse_up(self, event):
        """マウスリリース時の処理"""
        if not self.is_dragging or self.start_x is None:
            return
        
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # 最小サイズチェック
        if abs(cx - self.start_x) < 5 or abs(cy - self.start_y) < 5:
            self.canvas.delete(self.current_rect_id)
            self.start_x = None
            self.start_y = None
            self.is_dragging = False
            return
        
        # 座標の正規化
        x0, x1 = sorted([self.start_x, cx])
        y0, y1 = sorted([self.start_y, cy])
        
        # 元画像の座標に変換
        rect_img = [
            int(x0 / self.display_scale),
            int(y0 / self.display_scale),
            int(x1 / self.display_scale),
            int(y1 / self.display_scale)
        ]
        
        # テキストを抽出
        new_text = self._extract_text_from_rect(rect_img)
        
        # 新しいクラスタを追加
        new_id = max([c.get('id', 0) for c in self.clusters], default=0) + 1
        new_cluster = {
            "id": new_id,
            "rect": rect_img,
            "text": new_text
        }
        
        self.clusters.append(new_cluster)
        
        # クリーンアップ
        self.canvas.delete(self.current_rect_id)
        self.start_x = None
        self.start_y = None
        self.is_dragging = False
        
        # 再描画
        self.redraw()
        
        # コールバック
        if self.on_cluster_change:
            self.on_cluster_change(self.clusters)
    
    def _on_right_click(self, event):
        """右クリック時の処理（削除）"""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # クリックされたクラスタを検索
        clicked_index = self._find_cluster_at(cx, cy)
        
        if clicked_index is not None:
            # 確認ダイアログ
            cluster = self.clusters[clicked_index]
            area_id = cluster.get('id', clicked_index + 1)
            
            if messagebox.askyesno(
                "確認",
                f"Area {area_id} を削除しますか？"
            ):
                del self.clusters[clicked_index]
                self.selected_cluster_index = None
                self.redraw()
                
                if self.on_cluster_change:
                    self.on_cluster_change(self.clusters)
    
    def _find_cluster_at(self, x: float, y: float) -> Optional[int]:
        """指定座標にあるクラスタのインデックスを返す"""
        for i, cluster in enumerate(self.clusters):
            rect = cluster.get("rect", [0, 0, 0, 0])
            x0, y0, x1, y1 = [v * self.display_scale for v in rect]
            
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        
        return None
    
    def _extract_text_from_rect(self, rect: List[int]) -> str:
        """
        矩形領域内のテキストを抽出
        raw_words から該当する単語を集める
        """
        if not self.raw_words:
            return ""
        
        x0, y0, x1, y1 = rect
        included_words = []
        
        for word in self.raw_words:
            wx, wy = word.get("center", (0, 0))
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                included_words.append(word)
        
        # Y座標でソート（行ごとにまとめる）
        included_words.sort(key=lambda w: (
            round(w.get("rect", [0, 0, 0, 0])[1] / 20) * 20,
            w.get("rect", [0, 0, 0, 0])[0]
        ))
        
        # テキスト結合
        lines = []
        current_line = []
        last_y = -1
        
        for w in included_words:
            rect = w.get("rect", [0, 0, 0, 0])
            cy = (rect[1] + rect[3]) / 2
            
            if last_y != -1 and abs(cy - last_y) > 20:
                lines.append("".join(current_line))
                current_line = []
            
            current_line.append(w.get("text", ""))
            last_y = cy
        
        if current_line:
            lines.append("".join(current_line))
        
        return "\n".join(lines)
    
    def select_cluster(self, index: int):
        """プログラムからクラスタを選択"""
        if 0 <= index < len(self.clusters):
            self.selected_cluster_index = index
            self.redraw()
            
            if self.on_selection_change:
                self.on_selection_change(index)
    
    def delete_selected(self):
        """選択中のクラスタを削除"""
        if self.selected_cluster_index is not None:
            del self.clusters[self.selected_cluster_index]
            self.selected_cluster_index = None
            self.redraw()
            
            if self.on_cluster_change:
                self.on_cluster_change(self.clusters)
    
    def get_selected_cluster(self) -> Optional[Dict]:
        """選択中のクラスタを取得"""
        if self.selected_cluster_index is not None:
            return self.clusters[self.selected_cluster_index]
        return None
    
    def update_selected_text(self, new_text: str):
        """選択中のクラスタのテキストを更新"""
        if self.selected_cluster_index is not None:
            self.clusters[self.selected_cluster_index]["text"] = new_text
            
            if self.on_cluster_change:
                self.on_cluster_change(self.clusters)
    
    def clear(self):
        """全てクリア"""
        self.original_image = None
        self.clusters = []
        self.raw_words = []
        self.selected_cluster_index = None
        self.redraw()

