"""
テキスト比較ビューワー生成モジュール
Web/PDF テキストを2x3マトリクスで比較するHTML生成
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


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
        summary = comparison_result.get("summary", "") if comparison_result else ""
        
        suggestions_json = json.dumps(suggestions or [], ensure_ascii=False)
        
        html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', sans-serif;
            background: #0d1117;
            color: #e6edf3;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        
        /* ツールバー */
        .toolbar {{
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 12px 20px;
            background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
            border-bottom: 1px solid #30363d;
        }}
        
        .toolbar h1 {{
            font-size: 18px;
            background: linear-gradient(135deg, #58a6ff, #3fb950);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            margin-right: auto;
        }}
        
        .toolbar-btn {{
            background: #21262d;
            border: 1px solid #30363d;
            color: #8b949e;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .toolbar-btn:hover {{
            background: #30363d;
            color: #e6edf3;
            border-color: #58a6ff;
        }}
        
        .toolbar-btn.active {{
            background: #238636;
            color: white;
            border-color: #3fb950;
        }}
        
        .sync-rate {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: #21262d;
            border-radius: 6px;
            border: 1px solid #30363d;
        }}
        
        .sync-rate-value {{
            font-size: 20px;
            font-weight: bold;
            color: {self._get_sync_color(sync_rate)};
        }}
        
        .sync-rate-label {{
            font-size: 12px;
            color: #8b949e;
        }}
        
        /* メインコンテナ */
        .main-container {{
            flex: 1;
            display: grid;
            grid-template-columns: 1fr 1fr 350px;
            grid-template-rows: 1fr 1fr;
            gap: 1px;
            background: #30363d;
            overflow: hidden;
        }}
        
        .panel {{
            background: #0d1117;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        
        .panel-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 15px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }}
        
        .panel-title {{
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .panel-title .icon {{
            font-size: 16px;
        }}
        
        .panel-content {{
            flex: 1;
            overflow: auto;
            padding: 15px;
        }}
        
        /* キャプチャエリア */
        .capture-panel {{
            position: relative;
        }}
        
        .capture-image {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
        }}
        
        .capture-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
        }}
        
        .selection-region {{
            position: absolute;
            border: 2px solid #58a6ff;
            background: rgba(88, 166, 255, 0.1);
            cursor: move;
            pointer-events: auto;
        }}
        
        .selection-region.active {{
            border-color: #3fb950;
            background: rgba(63, 185, 80, 0.15);
        }}
        
        .selection-region .region-id {{
            position: absolute;
            top: -20px;
            left: 0;
            background: #58a6ff;
            color: white;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        
        /* リサイズハンドル */
        .selection-region .resize-handles {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }}
        
        .selection-region .resize-handle {{
            position: absolute;
            width: 10px;
            height: 10px;
            background: #58a6ff;
            border-radius: 2px;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        
        .selection-region:hover .resize-handle,
        .selection-region.active .resize-handle {{
            opacity: 1;
        }}
        
        .selection-region .resize-handle.nw {{ top: -5px; left: -5px; cursor: nw-resize; }}
        .selection-region .resize-handle.ne {{ top: -5px; right: -5px; cursor: ne-resize; }}
        .selection-region .resize-handle.sw {{ bottom: -5px; left: -5px; cursor: sw-resize; }}
        .selection-region .resize-handle.se {{ bottom: -5px; right: -5px; cursor: se-resize; }}
        
        .selection-region.drawing {{
            border-style: dashed;
            background: rgba(88, 166, 255, 0.2);
        }}
        
        .selection-region.loading {{
            opacity: 0.6;
        }}
        
        .selection-region.loading::after {{
            content: '⏳';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 20px;
        }}
        
        /* テキストエリア */
        .text-panel .panel-content {{
            font-size: 14px;
            line-height: 1.8;
            white-space: pre-wrap;
        }}
        
        .text-block {{
            padding: 12px 15px;
            margin-bottom: 10px;
            background: #161b22;
            border-radius: 6px;
            border-left: 3px solid #30363d;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .text-block:hover {{
            background: #21262d;
            border-left-color: #58a6ff;
        }}
        
        .text-block.active {{
            border-left-color: #3fb950;
            background: rgba(63, 185, 80, 0.1);
        }}
        
        .text-block-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            font-size: 11px;
            color: #8b949e;
        }}
        
        .text-block-id {{
            background: #58a6ff;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 600;
        }}
        
        /* 比較結果パネル */
        .comparison-panel {{
            grid-row: span 2;
        }}
        
        .comparison-summary {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: #161b22;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 4px;
        }}
        
        .stat-label {{
            font-size: 11px;
            color: #8b949e;
        }}
        
        /* 差分表示 */
        .diff-container {{
            font-size: 14px;
            line-height: 1.8;
            background: #161b22;
            padding: 15px;
            border-radius: 6px;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .diff-equal {{
            color: #e6edf3;
        }}
        
        .diff-delete {{
            background: rgba(248, 81, 73, 0.3);
            color: #ffa198;
            text-decoration: line-through;
            padding: 0 2px;
            border-radius: 2px;
        }}
        
        .diff-insert {{
            background: rgba(63, 185, 80, 0.3);
            color: #7ee787;
            padding: 0 2px;
            border-radius: 2px;
        }}
        
        /* サジェストパネル */
        .suggestions-panel {{
            display: none;
        }}
        
        .suggestions-panel.visible {{
            display: block;
        }}
        
        .suggestion-item {{
            background: #161b22;
            padding: 12px 15px;
            margin-bottom: 8px;
            border-radius: 6px;
            border-left: 3px solid #f0883e;
        }}
        
        .suggestion-type {{
            font-size: 10px;
            text-transform: uppercase;
            color: #f0883e;
            margin-bottom: 6px;
        }}
        
        .suggestion-original {{
            font-size: 13px;
            color: #ffa198;
            margin-bottom: 4px;
        }}
        
        .suggestion-new {{
            font-size: 13px;
            color: #7ee787;
        }}
        
        /* トグルスイッチ */
        .toggle-switch {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .toggle-switch input {{
            display: none;
        }}
        
        .toggle-slider {{
            width: 40px;
            height: 20px;
            background: #30363d;
            border-radius: 10px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        }}
        
        .toggle-slider::after {{
            content: '';
            position: absolute;
            width: 16px;
            height: 16px;
            background: #8b949e;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: all 0.2s;
        }}
        
        .toggle-switch input:checked + .toggle-slider {{
            background: #238636;
        }}
        
        .toggle-switch input:checked + .toggle-slider::after {{
            left: 22px;
            background: white;
        }}
        
        /* レスポンシブ */
        @media (max-width: 1200px) {{
            .main-container {{
                grid-template-columns: 1fr 1fr;
            }}
            .comparison-panel {{
                grid-column: span 2;
                grid-row: auto;
            }}
        }}
        
        /* アニメーション */
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .loading {{
            animation: pulse 1.5s infinite;
        }}
        
        /* 選択モード */
        .selection-mode .capture-panel {{
            cursor: crosshair;
        }}
        
        /* コンテキストメニュー */
        .context-menu {{
            position: fixed;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 8px 0;
            min-width: 150px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            z-index: 1000;
            display: none;
        }}
        
        .context-menu.visible {{
            display: block;
        }}
        
        .context-menu-item {{
            padding: 8px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }}
        
        .context-menu-item:hover {{
            background: #30363d;
        }}
    </style>
</head>
<body>
    <!-- ツールバー -->
    <div class="toolbar">
        <h1>📊 テキスト比較ビューワー</h1>
        
        <div class="sync-rate">
            <span class="sync-rate-value">{sync_rate}%</span>
            <span class="sync-rate-label">Sync Rate</span>
        </div>
        
        <button class="toolbar-btn" id="btn-select-mode">
            ✏️ 領域選択
        </button>
        
        <button class="toolbar-btn" id="btn-compare">
            🔄 再比較
        </button>
        
        <div class="toggle-switch">
            <span style="font-size:12px; color:#8b949e;">サジェスト</span>
            <input type="checkbox" id="toggle-suggestions">
            <label class="toggle-slider" for="toggle-suggestions"></label>
        </div>
        
        <button class="toolbar-btn" id="btn-export">
            💾 エクスポート
        </button>
    </div>
    
    <!-- メインコンテナ -->
    <div class="main-container">
        <!-- Web キャプチャ -->
        <div class="panel capture-panel" id="panel-web-capture">
            <div class="panel-header">
                <div class="panel-title">
                    <span class="icon">🌐</span>
                    Web キャプチャ
                </div>
                <button class="toolbar-btn" onclick="uploadImage('web')">📤</button>
            </div>
            <div class="panel-content">
                <div id="web-capture-container">
                    {f'<img src="{web_capture}" class="capture-image" id="web-capture-img">' if web_capture else '<p style="color:#8b949e;text-align:center;padding:40px;">Web URLを入力するか、画像をドロップ</p>'}
                    <svg class="capture-overlay" id="web-regions"></svg>
                </div>
            </div>
        </div>
        
        <!-- PDF プレビュー -->
        <div class="panel capture-panel" id="panel-pdf-preview">
            <div class="panel-header">
                <div class="panel-title">
                    <span class="icon">📕</span>
                    PDF プレビュー
                </div>
                <button class="toolbar-btn" onclick="uploadImage('pdf')">📤</button>
            </div>
            <div class="panel-content">
                <div id="pdf-capture-container">
                    {f'<img src="{pdf_preview}" class="capture-image" id="pdf-capture-img">' if pdf_preview else '<p style="color:#8b949e;text-align:center;padding:40px;">PDFをアップロードまたはURLを入力</p>'}
                    <svg class="capture-overlay" id="pdf-regions"></svg>
                </div>
            </div>
        </div>
        
        <!-- 比較結果 -->
        <div class="panel comparison-panel" id="panel-comparison">
            <div class="panel-header">
                <div class="panel-title">
                    <span class="icon">📊</span>
                    比較結果
                </div>
            </div>
            <div class="panel-content">
                <div class="comparison-summary">
                    <div class="stat-card">
                        <div class="stat-value" style="color:{self._get_sync_color(sync_rate)}">{sync_rate}%</div>
                        <div class="stat-label">一致率</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color:#ffa198">{diff_count}</div>
                        <div class="stat-label">差異箇所</div>
                    </div>
                </div>
                
                <h4 style="margin-bottom:10px; font-size:13px; color:#8b949e;">差分ハイライト</h4>
                <div class="diff-container" id="diff-display">
                    {diff_html if diff_html else '<p style="color:#8b949e;">比較結果がここに表示されます</p>'}
                </div>
                
                <!-- サジェストパネル -->
                <div class="suggestions-panel" id="suggestions-panel">
                    <h4 style="margin:20px 0 10px; font-size:13px; color:#8b949e;">💡 サジェスト</h4>
                    <div id="suggestions-list"></div>
                </div>
            </div>
        </div>
        
        <!-- Web テキスト -->
        <div class="panel text-panel" id="panel-web-text">
            <div class="panel-header">
                <div class="panel-title">
                    <span class="icon">📝</span>
                    Web 抽出テキスト
                </div>
                <span style="font-size:11px; color:#8b949e;">{len(web_text)} 文字</span>
            </div>
            <div class="panel-content" id="web-text-content">
                {self._format_text_blocks(web_text, "web")}
            </div>
        </div>
        
        <!-- PDF テキスト -->
        <div class="panel text-panel" id="panel-pdf-text">
            <div class="panel-header">
                <div class="panel-title">
                    <span class="icon">📝</span>
                    PDF 抽出テキスト (OCR)
                </div>
                <span style="font-size:11px; color:#8b949e;">{len(pdf_text)} 文字</span>
            </div>
            <div class="panel-content" id="pdf-text-content">
                {self._format_text_blocks(pdf_text, "pdf")}
            </div>
        </div>
    </div>
    
    <!-- コンテキストメニュー -->
    <div class="context-menu" id="context-menu">
        <div class="context-menu-item" onclick="extractRegion()">📋 この領域を抽出</div>
        <div class="context-menu-item" onclick="deleteRegion()">🗑️ 領域を削除</div>
        <div class="context-menu-item" onclick="linkRegion()">🔗 対応する領域とリンク</div>
    </div>
    
    <script>
        // ===================================================================
        // データ管理
        // ===================================================================
        const suggestions = {suggestions_json};
        let isSelectionMode = false;
        let selectedRegion = null;
        let webRegions = [];
        let pdfRegions = [];
        let regionIdCounter = 0;
        let isDragging = false;
        let isResizing = false;
        let dragStartX = 0;
        let dragStartY = 0;
        let currentPanel = null;
        let tempRect = null;
        let undoStack = [];
        
        // ===================================================================
        // 領域選択モード
        // ===================================================================
        document.getElementById('btn-select-mode').addEventListener('click', function() {{
            isSelectionMode = !isSelectionMode;
            this.classList.toggle('active', isSelectionMode);
            document.body.classList.toggle('selection-mode', isSelectionMode);
            
            if (isSelectionMode) {{
                initCanvasListeners();
            }} else {{
                removeCanvasListeners();
            }}
        }});
        
        function initCanvasListeners() {{
            ['panel-web-capture', 'panel-pdf-preview'].forEach(panelId => {{
                const panel = document.getElementById(panelId);
                const content = panel.querySelector('.panel-content');
                
                content.addEventListener('mousedown', startDrawing);
                content.addEventListener('mousemove', continueDrawing);
                content.addEventListener('mouseup', finishDrawing);
                content.addEventListener('mouseleave', finishDrawing);
            }});
        }}
        
        function removeCanvasListeners() {{
            ['panel-web-capture', 'panel-pdf-preview'].forEach(panelId => {{
                const panel = document.getElementById(panelId);
                const content = panel.querySelector('.panel-content');
                
                content.removeEventListener('mousedown', startDrawing);
                content.removeEventListener('mousemove', continueDrawing);
                content.removeEventListener('mouseup', finishDrawing);
                content.removeEventListener('mouseleave', finishDrawing);
            }});
        }}
        
        // ===================================================================
        // 矩形描画
        // ===================================================================
        function startDrawing(e) {{
            if (!isSelectionMode) return;
            
            const panel = e.currentTarget.closest('.panel');
            currentPanel = panel.id;
            isDragging = true;
            
            const rect = e.currentTarget.getBoundingClientRect();
            dragStartX = e.clientX - rect.left;
            dragStartY = e.clientY - rect.top;
            
            // 一時的な矩形を作成
            tempRect = document.createElement('div');
            tempRect.className = 'selection-region drawing';
            tempRect.style.cssText = `
                left: ${{dragStartX}}px;
                top: ${{dragStartY}}px;
                width: 0;
                height: 0;
                pointer-events: none;
            `;
            e.currentTarget.appendChild(tempRect);
        }}
        
        function continueDrawing(e) {{
            if (!isDragging || !tempRect) return;
            
            const rect = e.currentTarget.getBoundingClientRect();
            const currentX = e.clientX - rect.left;
            const currentY = e.clientY - rect.top;
            
            const width = Math.abs(currentX - dragStartX);
            const height = Math.abs(currentY - dragStartY);
            const left = Math.min(dragStartX, currentX);
            const top = Math.min(dragStartY, currentY);
            
            tempRect.style.left = left + 'px';
            tempRect.style.top = top + 'px';
            tempRect.style.width = width + 'px';
            tempRect.style.height = height + 'px';
        }}
        
        function finishDrawing(e) {{
            if (!isDragging || !tempRect) return;
            isDragging = false;
            
            const width = parseInt(tempRect.style.width);
            const height = parseInt(tempRect.style.height);
            
            // 最小サイズチェック
            if (width < 20 || height < 20) {{
                tempRect.remove();
                tempRect = null;
                return;
            }}
            
            // 正式な領域として登録
            const region = createRegion({{
                left: parseInt(tempRect.style.left),
                top: parseInt(tempRect.style.top),
                width: width,
                height: height,
                panel: currentPanel
            }});
            
            tempRect.remove();
            tempRect = null;
            
            // OCR実行
            extractRegionText(region);
        }}
        
        // ===================================================================
        // 領域管理
        // ===================================================================
        function createRegion(config) {{
            regionIdCounter++;
            const regionId = `region-${{regionIdCounter}}`;
            
            const region = {{
                id: regionId,
                panel: config.panel,
                bbox: [config.left, config.top, config.left + config.width, config.top + config.height],
                text: '',
                linkedTo: null
            }};
            
            // DOM要素を作成
            const el = document.createElement('div');
            el.className = 'selection-region';
            el.dataset.regionId = regionId;
            el.innerHTML = `
                <span class="region-id">#${{regionIdCounter}}</span>
                <div class="resize-handles">
                    <div class="resize-handle nw" data-dir="nw"></div>
                    <div class="resize-handle ne" data-dir="ne"></div>
                    <div class="resize-handle sw" data-dir="sw"></div>
                    <div class="resize-handle se" data-dir="se"></div>
                </div>
            `;
            el.style.cssText = `
                left: ${{config.left}}px;
                top: ${{config.top}}px;
                width: ${{config.width}}px;
                height: ${{config.height}}px;
            `;
            
            // イベント
            el.addEventListener('click', (e) => {{
                e.stopPropagation();
                selectRegion(regionId);
            }});
            el.addEventListener('contextmenu', (e) => {{
                e.preventDefault();
                showContextMenu(e, regionId);
            }});
            
            // リサイズハンドル
            el.querySelectorAll('.resize-handle').forEach(handle => {{
                handle.addEventListener('mousedown', (e) => startResize(e, regionId, handle.dataset.dir));
            }});
            
            // パネルに追加
            const panel = document.getElementById(config.panel);
            panel.querySelector('.panel-content').appendChild(el);
            
            // リストに追加
            if (config.panel === 'panel-web-capture') {{
                webRegions.push(region);
            }} else {{
                pdfRegions.push(region);
            }}
            
            // Undo用に保存
            undoStack.push({{ type: 'create', region: region }});
            
            return region;
        }}
        
        function selectRegion(regionId) {{
            // 既存の選択を解除
            document.querySelectorAll('.selection-region').forEach(r => r.classList.remove('active'));
            
            // 新しい領域を選択
            const el = document.querySelector(`[data-region-id="${{regionId}}"]`);
            if (el) {{
                el.classList.add('active');
                selectedRegion = regionId;
                
                // 対応するテキストブロックもハイライト
                const region = [...webRegions, ...pdfRegions].find(r => r.id === regionId);
                if (region && region.text) {{
                    updateTextPreview(region);
                }}
            }}
        }}
        
        function deleteRegion(regionId) {{
            const id = regionId || selectedRegion;
            if (!id) return;
            
            // DOM要素を削除
            const el = document.querySelector(`[data-region-id="${{id}}"]`);
            if (el) el.remove();
            
            // リストから削除
            webRegions = webRegions.filter(r => r.id !== id);
            pdfRegions = pdfRegions.filter(r => r.id !== id);
            
            selectedRegion = null;
            hideContextMenu();
        }}
        
        // ===================================================================
        // リサイズ
        // ===================================================================
        let resizeDir = null;
        let resizeRegion = null;
        let resizeStartRect = null;
        
        function startResize(e, regionId, dir) {{
            e.stopPropagation();
            isResizing = true;
            resizeDir = dir;
            resizeRegion = regionId;
            
            const el = document.querySelector(`[data-region-id="${{regionId}}"]`);
            resizeStartRect = {{
                left: parseInt(el.style.left),
                top: parseInt(el.style.top),
                width: parseInt(el.style.width),
                height: parseInt(el.style.height),
                mouseX: e.clientX,
                mouseY: e.clientY
            }};
            
            document.addEventListener('mousemove', doResize);
            document.addEventListener('mouseup', stopResize);
        }}
        
        function doResize(e) {{
            if (!isResizing) return;
            
            const el = document.querySelector(`[data-region-id="${{resizeRegion}}"]`);
            const dx = e.clientX - resizeStartRect.mouseX;
            const dy = e.clientY - resizeStartRect.mouseY;
            
            let newLeft = resizeStartRect.left;
            let newTop = resizeStartRect.top;
            let newWidth = resizeStartRect.width;
            let newHeight = resizeStartRect.height;
            
            if (resizeDir.includes('e')) {{ newWidth += dx; }}
            if (resizeDir.includes('w')) {{ newWidth -= dx; newLeft += dx; }}
            if (resizeDir.includes('s')) {{ newHeight += dy; }}
            if (resizeDir.includes('n')) {{ newHeight -= dy; newTop += dy; }}
            
            // 最小サイズ
            if (newWidth >= 20 && newHeight >= 20) {{
                el.style.left = newLeft + 'px';
                el.style.top = newTop + 'px';
                el.style.width = newWidth + 'px';
                el.style.height = newHeight + 'px';
            }}
        }}
        
        function stopResize(e) {{
            if (!isResizing) return;
            isResizing = false;
            
            // 領域データを更新
            const el = document.querySelector(`[data-region-id="${{resizeRegion}}"]`);
            const region = [...webRegions, ...pdfRegions].find(r => r.id === resizeRegion);
            if (region) {{
                region.bbox = [
                    parseInt(el.style.left),
                    parseInt(el.style.top),
                    parseInt(el.style.left) + parseInt(el.style.width),
                    parseInt(el.style.top) + parseInt(el.style.height)
                ];
                
                // 再OCR
                extractRegionText(region);
            }}
            
            document.removeEventListener('mousemove', doResize);
            document.removeEventListener('mouseup', stopResize);
        }}
        
        // ===================================================================
        // OCR抽出 (API連携)
        // ===================================================================
        async function extractRegionText(region) {{
            const bbox = region.bbox;
            const panel = region.panel;
            
            // ローディング表示
            const el = document.querySelector(`[data-region-id="${{region.id}}"]`);
            el.classList.add('loading');
            
            try {{
                // 画像パスを取得 (実際の実装では画像URLを使用)
                const imgEl = document.getElementById(
                    panel === 'panel-web-capture' ? 'web-capture-img' : 'pdf-capture-img'
                );
                
                if (!imgEl) {{
                    console.warn('Image not found for OCR');
                    return;
                }}
                
                // APIを呼び出し
                const res = await fetch('/api/v1/extract/region', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        image_path: imgEl.src,
                        bbox: bbox
                    }})
                }});
                
                if (res.ok) {{
                    const result = await res.json();
                    region.text = result.text || '';
                    updateTextPreview(region);
                }}
            }} catch (e) {{
                console.error('OCR extraction failed:', e);
            }} finally {{
                el.classList.remove('loading');
            }}
        }}
        
        function updateTextPreview(region) {{
            const panelId = region.panel === 'panel-web-capture' ? 'web-text-content' : 'pdf-text-content';
            const textPanel = document.getElementById(panelId);
            
            // 既存のブロックを更新または新規追加
            let block = textPanel.querySelector(`[data-region-id="${{region.id}}"]`);
            
            if (!block) {{
                block = document.createElement('div');
                block.className = 'text-block active';
                block.dataset.regionId = region.id;
                textPanel.appendChild(block);
            }}
            
            block.innerHTML = `
                <div class="text-block-header">
                    <span class="text-block-id">#${{region.id.split('-')[1]}}</span>
                    <span>${{region.text.length}} 文字</span>
                </div>
                ${{region.text || '(テキスト抽出中...)'}}
            `;
        }}
        
        // ===================================================================
        // コンテキストメニュー
        // ===================================================================
        function showContextMenu(e, regionId) {{
            const menu = document.getElementById('context-menu');
            menu.style.left = e.clientX + 'px';
            menu.style.top = e.clientY + 'px';
            menu.classList.add('visible');
            menu.dataset.regionId = regionId;
            selectedRegion = regionId;
        }}
        
        function hideContextMenu() {{
            document.getElementById('context-menu').classList.remove('visible');
        }}
        
        document.addEventListener('click', hideContextMenu);
        
        function extractRegionFromMenu() {{
            const regionId = document.getElementById('context-menu').dataset.regionId;
            const region = [...webRegions, ...pdfRegions].find(r => r.id === regionId);
            if (region) extractRegionText(region);
            hideContextMenu();
        }}
        
        function deleteRegionFromMenu() {{
            const regionId = document.getElementById('context-menu').dataset.regionId;
            deleteRegion(regionId);
        }}
        
        function linkRegion() {{
            const regionId = document.getElementById('context-menu').dataset.regionId;
            const region = [...webRegions, ...pdfRegions].find(r => r.id === regionId);
            
            if (!region) return;
            
            alert('リンク先の領域をクリックしてください');
            
            document.addEventListener('click', function linkHandler(e) {{
                const target = e.target.closest('.selection-region');
                if (target && target.dataset.regionId !== regionId) {{
                    region.linkedTo = target.dataset.regionId;
                    
                    // 視覚的なリンク表示
                    const el = document.querySelector(`[data-region-id="${{regionId}}"]`);
                    el.style.borderColor = '#a855f7';
                    target.style.borderColor = '#a855f7';
                    
                    document.removeEventListener('click', linkHandler);
                }}
            }}, {{ once: true }});
            
            hideContextMenu();
        }}
        
        // ===================================================================
        // キーボードショートカット
        // ===================================================================
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Delete' || e.key === 'Backspace') {{
                if (selectedRegion) {{
                    deleteRegion(selectedRegion);
                }}
            }}
            if (e.key === 'Escape') {{
                isSelectionMode = false;
                document.getElementById('btn-select-mode').classList.remove('active');
                document.body.classList.remove('selection-mode');
            }}
            if (e.ctrlKey && e.key === 'z') {{
                undo();
            }}
        }});
        
        function undo() {{
            const action = undoStack.pop();
            if (!action) return;
            
            if (action.type === 'create') {{
                deleteRegion(action.region.id);
            }}
        }}
        
        // ===================================================================
        // サジェスト・比較・エクスポート
        // ===================================================================
        document.getElementById('toggle-suggestions').addEventListener('change', function() {{
            const panel = document.getElementById('suggestions-panel');
            panel.classList.toggle('visible', this.checked);
            if (this.checked) {{
                renderSuggestions();
            }}
        }});
        
        function renderSuggestions() {{
            const list = document.getElementById('suggestions-list');
            if (!suggestions.length) {{
                list.innerHTML = '<p style="color:#8b949e;">サジェストはありません</p>';
                return;
            }}
            
            list.innerHTML = suggestions.map(s => `
                <div class="suggestion-item">
                    <div class="suggestion-type">${{s.type}}</div>
                    <div class="suggestion-original">元: ${{s.original}}</div>
                    <div class="suggestion-new">→ ${{s.suggestion}}</div>
                </div>
            `).join('');
        }}
        
        document.querySelectorAll('.text-block').forEach(block => {{
            block.addEventListener('click', function() {{
                document.querySelectorAll('.text-block').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                const regionId = this.dataset.regionId;
                highlightRegion(regionId);
            }});
        }});
        
        function highlightRegion(regionId) {{
            document.querySelectorAll('.selection-region').forEach(r => {{
                r.classList.toggle('active', r.dataset.regionId === regionId);
            }});
        }}
        
        document.getElementById('btn-export').addEventListener('click', function() {{
            const data = {{
                sync_rate: {sync_rate},
                diff_count: {diff_count},
                web_regions: webRegions,
                pdf_regions: pdfRegions,
                web_text: document.getElementById('web-text-content').innerText,
                pdf_text: document.getElementById('pdf-text-content').innerText,
                exported_at: new Date().toISOString()
            }};
            
            const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'comparison_result.json';
            a.click();
        }});
        
        document.getElementById('btn-compare').addEventListener('click', async function() {{
            const webText = webRegions.map(r => r.text).join('\\n\\n') || 
                           document.getElementById('web-text-content').innerText;
            const pdfText = pdfRegions.map(r => r.text).join('\\n\\n') || 
                           document.getElementById('pdf-text-content').innerText;
            
            this.classList.add('loading');
            this.textContent = '⏳ 比較中...';
            
            try {{
                const res = await fetch('/api/v1/compare', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        text_a: webText,
                        text_b: pdfText,
                        label_a: 'Web',
                        label_b: 'PDF'
                    }})
                }});
                
                const result = await res.json();
                
                document.querySelector('.sync-rate-value').textContent = result.sync_rate + '%';
                document.querySelector('.sync-rate-value').style.color = 
                    result.sync_rate >= 95 ? '#3fb950' : result.sync_rate >= 80 ? '#f0883e' : '#f85149';
                document.querySelector('.stat-card:first-child .stat-value').textContent = result.sync_rate + '%';
                document.querySelector('.stat-card:last-child .stat-value').textContent = result.diff_count;
                document.getElementById('diff-display').innerHTML = result.diff_html;
                
            }} catch (e) {{
                console.error(e);
                alert('比較に失敗しました');
            }} finally {{
                this.classList.remove('loading');
                this.textContent = '🔄 再比較';
            }}
        }});
    </script>
</body>
</html>'''
        
        return html
    
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
