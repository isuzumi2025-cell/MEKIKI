import customtkinter as ctk
import os
import sys

# パス設定
sys.path.append(os.getcwd())
from app.gui.sitemap_frame import SitemapFrame
from app.gui.ocr_frame import OCRFrame

# デザイン設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class OCRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI-OCR Workspace Ultimate (Genius Edition)")
        self.geometry("1400x900")
        
        # Grid Layout
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()

    def _setup_ui(self):
        """Construct the Main Window Container"""
        
        # Create Tabview (Full Screen)
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # --- Add Tabs ---
        self.tab_ocr = self.tabview.add("📂 OCR / Workspace")
        self.tab_sitemap = self.tabview.add("🌐 Sitemap & Compare")
        
        # --- TAB 1: OCR Workspace (Modernized) ---
        self.ocr_frame = OCRFrame(self.tab_ocr)
        self.ocr_frame.pack(fill="both", expand=True)
        
        # --- TAB 2: Sitemap & Compare (Verified) ---
        self.sitemap_frame = SitemapFrame(self.tab_sitemap)
        self.sitemap_frame.pack(fill="both", expand=True)

if __name__ == "__main__":
    app = OCRApp()
    app.mainloop()