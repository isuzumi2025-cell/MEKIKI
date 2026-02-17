print("<<< HELLO_FROM_SCHEMA_ENGINE_TOPLEVEL >>>")
# src/schema_engine.py
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import yaml
import json
import re


def load_schema(path: Path) -> Dict[str, Any]:
    """YAML スキーマを読み込む"""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _contains_any(text: str, keywords: List[str]) -> bool:
    text = str(text) if text is not None else ""
    return any(k in text for k in keywords)


def _sort_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """page, y0, x0 で並び替え"""
    cols = df.columns
    for c in ["page", "y0", "x0", "text"]:
        if c not in cols:
            raise ValueError(f"必須カラム {c} が CSV にありません")
    return df.sort_values(["page", "y0", "x0"]).reset_index(drop=True)


def find_section_slice(df_sorted: pd.DataFrame, section_cfg: Dict[str, Any]):
    """セクションの開始/終了インデックスを見つける"""
    start_keys = section_cfg.get("start_keywords", [])
    end_keys = section_cfg.get("end_keywords", [])

    start_idx = None
    end_idx = None

    for idx, row in df_sorted.iterrows():
        t = str(row["text"])
        if start_idx is None and _contains_any(t, start_keys):
            start_idx = idx
            continue
        if start_idx is not None and end_keys and _contains_any(t, end_keys):
            end_idx = idx
            break

    if start_idx is None:
        return None, None
    if end_idx is None:
        end_idx = len(df_sorted)
    return start_idx, end_idx


def group_lines_by_y(df_section: pd.DataFrame, y_tol: float = None) -> List[pd.DataFrame]:
    """
    y座標の近さで行にグルーピング。
    y_tol が指定されていなければ、データから動的に推定する。
    """
    df_sorted = df_section.sort_values(["page", "y0", "x0"])
    ys = df_sorted["y0"].astype(float).tolist()

    # y_tol 未指定の場合、行間の差分から代表値を推定
    if y_tol is None and len(ys) > 3:
        diffs = sorted(
            abs(ys[i+1] - ys[i]) for i in range(len(ys)-1) if ys[i+1] != ys[i]
        )
        if diffs:
            # 小さい方の中央値あたりを採用（文字列の行間に近い）
            mid_idx = max(0, len(diffs)//4)
            base = diffs[mid_idx]
            y_tol = base * 0.6  # ちょっと余裕を見て 0.6 倍
        else:
            y_tol = 5.0
    elif y_tol is None:
        y_tol = 5.0

    lines: List[pd.DataFrame] = []
    current: List[pd.Series] = []
    current_y = None
    current_page = None

    for _, row in df_sorted.iterrows():
        y = float(row["y0"])
        page = row["page"]

        # ページが変わったら強制改行
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



def build_paragraph(lines: List[pd.DataFrame]) -> str:
    out_lines = []
    for line_df in lines:
        texts = line_df.sort_values("x0")["text"].tolist()
        line_text = "".join(str(t) for t in texts).strip()
        if line_text:
            out_lines.append(line_text)
    return "\n".join(out_lines)


def build_bullet_list(lines: List[pd.DataFrame]) -> List[str]:
    items = []
    for line_df in lines:
        texts = line_df.sort_values("x0")["text"].tolist()
        line_text = "".join(str(t) for t in texts).strip()
        if line_text:
            items.append(line_text)
    return items


def build_key_value(lines: List[pd.DataFrame], fields_cfg: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    ラベル:値 っぽい行から dict を作る。
    ラベルに match_keywords のどれかが含まれていれば、そのブロックより右側のテキストを値とする。
    同じフィールドが複数行に出る場合は結合する。
    """
    result: Dict[str, str] = {f["id"]: "" for f in fields_cfg}

    for line_df in lines:
        line_df_sorted = line_df.sort_values("x0")
        texts = [str(t) for t in line_df_sorted["text"].tolist()]
        full_line = "".join(texts)

        for f in fields_cfg:
            fid = f["id"]
            keywords = f.get("match_keywords", [])
            if not _contains_any(full_line, keywords):
                continue

            value_parts: List[str] = []
            matched = False

            for _, row in line_df_sorted.iterrows():
                t = str(row["text"])
                if not matched and _contains_any(t, keywords):
                    matched = True
                    continue
                if matched:
                    value_parts.append(t.strip())

            value = " ".join(v for v in value_parts if v)
            if value:
                if result.get(fid):
                    result[fid] = (result[fid] + " " + value).strip()
                else:
                    result[fid] = value

    return {k: v for k, v in result.items() if v}



def build_key_value_or_bullet(
    lines: List[pd.DataFrame],
    fields_cfg: List[Dict[str, Any]]
) -> Dict[str, Any]:
    kv = build_key_value(lines, fields_cfg)
    bullets = build_bullet_list(lines)
    return {
        "fields": kv,
        "raw_lines": bullets,
    }


def _cluster_x_positions(df_section: pd.DataFrame, min_gap: float = 40.0) -> List[float]:
    """
    x0 の位置からざっくり縦カラムをクラスタリングする簡易版。
    min_gap より離れていたら別カラムとみなす。
    """
    xs = sorted(df_section["x0"].astype(float).unique())
    if not xs:
        return []

    centers = [xs[0]]
    for x in xs[1:]:
        if abs(x - centers[-1]) >= min_gap:
            centers.append(x)
    return centers


def _assign_column_index(x: float, centers: List[float]) -> int:
    """x座標がどのカラム中心に一番近いかを返す"""
    if not centers:
        return 0
    return min(range(len(centers)), key=lambda i: abs(x - centers[i]))

def build_table_like(
    lines: List[pd.DataFrame],
    column_keywords: List[List[str]] = None
) -> List[Dict[str, str]]:
    """
    ざっくりと表を構造化する。
    - x0 のクラスタリングで縦カラムを推定
    - 先頭付近の1〜2行をヘッダー候補とし、column_keywords から列名を推定
    - 各行について {列名: テキスト} の dict を返す
    """
    if not lines:
        return []

    # lines 全体をまとめてカラム位置推定
    all_rows = pd.concat(lines, ignore_index=True)
    centers = _cluster_x_positions(all_rows, min_gap=40.0)

    # ヘッダー候補：最初の1〜2行
    header_lines = lines[:2] if len(lines) >= 2 else lines
    header_texts_by_col: Dict[int, str] = {}

    for line_df in header_lines:
        for _, row in line_df.sort_values("x0").iterrows():
            col_idx = _assign_column_index(float(row["x0"]), centers)
            t = str(row["text"]).strip()
            if not t:
                continue
            header_texts_by_col.setdefault(col_idx, "")
            if header_texts_by_col[col_idx]:
                header_texts_by_col[col_idx] += " " + t
            else:
                header_texts_by_col[col_idx] = t

    # 列名推定
    col_names_by_idx: Dict[int, str] = {}
    if column_keywords:
        for idx, header_text in header_texts_by_col.items():
            for col_def in column_keywords:  # 例: ["期間", "配信期間", "期間"]
                for kw in col_def:
                    if kw in header_text:
                        col_names_by_idx[idx] = col_def[0]  # 代表名を採用
                        break
                if idx in col_names_by_idx:
                    break

    # 何もマッチしなかった列は col_0, col_1 ... としておく
    for i in range(len(centers)):
        if i not in col_names_by_idx:
            col_names_by_idx[i] = f"col_{i}"

    # 実データ行（ヘッダーとみなした最初の行はスキップ）を構造化
    data_lines = lines[1:] if len(lines) > 1 else []
    structured_rows: List[Dict[str, str]] = []

    for line_df in data_lines:
        row_dict: Dict[str, str] = {name: "" for name in col_names_by_idx.values()}
        for _, row in line_df.sort_values("x0").iterrows():
            col_idx = _assign_column_index(float(row["x0"]), centers)
            col_name = col_names_by_idx[col_idx]
            t = str(row["text"]).strip()
            if not t:
                continue
            if row_dict[col_name]:
                row_dict[col_name] += " " + t
            else:
                row_dict[col_name] = t
        # 全カラム空の行はスキップ
        if any(v for v in row_dict.values()):
            structured_rows.append(row_dict)

    return structured_rows


def apply_schema(blocks_df: pd.DataFrame, schema: Dict[str, Any]) -> Dict[str, Any]:
    df_sorted = _sort_blocks(blocks_df)

    output: Dict[str, Any] = {
        "doc_type": schema.get("doc_type"),
        "display_name": schema.get("display_name"),
        "sections": {},
    }

    for sec in schema.get("sections", []):
        sec_id = sec["id"]
        layout = sec.get("layout_hint", "paragraph")
        fields_cfg = sec.get("fields", [])

        start_idx, end_idx = find_section_slice(df_sorted, sec)
        if start_idx is None:
            continue

        df_sec = df_sorted.iloc[start_idx:end_idx].copy()
        mask_header = df_sec["text"].astype(str).apply(
            lambda t: _contains_any(t, sec.get("start_keywords", []))
        )
        df_body = df_sec.loc[~mask_header]
        if df_body.empty:
            continue

        lines = group_lines_by_y(df_body)

        if layout == "paragraph":
            output["sections"][sec_id] = build_paragraph(lines)
        elif layout == "bullet_list":
            output["sections"][sec_id] = build_bullet_list(lines)
        elif layout == "key_value":
            output["sections"][sec_id] = build_key_value(lines, fields_cfg)
        elif layout == "key_value_or_bullet":
            output["sections"][sec_id] = build_key_value_or_bullet(lines, fields_cfg)
        elif layout == "table_like":
            col_kw = sec.get("column_keywords", [])
            output["sections"][sec_id] = build_table_like(lines, col_kw)

        else:
            output["sections"][sec_id] = build_paragraph(lines)

    return output


def main():
    base_dir = Path(__file__).resolve().parent.parent
    csv_path = base_dir / "data" / "sample_blocks.csv"
    schema_path = base_dir / "schemas" / "ad_spec_standard.yaml"
    out_json = base_dir / "data" / "sample_structured.json"

    print("[DEBUG] base_dir :", base_dir)
    print("[DEBUG] csv_path :", csv_path)
    print("[DEBUG] schema  :", schema_path)

    if not csv_path.exists():
        print(f"[ERROR] CSV が見つかりません: {csv_path}")
        print("→ 先に `python src\\pdf_ingest.py` を実行して sample_blocks.csv を生成してください。")
        return

    if not schema_path.exists():
        print(f"[ERROR] スキーマが見つかりません: {schema_path}")
        print("→ `schemas/ad_spec_standard.yaml` が正しく作成されているか確認してください。")
        return

    df = pd.read_csv(csv_path)
    schema = load_schema(schema_path)
    structured = apply_schema(df, schema)

    print("\n===== STRUCTURED JSON (preview) =====")
    print(json.dumps(structured, ensure_ascii=False, indent=2))

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(structured, f, ensure_ascii=False, indent=2)

    print(f"\n[INFO] 構造化JSONを書き出しました: {out_json}")


if __name__ == "__main__":
    main()
