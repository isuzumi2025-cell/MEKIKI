"""
ヘルパー関数集
"""

from typing import List, Dict, Tuple
from pathlib import Path
import json


def save_clusters_to_json(clusters: List[Dict], output_path: str):
    """
    クラスタ情報をJSONファイルに保存
    
    Args:
        clusters: クラスタリスト
        output_path: 出力パス
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(clusters, f, indent=2, ensure_ascii=False)
    
    print(f"✅ クラスタ情報を保存: {output_path}")


def load_clusters_from_json(input_path: str) -> List[Dict]:
    """
    JSONファイルからクラスタ情報を読み込み
    
    Args:
        input_path: 入力パス
    
    Returns:
        クラスタリスト
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        clusters = json.load(f)
    
    print(f"✅ クラスタ情報を読み込み: {input_path}")
    return clusters


def create_output_directory(base_dir: str = "output") -> Path:
    """
    出力ディレクトリを作成
    
    Args:
        base_dir: ベースディレクトリ名
    
    Returns:
        作成されたディレクトリのPath
    """
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(base_dir) / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 出力ディレクトリを作成: {output_dir}")
    return output_dir


def sanitize_filename(filename: str) -> str:
    """
    ファイル名として使用できない文字を除去
    
    Args:
        filename: 元のファイル名
    
    Returns:
        サニタイズされたファイル名
    """
    import re
    
    # Windows/Linux/macOSで使用できない文字を除去
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 連続するアンダースコアを1つに
    sanitized = re.sub(r'_{2,}', '_', sanitized)
    
    # 先頭・末尾の空白やドットを除去
    sanitized = sanitized.strip('. ')
    
    return sanitized


def format_file_size(size_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式に変換
    
    Args:
        size_bytes: バイト数
    
    Returns:
        フォーマットされた文字列（例: "1.5 MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} PB"


def calculate_image_similarity_score(rect1: List[int], rect2: List[int]) -> float:
    """
    2つの矩形の位置的類似度を計算
    
    Args:
        rect1: [x0, y0, x1, y1]
        rect2: [x0, y0, x1, y1]
    
    Returns:
        類似度スコア (0.0 - 1.0)
    """
    # 面積の計算
    def area(rect):
        return (rect[2] - rect[0]) * (rect[3] - rect[1])
    
    # 重なり領域の計算
    x_overlap = max(0, min(rect1[2], rect2[2]) - max(rect1[0], rect2[0]))
    y_overlap = max(0, min(rect1[3], rect2[3]) - max(rect1[1], rect2[1]))
    overlap_area = x_overlap * y_overlap
    
    # 合計面積
    area1 = area(rect1)
    area2 = area(rect2)
    union_area = area1 + area2 - overlap_area
    
    if union_area == 0:
        return 0.0
    
    # IoU (Intersection over Union)
    return overlap_area / union_area


def extract_url_domain(url: str) -> str:
    """
    URLからドメイン部分を抽出
    
    Args:
        url: URL文字列
    
    Returns:
        ドメイン文字列
    """
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    return parsed.netloc

