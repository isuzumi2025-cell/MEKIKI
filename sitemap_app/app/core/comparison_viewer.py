import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import jinja2


class ComparisonViewer:
    """
    テキスト比較ビューワーHTML生成
    
    2x3 マトリクスレイアウト:
    ┌─────────────────┬─────────────────┬────────────────┐
    │ 🌐 Web キャプチャ │ 📕 PDF プレビュー │ 📊 比較結果    │
    ├─────────────────┼─────────────────┼────────────────┤
    │ 📝 Web テキスト  │ 📝 PDF テキスト  │ ✏️ サジェスト   │
    └─────────────────┴─────────────────┴────────────────┘
    """
    
    def __init__(self, template_dir: str = "app/templates"):
        # テンプレートディレクトリのパス解決
        # このファイルは app/core/comparison_viewer.py にあると仮定
        # デフォルトは app/templates
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(base_dir, "templates")
        
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_path),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    
    def generate_comparison_html(
        self,
        web_capture: Optional[str] = None,
        pdf_preview: Optional[str] = None,
        web_text: str = "",
        pdf_text: str = "",
        comparison_result: Optional[Dict] = None,
        suggestions: Optional[List[Dict]] = None,
        title: str = "テキスト比較"
    ) -> str:
        """
        比較ビューワーHTMLを生成
        
        Args:
            web_capture: Web スクリーンショットのパス
            pdf_preview: PDF プレビュー画像のパス
            web_text: Web から抽出したテキスト
            pdf_text: PDF から抽出したテキスト
            comparison_result: TextComparator.compare() の結果
            suggestions: サジェストリスト
            title: ページタイトル
        """
        
        sync_rate = comparison_result.get("sync_rate", 0) if comparison_result else 0
        diff_count = comparison_result.get("diff_count", 0) if comparison_result else 0
        diff_html = comparison_result.get("diff_html", "") if comparison_result else ""
        
        suggestions_json = json.dumps(suggestions or [], ensure_ascii=False)
        sync_color = self._get_sync_color(sync_rate)
        
        formatted_web_text = self._format_text_blocks(web_text, "web")
        formatted_pdf_text = self._format_text_blocks(pdf_text, "pdf")
        # テンプレート読み込み
        template = self.env.get_template("comparison_view_new.html")
        
        # レンダリング
        return template.render(
            title=title,
            sync_rate=sync_rate,
            sync_color=sync_color,
            diff_count=diff_count,
            diff_html=diff_html,
            web_capture=web_capture,
            pdf_preview=pdf_preview,
            web_text=web_text,
            pdf_text=pdf_text,
            formatted_web_text=formatted_web_text,
            formatted_pdf_text=formatted_pdf_text,
            suggestions_json=suggestions_json
        )
    
    def _get_sync_color(self, sync_rate: float) -> str:
        """Sync Rateに応じた色を返す"""
        if sync_rate >= 95:
            return "#3fb950"  # green
        elif sync_rate >= 80:
            return "#f0883e"  # orange
        else:
            return "#f85149"  # red
    
    def _format_text_blocks(self, text: str, source: str) -> str:
        """テキストをブロックに分割してHTMLを生成"""
        if not text:
            return '<p style="color:#8b949e;">テキストがありません</p>'
        
        # 段落で分割
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        if not paragraphs:
            paragraphs = [text]
        
        html_blocks = []
        for i, para in enumerate(paragraphs):
            html_blocks.append(f'''
                <div class="text-block" data-region-id="{source}-{i+1}">
                    <div class="text-block-header">
                        <span class="text-block-id">#{i+1}</span>
                        <span>{len(para)} 文字</span>
                    </div>
                    {para}
                </div>
            ''')
        
        return "\n".join(html_blocks)
