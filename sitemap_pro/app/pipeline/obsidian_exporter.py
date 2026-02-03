"""
Obsidian Exporter
Converts crawl results to Obsidian-compatible Markdown notes with Vision API OCR.

Usage:
    python -m app.pipeline.obsidian_exporter --run-id 20260110_033618 --vault-dir ./test_vault
"""
import os
import sys
import json
import argparse
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class ObsidianExporter:
    """
    Exports crawl data to Obsidian Vault as Markdown notes.
    Optionally uses Vision API for OCR text extraction from screenshots.
    """
    
    def __init__(
        self,
        run_id: str,
        vault_dir: str,
        outputs_dir: str = "outputs",
        use_vision_api: bool = True,
        credentials_path: Optional[str] = None
    ):
        self.run_id = run_id
        self.vault_dir = Path(vault_dir)
        self.outputs_dir = Path(outputs_dir)
        self.use_vision_api = use_vision_api
        self.credentials_path = credentials_path
        
        # Paths
        self.run_dir = self.outputs_dir / run_id
        self.data_path = self.run_dir / "data.json"
        self.images_dir = self.run_dir / "images"
        
        # Output paths in vault (new structure: 20_Web/web_md)
        self.notes_dir = self.vault_dir / "20_Web" / "web_md" / run_id
        self.vault_images_dir = self.vault_dir / "20_Web" / "web_md" / run_id / "images"
        
        # Copy raw data to web_raw
        self.raw_dir = self.vault_dir / "20_Web" / "web_raw" / run_id
        
        # Vision API client (lazy init)
        self._vision_client = None
    
    def _init_vision_client(self):
        """Initialize Vision API client if needed."""
        if not self.use_vision_api:
            return None
        
        try:
            from google.cloud import vision
            
            if self.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            
            self._vision_client = vision.ImageAnnotatorClient()
            print("✅ Vision API client initialized")
            return self._vision_client
        except ImportError:
            print("⚠️ google-cloud-vision not installed. OCR disabled.")
            self.use_vision_api = False
            return None
        except Exception as e:
            print(f"⚠️ Vision API init failed: {e}. OCR disabled.")
            self.use_vision_api = False
            return None
    
    def _ocr_image(self, image_path: Path) -> str:
        """Extract text from image using Vision API."""
        if not self.use_vision_api or not image_path.exists():
            return ""
        
        if not self._vision_client:
            self._init_vision_client()
            if not self._vision_client:
                return ""
        
        try:
            from google.cloud import vision
            
            with open(image_path, "rb") as f:
                content = f.read()
            
            image = vision.Image(content=content)
            response = self._vision_client.document_text_detection(image=image)
            
            if response.error.message:
                print(f"  ⚠️ OCR error: {response.error.message}")
                return ""
            
            text = response.full_text_annotation.text if response.full_text_annotation else ""
            return text.strip()
            
        except Exception as e:
            print(f"  ⚠️ OCR failed: {e}")
            return ""
    
    def _generate_markdown(self, node: Dict, ocr_text: str) -> str:
        """Generate Obsidian-compatible Markdown note."""
        title = node.get("title", "Untitled")
        url = node.get("url", "")
        status = node.get("status", 0)
        h1 = node.get("h1", "").strip()
        meta_desc = node.get("meta_desc", "")
        canonical = node.get("canonical", "")
        links_count = node.get("links_count", 0)
        screenshot = node.get("screenshot", "")
        node_id = node.get("id", "")
        timestamp = datetime.now().isoformat()
        
        # Escape quotes in title for YAML
        safe_title = title.replace('"', "'")
        
        # Frontmatter (RAG optimized)
        frontmatter = f"""---
source: web
title: "{safe_title}"
url: "{url}"
captured_at: "{timestamp}"
status: {status}
content_hash: "{node_id}"
tags: [sitemap, web-crawl]
---"""
        
        # Main content
        content = f"""
# {title}

## Metadata
- **URL**: [{url}]({url})
- **Status**: {status}
- **Canonical**: {canonical if canonical else "N/A"}
- **H1**: {h1 if h1 else "N/A"}
- **Meta Description**: {meta_desc if meta_desc else "N/A"}
- **Links Found**: {links_count}

"""
        
        # OCR Text section
        if ocr_text:
            # Truncate if too long
            if len(ocr_text) > 5000:
                ocr_text = ocr_text[:5000] + "\n\n... (truncated)"
            content += f"""## Extracted Text (OCR)
```
{ocr_text}
```

"""
        
        # Screenshot
        if screenshot:
            screenshot_filename = Path(screenshot).name
            content += f"""## Screenshot
![[images/{screenshot_filename}]]
"""
        
        return frontmatter + content
    
    def _safe_filename(self, title: str, node_id: str) -> str:
        """Generate safe filename for Obsidian."""
        # Remove/replace invalid characters
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        safe = safe.strip()[:50]  # Limit length
        if not safe:
            safe = node_id[:8]
        return f"{safe}.md"
    
    def export(self) -> List[Path]:
        """
        Export all crawled pages to Obsidian Vault.
        
        Returns:
            List of created Markdown file paths.
        """
        print(f"📤 Exporting run {self.run_id} to Obsidian Vault")
        print(f"   Vault: {self.vault_dir}")
        
        # Load data
        if not self.data_path.exists():
            print(f"❌ data.json not found: {self.data_path}")
            return []
        
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        nodes = data.get("nodes", [])
        print(f"   Pages: {len(nodes)}")
        
        # Create directories
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.vault_images_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy images
        if self.images_dir.exists():
            import shutil
            for img in self.images_dir.glob("*.png"):
                shutil.copy(img, self.vault_images_dir / img.name)
            print(f"   Images copied: {len(list(self.images_dir.glob('*.png')))}")
        
        # Process each node
        created_files = []
        for i, node in enumerate(nodes, 1):
            node_id = node.get("id", f"node_{i}")
            title = node.get("title", "Untitled")
            screenshot = node.get("screenshot", "")
            
            print(f"   [{i}/{len(nodes)}] {title[:40]}...")
            
            # OCR
            ocr_text = ""
            if self.use_vision_api and screenshot:
                screenshot_path = self.run_dir / screenshot
                print(f"      OCR processing...")
                ocr_text = self._ocr_image(screenshot_path)
                if ocr_text:
                    print(f"      ✅ Extracted {len(ocr_text)} chars")
            
            # Generate Markdown
            md_content = self._generate_markdown(node, ocr_text)
            
            # Write file
            filename = self._safe_filename(title, node_id)
            filepath = self.notes_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            
            created_files.append(filepath)
        
        print(f"\n✅ Export complete!")
        print(f"   Notes: {len(created_files)}")
        print(f"   Location: {self.notes_dir}")
        
        return created_files


def main():
    parser = argparse.ArgumentParser(description="Export crawl data to Obsidian Vault")
    parser.add_argument("--run-id", required=True, help="Crawl run ID (folder name in outputs/)")
    parser.add_argument("--vault-dir", required=True, help="Path to Obsidian Vault")
    parser.add_argument("--outputs-dir", default="outputs", help="Path to outputs directory")
    parser.add_argument("--no-ocr", action="store_true", help="Disable Vision API OCR")
    parser.add_argument("--credentials", help="Path to Google Cloud credentials JSON")
    
    args = parser.parse_args()
    
    exporter = ObsidianExporter(
        run_id=args.run_id,
        vault_dir=args.vault_dir,
        outputs_dir=args.outputs_dir,
        use_vision_api=not args.no_ocr,
        credentials_path=args.credentials
    )
    
    exporter.export()


if __name__ == "__main__":
    main()
