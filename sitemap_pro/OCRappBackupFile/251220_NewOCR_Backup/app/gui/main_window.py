import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from PIL import Image, ImageTk
import threading
import sys
import os
import traceback

sys.path.append(os.getcwd())
from app.utils.file_loader import FileLoader
from app.core.engine_cloud import CloudOCREngine
from app.utils.project_handler import ProjectHandler
from app.utils.exporter import DataExporter

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("高精度OCRエディタ (Pro版: 保存・出力機能付き)")
        self.root.geometry("1200x900")

        self.original_image = None
        self.image_path = None
        self.raw_words = []
        self.clusters = []
        self.display_scale = 1.0
        
        self.start_x = None
        self.start_y = None
        self.current_rect_id = None
        self.selected_cluster_index = None

        self.is_detached = False
        self.external_window = None
        
        self._setup_ui()

    def _setup_ui(self):
        # ツールバー構成
        toolbar_top = ttk.Frame(self.root, padding=2)
        toolbar_top.pack(fill=tk.X)
        toolbar_bottom = ttk.Frame(self.root, padding=2)
        toolbar_bottom.pack(fill=tk.X)
        
        # 上段
        ttk.Button(toolbar_top, text="📂 画像を開く", command=self.load_file).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar_top, text="|").pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_top, text="💾 プロジェクト保存", command=self.save_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_top, text="📂 プロジェクト読込", command=self.load_project).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar_top, text="   ").pack(side=tk.LEFT)
        self.btn_run = ttk.Button(toolbar_top, text="▶ 自動解析実行", command=self.run_ocr_thread)
        self.btn_run.pack(side=tk.LEFT, padx=5)

        # 下段
        ttk.Button(toolbar_bottom, text="📊 CSV出力", command=self.export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_bottom, text="Google Sheets出力", command=self.open_gsheet_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar_bottom, text="|").pack(side=tk.LEFT, padx=5)
        self.btn_detach = ttk.Button(toolbar_bottom, text="🗔 ウィンドウ分離", command=self.toggle_window_mode)
        self.btn_detach.pack(side=tk.LEFT, padx=2)
        
        self.progress = ttk.Progressbar(toolbar_top, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)

        # メインエリア
        self.paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas_frame = ttk.Labelframe(self.paned, text="エディタ")
        self.paned.add(self.canvas_frame, weight=3)
        
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#F0F0F0", 
                                xscrollcommand=self.h_scroll.set, 
                                yscrollcommand=self.v_scroll.set)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", lambda e: self._draw_canvas())

        self.result_container = ttk.Frame(self.paned)
        self.paned.add(self.result_container, weight=1)
        self._build_result_area(self.result_container)

    def _build_result_area(self, parent_frame):
        for widget in parent_frame.winfo_children():
            widget.destroy()
        lbl_frame = ttk.Labelframe(parent_frame, text="抽出テキスト (エリア別)")
        lbl_frame.pack(fill=tk.BOTH, expand=True)
        self.txt_result = scrolledtext.ScrolledText(lbl_frame, font=("Meiryo", 10), height=10)
        self.txt_result.pack(fill=tk.BOTH, expand=True)
        self._update_text_area()

    # --- Google Sheets 出力用 専用ダイアログ (修正版) ---

    def open_gsheet_dialog(self):
        if not self.clusters: return

        dialog = tk.Toplevel(self.root)
        dialog.title("Google Sheets 出力設定")
        dialog.geometry("500x350") # 少し縦長に
        dialog.transient(self.root)
        dialog.grab_set()

        # 1. シート名
        ttk.Label(dialog, text="スプレッドシート名:").pack(anchor=tk.W, padx=20, pady=(20, 5))
        default_name = f"OCR_Result_{os.path.basename(self.image_path or 'data')}"
        entry_name = ttk.Entry(dialog, width=50)
        entry_name.insert(0, default_name)
        entry_name.pack(padx=20, pady=5)

        # 2. 保存先フォルダURL (追加機能)
        ttk.Label(dialog, text="保存先フォルダのURL (推奨):\n※空欄の場合はルートに作成されます").pack(anchor=tk.W, padx=20, pady=(15, 5))
        entry_folder = ttk.Entry(dialog, width=50)
        entry_folder.pack(padx=20, pady=5)
        
        # 前回のフォルダURLを復元
        if hasattr(self, '_last_folder_url'):
            entry_folder.insert(0, self._last_folder_url)

        # 3. メールアドレス
        ttk.Label(dialog, text="共有するGmailアドレス:").pack(anchor=tk.W, padx=20, pady=(15, 5))
        entry_email = ttk.Entry(dialog, width=50)
        entry_email.pack(padx=20, pady=5)
        
        if hasattr(self, '_last_email'):
            entry_email.insert(0, self._last_email)

        def on_submit():
            sheet_name = entry_name.get().strip()
            folder_url = entry_folder.get().strip()
            user_email = entry_email.get().strip()
            
            if not sheet_name:
                messagebox.showwarning("入力エラー", "シート名を入力してください", parent=dialog)
                return
            if not user_email:
                messagebox.showwarning("入力エラー", "メールアドレスを入力してください", parent=dialog)
                return
            
            # 入力値を記憶
            self._last_email = user_email
            self._last_folder_url = folder_url
            
            dialog.destroy()
            self.progress.start(10)
            threading.Thread(target=self._run_gsheet_export, args=(sheet_name, user_email, folder_url), daemon=True).start()

        ttk.Button(dialog, text="出力開始", command=on_submit).pack(pady=20)

    def _run_gsheet_export(self, sheet_name, user_email, folder_url):
        try:
            # folder_url 引数を追加
            url = DataExporter.export_to_gsheet(sheet_name, self.clusters, user_email, folder_url)
            self.root.after(0, lambda: messagebox.showinfo("完了", f"スプレッドシートを作成しました\nURL: {url}"))
        except Exception as e:
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("エラー", f"出力失敗: {str(e)}\n※詳細はターミナルを確認してください"))
        finally:
            self.root.after(0, self.progress.stop)

    # --- 以下、既存機能 ---
    
    def save_project(self):
        if not self.image_path or not self.clusters:
            messagebox.showwarning("警告", "保存するデータがありません")
            return
        target_dir = filedialog.askdirectory(title="保存先フォルダを選択")
        if target_dir:
            try:
                ProjectHandler.save_project(target_dir, self.image_path, self.clusters)
                messagebox.showinfo("完了", "プロジェクトを保存しました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def load_project(self):
        target_dir = filedialog.askdirectory(title="プロジェクトフォルダを選択")
        if target_dir:
            try:
                img_path, clusters = ProjectHandler.load_project(target_dir)
                self.load_file(initial_path=img_path)
                self.clusters = clusters
                self._refresh_all()
                messagebox.showinfo("完了", "プロジェクトを読み込みました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def export_csv(self):
        if not self.clusters: return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                DataExporter.export_to_csv(path, self.clusters)
                messagebox.showinfo("完了", "CSVファイルを出力しました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def toggle_window_mode(self):
        if self.is_detached:
            if self.external_window:
                self.external_window.destroy()
                self.external_window = None
            self.result_container = ttk.Frame(self.paned)
            self.paned.add(self.result_container, weight=1)
            self._build_result_area(self.result_container)
            self.btn_detach.config(text="🗔 ウィンドウ分離")
            self.is_detached = False
        else:
            self.paned.forget(self.result_container)
            self.external_window = tk.Toplevel(self.root)
            self.external_window.title("抽出テキスト結果")
            self.external_window.geometry("600x800")
            self.external_window.protocol("WM_DELETE_WINDOW", self.toggle_window_mode)
            self._build_result_area(self.external_window)
            self.btn_detach.config(text="📥 ウィンドウ結合")
            self.is_detached = True

    def load_file(self, initial_path=None):
        if initial_path:
            path = initial_path
        else:
            path = filedialog.askopenfilename(filetypes=[("Image/PDF", "*.png;*.jpg;*.jpeg;*.pdf")])
        if path:
            try:
                images = FileLoader.load_file(path)
                self.original_image = images[0]
                self.image_path = path
                if not initial_path:
                    self.clusters = []
                    self.raw_words = []
                self._draw_canvas()
                self._update_text_area()
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def _draw_canvas(self):
        self.canvas.delete("all")
        if not self.original_image: return
        canvas_w = self.canvas.winfo_width()
        if canvas_w < 100: canvas_w = 800
        img_w, img_h = self.original_image.size
        self.display_scale = canvas_w / img_w
        display_w = int(img_w * self.display_scale)
        display_h = int(img_h * self.display_scale)
        if hasattr(self, '_cached_image_size') and self._cached_image_size == (display_w, display_h):
            pass
        else:
            self._resized_image = self.original_image.resize((display_w, display_h), Image.Resampling.LANCZOS)
            self._cached_image_size = (display_w, display_h)
            self.tk_img = ImageTk.PhotoImage(self._resized_image)
        self.canvas.config(scrollregion=(0, 0, display_w, display_h))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        for idx, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            color = "blue" if idx == self.selected_cluster_index else "red"
            width = 3 if idx == self.selected_cluster_index else 2
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=width, tags=f"box_{idx}")
            self.canvas.create_rectangle(x0, y0-20, x0+60, y0, fill=color, outline=color, tags=f"box_{idx}")
            self.canvas.create_text(x0+30, y0-10, text=f"Area {idx+1}", fill="white", tags=f"box_{idx}")

    def run_ocr_thread(self):
        if not self.original_image: return
        self.btn_run.config(state=tk.DISABLED)
        self.progress.start(10)
        threading.Thread(target=self._execute_ocr, daemon=True).start()

    def _execute_ocr(self):
        try:
            engine = CloudOCREngine()
            clusters, raw_words = engine.extract_text(self.original_image)
            self.clusters = clusters
            self.raw_words = raw_words
            self.root.after(0, self._refresh_all)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", str(e)))
        finally:
            self.root.after(0, self._reset_ui)

    def _refresh_all(self):
        self._draw_canvas()
        self._update_text_area()

    def _update_text_area(self):
        if not hasattr(self, 'txt_result') or not self.txt_result.winfo_exists(): return
        self.txt_result.delete(1.0, tk.END)
        output = []
        for i, cluster in enumerate(self.clusters):
            header = f"━━━━━━━━━━ [Area {i+1}] ━━━━━━━━━━"
            content = cluster["text"]
            output.append(header)
            output.append(content)
            output.append("")
        self.txt_result.insert(tk.END, "\n".join(output))

    def _reset_ui(self):
        self.progress.stop()
        self.btn_run.config(state=tk.NORMAL)

    def on_mouse_down(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked_index = None
        for i, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                clicked_index = i
                break
        if clicked_index is not None:
            self.selected_cluster_index = clicked_index
            self._draw_canvas()
            return
        self.selected_cluster_index = None
        self.start_x = cx
        self.start_y = cy
        self.current_rect_id = self.canvas.create_rectangle(cx, cy, cx, cy, outline="green", width=2, dash=(4, 4))

    def on_mouse_drag(self, event):
        if self.start_x is None: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self.canvas.coords(self.current_rect_id, self.start_x, self.start_y, cx, cy)

    def on_mouse_up(self, event):
        if self.start_x is None: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if abs(cx - self.start_x) < 10 or abs(cy - self.start_y) < 10:
            self.canvas.delete(self.current_rect_id)
            self.start_x = None
            return
        x0, x1 = sorted([self.start_x, cx])
        y0, y1 = sorted([self.start_y, cy])
        rect_img = [int(x0 / self.display_scale), int(y0 / self.display_scale), int(x1 / self.display_scale), int(y1 / self.display_scale)]
        new_text = self._extract_text_from_rect(rect_img)
        self.clusters.append({"rect": rect_img, "text": new_text})
        self.start_x = None
        self.canvas.delete(self.current_rect_id)
        self._refresh_all()

    def on_right_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        target_index = None
        for i, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                target_index = i
                break
        if target_index is not None:
            del self.clusters[target_index]
            self.selected_cluster_index = None
            self._refresh_all()

    def _extract_text_from_rect(self, rect):
        if not self.raw_words: return ""
        x0, y0, x1, y1 = rect
        included_words = []
        for word in self.raw_words:
            wx, wy = word["center"]
            if x0 <= wx <= x1 and y0 <= wy <= y1:
                included_words.append(word)
        included_words.sort(key=lambda w: (round(w["rect"][1]/20)*20, w["rect"][0]))
        lines = []
        current_line = []
        last_y = -1
        for w in included_words:
            cy = w["center"][1]
            if last_y != -1 and abs(cy - last_y) > 20:
                lines.append("".join(current_line))
                current_line = []
            current_line.append(w["text"])
            last_y = cy
        if current_line: lines.append("".join(current_line))
        return "\n".join(lines)

if __name__ == "__main__":
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()