import difflib
import re

class Comparator:
    """
    Compares two text sources, calculates Sync Rate, and generates alignment data.
    """

    @staticmethod
    def compare(source_text: str, target_text: str):
        """
        Input:
            source_text (Web): The 'correct' reference.
            target_text (OCR): The text to check.
        
        Output:
            dict: {
                "sync_rate": float,
                "diff_html": str,
                "aligned_blocks": list
            }
        """
        # 1. Normalization
        s_norm = Comparator._normalize(source_text)
        t_norm = Comparator._normalize(target_text)

        # 2. Sync Rate Calculation
        matcher = difflib.SequenceMatcher(None, s_norm, t_norm)
        sync_rate = matcher.ratio() * 100  # 0.0 to 100.0

        # 3. Diff Generation (HTML)
        # Using difflib.HtmlDiff for a quick, nice visualization, 
        # but for "Genius UX", we might want custom structured data.
        # Let's generate a custom diff structure for the GUI to render.
        
        diff_ops = matcher.get_opcodes()
        diff_segments = []
        
        for tag, i1, i2, j1, j2 in diff_ops:
            segment = {
                "tag": tag, # 'replace', 'delete', 'insert', 'equal'
                "source": s_norm[i1:i2],
                "target": t_norm[j1:j2]
            }
            diff_segments.append(segment)

        return {
            "sync_rate": round(sync_rate, 2),
            "segments": diff_segments,
            "raw_ratio": sync_rate
        }

    @staticmethod
    def _normalize(text):
        # Remove extra whitespace, newlines, and non-printable chars
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def align_paragraphs(source_blocks, target_blocks):
        """
        Attempts to align a list of text blocks (Web Paragraphs) with OCR Clusters.
        Uses a similarity matrix to find the best path.
        """
        aligned = []
        # Simple greedy alignment for now (O(N*M)) - can be optimized
        used_targets = set()

        for s_idx, s_block in enumerate(source_blocks):
            best_match = None
            best_score = 0.0
            best_t_idx = -1

            for t_idx, t_block in enumerate(target_blocks):
                if t_idx in used_targets: continue
                
                score = difflib.SequenceMatcher(None, s_block, t_block).ratio()
                if score > best_score:
                    best_score = score
                    best_match = t_block
                    best_t_idx = t_idx
            
            if best_score > 0.4: # Threshold
                used_targets.add(best_t_idx)
                aligned.append({
                    "source": s_block,
                    "target": best_match,
                    "score": best_score
                })
            else:
                 aligned.append({
                    "source": s_block,
                    "target": None,
                    "score": 0.0
                })
        
        return aligned
