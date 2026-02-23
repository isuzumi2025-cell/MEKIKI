# MEKIKI Proofing System - Claude Code Context

**Last Updated**: 2026-02-23
**Last Verified Against Code**: 2026-02-23 (Claude Code + Cursor Agent cross-check)
**Purpose**: AgentOps SDK導入による開発・運用の高速化と手戻り最小化

---

## 🚨 PRE-FLIGHT CHECK（作業開始前に必須実行）

> [!CAUTION]
> 以下を実行せずに作業を開始することは**禁止**

| # | チェック項目 | コマンド |
|---|-------------|----------|
| 1 | メソドロジー参照 | `view_file Vault/00_Runbook/autonomous_methodology.md` |
| 2 | バックアップ正本確認 | `view_file Vault/10_Projects/mekiki/backup_catalog.md` |
| 3 | 関連ログ検索 | `Vault/50_Logs/` 内を検索 |
| 4 | Slack通知 | Clawdbotで作業開始を共有 |
| 5 | 計画書作成 | ユーザー承認後に実装開始 |

**ワークフロー**: `/start-work` で自動実行可能

---

## 🚨 CRITICAL PITFALLS（必読）

### 1. ID整合性の破綻 🔴 CRITICAL

**問題**: `SyncPair.web_id` / `pdf_id` と `Region.area_code` の不一致により、サムネイル・リージョンが空欄表示される。

**ID体系の完全仕様**:

| データ構造 | フィールド | 形式 | 生成場所 |
|:---|:---|:---|:---|
| `SelectionResult` | `area_code` | `W-{3桁}` / `P-{3桁}` | `app/sdk/selection/simple_handler.py` L70 |
| `SyncPair` | `web_id`, `pdf_id` | `W-001`, `P-001` | `app/sdk/similarity/paragraph_matcher.py` L28-31 |
| `ParaRegion` (GUI) | `area_code` | 同上 | `app/gui/windows/advanced_comparison_view.py` |

**紐付けルール**:

- `spreadsheet_panel.py` は `SyncPair.web_id` と `web_regions[i].area_code` の**完全一致**を前提にサムネイル表示
- 不一致が1件でも発生 → その行のID/サムネイルが空欄

**検証方法**:

```bash
# audit_ids コマンドで検証（Phase 1で実装）
/audit-ids
```

**禁止事項**:

- ❌ ID生成ロジックの独自実装（既存の生成ルールを遵守）
- ❌ `area_code` のリネーム・フォーマット変更
- ❌ ID重複の放置

---

### 2. 座標系のズレ 🔴 CRITICAL

**問題**: Web/PDF間、UI選択範囲と内部座標の変換ミスにより、サムネイル切り出し位置がズレる・リージョン表示が消える。

**座標系の完全仕様**:

| ソース | 座標系 | 原点 | 単位 | 変換式 |
|:---|:---|:---|:---|:---|
| **Web** | ピクセル座標 | 左上(0,0) | px | `bbox = (x1, y1+y_offset, x2, y2+y_offset)` |
| **PDF** | PyMuPDF座標 | 左下(0,0) | pt (72 DPI) | `scaled_bbox = [int(b * DPI_SCALE + y_offset) for b in bbox]` |
| **UI選択** | Canvas座標 | 左上(0,0) | px（スケール済み） | `image_x = canvasx(event.x) / scale_x` |

**重要定数**:

```python
DPI_SCALE = 300.0 / 72.0  # ≈ 4.166（PDF座標 → 画像座標）
# 定義場所: unified_app.py L1420（ローカル定数として定義）
# ※ engine_cloud.py には DPI_SCALE は存在しない（2026-02-23検証済み）
```

**y_offset（縦連結対応）**:

- Web/PDFの複数ページを縦に連結する際、各ページの座標に累積オフセットを加算
- 計算: `y_offset = sum(previous_page_heights)`
- 適用箇所: `unified_app.py` L1183-1233（Web）, L1236-1284（PDF）

**検証方法**:

```bash
# audit_coords コマンドで検証（Phase 1で実装）
/audit-coords
```

**禁止事項**:

- ❌ DPI_SCALE の変更（300/72固定）
- ❌ y_offset の加算忘れ
- ❌ PDF原点の左上/左下混同

---

### 3. クラスタリング設定の誤用 🔴 CRITICAL

**問題**: 緩和パラメータ（`overlap 0.4`, `gap_y 80`）を使用すると、虚構のマッチ（Match:2）が発生し、精度が破綻する。

**正しい設定（CHECKPOINT: Match=70）— 2026-02-23 実コード検証済み**:

```python
# app/core/engine_cloud.py _vertical_stack_clustering() ハードコード値

# アライメント判定（X方向）
overlap_ratio > 0.5        # ✅ 実値（旧ドキュメントの 0.6 は誤り）
left_diff < 40             # ✅ 通常時（layout_similar 判定は < 20）
# ※ is_layout_similar = (left_diff < 20 and width_diff < 50)
# ※ is_aligned = overlap_ratio > 0.5 OR left_diff < 40 OR is_layout_similar

# Y方向動的閾値（GPT戦略: 2.0-4.0x）
y_multiplier = 4.0  # is_layout_similar の場合
y_multiplier = 3.5  # is_both_template の場合
y_multiplier = 3.0  # 通常の場合
threshold_y = max(base_size * y_multiplier * template_bonus, 60)
# ✅ 実値（旧ドキュメントの max(base_size*2.5, 50) は誤り）

# X方向ギャップ
gap_x_threshold = 30  # is_layout_similar の場合
gap_x_threshold = 20  # 通常の場合
# ✅ 実値（旧ドキュメントの > 15 は誤り）

# フォントサイズ許容
if current["avg_font_size"] > target["avg_font_size"] * 3.0: continue
if target["avg_font_size"] > current["avg_font_size"] * 2.5: continue
```

**禁止設定**:

- ❌ `overlap_ratio 0.4`（緩すぎ）
- ❌ `gap_y 80`（緩すぎ）
- ❌ `gap_x_threshold > 30`（緩すぎ）
- ❌ `y_multiplier < 3.0` または `threshold_y < 60`（精度破綻）

**復元方法**:

```powershell
# バックアップから復元
Copy-Item "backup_20260112_004423\engine_cloud.py" "OCR\app\core\engine_cloud.py" -Force
```

**検証方法**:

```bash
# audit_match_quality コマンドで検証（Phase 1で実装）
/audit-match-quality
```

---

### 4. 状態管理の不整合 🟡 MAJOR

**問題**: 2回目以降のOCR/AI分析実行時に、画像・テキスト・Sync Rateが消失する。

**原因**: リストへの `append` によりインデックスがズレる、状態初期化の重複。

**正しいパターン**:

```python
def process_data(view):
    # ★ 関数冒頭で結果データのみクリア（入力データは保持）
    view.sync_pairs = []
    view.web_regions = []
    view.pdf_regions = []
    # view.web_image / pdf_image は保持

    # 処理...

    # 最後に新しいデータで更新
    view.sync_pairs = new_sync_pairs
```

**参考**: `backup_Case1_StateManagementFix_20260113/unified_app.py` L1095-1112

---

### 5. Configure イベント干渉 🟡 MAJOR

**問題**: AI分析実行後、Canvasの `<Configure>` イベントが遅延発火し、リージョン矩形が消失する。

**原因**: デバウンス処理（100ms）が `_display_image()` のみを呼び出し、`_redraw_regions()` を再実行しない。

**正しいパターン**:

```python
def _on_canvas_configure(self, event):
    if getattr(self, '_display_in_progress', False):
        return  # 描画中はスキップ

    def _redisplay():
        self._display_image(self.canvas, self.image)
        if self.regions:
            self._redraw_regions()  # ★ リージョンも再描画

    self._resize_job = self.after(100, _redisplay)
```

**参考**: `backup_Case2_ImageDisplayDebug_20260113/advanced_comparison_view.py` L673-697

---

### 6. マッチ結果スキーマの未定義 🟡 MAJOR ✅ Phase 1 Unit 2で解決

**問題**: MatchResult/SyncPairの形式が暗黙的で、bbox/page範囲外・スコア範囲外データが検証されずに下流に流れる。

**発見した脆弱性**:

- BBox座標が反転（x1 > x2, y1 > y2）しても検出されない
- Page indexが負数・範囲外でもパスする
- Scoreが [0.0, 1.0] 範囲外（例: 2.0, -0.5）でもエラーにならない
- ID format（W-XXX, P-XXX）の検証がない

**Phase 1 Unit 2での解決策**:

```python
# OCR/app/sdk/similarity/match_schema.py
@dataclass
class MatchResult:
    match_id: str
    web: Optional[MatchEntity]  # BBox, page, text
    pdf: Optional[MatchEntity]
    score: MatchScore           # overall, text, layout, style
    status: MatchStatus         # EXACT | PARTIAL | LOW_CONF | NO_MATCH
    debug: MatchDebug

# OCR/app/sdk/similarity/schema_validator.py
validator = MatchSchemaValidator()
result = validator.validate(match, image_size=(W, H), page_count=N)
```

**検証項目**:

- ✅ BBox: `x1 < x2`, `y1 < y2`, `bbox ⊆ image_size`
- ✅ Page: `0 <= page < page_count`
- ✅ Score: `0.0 <= score <= 1.0`
- ✅ ID: `^(W|P|SEL)[-_]\d{3}$`

**Backward Compatibility**:

```python
# Legacy SyncPair ↔ MatchResult 双方向変換
match = MatchResult.from_legacy_syncpair(sync_pair)
sync_pair = match.to_legacy_syncpair()
```

**テスト**: `pytest OCR/tests/test_match_schema.py -v`

**AC**: `AC-SCHEMA-1` 〜 `AC-SCHEMA-6` (sdk/contracts/acceptance_criteria.md)

---

### 7. スプレッドシートスキーマの暗黙的変更 🟡 MAJOR

**問題**: 列定義がコード内に散在し、変更時にバージョン管理されない。

**現在の列定義**（暗黙的）:

```
| # | Web ID | Web Thumb | Web Text | ⇔ | PDF Text | PDF Thumb | PDF ID | Sync Rate |
```

**実装箇所**:

- `app/gui/panels/spreadsheet_panel.py` L150-350（表示）
- `app/sdk/export/spreadsheet.py` L50-120（エクスポート）

**対策**: Phase 2で `sdk/contracts/spreadsheet_schema_v1.json` を作成し、バージョン管理。

---

## 📁 リポジトリ構造

### 既存SDK（変更禁止）

| パス | 責務 |
|:---|:---|
| `OCR/app/sdk/ocr/` | OCR処理（Vision API統合） |
| `OCR/app/sdk/similarity/` | パラグラフマッチング |
| `OCR/app/sdk/similarity/match_schema.py` | ✨ MatchResult schema v1.0.0（Phase 1 Unit 2追加） |
| `OCR/app/sdk/similarity/schema_validator.py` | ✨ Schema validation（Phase 1 Unit 2追加） |
| `OCR/app/sdk/selection/` | UI範囲選択ハンドラ |
| `OCR/app/sdk/canvas/` | キャンバス座標処理 |
| `OCR/app/sdk/export/` | Google Sheets エクスポート |
| `OCR/app/sdk/matching/` | マッチングロジック |
| `OCR/app/sdk/llm/` | LLM統合 |

### AgentOps SDK（新規導入）

| パス | 責務 |
|:---|:---|
| `sdk/orchestrator/` | タスク状態管理、並列エージェント調整 |
| `sdk/contracts/` | Plan契約、AC定義 |
| `sdk/telemetry/` | KPI測定 |

**責務分離**:

- 既存SDK: **ドメインロジック**（OCR、マッチング、エクスポート）
- AgentOps SDK: **開発プロセス改善**（タスク管理、検証、メトリクス）

---

## 🔄 データフロー

```
[Input]
  Web URL → Playwright → 画像キャプチャ（縦連結）→ Vision API → クラスタリング
  PDF File → PyMuPDF → 埋め込みテキスト優先 → OCRフォールバック

[Paragraphs]
  Web: W-001, W-002... (area_code)
  PDF: P-001, P-002... (area_code)

[Matching]
  paragraph_matcher.py:
    - 類似度行列計算（全組み合わせ）
    - 貪欲法で最適ペア選択
    - threshold=0.25でフィルタリング
  → SyncPair (web_id, pdf_id, similarity, bbox...)

[Display]
  advanced_comparison_view.py:
    - Canvas描画（web_canvas, pdf_canvas）
    - リージョン矩形表示

  spreadsheet_panel.py:
    - Live Comparison Sheet
    - サムネイル表示（SyncPair.web_id ↔ Region.area_code 紐付け）
    - Sync Rate計算

[Export]
  sdk/export/spreadsheet.py:
    - Google Sheets API
    - 固定スキーマ（暗黙的）
```

---

## 🎯 ベースラインメトリクス

| メトリクス | 現状値 | 目標値 |
|:---|:---|:---|
| **Match数** | 70（Match:70設定） | ≥70 |
| **Sync Rate** | 36.6% (48/131) | 維持 |
| **虚構マッチ** | 0件（厳格設定） | 0件 |
| **往復回数** | 測定未 | ≤3 |
| **差分量** | 測定未 | ≤100 LOC/ファイル |
| **テスト失敗率** | 測定未 | ≤10% |

---

## 🛠️ 開発環境

| 項目 | 値 |
|:---|:---|
| **Python** | 3.11+ |
| **主要依存** | Pillow, google-cloud-vision, gspread, pdf2image, PyMuPDF, Playwright |
| **GUI** | CustomTkinter (dark mode) |
| **テスト** | pytest（推奨、現在3テストのみ） |
| **起動** | `cd OCR && py -3 run_unified.py` |
| **認証** | `service_account.json`（Google Cloud） |

---

## 🚫 変更禁止ファイル（精度に直結）

| ファイル | 理由 |
|:---|:---|
| `app/core/engine_cloud.py` | OCRクラスタリング精度（Match:70設定） |
| `app/core/sync_matcher.py` | マッチングロジック |
| `app/core/paragraph_matcher.py` | パラグラフ比較 |

**変更時の手順**:

1. `backup_YYYYMMDD_HHMMSS/` にバックアップ
2. 変更後にOCRテスト実行
3. Match数低下 → バックアップから復元

---

## 📚 参考ドキュメント

| ファイル | 内容 |
|:---|:---|
| `OCR/RUNBOOK.md` | 既存の運用マニュアル（1278行） |
| `OCR/README.md` | ユーザーマニュアル |
| `OCR/app/core/schemas.py` | Pydantic統一スキーマ |
| `backup_ParagraphSorted_SUCCESS_20260113/` | AI分析モード成功時のバックアップ |
| `backup_Case1_StateManagementFix_20260113/` | 状態管理修正版 |

---

## 🔄 AgentOps SDK運用フロー

```
[Plan] → [Phase実行] → [検証] → [修正] → [Tag] → [Next Phase]
   ↑                      ↓
   └──────── 失敗時Rollback ──────┘
```

**Phase分割**:

- Phase 0: 非破壊（ドキュメント・規約・検証基盤）✅ 完了
- Phase 1 Unit 1: audit_ids実装 ✅ 完了
- Phase 1 Unit 2: match_paragraphsスキーマ固定 ✅ 完了
- Phase 2: render_diff/sync_spreadsheetスキーマ固定、座標系修正
- Phase 3: 状態管理改善、回帰テスト

---

## ⚡ クイックリファレンス

### ID整合性チェック

```bash
/audit-ids  # Phase 1で実装
```

### 座標監査

```bash
/audit-coords  # Phase 1で実装
```

### マッチ品質監査

```bash
/audit-match-quality  # Phase 1で実装
```

### バックアップから復元

```powershell
# Match:70設定を復元
Copy-Item "backup_20260112_004423\engine_cloud.py" "OCR\app\core\engine_cloud.py" -Force

# AI分析モード成功版を復元
Copy-Item "backup_ParagraphSorted_SUCCESS_20260113\unified_app.py" "OCR\app\gui\unified_app.py" -Force
```

---

## 🐛 Bug Registry Protocol

アクティブなバグは以下のファイルで管理する:

`OCR/Vault/50_Logs/active_bug_registry_YYYYMMDD.md`

**ルール**:

1. コード変更前に必ずアクティブバグ一覧を確認する
2. バグを修正したら「Active」→「Fixed」に移動し、日付とコミットを記録する
3. 新バグを発見したら severity（CRITICAL/MAJOR/MEDIUM/LOW）付きで登録する
4. **CLAUDE.md のパラメータ値は四半期ごとに実コードと照合する**
5. CLAUDE.md と実コードに乖離が発生した場合 = CRITICAL 優先度で即時修正（B9クラス）

**最終検証日**: 2026-02-23
**検証者**: Cursor Agent + Claude Code クロスチェック

---

## 📋 Document Accuracy

このドキュメントが最後に実コードと照合された日: **2026-02-23**

このドキュメントの値が実コードと一致しない場合:

1. **コードが正**: このドキュメントではなくコードを信頼する
2. このドキュメントを即座に修正する（B9クラスのバグ）
3. 乖離内容をバグレジストリに記録する

**既知の修正履歴**:

| 日付 | 修正内容 | 修正者 |
|:---|:---|:---|
| 2026-02-23 | Pitfall#3 クラスタリング値を実コードに合わせて修正（overlap/left_diff/threshold_y/gap_x） | Claude Code |
| 2026-02-23 | Pitfall#2 DPI_SCALE の定義場所を `unified_app.py L1420` に訂正 | Claude Code |

---

**このファイルは全セッションで最初に参照すること。**
