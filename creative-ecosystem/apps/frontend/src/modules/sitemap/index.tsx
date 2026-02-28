import { useState, useEffect } from 'react'
import { Globe, Plus, Loader2, AlertCircle, RefreshCw, ExternalLink } from 'lucide-react'
import clsx from 'clsx'
import { api, type SitemapJob } from '@/api/client'

function statusClasses(status: SitemapJob['status']): string {
  switch (status) {
    case 'done':
      return 'bg-emerald-900/50 text-emerald-300 border-emerald-700'
    case 'running':
      return 'bg-blue-900/50 text-blue-300 border-blue-700'
    case 'pending':
      return 'bg-yellow-900/50 text-yellow-300 border-yellow-700'
    case 'error':
      return 'bg-red-900/50 text-red-300 border-red-700'
    default:
      return 'bg-gray-700 text-gray-300 border-gray-600'
  }
}

function statusLabel(status: SitemapJob['status']): string {
  switch (status) {
    case 'done':
      return '完了'
    case 'running':
      return '実行中'
    case 'pending':
      return '待機中'
    case 'error':
      return 'エラー'
    default:
      return status
  }
}

export default function SitemapModule() {
  const [url, setUrl] = useState('')
  const [jobs, setJobs] = useState<SitemapJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(true)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  useEffect(() => {
    fetchJobs()
  }, [])

  const fetchJobs = async () => {
    setLoadingJobs(true)
    setListError(null)
    try {
      const data = await api.sitemap.listJobs()
      setJobs(data.jobs ?? [])
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoadingJobs(false)
    }
  }

  const handleCreateJob = async (e: React.FormEvent) => {
    e.preventDefault()
    const target = url.trim()
    if (!target) return
    setCreating(true)
    setCreateError(null)
    try {
      await api.sitemap.createJob(target)
      setUrl('')
      await fetchJobs()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create job')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Module header */}
      <div className="border-b border-gray-800 bg-gray-900/80 px-6 py-4 flex items-center gap-3 flex-shrink-0">
        <Globe size={18} className="text-cyan-400" />
        <h1 className="text-base font-semibold text-gray-100">サイト分析 — Sitemap Pro</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Create job form */}
          <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-5">
            <h2 className="text-sm font-semibold text-gray-300 mb-4">
              クロール開始
            </h2>
            <form onSubmit={handleCreateJob} className="flex gap-2">
              <div className="relative flex-1">
                <Globe
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
                />
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-gray-900 border border-gray-700 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-600"
                />
              </div>
              <button
                type="submit"
                disabled={creating || !url.trim()}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white text-sm font-medium transition-colors disabled:opacity-50"
              >
                {creating ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Plus size={15} />
                )}
                クロール開始
              </button>
            </form>

            {createError && (
              <div className="mt-3 flex items-center gap-2 text-red-400 text-xs">
                <AlertCircle size={13} />
                {createError}
              </div>
            )}
          </div>

          {/* Jobs list */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-300">
                ジョブ一覧
              </h2>
              <button
                onClick={fetchJobs}
                disabled={loadingJobs}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50"
              >
                <RefreshCw size={12} className={loadingJobs ? 'animate-spin' : ''} />
                更新
              </button>
            </div>

            {loadingJobs && (
              <div className="text-sm text-gray-500 animate-pulse py-6 text-center">
                Loading...
              </div>
            )}

            {!loadingJobs && listError && (
              <div className="flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle size={14} />
                {listError}
              </div>
            )}

            {!loadingJobs && !listError && jobs.length === 0 && (
              <div className="text-center py-10 text-gray-600 text-sm">
                ジョブがありません。URLを入力してクロールを開始してください。
              </div>
            )}

            {!loadingJobs && jobs.length > 0 && (
              <div className="space-y-2">
                {jobs.map((job) => (
                  <div
                    key={job.job_id}
                    className="rounded-lg bg-gray-800/60 border border-gray-700 px-4 py-3 flex items-center gap-4"
                  >
                    {/* Status badge */}
                    <span
                      className={clsx(
                        'flex-shrink-0 px-2 py-0.5 rounded text-xs font-semibold border',
                        statusClasses(job.status),
                      )}
                    >
                      {statusLabel(job.status)}
                    </span>

                    {/* URL */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-200 truncate">{job.url}</p>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs font-mono text-gray-600">
                          {job.job_id}
                        </span>
                        {job.created_at && (
                          <span className="text-xs text-gray-600">
                            {job.created_at}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Result link */}
                    {job.status === 'done' && job.result_url && (
                      <a
                        href={job.result_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors flex-shrink-0"
                      >
                        結果を見る
                        <ExternalLink size={11} />
                      </a>
                    )}

                    {/* Running spinner */}
                    {job.status === 'running' && (
                      <Loader2
                        size={14}
                        className="text-blue-400 animate-spin flex-shrink-0"
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
