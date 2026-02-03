# 統合テキスト抽出・比較システム タスク

## Phase 1: コアモジュール統合 ✅
- [x] `text_extractor.py` 新規作成
  - [x] DomXPathHandler 統合 (DOM/XPath テキスト抽出)
  - [x] OCREngine 統合 (Google Vision API)
  - [x] PDF テキスト抽出 (PyMuPDF)
  - [x] パラグラフ自動検出・bbox付与

## Phase 2: API エンドポイント ✅
- [x] `/extract/web` - Web URL テキスト抽出
- [x] `/extract/pdf` - PDF OCR テキスト抽出
- [x] `/extract/region` - 指定領域テキスト抽出
- [x] `/compare` - 2テキスト比較・差分計算

## Phase 3: マルチウィンドウUI ✅
- [x] 2x3 マトリクスレイアウト実装 (`comparison_viewer.py`)
- [x] Web キャプチャパネル
- [x] PDF プレビューパネル
- [x] リアルタイムテキストパネル ×2
- [x] 比較結果パネル (Sync Rate + 差分)
- [x] サジェストパネル (ON/OFF トグル)

## Phase 4: 領域選択機能 ✅
- [x] JavaScript Canvas 領域選択
- [x] リサイズハンドル (4隅)
- [x] 領域編集・削除
- [x] リアルタイムテキスト反映 (OCR API連携)
- [x] 領域親和性マッピング (リンク機能)
- [x] コンテキストメニュー
- [x] キーボードショートカット (Delete/Esc/Ctrl+Z)

## Phase 5: テキスト比較エンジン ✅
- [x] `text_comparator.py` 新規作成
- [x] 文字差分計算 (diff-match-patch)
- [x] Sync Rate 計算
- [x] 差分ハイライトHTML生成
- [x] サジェスト生成 (LLM連携)

## 拡張機能 (Future)
- [ ] クリエイティブ評価
- [ ] ストーリーボード作成
- [ ] マルチドキュメント比較
