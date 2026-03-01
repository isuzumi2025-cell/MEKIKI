const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1'

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${method} ${path} → ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

const get = <T>(path: string) => request<T>('GET', path)
const post = <T>(path: string, body: unknown) => request<T>('POST', path, body)
const patch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MekikiIssue {
  issue_id: string
  severity: 'CRITICAL' | 'MAJOR' | 'MINOR' | 'INFO'
  diff_type: string
  left_text_norm: string
  right_text_norm: string
  risk_reason: string[]
  score_total: number
  status: string
  comment?: string
  diff_html?: string
  field_types?: string[]
  evidence_left_crop?: string
  evidence_right_crop?: string
  evidence_overlay?: string
}

export interface QueueResponse {
  queue: MekikiIssue[]
  total: number
}

export interface IssueListResponse {
  issues: MekikiIssue[]
}

export interface OrchestraContext {
  session_id: string
  trace_id: string
  route?: string
  source?: string
  job_id?: string
  profile_id?: number | string | null
  payload?: Record<string, unknown>
}

export interface OrchestraInsight {
  insight_id: string
  level: string
  title?: string
  message: string
  trace_id?: string
  created_at?: string
}

export interface StoryboardPlanRequest {
  brief: string
  duration: '15s' | '30s' | '60s'
  style: 'リアル' | 'アニメ' | '説明的'
}

export interface StoryboardShot {
  shot_no: number
  phase: string
  copy_text: string
  narration_text: string
  visual_hint: string
  start_sec: number
  end_sec: number
  duration_sec: number
  source_excerpt: string
  // TBEX extended fields
  scene_description?: string
  telop?: string
  audio?: string
}

export type PatternId = 'p1_sns_15s' | 'p2_feature_15s' | 'p3_main_40s' | 'p4_hybrid_40s'

export interface PatternShot {
  time: string          // e.g. "0-5"
  phase: string         // e.g. "キャッチ"
  scene_description: string
  telop: string
  audio: string
}

export interface PatternPreset {
  id: PatternId
  label: string         // e.g. "パターン1: SNS 15秒"
  duration: '15s' | '30s' | '60s'
  duration_sec: number
  description: string
  shots: PatternShot[]
}

export interface StoryboardPlanResponse {
  plan_id: string
  shots: StoryboardShot[]
  total_duration_sec: number
  created_at: string
}

export interface ShotsResponse {
  shots: StoryboardShot[]
}

export interface VaultSearchResult {
  id: string
  title: string
  excerpt: string
  tags: string[]
  score?: number
}

export interface VaultSearchResponse {
  results: VaultSearchResult[]
  query: string
}

export interface SitemapJob {
  job_id: string
  url: string
  status: 'pending' | 'running' | 'done' | 'error'
  created_at?: string
  result_url?: string
}

export interface SitemapJobsResponse {
  jobs: SitemapJob[]
}

export interface SitemapCreateResponse {
  job_id: string
  status: string
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export const api = {
  mekiki: {
    getQueue: (filter?: string) => {
      if (!filter || filter === 'all') {
        return get<QueueResponse>('/mekiki/queue?limit=100')
      }
      return get<IssueListResponse>(
        `/mekiki/issues?severity=${encodeURIComponent(filter)}&status=OPEN&limit=100`,
      )
    },

    getStats: () => get<QueueResponse>('/mekiki/queue?limit=100'),

    updateIssue: (issueId: string, data: { status?: string; comment?: string }) =>
      patch<MekikiIssue>(`/mekiki/issues/${encodeURIComponent(issueId)}`, data),

    saveFeedback: (data: {
      issue_id: string
      left_text: string
      right_text: string
      user_verdict: string
      comment: string
    }) => post<{ ok: boolean }>('/mekiki/dataset/feedback', data),

    getOrchestraContext: (sessionId: string) =>
      get<OrchestraContext>(
        `/mekiki/orchestra/context/${encodeURIComponent(sessionId)}`,
      ),

    listInsights: (params: {
      job_id?: string
      trace_id?: string
      limit?: number
    }) => {
      const qs = new URLSearchParams()
      if (params.job_id) qs.set('job_id', params.job_id)
      if (params.trace_id) qs.set('trace_id', params.trace_id)
      if (params.limit) qs.set('limit', String(params.limit))
      return get<OrchestraInsight[]>(`/mekiki/orchestra/insights?${qs}`)
    },
  },

  storyboard: {
    createPlan: (data: StoryboardPlanRequest) => {
      const durationMap: Record<string, number> = { '15s': 15, '30s': 30, '60s': 60 }
      const styleMap: Record<string, string> = { 'リアル': 'realistic', 'アニメ': 'anime', '説明的': 'descriptive' }
      return post<StoryboardPlanResponse>('/storyboard/plan', {
        brief: data.brief,
        duration_sec: durationMap[data.duration] ?? 30,
        style: styleMap[data.style] ?? 'realistic',
      })
    },

    createFromPattern: (patternId: PatternId, brief?: string) =>
      post<StoryboardPlanResponse>('/storyboard/from-pattern', {
        pattern_id: patternId,
        brief: brief ?? '',
      }),

    getShots: (planId: string) =>
      get<ShotsResponse>(`/storyboard/shots?plan_id=${encodeURIComponent(planId)}`),

    getPatterns: () =>
      get<PatternPreset[]>('/storyboard/patterns'),
  },

  vault: {
    search: (q: string) =>
      get<VaultSearchResponse>(
        `/vault/search?q=${encodeURIComponent(q)}`,
      ),
  },

  sitemap: {
    createJob: (url: string) =>
      post<SitemapCreateResponse>('/sitemap/jobs', { url }),

    listJobs: () => get<SitemapJobsResponse>('/sitemap/jobs'),
  },
}
