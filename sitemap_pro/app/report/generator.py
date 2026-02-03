import os
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.output_dir = os.path.join(settings.OUTPUT_DIR, self.run_id)
        self.report_dir = os.path.join(self.output_dir, "report")
        self.data_path = os.path.join(self.output_dir, "data.json")
        self.template_path = os.path.join(os.path.dirname(__file__), "template", "index.html")

    def generate(self):
        logger.info(f"Generating report for Run ID: {self.run_id}")
        
        # 1. Load Data
        if not os.path.exists(self.data_path):
            logger.error("data.json not found")
            return False
            
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 2. Load Template
        if not os.path.exists(self.template_path):
            logger.error("Template index.html not found")
            return False
            
        with open(self.template_path, "r", encoding="utf-8") as f:
            template = f.read()
            
        # 3. Inject Data
        # We inject the JSON directly into the window.SITEMAP_DATA variable
        # SECURITY: Escape </script> to prevent XSS
        json_str = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        html_content = template.replace(
            "const data = window.SITEMAP_DATA || {};", 
            f"const data = {json_str};"
        )
        
        # 4. Write Output
        output_path = os.path.join(self.report_dir, "index.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        logger.info(f"Report generated at: {output_path}")
        return True
