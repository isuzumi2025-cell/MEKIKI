# AgentOps SDK 実装指示

## ROLE

あなたは「AgentOps SDK」を実装するシニアテックリードです。目的は、Web/PDF検版アプリの開発・運用を、並列エージェント運用＋複利ルール化＋契約駆動Plan＋自動検証ループで高速化し、手戻りを最小化することです。

## CONTEXT

- 対象：WebとPDFの広告素材を比較検版するアプリ（OCRアプリ）
- コア：OCR→要素正規化→視覚解析→クラスタリング→ロール推定→Sync計算→色分け表示
- 要注意：ID整合（web_id/pdf_id/area_code）と座標リンクの破綻が致命的
- 既存SDK: `OCR/app/sdk/` に `ocr/`, `similarity/`, `llm/` 等が存在

## GOAL

以下の構造で AgentOps SDK 基盤を導入：

```
c:\Users\raiko\OneDrive\Desktop\26\
├── CLAUDE.md
├── .claude/
│   ├── settings.json
│   ├── commands/
│   │   ├── ingest-web.md
│   │   ├── ingest-pdf.md
│   │   ├── match-paragraphs.md
│   │   ├── render-diff.md
│   │   ├── sync-spreadsheet.md
│   │   └── audit-ids.md
│   ├── agents/
│   │   ├── implementer.md
│   │   ├── investigator.md
│   │   ├── verifier.md
│   │   └── refactorer.md
│   └── hooks/
│       └── post-tool-use.md
├── sdk/
│   ├── orchestrator/
│   │   ├── task_model.md
│   │   └── state_machine.md
│   ├── contracts/
│   │   ├── plan_contract.md
│   │   └── acceptance_criteria.md
│   └── telemetry/
│       └── metrics.md
└── docs/
    ├── runbook_agentops.md
    └── onboarding.md
```

## HARD CONSTRAINTS

- まずPlan（契約）を作る。Plan承認前に大規模編集しない
- 変更は小さく刻み、各コミット/差分の受け入れ条件（AC）を明示
- 追加する設定・ルール・コマンド定義はGit管理し、再現可能に
- 危険な全許可は避け、許可リストで運用

## PHASE 0: 基盤設定（最初に実行）

### CLAUDE.md

リポジトリ全体のルール・コンテキストを定義

### .claude/settings.json

許可リスト方針を定義

## PHASE 1: コマンド定義

各コマンドは SKILL.md 形式で：

- `name`: スラッシュコマンド名
- `description`: いつ使うか
- 入力/出力/手順/AC を記載

| コマンド | 目的 |
|:---|:---|
| ingest-web | Web OCR → web_paragraphs |
| ingest-pdf | PDF抽出 → pdf_paragraphs |
| match-paragraphs | マッチング → sync_pairs |
| render-diff | 色分け表示 |
| sync-spreadsheet | スプレッドシート反映 |
| audit-ids | ID整合チェック |

## PHASE 2: エージェントロール

| エージェント | 責務 |
|:---|:---|
| implementer | 最小差分でコード変更 |
| investigator | 原因調査・ログ分析 |
| verifier | テスト・E2E・ゴールデン比較 |
| refactorer | 命名・分割・重複除去 |

## PHASE 3: 検証フック・KPI

post-tool-use フック：

- formatter/lint/test
- ドメイン検証（ID監査・座標監査・マッチ品質）

KPI:

- 往復回数 ≤3
- 差分量 ≤100 LOC
- 失敗率 ≤10%

## DOMAIN-SPECIFIC AC

- ID監査：web_id/pdf_id/area_code の整合チェック
- 座標監査：選択範囲の座標がUIと内部表現で一致
- マッチ品質：スコア分布が異常なら警告
- スプレッドシート：スキーマ（列定義）固定、入力検証

## EXECUTE

Phase 0 から順に実行してください。各ファイルを作成し、ACを満たすことを確認してから次へ進んでください。
