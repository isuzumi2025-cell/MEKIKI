# FlowForge SDK — 統合実装計画 v2（正本）

> **最終更新: 2026-02-18**
> 6 Phase 構成 — 完了フェーズ明示 + 未着手フェーズ詳細設計

---

## 全体進捗

| Phase | タイトル | 状態 | 完了率 |
| :-----: | ---------- | :----: | :------: |
| 0 | Nano Banana → Veo パイプライン | 🟡 部分完了 | 80% |
| 1 | 型安全性 + リトライ + Strategy | ✅ 完了 | 100% |
| 2 | Agent セキュリティ + 耐障害性 | ✅ 完了 | 100% |
| 3 | 画像参照修正 (VisualEditEngine) | ✅ コア完了 | 90% |
| 4 | StoryboardPipeline + GUI | 🟡 部分完了 | 70% |
| 5 | テスト + 品質 + 再評価 | 🟡 部分完了 | 60% |

---

## Phase 0: Nano Banana → Veo パイプライン [60%]

### ✅ 完了

- [image-gen-client.ts](file:///c:/Users/raiko/OneDrive/Desktop/RemotionProject/src/lib/image-gen-client.ts): `generateStartFrame()` — Nano Banana (`gemini-2.5-flash-image`) でコンテ画像生成
- [veo-client.ts](file:///c:/Users/raiko/OneDrive/Desktop/RemotionProject/src/lib/veo-client.ts): `generateVideoFromImage()` — 画像 → Veo 3.1 動画生成
- [generate-video.ts](file:///c:/Users/raiko/OneDrive/Desktop/RemotionProject/scripts/generate-video.ts): `image_to_video` モードで E2E テスト成功 (0.98MB MP4)

### ❌ 未完了

#### [NEW] storyboard-pipeline.ts

複数ショットから一括でコンテ画像 → 動画を生成するオーケストレーター。

```typescript
export interface StoryboardPipelineOptions {
    imageOnly?: boolean;          // コンテ画像のみ (動画化スキップ)
    parallelShots?: number;       // 並列生成ショット数 (default: 1)
    aspectRatio?: string;
    onProgress?: (shotIndex: number, total: number, step: string) => void;
}

export interface StoryboardResult {
    shots: ShotResult[];
    totalDurationMs: number;
}

export class StoryboardPipeline {
    private imageClient: ImageGenClient;
    private veoClient: VeoClient;
    private refiner: PromptRefiner;

    async generateFromStoryboard(
        storyboard: FlowStoryboardData,
        options?: StoryboardPipelineOptions,
    ): Promise<StoryboardResult>;
}
```

---

## Phase 1: 型安全性 + リトライ + Strategy [✅ 100%]

> Devin PR#2 により完了。ローカル適用 + 追加修正済み。

### 完了メソッド一覧

| ファイル | メソッド | 修正内容 |
| --- | --- | --- |
| veo-client.ts | `constructor()` | fail-fast + メソッド存在チェック |
| veo-client.ts | `generateVideo()` | SDK型使用 + withRetry + 指数バックオフ + AbortSignal |
| veo-client.ts | `downloadVideo()` | withRetry ラップ |
| veo-client.ts | `validateGenerateVideoOptions()` | 🆕 prompt/image 検証 |
| image-gen-client.ts | `generateWithGemini()` | hasInlineImageData 型ガード + withRetry |
| image-gen-client.ts | `generateWithImagen()` | メソッド存在チェック + withRetry |
| retry.ts | `withRetry<T>()` | 🆕 指数バックオフ + jitter + AbortSignal |
| strategy-manager.ts | `selectStrategy()` | 🆕 コンテキストベース戦略選択 |

---

## Phase 2: Agent セキュリティ + 耐障害性 [✅ 100% — Devin PR #5]

> 出典: `flowforge_improvement_spec_v1.md` Section 2.1–2.8

### [MODIFY] flowforge-agent-worker.ts

#### 2.1 セキュリティ修正 [CRITICAL]

```diff
- const url = `https://...?key=${this.config.geminiApiKey}&pageSize=1`;
- const res = await fetch(url, { method: "GET", ... });
+ const url = "https://generativelanguage.googleapis.com/v1beta/models";
+ const res = await fetch(url, {
+   method: "GET",
+   headers: { "x-goog-api-key": this.config.geminiApiKey! },
+   ...
+ });
```

#### 2.2 DI (依存性注入)

```typescript
interface IHealthChecker {
    checkGemini(config: AgentConfig): Promise<ServiceHealth>;
    checkGrok(config: AgentConfig): Promise<ServiceHealth>;
    checkDevin(config: AgentConfig): Promise<ServiceHealth>;
}

class HealthMonitor {
    constructor(config: AgentConfig, checker?: IHealthChecker) {
        this.checker = checker ?? new DefaultHealthChecker();
    }
}
```

#### 2.3 レース条件修正

```typescript
class HealthMonitor {
    private isChecking = false;
    async check(): Promise<HealthStatus> {
        if (this.isChecking) return this.cache!;
        this.isChecking = true;
        try { /* ... */ }
        finally { this.isChecking = false; }
    }
}
```

#### 2.4 Graceful Shutdown

```typescript
const shutdownController = new AbortController();
case "shutdown":
    shutdownController.abort();
    clearInterval(healthTimer);
    clearInterval(nudgeTimer);
    emit({ type: "shutdown_complete" });
    setTimeout(() => process.exit(0), 500);
    break;
```

### [MODIFY] flowforge-agent.ts

#### 2.5 Worker 自動再起動

```typescript
this.worker.on("exit", (code) => {
    if (code !== 0 && this.shouldAutoRestart) {
        console.warn(`[Agent] Worker crashed (code=${code}), restarting...`);
        setTimeout(() => this.start(), 1000);
        this.restartCount++;
    }
});
```

### [NEW] flowforge-agent-types.ts

型をWorkerファイルから分離。`AgentCommand`, `AgentEvent`, `AgentConfig`, `AgentContext` を集約。

### [NEW] resilience.ts (Agent 用回路ブレーカー)

```typescript
interface CircuitBreakerConfig {
    failureThreshold: number;  // default: 5
    resetTimeoutMs: number;    // default: 60000
}
function createCircuitBreaker(name: string, config: CircuitBreakerConfig): CircuitBreaker;
```

### [MODIFY] NudgeEngine — プラグイン化

```typescript
interface NudgeRule {
    id: string;
    priority: "low" | "medium" | "high";
    cooldownMs: number;
    condition: (ctx: AgentContext, health: HealthStatus | null) => boolean;
    message: string | ((ctx: AgentContext) => string);
}
class NudgeEngine {
    constructor(rules: NudgeRule[] = DEFAULT_RULES) { ... }
}
```

---

## Phase 3: 画像参照修正 (VisualEditEngine) [❌ 未着手]

> [!IMPORTANT]
> ユーザー要件: 「リーダー格の作業員が持っている棒の形状を画像のものに変えて」のような、参照画像ベースの動画修正機能。

### [NEW] visual-edit-engine.ts

```typescript
/** 画像参照による修正指示 */
export interface VisualEditInstruction {
    /** 参照画像 (Base64 バイナリ) */
    referenceImageBytes: string;
    referenceImageMimeType: "image/png" | "image/jpeg" | "image/webp";

    /** 修正対象のオブジェクト/人物の自然言語記述 */
    targetElement: string;

    /** 修正の種類 */
    editType:
        | "replace_shape"     // 形状を参照画像のものに変更
        | "replace_style"     // スタイル/質感を参照画像のものに変更
        | "replace_color"     // 色を参照画像のものに変更
        | "add_from_image"    // 参照画像のオブジェクトを動画に追加
        | "match_pose";       // 参照画像のポーズに合わせる

    /** 追加の修正指示 (自然言語) */
    additionalInstruction?: string;
}

/** 修正差分解析の結果 */
export interface VisualEditAnalysis {
    referenceObjects: ObjectDetail[];       // 参照画像から抽出したオブジェクト
    targetObjects: ObjectDetail[];          // 既存プロンプトのオブジェクト
    matchedPairs: [ObjectDetail, ObjectDetail][];  // マッチング結果
    editPromptDiff: string;                 // プロンプトの差分テキスト
}

export class VisualEditEngine {
    private analyzer: ResourceAnalyzer;
    private geminiApiKey: string;

    /**
     * 参照画像を解析し、既存動画のプロンプトと照合して
     * 修正すべき差分プロンプトを生成する
     */
    async analyzeEdit(
        previousResult: GenerationJobResult,
        instruction: VisualEditInstruction,
    ): Promise<VisualEditAnalysis>;

    /**
     * 解析結果をもとに EditablePrompt を修正して再生成
     */
    async regenerateWithVisualReference(
        previousResult: GenerationJobResult,
        instruction: VisualEditInstruction,
    ): Promise<GenerationJobResult>;

    /**
     * Gemini Vision で参照画像の該当オブジェクトを
     * 詳細記述に変換する (Veo プロンプト最適化済み)
     */
    private async describeObjectForVeo(
        imageBytes: string,
        mimeType: string,
        targetElement: string,
    ): Promise<string>;
}
```

### ResourceVideoGenerator への統合

```typescript
// resource-video-generator.ts に追加
async regenerateWithVisualReference(
    previousResult: GenerationJobResult,
    instruction: VisualEditInstruction,
): Promise<GenerationJobResult> {
    const visualEngine = new VisualEditEngine(/* ... */);
    return visualEngine.regenerateWithVisualReference(previousResult, instruction);
}
```

### VeoClient の referenceImages 活用

```typescript
// veo-client.ts の referenceImages パラメータを修正タイプに応じて使い分け
// editType → referenceType マッピング:
//   "replace_shape" → "ASSET"     (オブジェクト形状)
//   "replace_style" → "STYLE"     (スタイル参照)
//   "match_pose"    → "SUBJECT"   (人物参照)
```

---

## Phase 4: StoryboardPipeline + FlowForge GUI [❌ 未着手]

### 4.1 StoryboardPipeline (Phase 0 残り)

前述の `storyboard-pipeline.ts` をフル実装。

### 4.2 FlowForge GUI コンポーネント

```text
src/components/flowforge/
├── FlowForgeStudio.tsx       # メインパネル
├── PromptEditor.tsx          # セクション別編集 + 自動強化ボタン
├── ResourceUploader.tsx      # ドラッグ&ドロップ + 解析プレビュー
├── TextProcessingPanel.tsx   # preserve / erase / animate 3モード
├── CharacterPanel.tsx        # キャラクター詳細エディタ
├── ToneMannerPanel.tsx       # URL入力 + カラーパレット
├── VisualEditPanel.tsx       # 🆕 参照画像修正UI
├── MotionGraphicsPanel.tsx   # MG ベクトル設定
└── GenerationProgress.tsx    # 進捗 + プレビュー
```

---

## Phase 5: テスト + 品質 + 再評価 [60%]

### ✅ Phase 5 完了項目

- `npx tsc --noEmit` パス
- Nano Banana → Veo E2E テスト成功
- 6軸プロンプト理解テスト成功 (confidence 100/100)
- Vitest 42/42 passed *(Devin PR #5)*
  - `__tests__/resilience.test.ts` (17), `nudge-rules.test.ts` (13), `prompt-understanding-schemas.test.ts` (12)
- `logger.ts` 構造化ロギング pino 導入 *(Devin PR #5)*
- T-601 Zod スキーマ (GrokAxes + OpusAxes) *(Devin PR #5)*

### ❌ Phase 5 未完了項目

| タスク | 内容 |
| --- | --- |
| Vitest ユニットテスト | HealthMonitor / NudgeEngine / ContextRegistry (80%+ カバレッジ) |
| 統合テスト | Graceful Shutdown / Worker再起動 / 回路ブレーカー |
| 負荷テスト | 1時間連続稼働 + heapdump メモリリーク検証 |
| 構造化ロギング | pino 導入 + メトリクス収集 |
| 入力バリデーション | Zod スキーマ (AgentCommand) |
| 5次元再評価 | Orchestra 4エージェント再評価 → 44+/50 目標 |

---

## 検証計画

### 自動テスト

```bash
npx tsc --noEmit
npx tsx scripts/test-flowforge-e2e.ts
npx tsx scripts/test-6axis-understanding.ts
npx vitest run           # Phase 5 完了後
```

### ブラウザテスト

- Remotion Studio 起動 → FlowForge GUI 操作テスト

### 手動検証

- 画像参照修正: テスト画像でオブジェクト差替テスト (Phase 3 完了後)
- StoryboardPipeline: 3ショットストーリーボードで一括生成 (Phase 4 完了後)
