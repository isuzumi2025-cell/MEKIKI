# Phase 1: コア機能（OCR → 段落構造化 → 日本語チェック）

## 目的

画像/PDF（将来はWebスクショ）から高精度に日本語文言を抽出し、広告レイアウトを考慮して段落単位に構造化する。線/枠/装飾等の非テキスト要素の影響を低減し、日本語文法/表記の問題を検出する。

## 実行手順

### CLI

```bash
python -m app ingest \
  --input <file_or_dir> \
  --client <name> \
  --campaign <name> \
  [--month YYYY-MM] \
  [--preprocess-lines on/off] \
  [--debug on/off]
```

### 処理フロー

1. **入力検証**: ファイル形式チェック（PNG/JPG/PDF）
2. **前処理**: 線マスク（オプション）、ノイズ除去
3. **OCR実行**: Google Cloud Vision API / Azure / Tesseract
4. **OCR生JSON保存**: `/library/{client}/{campaign}/{month}/ocr/ocr_vision.json`
5. **段落クラスタリング**: 近接×整列×サイズでグループ化
6. **ロール推定**: headline/body/caption/price/legal/other
7. **日本語チェック**: ルールベース検証
8. **正規化JSON保存**: `/library/.../normalized/normalized.json`
9. **デバッグ出力**: オーバーレイ画像（debug=on時）

## 設計

### Staged Reasoning Pipeline

#### Step A: OCR要素の正規化

* 座標ソート規則を固定（上→下、左→右）
* 空白推定（行間、単語間）
* テキスト結合ルール

#### Step B: 段落クラスタリング

* 距離閾値: `pipeline.yaml` で設定可能
* 整列判定: 水平/垂直方向の整列度
* サイズ類似度: フォントサイズの近さ

#### Step C: 段落ロール推定

* ヒューリスティックベース（Phase 1）
  * フォントサイズが大きい → headline
  * 位置が上部 → headline
  * 数字+記号が多い → price
  * フォントサイズが小さい → caption/legal
  * デフォルト → body

#### Step D: 日本語整合

* ルールベースチェック:
  * 括弧不整合: `（` と `）` の対応
  * 句読点連続: `。。`、`，，` など
  * 全半角混在: 数字・英字の全半角統一
  * 単位表記揺れ: `円` vs `¥` など
  * 不要空白: 日本語中の不自然な空白
  * 英数字周りのスペース: `100 円` vs `100円`

#### Step E: 自己整合チェック

* 段落境界の妥当性検証
* 過分断の検出（警告）
* 再クラスタリング候補の特定

### データモデル

`normalized.json` のスキーマは `docs/requirements.md` 5.1節を参照。

## 制約

* Phase 2（比較/同期率/CSV等）は実装しない
* Phase 3（Web取得/ログイン）は実装しない
* LLM APIキー無しで必ず完走すること

## チューニングパラメータ

`configs/pipeline.yaml` で設定可能:

```yaml
ocr:
  confidence_threshold: 0.5
  provider: "google"  # google|azure|tesseract

preprocessing:
  line_mask_enabled: true

paragraph:
  clustering:
    distance_threshold: 50  # ピクセル
    alignment_threshold: 0.8
    size_similarity_threshold: 0.7

japanese:
  check_enabled: true
  morph analyzer: "sudachi"  # sudachi|none
```

## テスト

### 必須テスト

1. **E2Eテスト**: `tests/assets/` のサンプル画像/PDFで実行
2. **スキーマ検証**: 生成された `normalized.json` がスキーマ準拠
3. **再現性テスト**: 同一入力で同一出力が得られる

### テストデータ

`tests/assets/` に以下を配置:

* サンプル画像（JPG/PNG）: 1件以上
* サンプルPDF: 1件以上（可能なら）

## 受入基準

- [ ] `normalized.json` が生成される（必須）
- [ ] 主要段落が過分断しない（段落数が極端に多い場合は警告）
- [ ] 1ページ当たりの平均confidence、除外率、段落数がログに残る
- [ ] debug=on の場合、オーバーレイ画像が生成できる
- [ ] ルールベースの日本語チェックが動作する
- [ ] E2Eテストが1件以上成功する

## 品質指標

* **段落精度**: 目視検証で主要段落が適切に分割されている
* **日本語チェック**: 明らかな問題（括弧不整合など）が検出される
* **再現性**: 同一入力で同一出力（乱数シード固定）

## 次のPhase

Phase 1完了後、Phase 3（Web取得）または Phase 2（比較）へ進む。
