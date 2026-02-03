import os
import json
import base64

class SitemapGenerator:
    """
    Generates an interactive HTML sitemap using vis.js
    """
    
    @staticmethod
    def generate(nodes, edges, output_path="sitemap_view.html"):
        """
        nodes: list of dicts with id, url, title, screenshot (path), text
        edges: list of dicts with from, to
        """
        
        # 1. データをJS用に整形
        js_nodes = []
        for n in nodes:
            # 画像をBase64埋め込み（ローカルファイルアクセスのCORS回避 & ポータビリティのため）
            img_b64 = ""
            if n.get("screenshot") and os.path.exists(n["screenshot"]):
                try:
                    with open(n["screenshot"], "rb") as f:
                        start_bytes = f.read()
                        img_b64 = "data:image/png;base64," + base64.b64encode(start_bytes).decode('utf-8')
                except Exception as e:
                    print(f"Image load error: {e}")
            
            # ノード情報
            js_nodes.append({
                "id": n["url"], # IDをURLにする
                "label": n["title"][:15] + "..." if len(n["title"]) > 15 else n["title"],
                "title": n["url"], # ホバー時のツールチップ
                "shape": "image",
                "image": img_b64 if img_b64 else "https://via.placeholder.com/150", 
                "size": 40 if n["depth"] == 0 else 25,
                "data": { # クリック時に表示する詳細データ
                    "full_title": n["title"],
                    "url": n["url"],
                    "text_preview": n["text"],
                    "full_text": n.get("full_text", "")
                }
            })

        js_edges = []
        for e in edges:
            js_edges.append({
                "from": e["from"],
                "to": e["to"],
                "arrows": "to",
                "color": {"color": "#848484", "highlight": "#00d2ff"}
            })

        # 2. HTMLテンプレート生成
        html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visual Sitemap - Genius View</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        :root {{
            --bg-color: #1a1a1a;
            --panel-bg: rgba(43, 43, 43, 0.85);
            --text-color: #ffffff;
            --accent-color: #00d2ff;
        }}
        body {{ 
            margin: 0; 
            padding: 0; 
            background-color: var(--bg-color); 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden; 
            color: var(--text-color);
        }}
        #network {{ 
            width: 100vw; 
            height: 100vh; 
            position: absolute; 
            top: 0; 
            left: 0;
            z-index: 1;
        }}
        
        /* Glassmorphism Panel */
        #details-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            width: 400px;
            max-height: 90vh;
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            padding: 24px;
            z-index: 10;
            transform: translateX(450px);
            transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
            overflow-y: auto;
        }}
        
        #details-panel.active {{
            transform: translateX(0);
        }}

        h2 {{ margin-top: 0; font-size: 1.2rem; color: var(--accent-color); }}
        .meta-info {{ font-size: 0.85rem; color: #aaa; margin-bottom: 15px; word-break: break-all; }}
        .text-content {{ 
            font-size: 0.9rem; 
            line-height: 1.6; 
            background: rgba(0,0,0,0.3); 
            padding: 15px; 
            border-radius: 8px;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
        }}
        .close-btn {{
            position: absolute;
            top: 15px;
            right: 15px;
            background: none;
            border: none;
            color: #fff;
            font-size: 1.2rem;
            cursor: pointer;
            opacity: 0.7;
        }}
        .close-btn:hover {{ opacity: 1; }}

        #loading {{
            position: absolute; top: 50%; left: 50%; 
            transform: translate(-50%, -50%); 
            color: var(--accent-color); z-index: 100;
        }}
    </style>
</head>
<body>
    <div id="loading">Initializing Genius Engine...</div>
    <div id="network"></div>
    
    <div id="details-panel">
        <button class="close-btn" onclick="closePanel()">×</button>
        <h2 id="p-title">Page Title</h2>
        <div class="meta-info" id="p-url">https://example.com</div>
        <div class="text-content" id="p-text">
            No node selected.
        </div>
        <div style="margin-top: 15px; text-align: right;">
             <button onclick="copyText()" style="background:var(--accent-color); border:none; padding:8px 16px; border-radius:4px; cursor:pointer; font-weight:bold;">Copy Text</button>
        </div>
    </div>

    <script type="text/javascript">
        const nodes = new vis.DataSet({json.dumps(js_nodes, ensure_ascii=False)});
        const edges = new vis.DataSet({json.dumps(js_edges, ensure_ascii=False)});

        const container = document.getElementById('network');
        const data = {{ nodes: nodes, edges: edges }};
        const options = {{
            nodes: {{
                borderWidth: 2,
                borderWidthSelected: 4,
                color: {{
                    border: '#404040',
                    background: '#666666',
                    highlight: {{
                        border: '#00d2ff',
                        background: '#ffffff'
                    }}
                }},
                font: {{ color: '#ffffff' }}
            }},
            physics: {{
                stabilization: false,
                barnesHut: {{
                    gravitationalConstant: -8000,
                    springConstant: 0.04,
                    springLength: 95
                }}
            }},
            layout: {{
                hierarchical: {{
                    enabled: true,
                    direction: 'UD', // Up-Down
                    sortMethod: 'directed',
                    levelSeparation: 150,
                    nodeSpacing: 200
                }}
            }}
        }};

        const network = new vis.Network(container, data, options);

        network.on("click", function (params) {{
            if (params.nodes.length > 0) {{
                const nodeId = params.nodes[0];
                const nodeData = nodes.get(nodeId);
                showDetails(nodeData);
            }} else {{
                closePanel();
            }}
        }});
        
        network.once("afterDrawing", function() {{
             document.getElementById('loading').style.display = 'none';
        }});

        function showDetails(node) {{
            const d = node.data;
            document.getElementById('p-title').innerText = d.full_title;
            document.getElementById('p-url').innerText = d.url;
            document.getElementById('p-text').innerText = d.full_text || d.text_preview;
            document.getElementById('details-panel').classList.add('active');
        }}

        function closePanel() {{
            document.getElementById('details-panel').classList.remove('active');
        }}
        
        function copyText() {{
            const text = document.getElementById('p-text').innerText;
            navigator.clipboard.writeText(text).then(() => {{
                alert('Copied to clipboard!');
            }});
        }}
    </script>
</body>
</html>
        """
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return os.path.abspath(output_path)
