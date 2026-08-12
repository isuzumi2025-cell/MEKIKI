# Denbun Thread Aggregation — 散在エージェント作業の集約

Status: Reference
Last Updated: 2026-08-12
Scope: `isuzumi2025-cell/MEKIKI` に対して自律エージェント（主に Devin、一部 Claude Code / リポジトリオーナー）が個別にオープンした Pull Request（＝各エージェントからの「電文（denbun）」）の集約と現状整理

---

## 1. 背景

本リポジトリには `main` に対して開かれた PR が過去に **15件** 存在するが、**マージ済みは0件、全件クローズ済み** という状態だった。多くは Devin AI が個別セッションで独立にオープンしたもので、互いの存在を把握せずに重複領域へ着手しているケースが複数ある。

このドキュメントは、それら15件の PR（＝散在した開発スレッド）を横断的に洗い出し、

1. 何が提案されたか
2. なぜクローズされたか
3. その内容は `main` に何らかの形で反映されているか

を1箇所に集約し、今後の判断（再レビュー／マージ／破棄）をしやすくすることを目的とする。個別のコード変更は行っていない。

---

## 2. 全体サマリー

| # | タイトル | ブランチ | Author | Created → Closed | main への反映 |
|:-:|---|---|---|---|:-:|
| 1 | chore(submodule): OCR to manual-selection robustness fix | `chore/orchestra-governance` | isuzumi2025-cell | 02-11 → 03-01 (18日, 個別クローズ) | ⚠️ 未確認（submodule参照先が不一致） |
| 2 | FlowForge SDK改善 — as any撲滅 + retry/validation + Strategy | `devin/1771345287-flowforge-sdk-improvements` | devin-ai-integration[bot] | 02-17 → 02-18 (bulk close) | ✅ 反映済み |
| 3 | Phase 2 Agentセキュリティ + 耐障害性 (T-001〜T-011) | `feature/phase-2-agent-security` | devin-ai-integration[bot] | 02-17 → 02-18 (bulk close) | ✅ 反映済み（#5に統合） |
| 4 | Phase 3 VisualEditEngine | `feature/phase-3-visual-edit` | devin-ai-integration[bot] | 02-17 → 02-18 (bulk close) | ✅ 反映済み（#5に統合） |
| 5 | Phase 2-5 FlowForge SDK改善 一括 | `feature/remaining-improvements` | devin-ai-integration[bot] | 02-17 → 02-18 (bulk close) | ✅ 反映済み |
| 6 | 負荷テスト + 5軸評価プロンプト生成 (T-503, T-521) | `feature/load-test-and-eval` | devin-ai-integration[bot] | 02-18 → 03-01 (bulk close) | ✅ 反映済み |
| 7 | SubjectRegistry brushup (Gemini Vision, Jaccard, React GUI) | `feature/subject-registry-brushup` | devin-ai-integration[bot] | 02-18 → 03-01 (bulk close) | 🟡 部分反映（#10と重複競合） |
| 8 | FlowForge SDK Phase4-5 complete (GUI 9/9 + 170 tests) | `feature/flowforge-phase4-5-complete` | isuzumi2025-cell | 02-18 → 02-18 (4分, bulk close) | ✅ 反映済み |
| 9 | ArtMotion Forge + Client Material Pipeline | `feature/artmotion-forge-client-pipeline` | devin-ai-integration[bot] | 02-19 → 03-01 (bulk close) | ❌ 未反映 |
| 10 | FlowForge subject永続化, Jaccard類似度, VisualEdit, Vitest | `devin/1771551839-flowforge-subject-vitest` | devin-ai-integration[bot] | 02-20 → 03-01 (bulk close) | 🟡 部分反映（#7と重複競合） |
| 11 | PDF座標変換関数 + 123テスト（`mekiki/`パッケージ） | `devin/1772081373-coordinate-conversion-tests` | devin-ai-integration[bot] | 02-26 → 03-08 (**7日間放置で自動クローズ**) | ❌ 未反映 |
| 12 | PDF/Web座標一貫性テスト + 変換ユーティリティ | `devin/1772081494-coordinate-consistency-tests` | devin-ai-integration[bot] | 02-26 → 03-08 (自動クローズ) | ❌ 未反映 |
| 13 | Coordinate Transform POC (Master→Device, 精度/性能ベンチマーク) | `devin/1772082479-coordinate-transform-poc` | devin-ai-integration[bot] | 02-26 → 03-08 (自動クローズ) | ❌ 未反映 |
| 14 | AgentBackend ヘルスチェック + AgentOrchestra | `devin/1772086346-agent-health-check` | devin-ai-integration[bot] | 02-26 → 03-08 (自動クローズ) | ❌ 未反映 |
| 15 | compress_attachment パイプライン（エラー処理/ロギング） | `devin/1772087870-compression-error-handling` | devin-ai-integration[bot] | 02-26 → 03-08 (自動クローズ) | ❌ 未反映 |

凡例: ✅ 反映済み＝該当ファイルが `main` に存在 / 🟡 部分反映＝一部ファイルのみ存在・重複実装あり / ❌ 未反映＝該当ファイルが `main` に一切存在しない / ⚠️ 未確認＝submodule等、直接ファイル比較できない

**全ブランチは削除されておらず origin 上に現存している**（`git branch -a` で確認済み）。クローズ＝コード消失ではなく、いつでも再取得・再レビュー可能。

---

## 3. グループA: MEKIKI検版システム本体に関連する電文（#1, #11–#15）

CLAUDE.md が扱う「Web/PDF検版アプリ」本体、および AgentOps SDK（`sdk/orchestrator/`）に直接関係する提案。**このグループは1件も `main` に反映されていない。**

### 3.1 座標変換の三重独立実装（#11, #12, #13）— 要注意

2026-02-26 04:56〜05:15 の**20分間に3つの独立した Devin セッション**が、互いを認識しないまま同じ課題（PDF⇔Web座標変換）にそれぞれ別アプローチで着手していた。

| PR | アプローチ | 主な成果物 |
|---|---|---|
| #11 | 新規 `mekiki/` Python パッケージ、PDFユーザー空間(左下原点)⇔正規化0-1座標(左上原点) | `pdf_geometry.py`, `annotations/geometry.py`, テスト123件 |
| #12 | 正規/Web双方の型定義 + TS/Python両対応の canonical coordinate system | `middleware/logging.py`, `web/src/types/Coordinates.ts`, `web/src/utils/coordinates.ts`, テスト8,778件(parametrized) |
| #13 | mm→px の master/device変換パイプライン（iPad Pro / 4Kモニタ / A3プリンタ想定） | `master_schema.py`, `device_registry.py`, `transform_pipeline.py`, 精度/性能ベンチマーク |

これは CLAUDE.md **Pitfall #2「座標系のズレ」🔴 CRITICAL** が警告する領域そのものである。3案とも `main` の実装（`DPI_SCALE = 300/72` を使う `unified_app.py` 方式）とは別系統で、どれも未統合・未比較のまま7日間放置により自動クローズされた。座標系に手を入れる場合はこの3件を先に比較検討すべき。

### 3.2 AgentOrchestra 実装（#14）

`ROOT_AUTONOMOUS_ORCHESTRA_SPEC.md` および `sdk/orchestrator/` は現状 Markdown 仕様・ポリシーガード中心（`context_loader.py`, `policy_guard.py`, `completion_status.py` のみ）。#14 はこれを実装で埋める試みで、`AgentBackend`（gemini/grok/devin/openai/claude/local の6種）、並列ヘルスチェック付き `AgentOrchestra` を追加する内容。`main` の `sdk/orchestrator/` には該当ファイルが存在せず、未反映。

### 3.3 compress_attachment パイプライン（#15）

`ad_proofing_system/` 配下に添付ファイル圧縮（画像:Pillow, PDF:pikepdf+Ghostscriptフォールバック）を新規実装するもの。40テスト付き。`ad_proofing_system/src/` に該当モジュールは存在せず、未反映。

### 3.4 OCR submodule bump（#1）

`OCR` submodule を「手動選択の堅牢化」コミット (`39032f3`) へ更新する提案。現在の submodule ポインタ (`3960ce1...`) と一致しないため、この PR がそのまま適用された状態かは断定できない（別経路で異なる更新が入っている可能性）。他の14件と異なり Devin bot の自動クローズではなく、作成から18日後に個別にクローズされている。

---

## 4. グループB: FlowForge / ArtMotion（別プロダクト、動画生成パイプライン）（#2–#10）

`src/lib/`, `remotion.config.ts` 等に実装されている、Nano Banana → Veo の動画生成パイプライン（「FlowForge SDK」）関連。MEKIKI検版システムとは別の製品ラインで、`docs/flowforge_improvement_todo.md` / `docs/flowforge_improvement_spec_v2.md` が正本の進捗管理ドキュメントとして既に存在する。

### 4.1 このグループの特徴：PRはクローズだが中身はmainに反映済み

#2〜#8, #10 は PR としては未マージ・クローズだが、対象ファイル（`veo-client.ts`, `subject-registry.ts`, `visual-edit-engine.ts`, `resilience.ts`, `load-test-agent.ts` 等）は **`main` に実体として存在する**。`docs/flowforge_improvement_todo.md` が「T-001〜T-011 完了 (Devin PR #5)」のように PR番号を根拠に完了マークしている記述と整合しており、GitHubの「マージ」操作を経由せず、PR diff を手動で `main` に反映（コピー適用）した可能性が高い。

副作用として `src/lib/subject-registry-devin.ts`（Devin版オリジナル）と `src/lib/subject-registry.ts`（手動調整後の版）が両方残存している。前者が今も必要か要確認。

### 4.2 重複・統合関係

- **#2, #3, #4 → #5 に統合**: #5 のタイトルが明示的に "Phase 2-5 FlowForge SDK improvements" であり、#2(Phase1改善)・#3(Phase2)・#4(Phase3)の内容を包含する形で後発オープンされている。
- **#5, #8 は同一クローズバッチ**: #2,#3,#4,#5,#8 は 2026-02-18 09:56:45〜47 の**2秒間**に一斉クローズされている → 個別レビューではなく、まとめて手動整理された形跡。
- **#7 と #10 が重複**: 両方とも `subject-registry.ts` の Jaccard類似度実装 (`computeSimilarity`/`findSimilar`) を独立に実装しており、着手時期も02-18〜02-20と近い。
- **#9（ArtMotion Forge）のみ未反映**: `artmotion-forge.ts`, `client-material-pipeline.ts` は `main` に存在せず、このグループの中で唯一コードが失われている状態。

### 4.3 既存TODOドキュメントとの整合性について

`docs/flowforge_improvement_todo.md` / `flowforge_improvement_spec_v2.md` は「Devin PR #5」などPR番号を完了根拠として引用しているが、当該PRはGitHub上ではマージされていない（クローズのみ）。ドキュメント側の「完了」表記は実際のコード反映状況（4.1節）とは一致しているように見えるが、PRのマージ履歴という形での追跡可能性は失われている点に留意。

---

## 5. 主要な発見

1. **15件中14件が Devin bot による「7日間放置」自動クローズ**（#11〜#15はこのパターン、#2〜#10もbot自動クローズだが日付が近接しバルククローズ的）。人間による個別レビュー・却下ではなく、多くは放置の結果クローズされている。
2. **座標変換だけで3つの独立実装が並行発生**（#11,#12,#13）。CLAUDE.mdが最重要警告する「座標系のズレ」領域で、エージェント間の作業可視性が欠けていたことを示す実例。
3. **FlowForgeグループはPRフローを迂回してmainに反映されている**。「PRクローズ＝作業破棄」ではない実例であり、本集約作業のきっかけとなった「denbun（電文）がどこに消えたか分からない」問題の典型パターン。
4. **MEKIKI検版システム本体・AgentOps SDK関連の提案（#1, #11–#15）は反映ゼロ**。座標変換・AgentOrchestra実装・添付圧縮という、CLAUDE.md/ROOT_AUTONOMOUS_ORCHESTRA_SPEC.mdが言及する重要領域の提案が宙に浮いている。
5. **全ブランチはorigin上に現存**しており、破棄されたわけではない。再評価・再オープンは可能な状態。

---

## 6. 推奨アクション（人間の判断が必要）

- [ ] #11 / #12 / #13 を比較し、座標変換の実装をどれか一本化するか、`main`の既存方式（`unified_app.py` の `DPI_SCALE`方式）のまま維持するか判断する
- [ ] #14（AgentOrchestra実装）を `sdk/orchestrator/` に取り込むか、Markdown仕様のままにするか判断する
- [ ] #15（compress_attachment）が `ad_proofing_system/` のロードマップ上でまだ必要か確認する
- [ ] #1 のOCR submodule参照先と現在の `3960ce1...` の差分を確認する
- [ ] #9（ArtMotion Forge）のみFlowForgeグループ内で未反映なので、必要であれば `feature/artmotion-forge-client-pipeline` から再取得する
- [ ] `src/lib/subject-registry-devin.ts` が現在も参照されているか確認し、不要なら削除を検討する
- [ ] 今後の自律エージェント運用では、着手前に本ドキュメントのような集約状況を確認させ、同一領域への重複着手（#11/#12/#13、#7/#10のパターン）を防ぐ

---

## 7. 付録: 現存ブランチ一覧（origin）

```
chore/orchestra-governance
devin/1771345287-flowforge-sdk-improvements
devin/1771551839-flowforge-subject-vitest
devin/1772081373-coordinate-conversion-tests
devin/1772081494-coordinate-consistency-tests
devin/1772082479-coordinate-transform-poc
devin/1772086346-agent-health-check
devin/1772087870-compression-error-handling
feature/artmotion-forge-client-pipeline
feature/flowforge-phase4-5-complete
feature/load-test-and-eval
feature/phase-2-agent-security
feature/phase-3-visual-edit
feature/remaining-improvements
feature/subject-registry-brushup
```
