# 統合・改訂版 仕様書（最高水準）

## 1. プロダクト定義

### 1.1 目的

広告・チラシ・PDF・Webページから日本語文言を高精度に抽出し、**段落単位で構造化**した上で、**A/B差分と同期率（シンクロ率）を定量化**し、業務で再利用できる形（Spreadsheet/CSV/RAG）に落とす。

### 1.2 最重要価値（優先順位）

1. **日本語テキスト抽出の正確性（OCR + 構造化）**
2. **段落単位の再現性（比較・同期率の前提）**
3. **差分と同期率が説明可能であること（監査可能性）**
4. 出力・ライブラリ化（資産化）
5. 拡張（評価コメント / 絵コンテ / アナリティクス / Webスクレイピング）

---

## 2. スコープ（フェーズ）

* **Phase 1（コア）：** 画像/PDF/Webスクショから OCR → 非テキスト排除 → 段落構造化 → 日本語チェック → 正規化JSON保存
* **Phase 2（比較）：** A/B差分、段落対応付け、同期率算出、CSV/Excel/Sheets出力
* **Phase 3（Web）：** Web取得（静的/動的）＋ **パスワード入力型/フォームログイン/Basic認証** 対応 → 同パイプラインへ投入
* **Phase 4（拡張）：** Groq評価コメント（ON/OFF）、絵コンテ生成、アナリティクス連携（APIキー）

> ユーザー要望「すべて採用」は、**Phase 1〜4 で全採用**し、Phase 1/2 を揺るがせない構造にします。

---

## 3. 非機能要件（ここが"最高の仕様"の肝）

### 3.1 再現性・監査性

* すべての中間成果物を保存（入力・前処理・OCR生・構造化・比較）
* 同一入力・同一設定で結果が安定（乱数禁止・ソート規則固定）
* "なぜそう判断したか"は **ログとメタ情報**で追える（LLMの思考過程の開示は不要）

### 3.2 セキュリティ

* APIキー/ログイン情報は **Secrets** で管理（`.env` + OS Keychain/Secrets Manager想定）
* 取得したWebコンテンツや広告素材の取り扱いに備え、**PII/機密のマスキングを将来差し込み可能な設計**
* ログに本文を出しすぎない（debugフラグで切替）

### 3.3 運用性

* CLI中心（CIで自動検証できる）
* 失敗時に復旧可能（リトライ・部分再実行・キャッシュ）

---

## 4. 入力仕様

### 4.1 ファイル

* PNG/JPG, PDF（複数ページ可）

### 4.2 Web（Phase 3）

* **公開ページ**
* **Basic認証**
* **フォームログイン（ID/Password + Cookie + CSRF）**
* **"開発中のパスワード入力型"**（単一パスワード入力で閲覧可、あるいは簡易認証ゲート）

---

## 5. 出力仕様（データモデルを明確化）

### 5.1 正規化結果（Normalized Document JSON）

`normalized.json`（ページ単位 or ドキュメント単位）

```json
{
  "doc_id": "string",
  "source_type": "file|pdf|web",
  "pages": [
    {
      "page_index": 0,
      "paragraphs": [
        {
          "paragraph_id": "string",
          "role": "headline|body|caption|price|legal|other",
          "text_raw": "string",
          "text_normalized": "string",
          "tokens_ja": ["string"],
          "bbox_union": {
            "x": 0,
            "y": 0,
            "width": 0,
            "height": 0
          },
          "items": [],
          "confidence_stats": {
            "min": 0.0,
            "mean": 0.0,
            "p95": 0.0
          },
          "style_hints": {
            "font_size_bucket": "string",
            "weight_bucket": "string"
          },
          "grammar_issues": [
            {
              "type": "string",
              "span": [0, 0],
              "message": "string"
            }
          ],
          "suggestions": [
            {
              "before": "string",
              "after": "string",
              "reason": "string"
            }
          ]
        }
      ]
    }
  ]
}
```

> ポイント：**比較に必要な"構造"を先に決める**。ここが曖昧だとPhase 2が破綻します。

### 5.2 OCR生（Vision JSON）

`ocr_vision.json`（レスポンスを極力そのまま保存）

### 5.3 ライブラリ保存（資産化）

```
/library/{client}/{campaign}/{yyyy-mm}/
  source/
  fetched/         (webならHTML/スクショ)
  preprocessed/
  ocr/
  normalized/
  diff/
  exports/
  rag_chunks/
  debug/           (可視化画像・オーバーレイ)
  logs/
```

---

## 6. コア処理仕様（精度の要）

### 6.1 非テキスト除外（広告特化）

* 前処理オプション：線/枠マスク（ON/OFF）
* OCR後フィルタ：

  * confidence閾値
  * 異常に細長い/小さいbbox除外（装飾ノイズ対策）
  * 記号だけの孤立ブロックの扱い（価格・注釈は除外しない）

### 6.2 "CoT"の再定義（実装可能な形に落とす）

ユーザーが求めるCoTは「段階推論で精度を上げる」こと。実装では **Staged Reasoning Pipeline** として定義します（=ステップごとの判定＋自己整合チェック）。

* Step A：OCR要素の正規化（行/単語の並び順固定、空白推定）
* Step B：段落クラスタリング（近接×整列×サイズ）
* Step C：段落ロール推定（見出し/本文/注釈/価格/規約）
* Step D：日本語整合（表記・文法・不自然分断検出）
* Step E：自己整合チェック（段落境界が妥当か、再クラスタ候補）

> これにより「推論は段階化されているが、思考過程を露出しない」実装ができます。

### 6.3 日本語チェック（Phase 1で"使える"レベルに）

* ルールベース（必須）：括弧不整合、句読点連続、全半角混在、単位表記揺れ、不要空白、英数字周りのスペース
* 形態素（推奨）：SudachiPy等で token化し、怪しい分割や助詞連結を検知する下地を作る
* LLM（Phase 4強化）：改善提案をより自然にする（Groq/OpenAI/Claudeなど差替可能に）

---

## 7. Webスクレイピング（Phase 3）の仕様を"最初から"硬くする

### 7.1 取得方式（優先順）

1. **HTML抽出（可能なら最優先）**：広告ページでもテキストがDOMにある場合はOCRより正確
2. **レンダリング→スクショ→OCR**：デザイン重視・画像化された広告はこれが本命
3. **PDFリンクを検出して直接PDF処理**：多いので必須

### 7.2 認証対応（要件化）

* Basic認証：`Authorization` ヘッダ
* フォームログイン：CSRFトークン抽出→POST→Cookie保持
* "パスワード入力型"：

  * パターン1：単一フォームでパスワード送信→Cookie/Session発行
  * パターン2：URLパラメータ/簡易ゲート（あるなら）
* 重要：**ログイン手順を設定ファイル化**（案件ごとに差があるため）

### 7.3 設定スキーマ（例）

`connectors.yaml` に以下を定義できるようにする：

* target_url
* auth_type: none/basic/form/password_gate
* selectors（ユーザー名欄/パス欄/submit）
* csrf_selector（任意）
* post_login_url（任意）
* crawl_scope（同一ドメイン限定など）
* wait_for（SPA対応：networkidle等）

---

## 8. 比較・同期率（Phase 2）も最初から仕様に含める（ブレ防止）

* 段落対応：`paragraph_id`の一致ではなく **内容類似 + 位置類似**でマッチング
* 同期率：少なくとも3種を出す

  1. 文字正規化ベース
  2. 形態素ベース（日本語向け）
  3. 段落構造一致率（段落の対応率）

---

## 9. 品質ゲート（受入基準を"定量"に）

### Phase 1 合格条件（例）

* normalized.json が生成される（必須）
* 主要段落が過分断しない（段落数が極端に多い場合は警告）
* 1ページ当たりの平均confidence、除外率、段落数がログに残る
* debugオーバーレイ画像（段落bbox表示）が生成できる（オンで）

---

## 10. 技術スタック（推奨）

### Phase 1 必須

* Python 3.10+
* OCR: Google Cloud Vision API / Azure Computer Vision / Tesseract（フォールバック）
* 画像処理: OpenCV, PIL/Pillow
* PDF処理: PyPDF2 / pdf2image
* 形態素解析: SudachiPy（推奨）
* CLI: Click / argparse
* 設定: PyYAML

### Phase 3 追加

* Web取得: requests, playwright
* HTML解析: BeautifulSoup4, lxml

### Phase 4 追加

* LLM: OpenAI API / Groq API / Anthropic Claude API

---

## 11. データフロー

```
入力（画像/PDF/Web）
  ↓
前処理（線マスク、ノイズ除去）
  ↓
OCR（Vision API）
  ↓
OCR生JSON保存
  ↓
段落クラスタリング
  ↓
ロール推定
  ↓
日本語チェック
  ↓
正規化JSON保存
  ↓
（Phase 2: 比較・差分）
  ↓
（Phase 4: 評価・拡張）
```

---

## 12. バージョン管理

* 仕様書の変更はこのファイル（`docs/requirements.md`）を更新
* 各Phaseの詳細は `docs/phases/phase-*.md` に記載
* 実装の変更はGitで管理し、コミットメッセージにPhase番号を含める
