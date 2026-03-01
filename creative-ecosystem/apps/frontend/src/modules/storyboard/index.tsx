import { useState, useEffect } from 'react'
import clsx from 'clsx'
import { Film, Send, Loader2, AlertCircle, Edit3, Mic, Volume2, Camera, RefreshCw } from 'lucide-react'
import {
  api,
  type StoryboardShot,
  type StoryboardPlanResponse,
  type PatternPreset,
  type PatternId,
} from '@/api/client'

// ---------------------------------------------------------------------------
// Planner Page
// ---------------------------------------------------------------------------

type Duration = '15s' | '30s' | '60s'
type Style = 'リアル' | 'アニメ' | '説明的'

const PATTERN_LABELS: Record<PatternId, string> = {
  p1_sns_15s: 'パターン1: SNS 15秒',
  p2_feature_15s: 'パターン2: 機能特化 15秒',
  p3_main_40s: 'パターン3: メイン 40秒',
  p4_hybrid_40s: 'パターン4: ハイブリッド 40秒',
}

const PATTERN_DURATION: Record<PatternId, Duration> = {
  p1_sns_15s: '15s',
  p2_feature_15s: '15s',
  p3_main_40s: '60s',
  p4_hybrid_40s: '60s',
}

function PlannerPage({ onPlanCreated }: { onPlanCreated: (res: StoryboardPlanResponse) => void }) {
  const [brief, setBrief] = useState('')
  const [duration, setDuration] = useState<Duration>('30s')
  const [style, setStyle] = useState<Style>('リアル')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<StoryboardPlanResponse | null>(null)

  // Pattern preset state
  const [patterns, setPatterns] = useState<PatternPreset[]>([])
  const [selectedPattern, setSelectedPattern] = useState<PatternId | 'custom'>('custom')
  const [patternLoading] = useState(false)
  const [usePattern, setUsePattern] = useState(false)

  useEffect(() => {
    api.storyboard.getPatterns()
      .then(setPatterns)
      .catch(() => {/* patterns are optional */})
  }, [])

  // When pattern is selected, update duration to match
  const handlePatternSelect = (id: PatternId | 'custom') => {
    setSelectedPattern(id)
    if (id !== 'custom') {
      setDuration(PATTERN_DURATION[id])
      setUsePattern(true)
    } else {
      setUsePattern(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!brief.trim() && !usePattern) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let res: StoryboardPlanResponse
      if (usePattern && selectedPattern !== 'custom') {
        res = await api.storyboard.createFromPattern(selectedPattern, brief)
      } else {
        res = await api.storyboard.createPlan({ brief, duration, style })
      }
      setResult(res)
      onPlanCreated(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create plan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h2 className="text-lg font-semibold text-gray-100 mb-6">プランニング</h2>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* Pattern Selector */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">
            TBEXパターン <span className="text-gray-600 font-normal">（プリセット）</span>
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handlePatternSelect('custom')}
              className={clsx(
                'text-left px-3 py-2.5 rounded-lg border text-sm transition-colors',
                selectedPattern === 'custom'
                  ? 'border-indigo-500 bg-indigo-900/30 text-indigo-200'
                  : 'border-gray-700 bg-gray-800/40 text-gray-400 hover:border-gray-600',
              )}
            >
              <span className="font-medium">カスタム</span>
              <span className="block text-xs text-gray-600 mt-0.5">ブリーフから自由生成</span>
            </button>
            {patterns.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => handlePatternSelect(p.id as PatternId)}
                className={clsx(
                  'text-left px-3 py-2.5 rounded-lg border text-sm transition-colors',
                  selectedPattern === p.id
                    ? 'border-indigo-500 bg-indigo-900/30 text-indigo-200'
                    : 'border-gray-700 bg-gray-800/40 text-gray-400 hover:border-gray-600',
                )}
              >
                <span className="font-medium">{p.label}</span>
                <span className="block text-xs text-gray-600 mt-0.5 line-clamp-1">{p.description}</span>
              </button>
            ))}
          </div>
          {patternLoading && (
            <div className="flex items-center gap-1.5 mt-2 text-xs text-gray-500">
              <Loader2 size={11} className="animate-spin" /> パターン読み込み中...
            </div>
          )}
        </div>

        {/* Brief */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1.5">
            ブリーフ
            {usePattern && <span className="ml-2 text-gray-600 font-normal">（省略可 — パターンの説明文を使用）</span>}
          </label>
          <textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            placeholder={
              usePattern
                ? '省略可。具体的な訴求ポイントがあれば記入...'
                : '動画の目的・ターゲット・訴求ポイントを記入...'
            }
            rows={4}
            className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-600 resize-none"
          />
        </div>

        {/* Duration + Style (hidden when pattern selected) */}
        {!usePattern && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">動画尺</label>
              <select
                value={duration}
                onChange={(e) => setDuration(e.target.value as Duration)}
                className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-600"
              >
                <option value="15s">15秒</option>
                <option value="30s">30秒</option>
                <option value="60s">60秒</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">スタイル</label>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value as Style)}
                className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-indigo-600"
              >
                <option value="リアル">リアル</option>
                <option value="アニメ">アニメ</option>
                <option value="説明的">説明的</option>
              </select>
            </div>
          </div>
        )}

        {usePattern && (
          <div className="rounded-lg bg-indigo-900/20 border border-indigo-800/50 px-3 py-2 text-xs text-indigo-300">
            <span className="font-medium">{PATTERN_LABELS[selectedPattern as PatternId]}</span>
            {' '}— {PATTERN_DURATION[selectedPattern as PatternId]}・TBEXプリセットショットを使用
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle size={14} />
            {error}
          </div>
        )}

        {result && (
          <div className="rounded-lg bg-emerald-900/30 border border-emerald-700/50 px-4 py-3 text-emerald-300 text-sm">
            プラン作成完了: <span className="font-mono">{result.plan_id.slice(0, 8)}…</span>{' '}
            ({result.shots.length} ショット) → ショットグリッドに移動しました
          </div>
        )}

        <button
          type="submit"
          disabled={loading || (!brief.trim() && !usePattern)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white text-sm font-medium transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          {loading ? '生成中...' : 'プランを生成'}
        </button>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shot phase badge
// ---------------------------------------------------------------------------

const phasePalette: Record<string, string> = {
  Hook: 'bg-purple-900/60 text-purple-300 border-purple-700',
  Problem: 'bg-red-900/60 text-red-300 border-red-700',
  Insight: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  Solution: 'bg-emerald-900/60 text-emerald-300 border-emerald-700',
  Proof: 'bg-blue-900/60 text-blue-300 border-blue-700',
  CTA: 'bg-orange-900/60 text-orange-300 border-orange-700',
  // TBEX Japanese phases
  キャッチ: 'bg-purple-900/60 text-purple-300 border-purple-700',
  デモ: 'bg-blue-900/60 text-blue-300 border-blue-700',
  判定: 'bg-emerald-900/60 text-emerald-300 border-emerald-700',
  オファー: 'bg-orange-900/60 text-orange-300 border-orange-700',
  基本情報: 'bg-sky-900/60 text-sky-300 border-sky-700',
  分析詳細: 'bg-violet-900/60 text-violet-300 border-violet-700',
  傾向管理: 'bg-teal-900/60 text-teal-300 border-teal-700',
  アクション: 'bg-orange-900/60 text-orange-300 border-orange-700',
  リリース: 'bg-pink-900/60 text-pink-300 border-pink-700',
  機能: 'bg-blue-900/60 text-blue-300 border-blue-700',
  体験: 'bg-emerald-900/60 text-emerald-300 border-emerald-700',
  比較: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  信頼: 'bg-indigo-900/60 text-indigo-300 border-indigo-700',
  タグライン: 'bg-gray-700/60 text-gray-300 border-gray-600',
  課題: 'bg-red-900/60 text-red-300 border-red-700',
  録音: 'bg-sky-900/60 text-sky-300 border-sky-700',
  検査: 'bg-violet-900/60 text-violet-300 border-violet-700',
  管理: 'bg-teal-900/60 text-teal-300 border-teal-700',
}

function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span
      className={clsx(
        'px-2 py-0.5 rounded text-xs font-semibold border',
        phasePalette[phase] ?? 'bg-gray-700 text-gray-300 border-gray-600',
      )}
    >
      {phase}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Shot Card
// ---------------------------------------------------------------------------

function ShotCard({ shot }: { shot: StoryboardShot }) {
  const hasTbex = !!(shot.telop || shot.audio || shot.scene_description)

  return (
    <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4 space-y-3 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-gray-500">
          #{String(shot.shot_no).padStart(2, '0')}
          <span className="ml-2 text-gray-600">{shot.start_sec}s–{shot.end_sec}s</span>
        </span>
        <PhaseBadge phase={shot.phase} />
      </div>

      {/* TBEX: Scene description */}
      {shot.scene_description && (
        <div className="flex gap-2">
          <Camera size={12} className="text-gray-600 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-gray-500 leading-relaxed">{shot.scene_description}</p>
        </div>
      )}

      {/* TBEX: Telop */}
      {shot.telop ? (
        <div className="rounded-md bg-yellow-900/20 border border-yellow-800/40 px-3 py-2">
          <p className="text-xs text-yellow-500 mb-1 font-medium flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 inline-block" />
            テロップ
          </p>
          <p className="text-sm text-yellow-100 font-medium leading-snug whitespace-pre-line">{shot.telop}</p>
        </div>
      ) : (
        <div>
          <p className="text-xs text-gray-500 mb-1">コピー</p>
          <p className="text-sm text-gray-200 leading-snug">{shot.copy_text}</p>
        </div>
      )}

      {/* TBEX: Audio */}
      {shot.audio ? (
        <div className="flex gap-2 items-start">
          <Volume2 size={12} className="text-blue-500 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-blue-300/80 leading-relaxed">{shot.audio}</p>
        </div>
      ) : null}

      {/* Standard fields (when no TBEX data) */}
      {!hasTbex && (
        <>
          <div>
            <p className="text-xs text-gray-500 mb-1">ナレーション</p>
            <p className="text-sm text-gray-400 leading-snug">{shot.narration_text}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Visual Hint</p>
            <p className="text-xs text-gray-600 italic">{shot.visual_hint}</p>
          </div>
        </>
      )}

      {/* Narration (always shown when TBEX active, as secondary info) */}
      {hasTbex && shot.narration_text && (
        <div className="flex gap-2 items-start">
          <Mic size={12} className="text-gray-600 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-gray-500 leading-relaxed">{shot.narration_text}</p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Grid Page
// ---------------------------------------------------------------------------

function GridPage({ planResult }: { planResult: StoryboardPlanResponse | null }) {
  const [shots, setShots] = useState<StoryboardShot[]>(planResult?.shots ?? [])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fetched, setFetched] = useState(!!planResult)

  const fetchShots = async () => {
    if (!planResult?.plan_id) {
      setError('プランIDがありません。先にプランを生成してください。')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.storyboard.getShots(planResult.plan_id)
      setShots(data.shots ?? [])
      setFetched(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch shots')
    } finally {
      setLoading(false)
    }
  }

  // Detect if shots have TBEX data
  const hasTbexData = shots.some((s) => s.telop || s.audio || s.scene_description)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">ショット一覧</h2>
          {hasTbexData && (
            <p className="text-xs text-indigo-400 mt-0.5">TBEXパターン適用済み — テロップ・音響フィールドあり</p>
          )}
        </div>
        <button
          onClick={fetchShots}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {fetched ? '更新' : 'ショットを取得'}
        </button>
      </div>

      {loading && (
        <div className="text-gray-500 text-sm animate-pulse py-12 text-center">Loading...</div>
      )}

      {!loading && error && (
        <div className="flex items-center gap-2 text-red-400 text-sm">
          <AlertCircle size={14} />
          {error}
        </div>
      )}

      {!loading && !error && fetched && shots.length === 0 && (
        <div className="text-center py-12 text-gray-600 text-sm">
          ショットが見つかりません。先にプランを生成してください。
        </div>
      )}

      {!loading && !fetched && !planResult && (
        <div className="text-center py-12 text-gray-600 text-sm">
          プランナータブでプランを生成してください。
        </div>
      )}

      {!loading && shots.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {shots.map((shot) => (
            <ShotCard key={shot.shot_no} shot={shot} />
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Editor Page (Coming Soon)
// ---------------------------------------------------------------------------

function EditorPage() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center px-6">
      <div className="w-12 h-12 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center mb-4">
        <Edit3 size={22} className="text-gray-500" />
      </div>
      <h2 className="text-base font-semibold text-gray-300 mb-2">テロップ・演出編集</h2>
      <p className="text-sm text-gray-600">Coming Soon</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Storyboard Module root
// ---------------------------------------------------------------------------

type StoryboardTab = 'planner' | 'grid' | 'editor'

const TABS: { label: string; value: StoryboardTab }[] = [
  { label: 'プランナー', value: 'planner' },
  { label: 'ショットグリッド', value: 'grid' },
  { label: '演出編集', value: 'editor' },
]

export default function StoryboardModule() {
  const [activeTab, setActiveTab] = useState<StoryboardTab>('planner')
  const [planResult, setPlanResult] = useState<StoryboardPlanResponse | null>(null)

  return (
    <div className="flex flex-col h-full">
      {/* Module header */}
      <div className="border-b border-gray-800 bg-gray-900/80 px-6 py-4 flex items-center gap-4 flex-shrink-0">
        <Film size={18} className="text-indigo-400" />
        <h1 className="text-base font-semibold text-gray-100">絵コンテ — Storyboard</h1>
        {planResult && (
          <span className="ml-auto text-xs font-mono text-gray-600">
            plan: {planResult.plan_id.slice(0, 8)}… · {planResult.shots.length} shots
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div className="border-b border-gray-800 px-6 flex gap-1 flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value)}
            className={clsx(
              'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.value
                ? 'border-indigo-500 text-indigo-300'
                : 'border-transparent text-gray-500 hover:text-gray-300',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'planner' && (
          <PlannerPage
            onPlanCreated={(res) => {
              setPlanResult(res)
              setActiveTab('grid')
            }}
          />
        )}
        {activeTab === 'grid' && <GridPage planResult={planResult} />}
        {activeTab === 'editor' && <EditorPage />}
      </div>
    </div>
  )
}
