"""
エクスポーターモジュール
HTML/CSV/JSON/監査レポート生成
"""
import json
import csv
import io
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.db import models


class Exporter:
    """エクスポート機能"""
    
    def __init__(self, db: Session, job_id: str):
        self.db = db
        self.job_id = job_id
        self.job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    def export_csv(self) -> str:
        """CSV形式でエクスポート"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー
        writer.writerow([
            "ID", "URL", "Title", "Status", "Depth", "ParentID",
            "H1", "Description", "Canonical", "Noindex",
            "CrawledAt"
        ])
        
        # 親マップ構築
        parent_map = {}
        for link in self.job.links:
            parent_map[link.target_page_id] = link.source_page_id
        
        # データ行
        for page in self.job.pages:
            metadata = page.metadata_info or {}
            parent_id = parent_map.get(page.id, "")
            
            writer.writerow([
                page.id,
                page.url,
                page.title or "",
                page.status_code,
                page.depth,
                parent_id,
                metadata.get("h1", ""),
                metadata.get("description", ""),
                metadata.get("canonical", ""),
                "yes" if metadata.get("noindex") else "no",
                page.crawled_at.isoformat() if page.crawled_at else ""
            ])
        
        output.seek(0)
        return output.getvalue()
    
    def export_json(self) -> Dict[str, Any]:
        """JSON形式でエクスポート（ノード＆エッジ）"""
        nodes = []
        edges = []
        
        for page in self.job.pages:
            metadata = page.metadata_info or {}
            nodes.append({
                "id": page.id,
                "url": page.url,
                "title": page.title,
                "status_code": page.status_code,
                "depth": page.depth,
                "screenshot_path": page.screenshot_path,
                "screenshot_sp_path": page.screenshot_sp_path,
                "content_hash": page.content_hash,
                "metadata": metadata,
                "crawled_at": page.crawled_at.isoformat() if page.crawled_at else None
            })
        
        for link in self.job.links:
            edges.append({
                "source": link.source_page_id,
                "target": link.target_page_id,
                "type": link.type
            })
        
        return {
            "job_id": self.job_id,
            "start_url": self.job.start_url,
            "status": self.job.status,
            "pages_crawled": self.job.pages_crawled,
            "started_at": self.job.started_at.isoformat() if self.job.started_at else None,
            "completed_at": self.job.completed_at.isoformat() if self.job.completed_at else None,
            "result_summary": self.job.result_summary,
            "nodes": nodes,
            "edges": edges
        }
    
    def export_html(self) -> str:
        """
        インタラクティブHTMLサイトマップ生成
        Cytoscape.js を使用したツリービュー＋詳細パネル
        改良版: URLラベル、ツールチップ、凡例、操作ガイド付き
        """
        nodes = []
        edges = []
        
        for page in self.job.pages:
            metadata = page.metadata_info or {}
            # URLからパス部分を抽出（ラベル用）
            from urllib.parse import urlparse
            parsed = urlparse(page.url)
            path_label = parsed.path if parsed.path and parsed.path != '/' else '/'
            # 長いパスは省略
            if len(path_label) > 25:
                path_label = path_label[:22] + '...'
            
            nodes.append({
                "data": {
                    "id": str(page.id),
                    "url": page.url,
                    "title": page.title or "No Title",
                    "path_label": path_label,
                    "depth": page.depth,
                    "status": page.status_code,
                    "h1": metadata.get("h1", ""),
                    "description": metadata.get("description", ""),
                    "canonical": metadata.get("canonical", ""),
                    "noindex": metadata.get("noindex", False),
                    "screenshot": f"/api/v1/jobs/{self.job_id}/screenshots/{page.screenshot_path.split('/')[-1]}" if page.screenshot_path else None,
                    "crawled_at": page.crawled_at.isoformat() if page.crawled_at else ""
                }
            })
        
        for link in self.job.links:
            edges.append({
                "data": {
                    "source": str(link.source_page_id),
                    "target": str(link.target_page_id)
                }
            })
        
        nodes_json = json.dumps(nodes, ensure_ascii=False)
        edges_json = json.dumps(edges, ensure_ascii=False)
        
        # 結果サマリー
        summary = self.job.result_summary or {}
        
        html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>サイトマップ: {self.job.start_url}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', 'Hiragino Sans', sans-serif; 
            display: flex;
            flex-direction: column;
            height: 100vh;
            background: #1a1a2e;
            color: #eee;
        }}
        /* ツールバー */
        .toolbar {{
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 10px 20px;
            background: #0f3460;
            border-bottom: 1px solid #00d9ff;
        }}
        .toolbar h2 {{
            font-size: 16px;
            color: #00d9ff;
            margin-right: auto;
        }}
        .layout-btn {{
            background: #1a1a2e;
            border: 1px solid #0f3460;
            color: #888;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }}
        .layout-btn:hover {{ border-color: #00d9ff; color: #00d9ff; }}
        .layout-btn.active {{ background: #00d9ff; color: #1a1a2e; border-color: #00d9ff; }}
        /* メインコンテナ */
        .main-container {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}
        .main-container.matrix {{
            flex-wrap: wrap;
        }}
        .main-container.matrix #sidebar {{
            width: 50% !important;
            height: 50%;
            border-right: 1px solid #0f3460;
            border-bottom: 1px solid #0f3460;
        }}
        .main-container.matrix #cy {{
            width: 50%;
            height: 50%;
            border-bottom: 1px solid #0f3460;
        }}
        .main-container.matrix #resizer {{ display: none; }}
        .main-container.matrix .screenshot-panel {{
            width: 50%;
            height: 50%;
            overflow: auto;
            background: #16213e;
            padding: 20px;
        }}
        .main-container.matrix .page-list-panel {{
            width: 50%;
            height: 50%;
            overflow: auto;
            background: #1a1a2e;
            padding: 20px;
        }}
        /* サイドバー（左側） */
        #sidebar {{ 
            width: 400px; 
            padding: 20px; 
            overflow-y: auto; 
            background: #16213e;
            border-right: 1px solid #0f3460;
            order: 1;
        }}
        #resizer {{ order: 2; }}
        #cy {{ 
            flex: 1;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            position: relative;
            order: 3;
        }}
        .legend {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(15, 52, 96, 0.95);
            border-radius: 8px;
            padding: 15px;
            z-index: 100;
            font-size: 12px;
        }}
        .legend h4 {{ margin-bottom: 10px; color: #00d9ff; font-size: 14px; }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 8px; }}
        .legend-color {{ 
            width: 16px; height: 16px; border-radius: 50%; margin-right: 10px;
            border: 2px solid;
        }}
        .legend-color.root {{ background: #00d9ff; border-color: #00d9ff; }}
        .legend-color.normal {{ background: #0f3460; border-color: #00d9ff; }}
        .legend-color.error {{ background: #e94560; border-color: #e94560; }}
        .legend-text {{ color: #ccc; }}
        .help-text {{
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(15, 52, 96, 0.9);
            border-radius: 8px;
            padding: 12px 15px;
            z-index: 100;
            font-size: 12px;
            color: #888;
        }}
        .help-text strong {{ color: #00d9ff; }}
        .summary {{ 
            background: #0f3460; 
            border-radius: 8px; 
            padding: 15px; 
            margin-bottom: 20px;
        }}
        .summary h3 {{ margin-bottom: 10px; color: #e94560; }}
        .summary-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .stat {{ background: #1a1a2e; padding: 10px; border-radius: 4px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #00d9ff; }}
        .stat-label {{ font-size: 12px; color: #888; }}
        .detail {{ background: #0f3460; border-radius: 8px; padding: 15px; }}
        .detail h3 {{ margin-bottom: 15px; color: #e94560; }}
        .detail-row {{ margin-bottom: 12px; }}
        .detail-label {{ font-size: 11px; color: #888; text-transform: uppercase; }}
        .detail-value {{ 
            font-size: 14px; 
            word-break: break-all;
            margin-top: 4px;
        }}
        .detail-value a {{ color: #00d9ff; text-decoration: none; }}
        .detail-value a:hover {{ text-decoration: underline; }}
        img.preview {{ 
            max-width: 100%; 
            border: 1px solid #0f3460; 
            margin-top: 15px; 
            border-radius: 4px;
        }}
        .status-ok {{ color: #00d9ff; }}
        .status-error {{ color: #e94560; }}
        .status-warning {{ color: #ffc107; }}
        .tag {{ 
            display: inline-block; 
            padding: 2px 8px; 
            border-radius: 4px; 
            font-size: 11px;
            margin-right: 4px;
        }}
        .tag-error {{ background: #e94560; }}
        .tag-warning {{ background: #ffc107; color: #000; }}
        .tag-info {{ background: #0f3460; }}
        #tooltip {{
            position: absolute;
            background: rgba(15, 52, 96, 0.95);
            border: 1px solid #00d9ff;
            border-radius: 6px;
            padding: 10px 12px;
            font-size: 12px;
            z-index: 1000;
            pointer-events: none;
            display: none;
            max-width: 350px;
        }}
        #tooltip .tt-title {{ color: #00d9ff; font-weight: bold; margin-bottom: 4px; }}
        #tooltip .tt-url {{ color: #888; word-break: break-all; }}
        #tooltip .tt-status {{ margin-top: 4px; }}
        .initial-prompt {{
            text-align: center;
            color: #888;
            padding: 40px 20px;
        }}
        .initial-prompt .icon {{ font-size: 48px; margin-bottom: 15px; }}
        /* リサイザー */
        #resizer {{
            width: 6px;
            background: #0f3460;
            cursor: col-resize;
            transition: background 0.2s;
            flex-shrink: 0;
        }}
        #resizer:hover, #resizer.dragging {{
            background: #00d9ff;
        }}
        #resizer::after {{
            content: '⋮';
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            color: #888;
            font-size: 16px;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <!-- ツールバー -->
    <div class="toolbar">
        <h2>🗺️ サイトマップビューワー</h2>
        <span style="color:#888; font-size:12px;">レイアウト:</span>
        <button class="layout-btn active" onclick="setLayout('split')" id="btn-split">◧ 分割</button>
        <button class="layout-btn" onclick="setLayout('matrix')" id="btn-matrix">田 マトリクス</button>
    </div>
    
    <!-- メインコンテナ -->
    <div class="main-container" id="main-container">
        <!-- サイドバー（左側） -->
        <div id="sidebar">
            <div class="summary">
                <h3>📊 サイト構造サマリー</h3>
                <div class="summary-grid">
                    <div class="stat">
                        <div class="stat-value">{summary.get('total_pages', 0)}</div>
                        <div class="stat-label">総ページ数</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value status-ok">{summary.get('status_200', 0)}</div>
                        <div class="stat-label">正常 (200)</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value status-error">{summary.get('status_404', 0)}</div>
                        <div class="stat-label">404エラー</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value status-warning">{summary.get('warnings', 0)}</div>
                        <div class="stat-label">警告</div>
                    </div>
                </div>
            </div>
            <div class="detail">
                <h3>📄 ページ詳細</h3>
                <div id="detail">
                    <div class="initial-prompt">
                        <div class="icon">👆</div>
                        <p>グラフ上のノード（丸）をクリックすると<br>ページの詳細情報が表示されます</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- リサイザー -->
        <div id="resizer"></div>
        
        <!-- グラフエリア（右側） -->
        <div id="cy">
            <div id="tooltip"></div>
            <div class="help-text">
                <strong>🖱️ 操作方法:</strong> ドラッグで移動 / スクロールでズーム / <strong>クリックで詳細表示</strong>
            </div>
            <div class="legend">
                <h4>📍 凡例</h4>
                <div class="legend-item">
                    <div class="legend-color root"></div>
                    <span class="legend-text">開始ページ (トップ)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color normal"></div>
                    <span class="legend-text">正常ページ (HTTP 200)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color error"></div>
                    <span class="legend-text">エラーページ (404等)</span>
                </div>
            </div>
        </div>
        
        <!-- マトリクス用追加パネル（初期非表示） -->
        <div class="screenshot-panel" id="screenshot-panel" style="display:none;">
            <h3 style="color:#e94560; margin-bottom:15px;">🖼️ スクリーンショット</h3>
            <div id="screenshot-view">
                <div class="initial-prompt">
                    <p>ノードをクリックするとスクリーンショットが表示されます</p>
                </div>
            </div>
        </div>
        <div class="page-list-panel" id="page-list-panel" style="display:none;">
            <h3 style="color:#e94560; margin-bottom:15px;">📋 ページ一覧</h3>
            <div id="page-list"></div>
        </div>
    </div>
    
    <script>
        const elements = {{
            nodes: {nodes_json},
            edges: {edges_json}
        }};
        
        window.cy = cytoscape({{
            container: document.getElementById('cy'),
            elements: elements,
            style: [
                {{
                    selector: 'node',
                    style: {{
                        'background-color': '#0f3460',
                        'border-color': '#00d9ff',
                        'border-width': 2,
                        'label': 'data(path_label)',
                        'color': '#fff',
                        'text-valign': 'bottom',
                        'text-margin-y': 8,
                        'font-size': 9,
                        'width': 35, 
                        'height': 35,
                        'text-outline-color': '#1a1a2e',
                        'text-outline-width': 2
                    }}
                }},
                {{
                    selector: 'node[status!=200]',
                    style: {{ 
                        'background-color': '#e94560',
                        'border-color': '#e94560'
                    }}
                }},
                {{
                    selector: 'node[depth=0]',
                    style: {{ 
                        'width': 50, 
                        'height': 50, 
                        'background-color': '#00d9ff',
                        'border-color': '#00d9ff',
                        'font-size': 11,
                        'font-weight': 'bold'
                    }}
                }},
                {{
                    selector: 'node:selected',
                    style: {{
                        'border-width': 4,
                        'border-color': '#ffc107',
                        'overlay-opacity': 0.2,
                        'overlay-color': '#ffc107'
                    }}
                }},
                {{
                    selector: 'edge',
                    style: {{
                        'width': 2,
                        'line-color': '#0f3460',
                        'target-arrow-color': '#00d9ff',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'opacity': 0.7
                    }}
                }}
            ],
            layout: {{
                name: 'breadthfirst',
                directed: true,
                padding: 80,
                spacingFactor: 1.8,
                roots: elements.nodes.filter(n => n.data.depth === 0).map(n => n.data.id)
            }},
            wheelSensitivity: 0.3
        }});
        
        // ツールチップ
        var tooltip = document.getElementById('tooltip');
        
        cy.on('mouseover', 'node', function(evt){{
            var node = evt.target;
            var d = node.data();
            var pos = evt.renderedPosition;
            
            var statusText = d.status === 200 ? 
                '<span style="color:#00d9ff">✓ 正常</span>' : 
                '<span style="color:#e94560">✗ ' + d.status + '</span>';
            
            tooltip.innerHTML = `
                <div class="tt-title">${{d.title}}</div>
                <div class="tt-url">${{d.url}}</div>
                <div class="tt-status">${{statusText}} / 深さ: ${{d.depth}}</div>
            `;
            tooltip.style.left = (pos.x + 20) + 'px';
            tooltip.style.top = (pos.y - 10) + 'px';
            tooltip.style.display = 'block';
        }});
        
        cy.on('mouseout', 'node', function(){{
            tooltip.style.display = 'none';
        }});
        
        cy.on('tap', 'node', function(evt){{
            var node = evt.target;
            var d = node.data();
            
            var statusClass = d.status === 200 ? 'status-ok' : (d.status >= 400 ? 'status-error' : 'status-warning');
            var tags = '';
            if (d.noindex) tags += '<span class="tag tag-warning">noindex</span>';
            if (d.status === 404) tags += '<span class="tag tag-error">404</span>';
            if (!d.h1) tags += '<span class="tag tag-info">H1なし</span>';
            
            var html = `
                <div class="detail-row">
                    <div class="detail-label">URL</div>
                    <div class="detail-value"><a href="${{d.url}}" target="_blank">${{d.url}}</a></div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">タイトル</div>
                    <div class="detail-value">${{d.title}}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">ステータス</div>
                    <div class="detail-value ${{statusClass}}">${{d.status}} ${{tags}}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">深さ（階層）</div>
                    <div class="detail-value">${{d.depth}} 階層目</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">H1見出し</div>
                    <div class="detail-value">${{d.h1 || '(なし)'}}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Meta Description</div>
                    <div class="detail-value">${{d.description || '(なし)'}}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Canonical URL</div>
                    <div class="detail-value">${{d.canonical || '(設定なし)'}}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">取得日時</div>
                    <div class="detail-value">${{d.crawled_at}}</div>
                </div>
            `;
            
            if(d.screenshot) {{
                html += `<img class="preview" src="${{d.screenshot}}" alt="Screenshot">`;
            }}
            
            document.getElementById('detail').innerHTML = html;
        }});
        
        // リサイズ機能
        (function() {{
            const resizer = document.getElementById('resizer');
            const sidebar = document.getElementById('sidebar');
            const cy = document.getElementById('cy');
            
            // 保存された幅を復元
            const savedWidth = localStorage.getItem('sitemapSidebarWidth');
            if (savedWidth) {{
                sidebar.style.width = savedWidth + 'px';
            }}
            
            let isResizing = false;
            let startX, startWidth;
            
            resizer.addEventListener('mousedown', function(e) {{
                isResizing = true;
                startX = e.clientX;
                startWidth = parseInt(getComputedStyle(sidebar).width, 10);
                resizer.classList.add('dragging');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
                e.preventDefault();
            }});
            
            document.addEventListener('mousemove', function(e) {{
                if (!isResizing) return;
                
                const dx = startX - e.clientX;
                const newWidth = Math.max(250, Math.min(800, startWidth + dx));
                sidebar.style.width = newWidth + 'px';
            }});
            
            document.addEventListener('mouseup', function() {{
                if (isResizing) {{
                    isResizing = false;
                    resizer.classList.remove('dragging');
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';
                    
                    // 幅を保存
                    const currentWidth = parseInt(getComputedStyle(sidebar).width, 10);
                    localStorage.setItem('sitemapSidebarWidth', currentWidth);
                    
                    // グラフを再描画
                    window.cy && window.cy.resize();
                }}
            }});
        }})();
        
        // レイアウト切り替え
        function setLayout(mode) {{
            const container = document.getElementById('main-container');
            const screenshotPanel = document.getElementById('screenshot-panel');
            const pageListPanel = document.getElementById('page-list-panel');
            const btnSplit = document.getElementById('btn-split');
            const btnMatrix = document.getElementById('btn-matrix');
            
            if (mode === 'matrix') {{
                container.classList.add('matrix');
                screenshotPanel.style.display = 'block';
                pageListPanel.style.display = 'block';
                btnSplit.classList.remove('active');
                btnMatrix.classList.add('active');
                
                // ページ一覧を生成
                generatePageList();
            }} else {{
                container.classList.remove('matrix');
                screenshotPanel.style.display = 'none';
                pageListPanel.style.display = 'none';
                btnSplit.classList.add('active');
                btnMatrix.classList.remove('active');
            }}
            
            // グラフを再描画
            setTimeout(() => window.cy && window.cy.resize(), 100);
        }}
        
        // ページ一覧生成
        function generatePageList() {{
            const pageList = document.getElementById('page-list');
            const nodes = elements.nodes;
            
            let html = '<table style="width:100%; border-collapse:collapse; font-size:12px;">';
            html += '<tr style="background:#0f3460;"><th style="padding:8px; text-align:left;">URL</th><th style="padding:8px;">ステータス</th></tr>';
            
            nodes.forEach(node => {{
                const d = node.data;
                const statusColor = d.status === 200 ? '#00d9ff' : '#e94560';
                html += `<tr style="border-bottom:1px solid #0f3460; cursor:pointer;" onclick="selectNode('${{d.id}}')">
                    <td style="padding:8px; word-break:break-all;">${{d.path_label}}</td>
                    <td style="padding:8px; text-align:center; color:${{statusColor}}">${{d.status}}</td>
                </tr>`;
            }});
            
            html += '</table>';
            pageList.innerHTML = html;
        }}
        
        // ノード選択
        function selectNode(nodeId) {{
            const node = window.cy.getElementById(nodeId);
            if (node) {{
                window.cy.elements().unselect();
                node.select();
                node.trigger('tap');
                
                // スクリーンショットパネル更新
                const d = node.data();
                const screenshotView = document.getElementById('screenshot-view');
                if (d.screenshot) {{
                    screenshotView.innerHTML = `<img src="${{d.screenshot}}" style="max-width:100%; border-radius:8px;">`;
                }} else {{
                    screenshotView.innerHTML = '<div class="initial-prompt"><p>スクリーンショットがありません</p></div>';
                }}
            }}
        }}
        
        // ノードクリック時にスクリーンショットパネルも更新
        window.cy.on('tap', 'node', function(evt) {{
            const d = evt.target.data();
            const screenshotView = document.getElementById('screenshot-view');
            if (screenshotView) {{
                if (d.screenshot) {{
                    screenshotView.innerHTML = `<img src="${{d.screenshot}}" style="max-width:100%; border-radius:8px;">`;
                }} else {{
                    screenshotView.innerHTML = '<div class="initial-prompt"><p>スクリーンショットがありません</p></div>';
                }}
            }}
        }});
    </script>
</body>
</html>"""
        
        return html_content
    
    def export_audit_report(self) -> Dict[str, Any]:
        """監査レポートをJSON形式で生成"""
        findings = self.db.query(models.Finding).filter(
            models.Finding.job_id == self.job_id
        ).all()
        
        # タイプ別にグルーピング
        findings_by_type = {}
        for f in findings:
            if f.issue_type not in findings_by_type:
                findings_by_type[f.issue_type] = []
            
            page = self.db.query(models.Page).filter(models.Page.id == f.page_id).first()
            findings_by_type[f.issue_type].append({
                "page_id": f.page_id,
                "url": page.url if page else None,
                "level": f.level,
                "message": f.message
            })
        
        # サマリー
        summary = {
            "total": len(findings),
            "errors": sum(1 for f in findings if f.level == "error"),
            "warnings": sum(1 for f in findings if f.level == "warning"),
            "info": sum(1 for f in findings if f.level == "info")
        }
        
        return {
            "job_id": self.job_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "findings_by_type": findings_by_type
        }
    
    def export_audit_html(self) -> str:
        """監査レポートをHTML形式で生成"""
        audit_data = self.export_audit_report()
        summary = audit_data["summary"]
        findings_by_type = audit_data["findings_by_type"]
        
        # 問題タイプの表示名
        type_names = {
            "http_404": "404 Not Found",
            "http_5xx": "サーバーエラー",
            "redirect_chain": "リダイレクトチェーン",
            "missing_title": "Titleなし",
            "missing_h1": "H1なし",
            "missing_description": "Descriptionなし",
            "missing_ogp": "OGP欠落",
            "canonical_mismatch": "Canonical不整合",
            "noindex_detected": "noindex検出",
            "duplicate_content": "コンテンツ重複"
        }
        
        # 問題リストHTML生成
        findings_html = ""
        for issue_type, items in findings_by_type.items():
            level = items[0]["level"] if items else "info"
            level_class = "error" if level == "error" else ("warning" if level == "warning" else "info")
            type_name = type_names.get(issue_type, issue_type)
            
            items_html = ""
            for item in items:
                items_html += f"""
                <tr>
                    <td><a href="{item['url']}" target="_blank">{item['url']}</a></td>
                    <td>{item['message']}</td>
                </tr>
                """
            
            findings_html += f"""
            <div class="issue-group">
                <h3 class="{level_class}">{type_name} ({len(items)}件)</h3>
                <table>
                    <thead><tr><th>URL</th><th>詳細</th></tr></thead>
                    <tbody>{items_html}</tbody>
                </table>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>監査レポート - {self.job.start_url}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; border-bottom: 2px solid #e94560; padding-bottom: 10px; }}
        .summary {{ display: flex; gap: 20px; margin: 30px 0; }}
        .stat-card {{ 
            flex: 1; padding: 20px; border-radius: 8px; 
            background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card.error {{ border-left: 4px solid #e94560; }}
        .stat-card.warning {{ border-left: 4px solid #ffc107; }}
        .stat-card.info {{ border-left: 4px solid #00d9ff; }}
        .stat-value {{ font-size: 36px; font-weight: bold; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        .issue-group {{ 
            background: white; 
            margin-bottom: 20px; 
            border-radius: 8px; 
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .issue-group h3 {{ margin-bottom: 15px; }}
        .issue-group h3.error {{ color: #e94560; }}
        .issue-group h3.warning {{ color: #ffc107; }}
        .issue-group h3.info {{ color: #00d9ff; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f9f9f9; }}
        a {{ color: #0066cc; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 監査レポート</h1>
        <p>対象: <a href="{self.job.start_url}">{self.job.start_url}</a></p>
        <p>生成日時: {audit_data['generated_at']}</p>
        
        <div class="summary">
            <div class="stat-card error">
                <div class="stat-value">{summary['errors']}</div>
                <div class="stat-label">エラー</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-value">{summary['warnings']}</div>
                <div class="stat-label">警告</div>
            </div>
            <div class="stat-card info">
                <div class="stat-value">{summary['info']}</div>
                <div class="stat-label">情報</div>
            </div>
        </div>
        
        {findings_html if findings_html else "<p>問題は検出されませんでした。</p>"}
    </div>
</body>
</html>"""
        
        return html
