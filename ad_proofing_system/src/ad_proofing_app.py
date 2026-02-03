import streamlit as st
import io
import logging
import hashlib
import statistics
import copy
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import fitz  # PyMuPDF
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

# AI Models
try:
    from paddleocr import PaddleOCR
    from sentence_transformers import SentenceTransformer
except ImportError:
    st.error("Required libraries missing. Run: pip install paddlepaddle paddleocr sentence-transformers scikit-learn opencv-python")
    st.stop()

# ==========================================
# 0. Global Config
# ==========================================
logging.getLogger("ppocr").setLevel(logging.ERROR)
Image.MAX_IMAGE_PIXELS = None

# ==========================================
# 1. Vision Core (The Eye)
# ==========================================
# Omni-directional scanning logic from V9, refined for V10

@st.cache_resource
def load_ocr():
    return PaddleOCR(
        use_angle_cls=True, lang='japan', ocr_version='PP-OCRv4',
        use_gpu=False, show_log=False,
        det_db_thresh=0.05, det_db_box_thresh=0.2, det_db_unclip_ratio=2.5,
        rec_batch_num=1
    )

class VisionCore:
    def __init__(self):
        self.ocr = load_ocr()

    def omni_scan_and_merge(self, img_cv):
        """
        0度と180度の世界を統合し、最も確からしい文字だけを残す
        """
        h, w = img_cv.shape[:2]
        candidates = []
        
        # 1. Multi-Angle Scanning
        angles = [0, 180] # 90/270 needed? Usually auto-handled, but can add if vertical text fails
        
        progress = st.progress(0)
        
        for i, ang in enumerate(angles):
            work_img = img_cv
            if ang == 180: work_img = cv2.rotate(img_cv, cv2.ROTATE_180)
            
            # OCR Execution
            res = self.ocr.ocr(work_img, cls=True)
            
            if res and res[0]:
                for line in res[0]:
                    box = np.array(line[0])
                    text, conf = line[1]
                    
                    # Coordinate Restoration
                    if ang == 180:
                        restored_box = []
                        for p in box:
                            restored_box.append([w - p[0], h - p[1]])
                        box = np.array(restored_box)
                    
                    # Center Calc
                    center = np.mean(box, axis=0)
                    
                    candidates.append({
                        "text": text,
                        "conf": conf,
                        "box": box.tolist(),
                        "center": center.tolist(),
                        "angle_src": ang
                    })
            progress.progress((i+1)/len(angles))
        progress.empty()
        
        # 2. Advanced Merging (Spatially Aware NMS)
        # 近くにあってテキストが似ているものを統合
        candidates.sort(key=lambda x: x['conf'], reverse=True)
        unique_items = []
        
        while candidates:
            best = candidates.pop(0)
            unique_items.append(best)
            
            # Remove nearby duplicates
            best_center = np.array(best['center'])
            # 閾値: 文字の高さ程度
            h_char = np.linalg.norm(np.array(best['box'][0]) - np.array(best['box'][3]))
            
            keep = []
            for other in candidates:
                dist = np.linalg.norm(best_center - np.array(other['center']))
                if dist < h_char * 0.5: continue # Too close, drop it
                keep.append(other)
            candidates = keep
            
        return unique_items

# ==========================================
# 2. Semantic Cortex (The Brain)
# ==========================================
# Uses BERT embeddings instead of Regex

@st.cache_resource
def load_semantic_model():
    # Multilingual MiniLM: Lightweight, fast, good for Japanese context
    return SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

class SemanticCortex:
    def __init__(self):
        self.model = load_semantic_model()
        
        # Define Concept Anchors (The "Meaning" of categories)
        self.categories = {
            "Price/Offer": ["価格", "円", "税込", "OFF", "割引", "特別価格", "¥", "値段"],
            "Legal/Note": ["※", "注", "返品", "交換", "特定商取引", "個人の感想", "有効期限", "規約"],
            "Spec/Info": ["サイズ", "素材", "成分", "内容量", "cm", "kg", "原産国", "仕様"],
            "Contact/CTA": ["電話", "TEL", "http", "検索", "アクセス", "住所", "お問い合わせ"],
            "Catchcopy": ["最高", "No.1", "登場", "新発売", "ランキング", "衝撃", "感動"],
            "Review": ["お客様の声", "満足", "愛用", "使いやすい", "リピート"],
            "Body": ["説明", "本文", "詳細"]
        }
        
        # Pre-compute anchor embeddings
        self.anchor_embeddings = {}
        for cat, keywords in self.categories.items():
            # Combine keywords into a "concept sentence"
            concept_text = " ".join(keywords)
            self.anchor_embeddings[cat] = self.model.encode(concept_text)

    def classify_and_structure(self, raw_items):
        """
        1. Spatial Clustering (DBSCAN) -> Form Paragraphs
        2. Semantic Classification (BERT) -> Assign Category
        """
        if not raw_items: return []
        
        # --- A. Spatial Clustering (Form Paragraphs) ---
        centers = np.array([r['center'] for r in raw_items])
        # 重み付け: Y軸(行)を重視
        features = centers * np.array([0.2, 1.5]) 
        
        # 平均文字高さを取得
        heights = []
        for r in raw_items:
            pts = np.array(r['box'])
            h = np.linalg.norm(pts[0] - pts[3])
            heights.append(h)
        avg_h = statistics.median(heights) if heights else 20
        
        # DBSCAN
        clustering = DBSCAN(eps=avg_h * 2.5, min_samples=1).fit(features)
        
        clusters = {}
        for idx, label in enumerate(clustering.labels_):
            if label not in clusters: clusters[label] = []
            clusters[label].append(raw_items[idx])
            
        structured_blocks = []
        
        # --- B. Process Each Cluster ---
        for label, items in clusters.items():
            # Reading Order Sort (Top-Down, Left-Right)
            items.sort(key=lambda x: (int(x['center'][1] // (avg_h * 0.8)), x['center'][0]))
            
            # Merge Text
            full_text = "".join([i['text'] for i in items])
            
            # --- C. Semantic Classification ---
            # Encode text
            text_vec = self.model.encode(full_text)
            
            # Find closest category
            best_cat = "Body"
            max_score = -1
            
            for cat, anchor_vec in self.anchor_embeddings.items():
                score = cosine_similarity([text_vec], [anchor_vec])[0][0]
                
                # Heuristic Boosts
                if cat == "Price/Offer" and any(c in full_text for c in "円¥"): score += 0.3
                if cat == "Legal/Note" and "※" in full_text: score += 0.3
                
                if score > max_score:
                    max_score = score
                    best_cat = cat
            
            # Bounding Rect
            all_pts = []
            for i in items: all_pts.extend(i['box'])
            all_pts = np.array(all_pts)
            x_min, y_min = np.min(all_pts, axis=0)
            x_max, y_max = np.max(all_pts, axis=0)
            
            structured_blocks.append({
                "id": str(label),
                "category": best_cat,
                "text": full_text,
                "raw_items": items,
                "rect": [int(x_min), int(y_min), int(x_max-x_min), int(y_max-y_min)],
                "conf": statistics.mean([i['conf'] for i in items])
            })
            
        # Final Sort
        structured_blocks.sort(key=lambda x: x['rect'][1])
        return structured_blocks

# ==========================================
# 3. Ergonomic UI (The Interface)
# ==========================================

def main():
    st.set_page_config(layout="wide", page_title="Ultrathink V10: Chimera", initial_sidebar_state="expanded")
    
    # Ergonomic CSS: Dark Mode, Card Layout, Hover effects
    st.markdown("""
    <style>
        .stApp { background-color: #1e1e1e; color: #f0f0f0; }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] { background-color: #252526; border-right: 1px solid #333; }
        
        /* Metric cards */
        div[data-testid="stMetricValue"] { font-size: 1.2rem; }
        
        /* Input areas */
        textarea { background-color: #2d2d2d !important; color: #eee !important; border: 1px solid #444 !important; }
        
        /* Category Tags */
        .cat-badge { padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; display: inline-block; margin-bottom: 4px; }
    </style>
    """, unsafe_allow_html=True)

    # Init Engines
    if 'vision' not in st.session_state: st.session_state['vision'] = VisionCore()
    if 'semantic' not in st.session_state: st.session_state['semantic'] = SemanticCortex()
    
    # State
    if 'blocks' not in st.session_state: st.session_state['blocks'] = []
    if 'active_block_idx' not in st.session_state: st.session_state['active_block_idx'] = None

    # --- 1. Left Sidebar (Control & Status) ---
    with st.sidebar:
        st.header("🧬 Chimera V10")
        st.caption("Vision + Semantics + Ergonomics")
        
        uploaded = st.file_uploader("Upload Creative", type=["pdf", "png", "jpg"])
        
        if uploaded:
            fb = uploaded.getvalue()
            fh = hashlib.md5(fb).hexdigest()
            if st.session_state.get('fh') != fh:
                st.session_state['fh'] = fh
                # High DPI is non-negotiable
                if uploaded.type == "application/pdf":
                    with st.spinner("Rendering 600 DPI High-Res..."):
                        pix = fitz.open(stream=fb, filetype="pdf")[0].get_pixmap(dpi=600)
                        st.session_state['img'] = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                else:
                    st.session_state['img'] = Image.open(io.BytesIO(fb)).convert("RGB")
                st.session_state['blocks'] = []
                st.rerun()
        
        if 'img' in st.session_state:
            st.divider()
            if st.button("🚀 IGNITE CHIMERA ENGINE", type="primary", use_container_width=True):
                with st.spinner("Step 1: Omni-Directional Vision Scanning..."):
                    img_cv = cv2.cvtColor(np.array(st.session_state['img']), cv2.COLOR_RGB2BGR)
                    raw_items = st.session_state['vision'].omni_scan_and_merge(img_cv)
                
                with st.spinner("Step 2: Semantic Cortex processing (BERT)..."):
                    blocks = st.session_state['semantic'].classify_and_structure(raw_items)
                    st.session_state['blocks'] = blocks
                
                st.success(f"Synthesized {len(blocks)} Semantic Blocks.")
                st.rerun()

            st.divider()
            # Mini Dashboard
            if st.session_state['blocks']:
                counts = pd.DataFrame(st.session_state['blocks'])['category'].value_counts()
                st.write("**Segment Distribution**")
                st.dataframe(counts, use_container_width=True)

    # --- Main Workspace ---
    if 'img' in st.session_state:
        # Layout: 2/3 Visual, 1/3 Editor
        col_vis, col_edit = st.columns([1.8, 1.2])
        
        # --- 2. Center Pane (Visual Canvas) ---
        with col_vis:
            st.subheader("👁️ Contextual View")
            
            vis_img = np.array(st.session_state['img']).copy()
            overlay = vis_img.copy()
            
            # Color Map
            colors = {
                "Price/Offer": (0, 215, 255), "Legal/Note": (0, 0, 255),
                "Catchcopy": (255, 0, 215), "Spec/Info": (0, 255, 0),
                "Contact/CTA": (255, 165, 0), "Review": (128, 0, 128), "Body": (200, 200, 200)
            }

            if st.session_state['blocks']:
                # Draw Blocks
                for idx, b in enumerate(st.session_state['blocks']):
                    x, y, w, h = b['rect']
                    color = colors.get(b['category'], (200, 200, 200))
                    
                    # Highlight Active
                    thickness = 2
                    if idx == st.session_state['active_block_idx']:
                        thickness = -1 # Fill
                        cv2.rectangle(overlay, (x, y), (x+w, y+h), color, thickness)
                    else:
                        cv2.rectangle(vis_img, (x, y), (x+w, y+h), color, thickness)
                        # Add label ID
                        cv2.putText(vis_img, str(idx+1), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                
                # Blend overlay for active highlight
                cv2.addWeighted(overlay, 0.4, vis_img, 0.6, 0, vis_img)
                
                st.image(vis_img, use_column_width=True, caption="Select block from the right list to highlight.")

        # --- 3. Right Pane (Ergonomic Editor) ---
        with col_edit:
            st.subheader("📝 Semantic Editor")
            
            if not st.session_state['blocks']:
                st.info("Run the engine to extract data.")
            else:
                # Group by Category for easier navigation
                cats = sorted(list(set(b['category'] for b in st.session_state['blocks'])))
                selected_cat_filter = st.selectbox("Filter by Category", ["All"] + cats)
                
                # Scrollable area container
                with st.container(height=700):
                    for idx, b in enumerate(st.session_state['blocks']):
                        if selected_cat_filter != "All" and b['category'] != selected_cat_filter:
                            continue
                        
                        # Determine card style based on active state
                        border_color = "#444"
                        if idx == st.session_state['active_block_idx']:
                            border_color = "#00d2ff"
                        
                        # Card Component
                        with st.container():
                            # Create a clickable header simulation
                            c1, c2 = st.columns([1, 4])
                            with c1:
                                if st.button(f"#{idx+1}", key=f"btn_{idx}"):
                                    st.session_state['active_block_idx'] = idx
                                    st.rerun()
                            with c2:
                                # Category Badge
                                color_hex = '#{:02x}{:02x}{:02x}'.format(*reversed(colors.get(b['category'], (200,200,200))))
                                st.markdown(f"<span style='color:{color_hex}; font-weight:bold;'>{b['category']}</span>", unsafe_allow_html=True)
                            
                            # Content Editor
                            new_text = st.text_area(
                                label="Content",
                                value=b['text'],
                                key=f"txt_{idx}",
                                height=80,
                                label_visibility="collapsed"
                            )
                            if new_text != b['text']: b['text'] = new_text
                            
                            # Validation Metrics
                            conf_color = "green" if b['conf'] > 0.8 else "orange" if b['conf'] > 0.6 else "red"
                            st.markdown(f"<small style='color:#888'>Confidence: <span style='color:{conf_color}'>{b['conf']:.2f}</span></small>", unsafe_allow_html=True)
                            st.divider()

                # Export Action
                if st.button("💾 Export JSON for Analytics"):
                    import json
                    # Clean data for export
                    export_data = [{k: v for k, v in b.items() if k != 'raw_items'} for b in st.session_state['blocks']]
                    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                    st.download_button("Download JSON", json_str, "ad_semantics.json", "application/json")

if __name__ == "__main__":
    main()