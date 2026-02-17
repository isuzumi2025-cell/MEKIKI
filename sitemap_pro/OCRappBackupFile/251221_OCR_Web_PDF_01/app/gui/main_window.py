import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import sys
import os
import traceback

# パス設定
sys.path.append(os.getcwd())
from app.utils.file_loader import FileLoader
from app.core.engine_cloud import CloudOCREngine
from app.utils.project_handler import ProjectHandler
from app.utils.exporter import DataExporter
from app.core.scraper import WebScraper

# デザイン設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class OCRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI-OCR Workspace (Pro)")
        self.geometry("1200x900")

        # データ管理変数
        self.original_image = None
        self.image_full = None
        self.image_viewport = None
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
        self.result_container = None 
        
        self._last_folder_url = ""
        self._last_email = ""
        self._web_username = ""
        self._web_password = ""

        self._setup_ui()

    def _setup_ui(self):
        """UI構築"""
        # --- 上部ツールバー ---
        self.toolbar_top = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.toolbar_top.pack(side="top", fill="x", padx=0, pady=0)

        ctk.CTkButton(self.toolbar_top, text="📂 画像を開く", command=self.load_file, width=100).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(self.toolbar_top, text="🌐 Web読込", command=self.open_web_dialog, width=100, fg_color="#E08E00").pack(side="left", padx=5, pady=5)

        # 表示切替スイッチ（Web用）
        self.seg_view_mode = ctk.CTkSegmentedButton(self.toolbar_top, values=["全体", "1画面"], command=self.switch_view_mode)
        self.seg_view_mode.set("全体")
        self.seg_view_mode.pack(side="left", padx=10, pady=5)
        self.seg_view_mode.configure(state="disabled")

        ctk.CTkLabel(self.toolbar_top, text="|", text_color="gray").pack(side="left", padx=5)

        # ★追加: 範囲指定OCRモードスイッチ
        self.switch_partial_ocr = ctk.CTkSwitch(self.toolbar_top, text="範囲指定OCR", command=None)
        self.switch_partial_ocr.pack(side="left", padx=15, pady=5)

        ctk.CTkButton(self.toolbar_top, text="💾 保存", command=self.save_project, width=80, fg_color="gray").pack(side="left", padx=2, pady=5)
        ctk.CTkButton(self.toolbar_top, text="📂 読込", command=self.load_project, width=80, fg_color="gray").pack(side="left", padx=2, pady=5)
        
        ctk.CTkLabel(self.toolbar_top, text="   ").pack(side="left")
        self.btn_run = ctk.CTkButton(self.toolbar_top, text="▶ 全体AI解析", command=self.run_ocr_thread, fg_color="#1F6AA5", width=120)
        self.btn_run.pack(side="left", padx=10, pady=5)

        self.progress = ctk.CTkProgressBar(self.toolbar_top, mode='indeterminate', width=150)

        # --- 下部ツールバー ---
        self.toolbar_bottom = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.toolbar_bottom.pack(side="bottom", fill="x")

        ctk.CTkButton(self.toolbar_bottom, text="CSV出力", command=self.export_csv, width=100).pack(side="left", padx=5, pady=5)
        ctk.CTkButton(self.toolbar_bottom, text="Google Sheets出力", command=self.open_gsheet_dialog, fg_color="#207f4c").pack(side="left", padx=5, pady=5)
        
        ctk.CTkLabel(self.toolbar_bottom, text="|", text_color="gray").pack(side="left", padx=5)
        self.btn_detach = ctk.CTkButton(self.toolbar_bottom, text="🗔 ウィンドウ分離", command=self.toggle_window_mode, width=120, fg_color="#555")
        self.btn_detach.pack(side="left", padx=5, pady=5)

        # --- メインエリア ---
        self.paned = tk.PanedWindow(self, orient="vertical", bg="#2B2B2B", sashwidth=4)
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        # エディタエリア
        self.editor_frame = ctk.CTkFrame(self.paned, corner_radius=0)
        self.paned.add(self.editor_frame, height=500) 
        ctk.CTkLabel(self.editor_frame, text=" エディタエリア", font=("Arial", 12, "bold"), anchor="w").pack(fill="x", padx=5, pady=2)

        self.canvas_container = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        self.canvas_container.pack(fill="both", expand=True)

        self.v_scroll = tk.Scrollbar(self.canvas_container, orient="vertical")
        self.h_scroll = tk.Scrollbar(self.canvas_container, orient="horizontal")
        
        self.canvas = tk.Canvas(
            self.canvas_container, bg="#202020", highlightthickness=0,
            xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set
        )
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", lambda e: self._draw_canvas())

        # 結果エリア
        self.result_container = ctk.CTkFrame(self.paned, corner_radius=0)
        self.paned.add(self.result_container)
        self._build_result_area(self.result_container)

    def _build_result_area(self, parent):
        for widget in parent.winfo_children():
            widget.destroy()
        header = ctk.CTkLabel(parent, text=" 抽出テキスト (編集可能)", font=("Arial", 12, "bold"), anchor="w")
        header.pack(fill="x", padx=5, pady=2)
        self.txt_result = ctk.CTkTextbox(parent, font=("Meiryo", 12), wrap="word")
        self.txt_result.pack(fill="both", expand=True, padx=5, pady=5)
        self._update_text_area() 

    # --- 範囲指定OCR機能 (★新規) ---

    def _run_partial_ocr(self, rect_img):
        """指定された矩形範囲だけをクロップしてOCRにかける"""
        if not self.original_image: return
        
        try:
            # 1. 画像の切り抜き
            x0, y0, x1, y1 = rect_img
            # 座標が逆転している場合の対策 & 範囲チェック
            left, right = sorted([x0, x1])
            top, bottom = sorted([y0, y1])
            
            # 画像範囲内に収める
            w, h = self.original_image.size
            left = max(0, left); top = max(0, top)
            right = min(w, right); bottom = min(h, bottom)

            if (right - left) < 5 or (bottom - top) < 5:
                return # 小さすぎる場合は無視

            cropped_img = self.original_image.crop((left, top, right, bottom))

            # 2. OCR実行 (CloudOCREngineを流用)
            engine = CloudOCREngine()
            
            # CloudOCREngineは extract_text 内で画像をバイト変換してくれるのでそのまま渡す
            # ただし、結果は「全体のクラスタ」として返ってくるので、テキストだけ結合する
            new_clusters, _ = engine.extract_text(cropped_img)
            
            if not new_clusters:
                print("文字が見つかりませんでした")
                return

            # テキストを結合
            extracted_text = "\n".join([c["text"] for c in new_clusters])
            
            # 3. データを追加
            # 矩形は元の画像の座標で登録
            self.clusters.append({
                "rect": [left, top, right, bottom],
                "text": extracted_text
            })
            
            # 4. UI更新 (メインスレッドで実行)
            self.after(0, lambda: self._on_partial_ocr_success(extracted_text))

        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror("部分OCRエラー", str(e)))
        finally:
            self.after(0, self._reset_ui)

    def _on_partial_ocr_success(self, text):
        """部分OCR成功時の画面更新"""
        self._draw_canvas()
        
        # テキストエリアの末尾に追加
        current_text = self.txt_result.get("1.0", "end").strip()
        new_entry = f"\n\n━━━━━━━━━━ [追加OCR] ━━━━━━━━━━\n{text}"
        
        # 既存テキストが空なら改行なしで追加
        if not current_text:
            new_entry = f"━━━━━━━━━━ [追加OCR] ━━━━━━━━━━\n{text}"
            
        self.txt_result.insert("end", new_entry)
        self.txt_result.see("end") # 末尾へスクロール

    # --- マウスイベント (修正: スイッチによる分岐) ---

    def on_mouse_down(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # 既存枠の選択 (スイッチOFF時のみ)
        if not self.switch_partial_ocr.get():
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
        
        # 新規矩形作成開始
        self.selected_cluster_index = None
        self.start_x = cx
        self.start_y = cy
        color = "#FFAA00" if self.switch_partial_ocr.get() else "#00FF00" # モードで色分け
        self.current_rect_id = self.canvas.create_rectangle(cx, cy, cx, cy, outline=color, width=2, dash=(4, 4))

    def on_mouse_drag(self, event):
        if self.start_x is None: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self.canvas.coords(self.current_rect_id, self.start_x, self.start_y, cx, cy)

    def on_mouse_up(self, event):
        if self.start_x is None: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # クリックキャンセル判定
        if abs(cx - self.start_x) < 5 or abs(cy - self.start_y) < 5:
            self.canvas.delete(self.current_rect_id)
            self.start_x = None
            return

        x0, x1 = sorted([self.start_x, cx])
        y0, y1 = sorted([self.start_y, cy])
        
        # 画像座標系へ変換
        rect_img = [int(x0 / self.display_scale), int(y0 / self.display_scale), 
                    int(x1 / self.display_scale), int(y1 / self.display_scale)]
        
        self.canvas.delete(self.current_rect_id)
        self.start_x = None

        # ★分岐ポイント
        if self.switch_partial_ocr.get():
            # 【A】範囲指定OCRモード: 即座にOCRを実行
            self.progress.pack(side="left", padx=10)
            self.progress.start()
            threading.Thread(target=self._run_partial_ocr, args=(rect_img,), daemon=True).start()
        else:
            # 【B】通常編集モード: 既存のraw_wordsから文字を拾う (既存ロジック)
            new_text = self._extract_text_from_rect(rect_img)
            self.clusters.append({"rect": rect_img, "text": new_text})
            self._refresh_all()

    # --- Webスクレイピング ---

    def open_web_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Webページ読込設定")
        dialog.geometry("500x450")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Webページ読込 (高画質モード)", font=("Meiryo", 16, "bold")).pack(pady=10)
        ctk.CTkLabel(dialog, text="対象URL:", anchor="w").pack(fill="x", padx=20, pady=(5, 0))
        entry_url = ctk.CTkEntry(dialog, placeholder_text="https://...")
        entry_url.pack(fill="x", padx=20, pady=5)

        auth_frame = ctk.CTkFrame(dialog)
        auth_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(auth_frame, text="🔒 Basic認証 / ログイン情報 (必要な場合のみ)", font=("Meiryo", 11, "bold")).pack(pady=5)
        
        ctk.CTkLabel(auth_frame, text="ユーザー名:", anchor="w", font=("Meiryo", 10)).pack(fill="x", padx=10)
        entry_user = ctk.CTkEntry(auth_frame, height=25)
        entry_user.pack(fill="x", padx=10, pady=(0, 5))
        if self._web_username: entry_user.insert(0, self._web_username)

        ctk.CTkLabel(auth_frame, text="パスワード:", anchor="w", font=("Meiryo", 10)).pack(fill="x", padx=10)
        entry_pass = ctk.CTkEntry(auth_frame, show="*", height=25)
        entry_pass.pack(fill="x", padx=10, pady=(0, 10))
        if self._web_password: entry_pass.insert(0, self._web_password)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(pady=10)

        ctk.CTkLabel(dialog, text="※401エラーが出る場合は、上記にID/PASSを入力して\n「テキスト取得」を押してください。", font=("Meiryo", 10), text_color="gray").pack(pady=5)

        def on_scrape():
            url = entry_url.get().strip()
            user = entry_user.get().strip()
            pw = entry_pass.get().strip()
            if not url: return
            self._web_username = user
            self._web_password = pw
            dialog.destroy()
            self.progress.pack(side="left", padx=10)
            self.progress.start()
            threading.Thread(target=self._run_scrape, args=(url, user, pw), daemon=True).start()

        def on_auth_mode():
            url = entry_url.get().strip()
            if not url: return
            dialog.destroy()
            self._run_auth_browser(url)

        ctk.CTkButton(button_frame, text="🔑 認証モード(画面操作)", command=on_auth_mode, fg_color="#555", width=140).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="⬇ テキスト取得", command=on_scrape, fg_color="#1F6AA5", width=140).pack(side="left", padx=10)

    def _run_auth_browser(self, url):
        scraper = WebScraper()
        def wait_for_user_ok():
            messagebox.showinfo("手順", "ブラウザ操作が完了したら、\nこの画面のOKを押してください。")
        try:
            scraper.interactive_login(url, wait_for_user_ok)
            messagebox.showinfo("成功", "Cookieを保存しました。")
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("エラー", err_msg))

    def _run_scrape(self, url, user, pw):
        scraper = WebScraper()
        try:
            title, text, img_full, img_view = scraper.fetch_text(url, username=user, password=pw)
            # 初期状態: Webのテキストのみ
            self.clusters = [{
                "rect": [0, 0, 0, 0], 
                "text": f"【Title】 {title}\n\n{text}"
            }]
            self.image_full = img_full
            self.image_viewport = img_view
            self.original_image = self.image_full
            self.image_path = "Web_Screenshot.png"
            self.after(0, self._refresh_all_web_mode)
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("エラー", err_msg))
        finally:
            self.after(0, self._reset_ui)

    def _refresh_all_web_mode(self):
        self.seg_view_mode.configure(state="normal")
        self.seg_view_mode.set("全体")
        
        # ★追加: 部分OCRスイッチも有効化してONにする
        self.switch_partial_ocr.select()
        
        self._draw_canvas()
        self._update_text_area()
        self.title(f"AI-OCR Workspace (Pro) - Web Result")
        messagebox.showinfo("Web読込完了", "HTMLテキストを取得しました。\n\n【使い方】\n画面上部の「範囲指定OCR」がONになっています。\nバナーや画像文字をマウスで囲むと、そこだけ追加でOCRされます。")

    def switch_view_mode(self, value):
        if value == "全体":
            if self.image_full:
                self.original_image = self.image_full
        else:
            if self.image_viewport:
                self.original_image = self.image_viewport
        if hasattr(self, '_cached_image_id'): delattr(self, '_cached_image_id')
        self._draw_canvas()

    # --- 共通機能 ---
    def toggle_window_mode(self):
        if self.is_detached:
            if self.external_window:
                self.external_window.destroy()
                self.external_window = None
            self.result_container = ctk.CTkFrame(self.paned, corner_radius=0)
            self.paned.add(self.result_container)
            self._build_result_area(self.result_container)
            self.btn_detach.configure(text="🗔 ウィンドウ分離")
            self.is_detached = False
        else:
            self.paned.forget(self.result_container)
            self.external_window = ctk.CTkToplevel(self)
            self.external_window.title("抽出テキスト詳細")
            self.external_window.geometry("600x800")
            self.external_window.protocol("WM_DELETE_WINDOW", self.toggle_window_mode)
            self._build_result_area(self.external_window)
            self.btn_detach.configure(text="📥 ウィンドウ結合")
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
                self.image_full = None
                self.image_viewport = None
                self.seg_view_mode.configure(state="disabled")
                if not initial_path:
                    self.clusters = []
                    self.raw_words = []
                self._draw_canvas()
                self._update_text_area()
                self.title(f"AI-OCR Workspace (Pro) - {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def _draw_canvas(self):
        self.canvas.delete("all")
        if not self.original_image: return
        canvas_w = self.canvas.winfo_width()
        if canvas_w < 100: return
        img_w, img_h = self.original_image.size
        self.display_scale = canvas_w / img_w
        display_w = int(img_w * self.display_scale)
        display_h = int(img_h * self.display_scale)

        if hasattr(self, '_cached_image_size') and self._cached_image_size == (display_w, display_h) and getattr(self, '_cached_image_id', None) == id(self.original_image):
            pass
        else:
            self._resized_image = self.original_image.resize((display_w, display_h), Image.Resampling.LANCZOS)
            self._cached_image_size = (display_w, display_h)
            self._cached_image_id = id(self.original_image)
            self.tk_img = ImageTk.PhotoImage(self._resized_image)

        self.canvas.config(scrollregion=(0, 0, display_w, display_h))
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        for idx, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            color = "#00FFFF" if idx == self.selected_cluster_index else "#FF4444"
            width = 3 if idx == self.selected_cluster_index else 2
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=width, tags=f"box_{idx}")
            self.canvas.create_rectangle(x0, y0-20, x0+60, y0, fill=color, outline=color, tags=f"box_{idx}")
            self.canvas.create_text(x0+30, y0-10, text=f"Area {idx+1}", fill="white", font=("Arial", 9, "bold"), tags=f"box_{idx}")

    def run_ocr_thread(self):
        if not self.original_image: return
        self.btn_run.configure(state="disabled")
        self.progress.pack(side="left", padx=10)
        self.progress.start()
        threading.Thread(target=self._execute_ocr, daemon=True).start()

    def _execute_ocr(self):
        try:
            engine = CloudOCREngine()
            clusters, raw_words = engine.extract_text(self.original_image)
            self.clusters = clusters
            self.raw_words = raw_words
            self.after(0, self._refresh_all)
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("エラー", err_msg))
        finally:
            self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_run.configure(state="normal")

    def _refresh_all(self):
        self._draw_canvas()
        self._update_text_area()

    def _update_text_area(self):
        if not hasattr(self, 'txt_result') or not self.txt_result.winfo_exists(): return
        self.txt_result.delete("1.0", "end")
        output = []
        for i, cluster in enumerate(self.clusters):
            # 追加OCRと通常エリアで見出しを変える工夫
            label = "追加OCR" if "追加" in cluster.get("note", "") else f"Area {i+1}"
            header = f"━━━━━━━━━━ [{label}] ━━━━━━━━━━"
            content = cluster["text"]
            output.append(header)
            output.append(content)
            output.append("")
        self.txt_result.insert("end", "\n".join(output))

    def on_right_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        for i, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                del self.clusters[i]
                self.selected_cluster_index = None
                self._refresh_all()
                return

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

    def open_gsheet_dialog(self):
        if not self.clusters: return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Google Sheets 出力設定")
        dialog.geometry("500x380")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Google Sheets 出力", font=("Meiryo", 16, "bold")).pack(pady=15)
        ctk.CTkLabel(dialog, text="スプレッドシートのURL (推奨):", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_name = ctk.CTkEntry(dialog, placeholder_text="https://docs.google.com/spreadsheets/...")
        entry_name.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(dialog, text="または保存先フォルダのURL:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_folder = ctk.CTkEntry(dialog)
        entry_folder.pack(fill="x", padx=20, pady=5)
        if self._last_folder_url: entry_folder.insert(0, self._last_folder_url)
        ctk.CTkLabel(dialog, text="共有するGmailアドレス:", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_email = ctk.CTkEntry(dialog)
        entry_email.pack(fill="x", padx=20, pady=5)
        if self._last_email: entry_email.insert(0, self._last_email)

        def on_submit():
            sheet_input = entry_name.get().strip()
            folder_url = entry_folder.get().strip()
            user_email = entry_email.get().strip()
            if not sheet_input:
                messagebox.showwarning("必須", "スプレッドシートのURL（または名前）を入力してください", parent=dialog)
                return
            self._last_folder_url = folder_url
            self._last_email = user_email
            dialog.destroy()
            self.progress.pack(side="left", padx=10)
            self.progress.start()
            threading.Thread(target=self._run_gsheet_export, args=(sheet_input, user_email, folder_url), daemon=True).start()

        ctk.CTkButton(dialog, text="出力実行", command=on_submit, fg_color="#207f4c").pack(pady=20)

    def _run_gsheet_export(self, sheet_input, user_email, folder_url):
        try:
            url = DataExporter.export_to_gsheet(sheet_input, self.clusters, user_email, folder_url)
            self.after(0, lambda: messagebox.showinfo("成功", f"出力しました:\n{url}"))
        except Exception as e:
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror("エラー", f"失敗しました:\n{str(e)}"))
        finally:
            self.after(0, self._reset_ui)

    def export_csv(self):
        if not self.clusters: return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                DataExporter.export_to_csv(path, self.clusters)
                messagebox.showinfo("完了", "CSVを出力しました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def save_project(self):
        if not self.image_path or not self.clusters: return
        target_dir = filedialog.askdirectory(title="保存先フォルダ")
        if target_dir:
            try:
                ProjectHandler.save_project(target_dir, self.image_path, self.clusters)
                messagebox.showinfo("完了", "保存しました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

    def load_project(self):
        target_dir = filedialog.askdirectory(title="プロジェクト読込")
        if target_dir:
            try:
                img_path, clusters = ProjectHandler.load_project(target_dir)
                self.load_file(initial_path=img_path)
                self.clusters = clusters
                self._refresh_all()
                messagebox.showinfo("完了", "読み込みました")
            except Exception as e:
                messagebox.showerror("エラー", str(e))

if __name__ == "__main__":
    app = OCRApp()
    app.mainloop()