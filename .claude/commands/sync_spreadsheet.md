# Command: sync_spreadsheet

**Purpose**: 結果のスプレッドシート反映

## Trigger

ユーザーが「Google Sheets出力」ボタンを押したとき、または自動エクスポート設定時。

## Input Schema

```json
{
  "sync_pairs": "List[SyncPair] (required)",
  "spreadsheet_url": "string (required)",
  "sheet_name": "string (optional, default: 'Sync Results')",
  "schema_version": "string (optional, default: 'v1.0.0')",
  "append_mode": "boolean (optional, default: false)"
}
```

**例**:
```json
{
  "sync_pairs": [...],
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/xxx",
  "sheet_name": "Sync Results",
  "schema_version": "v1.0.0",
  "append_mode": false
}
```

## Output Schema

```json
{
  "status": "success | error",
  "rows_written": 48,
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/xxx",
  "error_message": "string (if error)",
  "validation": {
    "schema_valid": true,
    "all_fields_present": true,
    "warnings": []
  }
}
```

## Execution Steps

1. **前提条件チェック**:
   - `service_account.json` が存在する
   - スプレッドシートURLが有効
   - ロボットアカウントが「編集者」権限で共有されている

2. **スキーマ検証**: `spreadsheet_schema_v1.json` との照合
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

3. **Google Sheets API認証**:
   ```python
   import gspread
   from google.oauth2.service_account import Credentials

   scopes = ['https://www.googleapis.com/auth/spreadsheets']
   creds = Credentials.from_service_account_file(
       'service_account.json', scopes=scopes
   )
   client = gspread.authorize(creds)
   ```

4. **シート取得/作成**:
   ```python
   spreadsheet = client.open_by_url(spreadsheet_url)
   try:
       sheet = spreadsheet.worksheet(sheet_name)
   except gspread.WorksheetNotFound:
       sheet = spreadsheet.add_worksheet(
           title=sheet_name, rows=1000, cols=9
       )
   ```

5. **ヘッダー書き込み**:
   ```python
   headers = ["#", "Web ID", "Web Thumb", "Web Text", "⇔",
              "PDF Text", "PDF Thumb", "PDF ID", "Sync Rate"]
   sheet.update('A1:I1', [headers])
   ```

6. **データ行書き込み**:
   ```python
   rows = []
   for i, pair in enumerate(sync_pairs, start=1):
       row = [
           i,  # #
           pair.web_id,  # Web ID
           "",  # Web Thumb（画像URLまたは空）
           pair.web_text[:200],  # Web Text（200文字まで）
           "⇔",  # 矢印
           pair.pdf_text[:200],  # PDF Text
           "",  # PDF Thumb
           pair.pdf_id,  # PDF ID
           f"{pair.similarity:.2%}"  # Sync Rate
       ]
       rows.append(row)

   sheet.update(f'A2:I{len(rows)+1}', rows)
   ```

7. **書式設定**（オプション）:
   - ヘッダー行を太字、背景色
   - Sync Rate列を％表示
   - Text列を折り返し表示

## Acceptance Criteria

- ✅ **AC-SYNC-SHEET-1**: スキーマバージョンが一致（v1.0.0）
- ✅ **AC-SYNC-SHEET-2**: 列定義が固定順序で書き込まれる
- ✅ **AC-SYNC-SHEET-3**: 全SyncPairが漏れなく書き込まれる
- ✅ **AC-SYNC-SHEET-4**: Web ID / PDF ID が area_code と一致
- ✅ **AC-SYNC-SHEET-5**: Sync Rate が正しく計算されている
- ✅ **AC-SYNC-SHEET-6**: テキストが200文字で切り詰められている
- ✅ **AC-SYNC-SHEET-7**: API認証エラーが適切にハンドリングされる

## Failure Modes & Error Handling

| エラー分類 | 原因例 | 対処 |
|:---|:---|:---|
| **AUTH_ERROR** | service_account.json不正 | ファイル確認、権限確認 |
| **PERMISSION_ERROR** | ロボット未共有 | スプレッドシートの共有設定確認 |
| **QUOTA_EXCEEDED** | APIクォータ超過 | リトライ、レート制限 |
| **SCHEMA_MISMATCH** | 列定義が不一致 | スキーマバージョン確認、マイグレーション |
| **URL_INVALID** | スプレッドシートURL不正 | URL形式確認 |
| **NETWORK_ERROR** | ネットワーク障害 | リトライ（最大3回） |

## Schema Versioning

**v1.0.0** (現在):
```
| # | Web ID | Web Thumb | Web Text | ⇔ | PDF Text | PDF Thumb | PDF ID | Sync Rate |
```

**v1.1.0** (Phase 2計画):
```
| # | Web ID | Web Thumb | Web Text | ⇔ | PDF Text | PDF Thumb | PDF ID | Sync Rate | Confidence |
```

**マイグレーション**:
- スキーマバージョンをシートの右下セルに記録
- バージョン不一致時に警告
- 後方互換性を維持

## Validation Commands

```bash
# スキーマ検証
python scripts/validate_spreadsheet_schema.py

# ID整合性チェック（エクスポート前）
/audit-ids

# テスト出力（ダミーデータ）
python scripts/test_spreadsheet_export.py
```

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

## Dependencies

- `gspread`
- `google-auth`
- `service_account.json`
- `app/sdk/export/spreadsheet.py`
- `sdk/contracts/spreadsheet_schema_v1.json` (Phase 2で作成)

## Example Usage

```python
# unified_app.py 内で呼び出し
from app.sdk.export.spreadsheet import SpreadsheetExporter

exporter = SpreadsheetExporter('service_account.json')
result = exporter.export(
    sync_pairs=sync_pairs,
    spreadsheet_url=user_input_url,
    sheet_name='Sync Results'
)

if result['status'] == 'success':
    print(f"✅ {result['rows_written']}行を書き込みました")
else:
    print(f"❌ エラー: {result['error_message']}")
```

---

**Next Command**: `audit_ids.md`
