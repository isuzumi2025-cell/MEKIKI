# AgentOps Runbook

**Purpose**: 並列エージェント運用の実践ガイド

## 運用原則

1. **役割固定**: 各エージェントは専門性を持つ（実装/調査/検証/整理）
2. **並列実行**: 独立タスクは並行処理
3. **検証必須**: 全変更は verifier を通す
4. **Plan駆動**: Plan承認なしで実装しない

## エージェント役割分担

| エージェント | 責務 | 入力 | 出力 |
|:---|:---|:---|:---|
| **implementer** | コード実装 | Task + Plan | Code + Tests |
| **investigator** | 原因調査 | Issue | RCA Report |
| **verifier** | 検証 | Handoff Note | Verification Report |
| **refactorer** | コード整理 | Refactoring Plan | Refactored Code |

## 標準ワークフロー

### 新機能実装

```
User Request
  ↓
Plan作成 (implementer)
  ↓
Plan承認 (user)
  ↓
実装 (implementer)
  ↓
Handoff to verifier
  ↓
検証 (verifier)
  ├─ PASS → git commit, tag作成
  └─ FAIL → 差し戻し (implementer)
```

### バグ修正

```
Bug Report
  ↓
調査 (investigator)
  ↓
RCA Report作成
  ↓
修正Plan作成 (implementer)
  ↓
Plan承認 (user)
  ↓
実装 (implementer)
  ↓
検証 (verifier)
  ├─ PASS → 完了
  └─ FAIL → 再調査 (investigator)
```

## 並列実行パターン

### Pattern 1: 独立タスクの並列実行

```
Task A (implementer) ─┐
                      ├─ 並列実行
Task B (implementer) ─┘
  ↓
両方完了後に verifier で一括検証
```

### Pattern 2: 調査と実装の並列

```
Investigation (investigator) ─┐
                              ├─ 並列実行
Unrelated Feature (implementer)─┘
```

### Pattern 3: 検証と次タスク準備の並列

```
Verification (verifier) ─┐
                         ├─ 並列実行
Next Task Planning ─────┘
```

## 競合回避ルール

### ファイルロック

同じファイルを複数エージェントが編集しない：

```
implementer A: ファイル X を編集中
  → implementer B: ファイル X は編集不可
  → implementer B: ファイル Y を編集可（独立）
```

### git作業ブランチ

```bash
# エージェントごとにブランチ作成
git checkout -b agent/implementer/task-001
git checkout -b agent/investigator/issue-015

# 完了後にmain にマージ
git checkout main
git merge agent/implementer/task-001
```

## 通知と完了判断

### Handoff通知

```
implementer → verifier:
  "Task #001 実装完了。検証をお願いします。"
  Handoff Note: sdk/handoffs/to_verifier_task_001.md

verifier → user:
  "Task #001 検証完了。Status: PASS"
  Verification Report: verifications/verification_task_001.md
```

### 完了判断基準

**Task完了**:
- ✅ 全ACがPASS
- ✅ Verifier承認
- ✅ git commit + tag作成

**Phase完了**:
- ✅ Phase内全Taskが完了
- ✅ Phase ACが全てPASS
- ✅ User承認

## トラブルシューティング

### 検証が繰り返しFAIL

1. investigator に調査依頼
2. RCA Report確認
3. Plan再検討
4. 必要なら一度Rollback

### 並列実行時の競合

1. ファイル単位で競合確認
2. 先行タスク優先
3. 後続タスクは待機 or 別ファイル

### ACが曖昧

1. User に明確化依頼
2. AC更新
3. Plan再承認

---

**Status**: Phase 0 定義完了、Phase 1以降で運用開始
