"""
Web vs PDF 整合性検証システム - メインアプリケーション
既存の高精度OCRツールの「脳」を移植し、Webスクレイピングに応用
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import threading
import os
from pathlib import Path

# コアエンジン
from app.core.crawler import WebCrawler
from app.core.pdf_loader import PDFLoader
from app.core.engine_clustering import ClusteringEngine, BlockExtractor
from app.core.engine_spreadsheet import SpreadsheetEngine
from app.core.comparator import Comparator

# GUI
from app.gui.canvas_editor import CanvasEditor
from app.gui.macro_view import MacroView

# デザイン設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class IntegrityVerificationApp(ctk.CTk):
    """
    Web vs PDF 整合性検証アプリケーション
    
    主要機能:
    1. Webクローリング（スクリーンショット撮影）
    2. PDF高解像度読み込み
    3. 高度な領域検出（クラスタリング）
    4. 編集可能なCanvas UI
    5. Web vs PDF 比較
    6. Googleスプレッドシート同期
    """
    
    def __init__(self):
        super().__init__()
        
        self.title("Web vs PDF 整合性検証システム")
        self.geometry("1400x900")
        
        # データ管理
        self.web_image = None
        self.pdf_image = None
        self.web_clusters = []
        self.pdf_clusters = []
        self.web_raw_words = []
        self.pdf_raw_words = []
        self.comparison_results = []
        
        # エンジン
        self.crawler = WebCrawler()
        self.pdf_loader = PDFLoader(dpi=300)
        self.clustering_engine = ClusteringEngine()
        self.spreadsheet_engine = None  # 必要時に初期化
        self.comparator = Comparator()
        
        # UI構築
        self._setup_ui()
        
        print("🚀 Web vs PDF 整合性検証システム - 起動完了")
    
    def _setup_ui(self):
        """UI構築"""
        # トップツールバー
        self._build_top_toolbar()
        
        # メインエリア（タブ）
        self.tab_view = ctk.CTkTabview(self, corner_radius=0)
        self.tab_view.pack(fill="both", expand=True, padx=5, pady=5)
        
        # タブ1: Web編集
        self.tab_web = self.tab_view.add("🌐 Web")
        self._build_edit_tab(self.tab_web, "web")
        
        # タブ2: PDF編集
        self.tab_pdf = self.tab_view.add("📄 PDF")
        self._build_edit_tab(self.tab_pdf, "pdf")
        
        # タブ3: 全体比較
        self.tab_compare = self.tab_view.add("🔍 比較")
        self._build_compare_tab()
        
        # ボトムステータスバー
        self._build_status_bar()
    
    def _build_top_toolbar(self):
        """トップツールバー"""
        toolbar = ctk.CTkFrame(self, height=60, corner_radius=0)
        toolbar.pack(side="top", fill="x", padx=0, pady=0)
        
        # タイトル
        ctk.CTkLabel(
            toolbar,
            text="🔬 Web vs PDF 整合性検証",
            font=("Arial", 16, "bold")
        ).pack(side="left", padx=20, pady=10)
        
        # セパレータ
        ctk.CTkLabel(toolbar, text="|", text_color="gray").pack(side="left", padx=5)
        
        # Web読込ボタン
        ctk.CTkButton(
            toolbar,
            text="🌐 Web読込",
            command=self.load_web_dialog,
            width=120,
            fg_color="#E08E00"
        ).pack(side="left", padx=5, pady=10)
        
        # PDF読込ボタン
        ctk.CTkButton(
            toolbar,
            text="📄 PDF読込",
            command=self.load_pdf_dialog,
            width=120,
            fg_color="#1F6AA5"
        ).pack(side="left", padx=5, pady=10)
        
        # セパレータ
        ctk.CTkLabel(toolbar, text="|", text_color="gray").pack(side="left", padx=10)
        
        # 解析実行ボタン
        self.btn_analyze = ctk.CTkButton(
            toolbar,
            text="▶ AI解析実行",
            command=self.run_analysis,
            width=140,
            fg_color="#207f4c"
        )
        self.btn_analyze.pack(side="left", padx=5, pady=10)
        
        # 比較実行ボタン
        self.btn_compare = ctk.CTkButton(
            toolbar,
            text="🔍 比較実行",
            command=self.run_comparison,
            width=120,
            fg_color="#9C27B0"
        )
        self.btn_compare.pack(side="left", padx=5, pady=10)
        
        # プログレスバー
        self.progress = ctk.CTkProgressBar(toolbar, mode='indeterminate', width=200)
        
        # セパレータ
        ctk.CTkLabel(toolbar, text="|", text_color="gray").pack(side="left", padx=10)
        
        # エクスポートボタン
        ctk.CTkButton(
            toolbar,
            text="📊 Sheets出力",
            command=self.export_to_sheets,
            width=120,
            fg_color="#555"
        ).pack(side="left", padx=5, pady=10)
        
        ctk.CTkButton(
            toolbar,
            text="💾 CSV出力",
            command=self.export_to_csv,
            width=100,
            fg_color="#555"
        ).pack(side="left", padx=5, pady=10)
    
    def _build_edit_tab(self, parent, side: str):
        """編集タブ（WebまたはPDF）"""
        # 左右分割
        paned = tk.PanedWindow(parent, orient="horizontal", bg="#2B2B2B", sashwidth=4)
        paned.pack(fill="both", expand=True)
        
        # 左: Canvas編集エリア
        editor_frame = ctk.CTkFrame(paned)
        paned.add(editor_frame, width=900)
        
        editor = CanvasEditor(
            editor_frame,
            on_cluster_change=lambda clusters: self._on_cluster_change(side, clusters),
            on_selection_change=lambda idx: self._on_selection_change(side, idx)
        )
        
        # 右: テキスト詳細エリア
        detail_frame = ctk.CTkFrame(paned)
        paned.add(detail_frame, width=400)
        
        ctk.CTkLabel(
            detail_frame,
            text="📝 抽出テキスト",
            font=("Arial", 12, "bold"),
            anchor="w"
        ).pack(fill="x", padx=10, pady=5)
        
        text_widget = ctk.CTkTextbox(detail_frame, font=("Meiryo", 11), wrap="word")
        text_widget.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 保存
        if side == "web":
            self.web_editor = editor
            self.web_text_widget = text_widget
        else:
            self.pdf_editor = editor
            self.pdf_text_widget = text_widget
    
    def _build_compare_tab(self):
        """比較タブ"""
        # マクロビュー
        self.macro_view = MacroView(
            self.tab_compare,
            on_area_click=self._on_area_click_in_macro
        )
        
        # サマリー表示エリア
        summary_frame = ctk.CTkFrame(self.tab_compare, height=150)
        summary_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            summary_frame,
            text="📊 比較サマリー",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", padx=10, pady=5)
        
        self.summary_label = ctk.CTkLabel(
            summary_frame,
            text="比較を実行してください",
            font=("Meiryo", 11),
            anchor="w",
            justify="left"
        )
        self.summary_label.pack(fill="both", padx=10, pady=5)
    
    def _build_status_bar(self):
        """ステータスバー"""
        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0)
        self.status_bar.pack(side="bottom", fill="x")
        
        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="準備完了",
            anchor="w"
        )
        self.status_label.pack(side="left", padx=10)
    
    # =============== イベントハンドラ ===============
    
    def _on_cluster_change(self, side: str, clusters):
        """クラスタ変更時"""
        if side == "web":
            self.web_clusters = clusters
        else:
            self.pdf_clusters = clusters
        
        self._update_text_area(side)
    
    def _on_selection_change(self, side: str, index: int):
        """選択変更時"""
        self._update_text_area(side, selected_index=index)
    
    def _on_area_click_in_macro(self, area_id: int):
        """マクロビューでエリアクリック時"""
        messagebox.showinfo(
            "エリア情報",
            f"Area {area_id} がクリックされました"
        )
    
    def _update_text_area(self, side: str, selected_index: int = None):
        """テキストエリアを更新"""
        if side == "web":
            clusters = self.web_clusters
            text_widget = self.web_text_widget
        else:
            clusters = self.pdf_clusters
            text_widget = self.pdf_text_widget
        
        text_widget.delete("1.0", "end")
        
        if selected_index is not None and 0 <= selected_index < len(clusters):
            # 選択されたクラスタのみ表示
            cluster = clusters[selected_index]
            text = f"━━━━━━━━ [Area {cluster.get('id', selected_index+1)}] ━━━━━━━━\n"
            text += cluster.get('text', '')
            text_widget.insert("end", text)
        else:
            # 全クラスタを表示
            for i, cluster in enumerate(clusters):
                text = f"━━━━━━━━ [Area {cluster.get('id', i+1)}] ━━━━━━━━\n"
                text += cluster.get('text', '') + "\n\n"
                text_widget.insert("end", text)
    
    # =============== データロード ===============
    
    def load_web_dialog(self):
        """Web読込ダイアログ"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Web読込")
        dialog.geometry("500x350")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Webページ読込", font=("Meiryo", 16, "bold")).pack(pady=15)
        
        ctk.CTkLabel(dialog, text="URL:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_url = ctk.CTkEntry(dialog, placeholder_text="https://...")
        entry_url.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(dialog, text="Basic認証 (オプション)", font=("Meiryo", 11, "bold")).pack(pady=5)
        
        ctk.CTkLabel(dialog, text="ユーザー名:", anchor="w").pack(fill="x", padx=20)
        entry_user = ctk.CTkEntry(dialog)
        entry_user.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(dialog, text="パスワード:", anchor="w").pack(fill="x", padx=20)
        entry_pass = ctk.CTkEntry(dialog, show="*")
        entry_pass.pack(fill="x", padx=20, pady=5)
        
        def on_load():
            url = entry_url.get().strip()
            user = entry_user.get().strip()
            pw = entry_pass.get().strip()
            
            if not url:
                messagebox.showwarning("入力エラー", "URLを入力してください", parent=dialog)
                return
            
            dialog.destroy()
            self._load_web_async(url, user or None, pw or None)
        
        ctk.CTkButton(dialog, text="読込実行", command=on_load, fg_color="#E08E00").pack(pady=20)
    
    def _load_web_async(self, url: str, username: str, password: str):
        """Webを非同期で読み込み"""
        self.status_label.configure(text=f"🌍 Web読込中: {url}")
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        
        def task():
            try:
                output_path = "temp_web_screenshot.png"
                result = self.crawler.crawl(
                    url, output_path,
                    username=username,
                    password=password,
                    wait_time=2,
                    full_page=True
                )
                
                if result["success"]:
                    self.web_image = Image.open(output_path)
                    self.after(0, lambda: self._on_web_loaded(result["title"]))
                else:
                    self.after(0, lambda: messagebox.showerror("エラー", result["error"]))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self._reset_progress)
        
        threading.Thread(target=task, daemon=True).start()
    
    def _on_web_loaded(self, title: str):
        """Web読み込み完了時"""
        self.web_editor.load_image(self.web_image)
        self.status_label.configure(text=f"✅ Web読込完了: {title}")
        messagebox.showinfo("完了", f"Web画像を読み込みました\n{title}")
    
    def load_pdf_dialog(self):
        """PDF読込ダイアログ"""
        path = filedialog.askopenfilename(
            title="PDFを選択",
            filetypes=[("PDF", "*.pdf")]
        )
        
        if path:
            self._load_pdf_async(path)
    
    def _load_pdf_async(self, path: str):
        """PDFを非同期で読み込み"""
        self.status_label.configure(text=f"📄 PDF読込中: {Path(path).name}")
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        
        def task():
            try:
                images = self.pdf_loader.load(path)
                if images:
                    self.pdf_image = images[0]  # 1ページ目
                    self.after(0, lambda: self._on_pdf_loaded(Path(path).name))
                else:
                    self.after(0, lambda: messagebox.showerror("エラー", "PDFの読み込みに失敗しました"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self._reset_progress)
        
        threading.Thread(target=task, daemon=True).start()
    
    def _on_pdf_loaded(self, filename: str):
        """PDF読み込み完了時"""
        self.pdf_editor.load_image(self.pdf_image)
        self.status_label.configure(text=f"✅ PDF読込完了: {filename}")
        messagebox.showinfo("完了", f"PDF画像を読み込みました\n{filename}")
    
    # =============== AI解析 ===============
    
    def run_analysis(self):
        """AI解析実行"""
        if not self.web_image and not self.pdf_image:
            messagebox.showwarning("警告", "WebまたはPDF画像を読み込んでください")
            return
        
        self.status_label.configure(text="🤖 AI解析中...")
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        self.btn_analyze.configure(state="disabled")
        
        def task():
            try:
                # Google Cloud Vision API を使う場合
                # ここでは簡易的にダミーデータを生成
                # 実際には BlockExtractor.extract_from_vision_api を使用
                
                if self.web_image:
                    # Web画像の解析
                    self.web_clusters = self._dummy_clusters(self.web_image)
                    self.after(0, lambda: self.web_editor.set_clusters(self.web_clusters))
                
                if self.pdf_image:
                    # PDF画像の解析
                    self.pdf_clusters = self._dummy_clusters(self.pdf_image)
                    self.after(0, lambda: self.pdf_editor.set_clusters(self.pdf_clusters))
                
                self.after(0, lambda: messagebox.showinfo("完了", "AI解析が完了しました"))
                self.after(0, lambda: self.status_label.configure(text="✅ AI解析完了"))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self._reset_progress)
                self.after(0, lambda: self.btn_analyze.configure(state="normal"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def _dummy_clusters(self, image: Image.Image) -> list:
        """ダミークラスタ生成（デモ用）"""
        # 実際には Google Cloud Vision API を使用
        width, height = image.size
        return [
            {
                "id": 1,
                "rect": [50, 50, 300, 150],
                "text": "サンプルテキスト 1\nこれはダミーデータです"
            },
            {
                "id": 2,
                "rect": [50, 200, 400, 300],
                "text": "サンプルテキスト 2\n実際にはCloud Vision APIを使用します"
            }
        ]
    
    # =============== 比較実行 ===============
    
    def run_comparison(self):
        """比較実行"""
        if not self.web_clusters or not self.pdf_clusters:
            messagebox.showwarning("警告", "両方のデータを解析してください")
            return
        
        self.status_label.configure(text="🔍 比較実行中...")
        
        # Comparator にデータをセット
        self.comparator.set_data(
            self.web_clusters,
            self.pdf_clusters,
            self.web_image,
            self.pdf_image
        )
        
        # 比較実行
        self.comparison_results = self.comparator.compare_all()
        
        # MacroView に表示
        self.macro_view.load_data(
            self.web_image,
            self.pdf_image,
            self.web_clusters,
            self.pdf_clusters,
            self.comparison_results
        )
        
        # サマリー更新
        summary = self.comparator.get_summary()
        summary_text = (
            f"総数: {summary['total']}  |  "
            f"✅ 一致: {summary['match']}  |  "
            f"⚠️ 不一致: {summary['mismatch']}  |  "
            f"🌐 Web専用: {summary['web_only']}  |  "
            f"📄 PDF専用: {summary['pdf_only']}\n"
            f"平均類似度: {summary['average_similarity']:.2%}"
        )
        self.summary_label.configure(text=summary_text)
        
        # 比較タブに切り替え
        self.tab_view.set("🔍 比較")
        
        self.status_label.configure(text="✅ 比較完了")
        messagebox.showinfo("完了", "比較が完了しました")
    
    # =============== エクスポート ===============
    
    def export_to_sheets(self):
        """Googleスプレッドシート出力"""
        if not self.comparison_results:
            messagebox.showwarning("警告", "先に比較を実行してください")
            return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sheets出力")
        dialog.geometry("500x300")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Google Sheets 出力", font=("Meiryo", 16, "bold")).pack(pady=15)
        
        ctk.CTkLabel(dialog, text="スプレッドシートURL:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_url = ctk.CTkEntry(dialog)
        entry_url.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(dialog, text="共有するメールアドレス:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_email = ctk.CTkEntry(dialog)
        entry_email.pack(fill="x", padx=20, pady=5)
        
        def on_export():
            sheet_url = entry_url.get().strip()
            email = entry_email.get().strip()
            
            if not sheet_url:
                messagebox.showwarning("入力エラー", "スプレッドシートURLを入力してください", parent=dialog)
                return
            
            dialog.destroy()
            self._export_sheets_async(sheet_url, email)
        
        ctk.CTkButton(dialog, text="出力実行", command=on_export, fg_color="#207f4c").pack(pady=20)
    
    def _export_sheets_async(self, sheet_url: str, email: str):
        """Sheets出力（非同期）"""
        self.status_label.configure(text="📊 Sheets出力中...")
        self.progress.pack(side="right", padx=10)
        self.progress.start()
        
        def task():
            try:
                # スプレッドシートエンジンの初期化
                if not self.spreadsheet_engine:
                    self.spreadsheet_engine = SpreadsheetEngine()
                
                # Web用シート
                url_web = self.spreadsheet_engine.sync_clusters(
                    self.web_clusters,
                    sheet_url,
                    worksheet_name="Web",
                    user_email=email or None
                )
                
                # PDF用シート
                url_pdf = self.spreadsheet_engine.sync_clusters(
                    self.pdf_clusters,
                    sheet_url,
                    worksheet_name="PDF",
                    user_email=email or None
                )
                
                self.after(0, lambda: messagebox.showinfo("完了", f"出力完了:\n{url_web}"))
                self.after(0, lambda: self.status_label.configure(text="✅ Sheets出力完了"))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("エラー", str(e)))
            finally:
                self.after(0, self._reset_progress)
        
        threading.Thread(target=task, daemon=True).start()
    
    def export_to_csv(self):
        """CSV出力"""
        if not self.comparison_results:
            messagebox.showwarning("警告", "先に比較を実行してください")
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        
        if path:
            try:
                self.comparator.export_to_csv(path)
                messagebox.showinfo("完了", f"CSVを出力しました:\n{path}")
            except Exception as e:
                messagebox.showerror("エラー", str(e))
    
    # =============== ユーティリティ ===============
    
    def _reset_progress(self):
        """プログレスバーをリセット"""
        self.progress.stop()
        self.progress.pack_forget()


def main():
    """メイン実行"""
    app = IntegrityVerificationApp()
    app.mainloop()


if __name__ == "__main__":
    main()

