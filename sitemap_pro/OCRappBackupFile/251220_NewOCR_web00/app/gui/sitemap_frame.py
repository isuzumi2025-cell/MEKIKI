import customtkinter as ctk
import threading
import webbrowser
import os
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from app.core.scraper import WebScraper
from app.core.sitemap_generator import SitemapGenerator
from app.core.comparator import Comparator

class SitemapFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.nodes = [] # Sitemap data
        self.edges = []
        self.sitemap_path = ""
        
        self._setup_ui()

    def _setup_ui(self):
        # 2 columns: Left (Controls/Sitemap), Right (Comparison)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left Panel: Visual Sitemap ---
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(left_panel, text="🌐 Visual Sitemap Generator", font=("Arial", 16, "bold")).pack(anchor="w", pady=5)
        
        # URL Input
        input_frame = ctk.CTkFrame(left_panel)
        input_frame.pack(fill="x", pady=5)
        self.entry_url = ctk.CTkEntry(input_frame, placeholder_text="Enter Root URL (e.g. https://docs.python.org/)")
        self.entry_url.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        self.btn_generate = ctk.CTkButton(input_frame, text="Generate Map", command=self.run_generation, fg_color="#1F6AA5")
        self.btn_generate.pack(side="right", padx=5, pady=5)
        
        # Status / Open Button
        self.lbl_status = ctk.CTkLabel(left_panel, text="Ready", text_color="gray")
        self.lbl_status.pack(pady=5)
        
        self.btn_open = ctk.CTkButton(left_panel, text="Open Interactive Sitemap ↗", state="disabled", command=self.open_sitemap_html, fg_color="#207f4c")
        self.btn_open.pack(fill="x", pady=10)

        # --- Authentication Section (New) ---
        auth_expander = ctk.CTkFrame(left_panel)
        auth_expander.pack(fill="x", pady=5)
        
        self.auth_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(auth_expander, text="🔒 Authentication Required", variable=self.auth_var, command=self._toggle_auth).pack(anchor="w", padx=5, pady=5)
        
        self.auth_frame = ctk.CTkFrame(auth_expander)
        # Initially hidden, will be packed in _toggle_auth if checked
        
        ctk.CTkLabel(self.auth_frame, text="Username:", font=("Arial", 10)).pack(anchor="w", padx=5)
        self.entry_user = ctk.CTkEntry(self.auth_frame, height=24)
        self.entry_user.pack(fill="x", padx=5, pady=(0,5))
        
        ctk.CTkLabel(self.auth_frame, text="Password:", font=("Arial", 10)).pack(anchor="w", padx=5)
        self.entry_pass = ctk.CTkEntry(self.auth_frame, height=24, show="*")
        self.entry_pass.pack(fill="x", padx=5, pady=(0,5))
        
        ctk.CTkButton(self.auth_frame, text="🔑 Interactive Login (Cookie)", command=self._run_interactive_login, height=24, fg_color="#555").pack(fill="x", padx=5, pady=5)

        # Node List (for manual selection)
        ctk.CTkLabel(left_panel, text="Detected Nodes (Select for Compare):", anchor="w").pack(fill="x", pady=(10, 0))
        self.node_listbox = ctk.CTkScrollableFrame(left_panel, height=300)
        self.node_listbox.pack(fill="both", expand=True, pady=5)
        self.radio_var = ctk.StringVar(value="")


        # --- Right Panel: Sync Rate Comparison ---
        right_panel = ctk.CTkFrame(self, fg_color=("#333", "#2b2b2b"))
        right_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(right_panel, text="⚖️ Alignment & Comparison", font=("Arial", 16, "bold")).pack(anchor="w", pady=5, padx=10)
        
        # Target Selection
        target_frame = ctk.CTkFrame(right_panel)
        target_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(target_frame, text="Target OCR Text:").pack(anchor="w", padx=5)
        self.txt_target_preview = ctk.CTkTextbox(target_frame, height=80)
        self.txt_target_preview.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(target_frame, text="Load from Clipboard", command=self.load_target_clipboard, width=150).pack(pady=5)

        # Action
        self.btn_compare = ctk.CTkButton(right_panel, text="Calculate Sync Rate", command=self.run_comparison, fg_color="#E08E00", state="disabled")
        self.btn_compare.pack(fill="x", padx=10, pady=15)
        
        # Result
        self.result_frame = ctk.CTkScrollableFrame(right_panel)
        self.result_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.lbl_sync_rate = ctk.CTkLabel(self.result_frame, text="Sync Rate: -%", font=("Arial", 24, "bold"))
        self.lbl_sync_rate.pack(pady=10)
        self.txt_diff = ctk.CTkTextbox(self.result_frame, font=("Consolas", 12))
        self.txt_diff.pack(fill="both", expand=True)

    def _toggle_auth(self):
        if self.auth_var.get():
            self.auth_frame.pack(fill="x", padx=5, pady=5)
        else:
            self.auth_frame.pack_forget()

    def _run_interactive_login(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter the Root URL first.")
            return
            
        def wait_for_user_ok():
            messagebox.showinfo("Interactive Login", "Please log in using the browser window.\nClick OK here once you are logged in.")

        threading.Thread(target=self._interactive_login_task, args=(url, wait_for_user_ok), daemon=True).start()

    def _interactive_login_task(self, url, cb):
        try:
            scraper = WebScraper()
            scraper.interactive_login(url, cb)
            self.after(0, lambda: messagebox.showinfo("Success", "Session/Cookies saved successfully."))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def run_generation(self):
        url = self.entry_url.get().strip()
        if not url: return
        
        user = self.entry_user.get().strip() if self.auth_var.get() else None
        password = self.entry_pass.get().strip() if self.auth_var.get() else None
        
        self.btn_generate.configure(state="disabled")
        self.lbl_status.configure(text="🕷️ Crawling & Photographing pages...")
        self.btn_open.configure(state="disabled")
        
        threading.Thread(target=self._generation_task, args=(url, user, password), daemon=True).start()

    def _generation_task(self, url, user, password):
        try:
            scraper = WebScraper()
            nodes, edges = scraper.recursive_crawl(url, max_depth=2, max_pages=10, username=user, password=password)
            self.nodes = nodes
            self.edges = edges
            
            self.lbl_status.configure(text="🎨 Generating Interactive Graph...")
            
            gen = SitemapGenerator()
            self.sitemap_path = gen.generate(nodes, edges)
            
            self.after(0, self._on_generation_success)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.lbl_status.configure(text="Error"))
        finally:
            self.after(0, lambda: self.btn_generate.configure(state="normal"))

    def _on_generation_success(self):
        self.lbl_status.configure(text="✅ Done! ready to view.")
        self.btn_open.configure(state="normal")
        
        # Populate Listbox
        for widget in self.node_listbox.winfo_children():
            widget.destroy()
            
        for n in self.nodes:
            # Container for each node
            row_frame = ctk.CTkFrame(self.node_listbox, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            # Thumbnail
            try:
                if n.get("screenshot") and os.path.exists(n["screenshot"]):
                    pil_img = Image.open(n["screenshot"])
                    # Resize for thumbnail
                    pil_img.thumbnail((60, 60))
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                    lbl_img = ctk.CTkLabel(row_frame, text="", image=ctk_img)
                    lbl_img.pack(side="left", padx=(0, 5))
            except Exception:
                pass # Fail silently if image error

            # Radio Button
            rb = ctk.CTkRadioButton(
                row_frame, 
                text=f"[{n['id']}] {n['title'][:30]}...", 
                variable=self.radio_var, 
                value=str(n['id']),
                command=self._on_node_selected
            )
            rb.pack(side="left", fill="x", expand=True)

    def open_sitemap_html(self):
        if self.sitemap_path:
            webbrowser.open(f"file://{self.sitemap_path}")

    def _on_node_selected(self):
        self.btn_compare.configure(state="normal")

    def load_target_clipboard(self):
        try:
            content = self.clipboard_get()
            self.txt_target_preview.delete("1.0", "end")
            self.txt_target_preview.insert("1.0", content)
        except:
            pass

    def run_comparison(self):
        # Source Text
        selected_id = self.radio_var.get()
        if not selected_id: return
        
        node = next((n for n in self.nodes if str(n["id"]) == selected_id), None)
        if not node: return
        source_text = node["full_text"]
        
        # Target Text
        target_text = self.txt_target_preview.get("1.0", "end").strip()
        
        # Compare
        result = Comparator.compare(source_text, target_text)
        
        # Display
        self.lbl_sync_rate.configure(text=f"Sync Rate: {result['sync_rate']}%")
        
        self.txt_diff.configure(state="normal")
        self.txt_diff.delete("1.0", "end")
        
        # Simple coloring for diff
        for seg in result["segments"]:
            tag = seg["tag"]
            if tag == 'replace':
                self.txt_diff.insert("end", f"[- {seg['source']} ]", "delete")
                self.txt_diff.insert("end", f"[+ {seg['target']} ]", "insert")
            elif tag == 'delete':
                self.txt_diff.insert("end", f"[- {seg['source']} ]", "delete")
            elif tag == 'insert':
                self.txt_diff.insert("end", f"[+ {seg['target']} ]", "insert")
            else:
                self.txt_diff.insert("end", seg['source'])
        
        self.txt_diff.tag_config("delete", foreground="#ff5555")
        self.txt_diff.tag_config("insert", foreground="#55ff55")
        self.txt_diff.configure(state="disabled")
