# AgentOps SDK Onboarding Guide

**Welcome to AgentOps SDK!**

このガイドでは、AgentOps SDKの使い方を5ステップで説明します。

## Step 1: リポジトリコンテキストを読む

```bash
# CLAUDE.mdを読む（最重要）
cat CLAUDE.md
```

**内容**:
- ID整合性の落とし穴
- 座標系の落とし穴
- クラスタリング設定の落とし穴
- 変更禁止ファイル

## Step 2: コマンドを理解する

```bash
# コマンド一覧を確認
ls .claude/commands/

# 各コマンドの仕様を読む
cat .claude/commands/ingest_web.md
cat .claude/commands/match_paragraphs.md
cat .claude/commands/audit_ids.md
```

**主要コマンド**:
- `ingest_web`: Web OCR → web_paragraphs
- `ingest_pdf`: PDF抽出 → pdf_paragraphs
- `match_paragraphs`: マッチング → sync_pairs
- `audit_ids`: ID整合性チェック

## Step 3: エージェント役割を理解する

```bash
# エージェント定義を読む
ls .claude/agents/

cat .claude/agents/implementer.md
cat .claude/agents/verifier.md
```

**エージェント**:
- **implementer**: コード実装（差分≤100 LOC）
- **investigator**: 原因調査（コード編集禁止）
- **verifier**: 検証（AC全PASS必須）
- **refactorer**: コード整理（機能不変）

## Step 4: 最初のタスクを実行する

### Phase 1 / Unit 1: audit_ids

**目的**: ID整合性チェックの実装

```bash
# 実装スクリプトを作成
# OCR/scripts/audit_ids.py

# テストを作成
# OCR/tests/test_audit_ids.py

# 実行
python OCR/scripts/audit_ids.py --test --format=console
```

**期待結果**:
```
✅ PASS
Web ID Match: 100%
PDF ID Match: 100%
Duplicates: 0
```

### Phase 1 / Unit 2: match_paragraphs スキーマ固定

**目的**: MatchResultスキーマの固定

```bash
# スキーマ定義を確認
cat OCR/app/sdk/similarity/match_schema.py

# バリデータを確認
cat OCR/app/sdk/similarity/schema_validator.py
```

## Step 5: 検証を実行する

```bash
# Unit Tests
pytest OCR/tests/test_audit_ids.py -v

# Domain Checks
python OCR/scripts/audit_ids.py --test --format=console

# E2E Test (手動)
# 1. アプリ起動
# 2. 1 Web + 1 PDF を実行
# 3. ID/サムネイル表示確認
```

## よくある質問

### Q1: どこから始めればよいですか？

**A**: `CLAUDE.md` を読んでください。リポジトリ固有の落とし穴が記載されています。

### Q2: コマンドの実行方法は？

**A**: Phase 1で実装されたコマンドから順次使用可能になります。Phase 0では仕様のみ定義されています。

### Q3: 検証が失敗したら？

**A**: `post_tool_use.md` のRollback手順に従ってください。

### Q4: Plan承認はどこで？

**A**: `sdk/contracts/plan_contract.md` のテンプレートを使用し、User承認を得てください。

### Q5: AC（受け入れ条件）はどこで確認？

**A**: `sdk/contracts/acceptance_criteria.md` にカタログ化されています。

## 次のステップ

1. **Phase 1完了**: audit_ids, match_paragraphs スキーマ固定
2. **Phase 2実行**: 座標系修正、状態管理改善
3. **Phase 3**: 並列エージェント運用開始

## サポート

- **ドキュメント**: `CLAUDE.md`, `.claude/commands/`, `docs/runbook_agentops.md`
- **Issue報告**: RUNBOOKに追記

---

**Status**: Phase 0 完了、Phase 1以降で段階的に実装
