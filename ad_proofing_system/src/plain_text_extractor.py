# src/plain_text_extractor.py
"""
普通の広告PDFから、レイアウトをざっくり保ったテキストを抽出する簡易エンジン。
- スキーマ適用はしない
- ページ / Y座標 / X座標で読み順を並べて、行ごとのテキストにする
"""

from pathlib import Path
from typing import List

import pandas as pd

# 同じ src フォルダ内の pdf_ingest から、ブロック抽出関数だけ再利用
from pdf_ingest import extract_to_blocks


def group_lines_by_y(df: pd.DataFrame, y_tol: float = None) -> List[pd.DataFrame]:
    """
    y座標の近さで行グルーピングする簡易版。
    schema_engine.py のロジックをシンプルにしたもの。
    """
    if df.empty:
        return []

    df_sorted = df.sort_values(["page", "y0", "x0"])
    ys = df_sorted["y0"].astype(float).tolist()

    # 行間の差から、だいたいの y_tol を推定
    if y_tol is None and len(ys) > 3:
        diffs = sorted(abs(ys[i + 1] - ys[i]) for i in range(len(ys) - 1) if ys[i + 1] != ys[i])
        if diffs:
            mid_idx = max(0, len(diffs) // 4)
            base = diffs[mid_idx]
            y_tol = base * 0.6
        else:
            y_tol = 5.0
    elif y_tol is None:
        y_tol = 5.0

    lines: List[pd.DataFrame] = []
    current = []
    current_y = None
    current_page = None

    for _, row in df_sorted.iterrows():
        y = float(row["y0"])
        page = row["page"]

        if current_page is not None and page != current_page:
            if current:
                lines.append(pd.DataFrame(current))
            current = []
            current_y = None

        if current_y is None or abs(y - current_y) <= y_tol:
            current.append(row)
            if current_y is None:
                current_y = y
        else:
            if current:
                lines.append(pd.DataFrame(current))
            current = [row]
            current_y = y

        current_page = page

    if current:
        lines.append(pd.DataFrame(current))

    return lines


def blocks_to_plain_text(df: pd.DataFrame) -> str:
    """
    page → y0 → x0 の順に並べて、読み順テキストを組み立てる。
    """
    if df.empty:
        return ""

    out_lines: List[str] = []

    for page_num, df_page in df.groupby("page"):
        out_lines.append(f"===== PAGE {page_num} =====")

        # ページごとに行グループ化
        lines = group_lines_by_y(df_page)

        for line_df in lines:
            texts = line_df.sort_values("x0")["text"].astype(str).tolist()
            line_text = "".join(t.strip() for t in texts).strip()
            if line_text:
                out_lines.append(line_text)

        out_lines.append("")  # ページ末に空行

    return "\n".join(out_lines)


def main():
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    pdf_path = data_dir / "sample.pdf"
    csv_path = data_dir / "sample_blocks.csv"
    txt_path = data_dir / "sample_plain.txt"

    print("<<< HELLO_FROM_PLAIN_TEXT_EXTRACTOR >>>")
    print(f"[DEBUG] base_dir : {base_dir}")
    print(f"[DEBUG] pdf_path : {pdf_path}")
    print(f"[DEBUG] csv_path : {csv_path}")
    print(f"[DEBUG] txt_path : {txt_path}")

    if not pdf_path.exists():
        print(f"[ERROR] PDF が見つかりません: {pdf_path}")
        print("→ data フォルダに sample.pdf を置いてください。")
        return

    # 既に sample_blocks.csv があればそれを使い、無ければ pdf_ingest で生成
    if csv_path.exists():
        print("[INFO] 既存の sample_blocks.csv を読み込みます。")
        df_blocks = pd.read_csv(csv_path)
    else:
        print("[INFO] sample_blocks.csv が無いので、PDF からブロック抽出します。")
        df_blocks = extract_to_blocks(pdf_path)
        if df_blocks.empty:
            print("[ERROR] ブロック抽出に失敗しました。")
            return
        df_blocks.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[INFO] CSV に書き出しました: {csv_path}")

    # プレーンテキスト生成
    plain_text = blocks_to_plain_text(df_blocks)

    if not plain_text.strip():
        print("[WARN] テキストがほとんど抽出できませんでした。")
        return

    # txt に保存
    txt_path.write_text(plain_text, encoding="utf-8")
    print(f"[INFO] 抽出テキストを書き出しました: {txt_path}")

    # 先頭だけコンソールにプレビュー
    print("\n===== TEXT PREVIEW (first 40 lines) =====")
    preview_lines = plain_text.splitlines()[:40]
    for line in preview_lines:
        print(line)


if __name__ == "__main__":
    main()
