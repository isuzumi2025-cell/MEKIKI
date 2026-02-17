# SKILL: sync_spreadsheet

**Version**: 1.0.0
**Phase**: Phase 2
**Priority**: 🟡 MAJOR

---

## Objective

Google Sheetsエクスポートのスキーマ固定化：スプレッドシート列定義を v1.0.0 に固定し、全SyncPairが漏れなく・ID紐付けが正確に・スキーマバージョン管理されてエクスポートされることを保証する。

---

## Scope

### ✅ このユニットで触って良い範囲

- `OCR/app/sdk/export/spreadsheet.py` - Google Sheets API統合
- `sdk/contracts/spreadsheet_schema_v1.json` - スキーマ定義（Phase 2で作成）
- Google Sheets API認証・書き込みロジック
- スキーマバリデーション

### ❌ このユニットで触るな

- SyncPair生成ロジック（Phase 1で完了）
- ID紐付けロジック（audit_ids で検証済み）
- `service_account.json` の内容（認証情報）

---

## Inputs

```python
@dataclass
class SyncSpreadsheetInput:
    sync_pairs: List[SyncPair]        # required
    spreadsheet_url: str              # required
    sheet_name: str = "Sync Results"  # optional
    schema_version: str = "v1.0.0"    # optional
    append_mode: bool = False         # optional
```

---

## Outputs

```python
@dataclass
class SyncSpreadsheetOutput:
    status: str                       # "success" | "error"
    rows_written: int
    spreadsheet_url: str
    error_message: Optional[str]
    validation: Dict[str, Any]
```

---

## Acceptance Criteria

### AC-SYNC-SHEET-1: スキーマバージョン一致 ✅

```
スキーマバージョンが v1.0.0 に一致

Validation:
  シート右下セル == "v1.0.0"
```

### AC-SYNC-SHEET-2: 列定義固定順序 ✅

```
列定義が固定順序で書き込まれる

Validation:
  ヘッダー行 == ["#", "Web ID", "Web Thumb", "Web Text", "⇔", "PDF Text", "PDF Thumb", "PDF ID", "Sync Rate"]
```

### AC-SYNC-SHEET-3: 全SyncPair書き込み ✅

```
全SyncPairが漏れなく書き込まれる

Validation:
  len(sync_pairs) == スプレッドシート行数 - 1 (header除く)
```

### AC-SYNC-SHEET-4: ID一致 ✅

```
Web ID / PDF ID が area_code と一致

Validation:
  /audit-ids
  → "Web ID Match: 100%"
```

### AC-SYNC-SHEET-5: Sync Rate 正確 ✅

```
Sync Rate が正しく計算されている

Validation:
  各行の Sync Rate == SyncPair.similarity
```

### AC-SYNC-SHEET-6: テキスト切り詰め ✅

```
テキストが200文字で切り詰められている

Validation:
  len(cell_value) <= 200
```

### AC-SYNC-SHEET-7: API認証エラーハンドリング ✅

```
API認証エラーが適切にハンドリングされる

Validation:
  service_account.json不正 → 明確なエラーメッセージ
```

---

## Validation Steps

```bash
# Step 1: スキーマ検証
python scripts/validate_spreadsheet_schema.py

# Step 2: ID整合性チェック（エクスポート前）
/audit-ids

# Step 3: テスト出力（ダミーデータ）
python scripts/test_spreadsheet_export.py

# Step 4: 実際のスプレッドシート確認
# Google Sheets を開いて目視確認：
# - ヘッダー行が正しい
# - 全行にデータが入っている
# - Sync Rateが％表示
# - 右下セルに "v1.0.0"
```

---

## Stop Conditions（中断条件）

### 🛑 IMMEDIATE STOP: API認証失敗

**検出方法**: `gspread.exceptions.APIError`

**対処**:
- `service_account.json` ファイル確認
- Cloud Console で権限確認
- スプレッドシート共有設定確認（ロボットアカウントが「編集者」）

---

### 🛑 IMMEDIATE STOP: スキーマ不一致

**検出方法**: 列定義が v1.0.0 と異なる

**対処**:
- `sdk/contracts/spreadsheet_schema_v1.json` 確認
- 列順序を修正
- バージョンマイグレーション実行

---

### 🛑 IMMEDIATE STOP: ID不一致検出

**検出方法**:
```bash
/audit-ids
# → "Web ID Match: < 100%"
```

**対処**: エクスポート中断、Phase 1 に戻ってID整合性を修正

---

### 🛑 WARNING: API Quota 超過

**検出方法**: `gspread.exceptions.APIError: Quota exceeded`

**対処**:
- リトライロジック追加（指数バックオフ）
- バッチ書き込み（複数行を1リクエストに統合）
- レート制限実装

---

### 🛑 WARNING: ネットワークエラー

**検出方法**: `requests.exceptions.ConnectionError`

**対処**:
- リトライ（最大3回）
- タイムアウト延長
- ローカルキャッシュに保存

---

## Schema Definition (v1.0.0)

```json
{
  "version": "v1.0.0",
  "columns": [
    {"name": "#", "type": "int", "required": true},
    {"name": "Web ID", "type": "string", "required": true},
    {"name": "Web Thumb", "type": "image", "required": false},
    {"name": "Web Text", "type": "string", "required": true},
    {"name": "⇔", "type": "string", "required": true},
    {"name": "PDF Text", "type": "string", "required": true},
    {"name": "PDF Thumb", "type": "image", "required": false},
    {"name": "PDF ID", "type": "string", "required": true},
    {"name": "Sync Rate", "type": "float", "required": true}
  ]
}
```

---

## Dependencies

- `gspread` (Google Sheets API)
- `google-auth` (認証)
- `service_account.json` (認証ファイル)
- `app/sdk/export/spreadsheet.py`
- `sdk/contracts/spreadsheet_schema_v1.json` (Phase 2で作成)

---

## Example Usage

```python
from app.sdk.export.spreadsheet import SpreadsheetExporter

exporter = SpreadsheetExporter('service_account.json')
result = exporter.export(
    sync_pairs=sync_pairs,
    spreadsheet_url=user_input_url,
    sheet_name='Sync Results',
    schema_version='v1.0.0'
)

if result['status'] == 'success':
    print(f"✅ {result['rows_written']}行を書き込みました")
else:
    print(f"❌ エラー: {result['error_message']}")
```

---

## Authentication Setup

**初回のみ**:
1. Google Cloudコンソールでサービスアカウント作成
2. `service_account.json` をダウンロード
3. スプレッドシートにロボットメールアドレスを「編集者」として共有

**ロボットメールアドレス確認**:
```bash
python check_account.py
# → xxx@xxx.iam.gserviceaccount.com
```

---

**Status**: Phase 2 実装予定

**Next Unit**: (Phase 2完了後、Phase 3へ)
