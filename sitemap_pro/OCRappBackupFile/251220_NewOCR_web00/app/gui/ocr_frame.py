import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import threading
import os
import sys

# Import core engines
from app.utils.file_loader import FileLoader
from app.core.engine_cloud import CloudOCREngine
from app.utils.project_handler import ProjectHandler
from app.utils.exporter import DataExporter

class OCRFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Data Models
        self.original_image = None
        self.image_path = None
        self.raw_words = []
        self.clusters = []
        self.display_scale = 1.0
        
        # Canvas Interaction State
        self.start_x = None
        self.start_y = None
        self.current_rect_id = None
        self.selected_cluster_index = None

        # External Window State
        self.is_detached = False
        self.external_window = None
        self.result_container = None 
        
        # Export Settings Memory
        self._last_folder_url = ""
        self._last_email = ""

        self._setup_ui()

    def _setup_ui(self):
        """Construct the Genius Interface"""
        # --- Top Toolbar (Glass Effect Style) ---
        self.toolbar_top = ctk.CTkFrame(self, height=45, corner_radius=10, fg_color=("gray90", "#2b2b2b"))
        self.toolbar_top.pack(side="top", fill="x", padx=10, pady=(10, 5))

        # File Operations
        ctk.CTkButton(self.toolbar_top, text="📂 Open Image", command=self.load_file, width=120, height=32, corner_radius=16).pack(side="left", padx=5, pady=5)
        
        # Save/Load Project (Subtle)
        ctk.CTkButton(self.toolbar_top, text="💾 Save", command=self.save_project, width=80, height=32, fg_color="transparent", border_width=1, text_color=("gray10", "gray90")).pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar_top, text="📂 Load", command=self.load_project, width=80, height=32, fg_color="transparent", border_width=1, text_color=("gray10", "gray90")).pack(side="left", padx=5)

        # Spacer
        ctk.CTkLabel(self.toolbar_top, text="").pack(side="left", expand=True)

        # AI Execution (Prominent)
        self.btn_run = ctk.CTkButton(self.toolbar_top, text="✨ Analyze with AI", command=self.run_ocr_thread, 
                                     fg_color="#4F46E5", hover_color="#4338CA", width=160, height=32, corner_radius=16, font=("Arial", 13, "bold"))
        self.btn_run.pack(side="right", padx=10)

        self.progress = ctk.CTkProgressBar(self.toolbar_top, mode='indeterminate', width=200, height=8)
        # Progress packed only when running

        # --- Main Split Area ---
        self.paned = tk.PanedWindow(self, orient="horizontal", bg="#1a1a1a", sashwidth=6, showhandle=True)
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        # 1. Image Canvas Area (Left/Top)
        self.editor_frame = ctk.CTkFrame(self.paned, corner_radius=0, fg_color="transparent")
        self.paned.add(self.editor_frame, minsize=400, stretch="always")

        # Canvas Controls
        canvas_ctrl = ctk.CTkFrame(self.editor_frame, height=30, fg_color="transparent")
        canvas_ctrl.pack(fill="x")
        ctk.CTkLabel(canvas_ctrl, text="👁️ Visual Input", font=("Arial", 12, "bold"), text_color="gray").pack(side="left", padx=5)

        self.canvas_container = ctk.CTkFrame(self.editor_frame, fg_color="#101010", corner_radius=10)
        self.canvas_container.pack(fill="both", expand=True)

        self.v_scroll = tk.Scrollbar(self.canvas_container, orient="vertical")
        self.h_scroll = tk.Scrollbar(self.canvas_container, orient="horizontal")
        
        self.canvas = tk.Canvas(
            self.canvas_container, bg="#101010", highlightthickness=0,
            xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set
        )
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", lambda e: self._draw_canvas())

        # 2. Result Editor Area (Right/Bottom)
        self.result_container = ctk.CTkFrame(self.paned, corner_radius=0, fg_color="transparent")
        self.paned.add(self.result_container, minsize=300, stretch="always")
        self._build_result_area(self.result_container)

        # --- Footer Toolbar ---
        self.toolbar_bottom = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="transparent")
        self.toolbar_bottom.pack(side="bottom", fill="x", padx=10, pady=5)

        ctk.CTkButton(self.toolbar_bottom, text="Export CSV", command=self.export_csv, width=100, height=28, fg_color="#333", hover_color="#444").pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar_bottom, text="Export G-Sheets", command=self.open_gsheet_dialog, width=120, height=28, fg_color="#107f4c", hover_color="#0e6b3f").pack(side="left", padx=5)
        
        self.btn_detach = ctk.CTkButton(self.toolbar_bottom, text="🗔 Detach Editor", command=self.toggle_window_mode, width=120, height=28, fg_color="#555", hover_color="#666")
        self.btn_detach.pack(side="right", padx=5)

    def _build_result_area(self, parent):
        for widget in parent.winfo_children():
            widget.destroy()
        
        ctrl_frame = ctk.CTkFrame(parent, height=30, fg_color="transparent")
        ctrl_frame.pack(fill="x")
        ctk.CTkLabel(ctrl_frame, text="📝 Digital Twin (Text)", font=("Arial", 12, "bold"), text_color="gray").pack(side="left", padx=5)

        self.txt_result = ctk.CTkTextbox(parent, font=("Meiryo", 12), wrap="word", corner_radius=10, fg_color="#1a1a1a", border_color="#333", border_width=1)
        self.txt_result.pack(fill="both", expand=True, pady=5)
        self._update_text_area() 

    # --- File & Project Operations ---
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
                # Try to access master window title if available
                try: print(f"Loaded: {os.path.basename(path)}")
                except: pass
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def save_project(self):
        if not self.image_path or not self.clusters: return
        target_dir = filedialog.askdirectory(title="Select Save Directory")
        if target_dir:
            try:
                ProjectHandler.save_project(target_dir, self.image_path, self.clusters)
                messagebox.showinfo("Saved", "Project saved successfully.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def load_project(self):
        target_dir = filedialog.askdirectory(title="Select Project Directory")
        if target_dir:
            try:
                img_path, clusters = ProjectHandler.load_project(target_dir)
                self.load_file(initial_path=img_path)
                self.clusters = clusters
                self._refresh_all()
                messagebox.showinfo("Loaded", "Project loaded successfully.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # --- Canvas Drawing & Logic ---
    def _draw_canvas(self):
        self.canvas.delete("all")
        if not self.original_image: return
        canvas_w = self.canvas.winfo_width()
        if canvas_w < 50: return # Too small
        
        img_w, img_h = self.original_image.size
        self.display_scale = canvas_w / img_w
        display_w = int(img_w * self.display_scale)
        display_h = int(img_h * self.display_scale)

        # Cache resized image for performance
        if hasattr(self, '_cached_image_size') and self._cached_image_size == (display_w, display_h):
            pass
        else:
            self._resized_image = self.original_image.resize((display_w, display_h), Image.Resampling.LANCZOS)
            self._cached_image_size = (display_w, display_h)
            self.tk_img = ImageTk.PhotoImage(self._resized_image)

        self.canvas.config(scrollregion=(0, 0, display_w, display_h))
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

        # Draw Clusters
        for idx, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            
            # Smart Coloring
            is_selected = (idx == self.selected_cluster_index)
            color = "#00FFFF" if is_selected else "#FF4444"
            width = 3 if is_selected else 1
            
            # Bounding Box
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=width, tags=f"box_{idx}")
            
            # Label Tag
            self.canvas.create_rectangle(x0, y0-18, x0+50, y0, fill=color, outline=color, tags=f"box_{idx}")
            self.canvas.create_text(x0+25, y0-9, text=f"#{idx+1}", fill="black" if is_selected else "white", font=("Arial", 9, "bold"), tags=f"box_{idx}")

    def run_ocr_thread(self):
        if not self.original_image: return
        self.btn_run.configure(state="disabled")
        self.progress.pack(side="right", padx=10) # Show progress next to button
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
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
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
            header = f"--- [Block {i+1}] ---"
            content = cluster["text"]
            output.append(header)
            output.append(content)
            output.append("")
        self.txt_result.insert("end", "\n".join(output))

    # --- Mouse Interaction ---
    def on_mouse_down(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked_index = None
        
        # Check for existing cluster click
        for i, cluster in enumerate(self.clusters):
            x0, y0, x1, y1 = [v * self.display_scale for v in cluster["rect"]]
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                clicked_index = i
                break
        
        if clicked_index is not None:
            self.selected_cluster_index = clicked_index
            self._draw_canvas()
            return
            
        # Start new selection
        self.selected_cluster_index = None
        self.start_x = cx
        self.start_y = cy
        self.current_rect_id = self.canvas.create_rectangle(cx, cy, cx, cy, outline="#00FF00", width=2, dash=(4, 4))

    def on_mouse_drag(self, event):
        if self.start_x is None: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self.canvas.coords(self.current_rect_id, self.start_x, self.start_y, cx, cy)

    def on_mouse_up(self, event):
        if self.start_x is None: return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # Ignore small clicks
        if abs(cx - self.start_x) < 5 or abs(cy - self.start_y) < 5:
            self.canvas.delete(self.current_rect_id)
            self.start_x = None
            return
            
        x0, x1 = sorted([self.start_x, cx])
        y0, y1 = sorted([self.start_y, cy])
        
        # Convert back to image coordinates
        img_rect = [int(v / self.display_scale) for v in [x0, y0, x1, y1]]
        new_text = self._extract_text_from_rect(img_rect)
        
        self.clusters.append({"rect": img_rect, "text": new_text})
        self.start_x = None
        self.canvas.delete(self.current_rect_id)
        self._refresh_all()

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
        # Sort by Y then X
        included_words.sort(key=lambda w: (round(w["rect"][1]/20)*20, w["rect"][0]))
        
        lines = []
        current_line = []
        last_y = -1
        for w in included_words:
            cy = w["center"][1]
            if last_y != -1 and abs(cy - last_y) > 20: # New line threshold
                lines.append("".join(current_line))
                current_line = []
            current_line.append(w["text"])
            last_y = cy
        if current_line: lines.append("".join(current_line))
        return "\n".join(lines)

    # --- Export Features ---
    def toggle_window_mode(self):
        """Toggle between split-view and detached window for editor"""
        if self.is_detached:
            if self.external_window:
                self.external_window.destroy()
                self.external_window = None
            # Re-attach
            self.result_container = ctk.CTkFrame(self.paned, corner_radius=0, fg_color="transparent")
            self.paned.add(self.result_container, minsize=300, stretch="always")
            self._build_result_area(self.result_container)
            self.btn_detach.configure(text="🗔 Detach Editor")
            self.is_detached = False
        else:
            # Detach
            self.paned.forget(self.result_container)
            self.external_window = ctk.CTkToplevel(self)
            self.external_window.title("Text Editor (Detached)")
            self.external_window.geometry("600x800")
            self.external_window.protocol("WM_DELETE_WINDOW", self.toggle_window_mode)
            
            # Build floating UI
            container = ctk.CTkFrame(self.external_window, fg_color="transparent")
            container.pack(fill="both", expand=True)
            self._build_result_area(container)
            
            self.btn_detach.configure(text="📥 Attach Editor")
            self.is_detached = True

    def open_gsheet_dialog(self):
        if not self.clusters: return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Export to Google Sheets")
        dialog.geometry("500x380")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Google Sheets Export", font=("Arial", 16, "bold")).pack(pady=15)
        
        ctk.CTkLabel(dialog, text="Spreadsheet URL (or Name):", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_name = ctk.CTkEntry(dialog, placeholder_text="e.g. https://docs.google.com/spreadsheets/...")
        entry_name.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(dialog, text="Destination Folder URL (Optional):", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_folder = ctk.CTkEntry(dialog)
        entry_folder.pack(fill="x", padx=20, pady=5)
        if self._last_folder_url: entry_folder.insert(0, self._last_folder_url)
        
        ctk.CTkLabel(dialog, text="Share with Email (Optional):", anchor="w").pack(fill="x", padx=20, pady=(10, 0))
        entry_email = ctk.CTkEntry(dialog)
        entry_email.pack(fill="x", padx=20, pady=5)
        if self._last_email: entry_email.insert(0, self._last_email)

        def on_submit():
            sheet_input = entry_name.get().strip()
            folder_url = entry_folder.get().strip()
            user_email = entry_email.get().strip()
            if not sheet_input:
                messagebox.showwarning("Required", "Please provide a Spreadsheet URL or Name.", parent=dialog)
                return
            
            self._last_folder_url = folder_url
            self._last_email = user_email
            dialog.destroy()
            
            # Show progress
            self.btn_run.configure(state="disabled") # Lock main UI
            
            def task():
                try:
                    url = DataExporter.export_to_gsheet(sheet_input, self.clusters, user_email, folder_url)
                    messagebox.showinfo("Success", f"Export Complete!\n{url}")
                    webbrowser.open(url)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    messagebox.showerror("Export Failed", str(e))
                finally:
                    self.btn_run.configure(state="normal")
            
            threading.Thread(target=task, daemon=True).start()

        ctk.CTkButton(dialog, text="Export Now", command=on_submit, fg_color="#107f4c", hover_color="#0e6b3f").pack(pady=20)
    
    def export_csv(self):
        if not self.clusters: return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            try:
                DataExporter.export_to_csv(path, self.clusters)
                messagebox.showinfo("Success", "CSV file saved.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
