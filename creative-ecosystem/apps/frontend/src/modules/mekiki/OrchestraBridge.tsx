import { useEffect, useState } from 'react'
import { ArrowLeft, RefreshCw, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { api, type OrchestraContext, type OrchestraInsight } from '@/api/client'

interface OrchestraBridgeProps {
  sessionId: string
  onBack: () => void
}

function levelClasses(level: string): string {
  switch (level.toLowerCase()) {
    case 'critical':
      return 'bg-red-900/60 text-red-300 border border-red-700'
    case 'major':
    case 'warning':
      return 'bg-orange-900/60 text-orange-300 border border-orange-700'
    case 'minor':
    case 'info':
      return 'bg-blue-900/60 text-blue-300 border border-blue-700'
    default:
      return 'bg-gray-700 text-gray-300 border border-gray-600'
  }
}

export default function OrchestraBridge({
  sessionId,
  onBack,
}: OrchestraBridgeProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [context, setContext] = useState<OrchestraContext | null>(null)
  const [insights, setInsights] = useState<OrchestraInsight[]>([])

  const fetchBridgeData = async () => {
    setLoading(true)
    setError(null)
    try {
      const ctx = await api.mekiki.getOrchestraContext(sessionId)
      setContext(ctx)
      const rows = await api.mekiki.listInsights({
        job_id: ctx.job_id,
        trace_id: ctx.trace_id,
        limit: 50,
      })
      setInsights(rows ?? [])
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load Orchestra context or insight logs.',
      )
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!sessionId) {
      setError('Missing session_id')
      setLoading(false)
      return
    }
    fetchBridgeData()
  }, [sessionId])

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center py-24 text-gray-500 text-sm animate-pulse">
        Loading Orchestra context...
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 space-y-4">
        <div className="rounded-xl bg-red-900/30 border border-red-700/50 px-4 py-3 text-red-300 text-sm flex items-start gap-2">
          <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
          {error}
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchBridgeData}
            className="px-4 py-2 rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white text-sm flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={14} />
            Retry
          </button>
          <button
            onClick={onBack}
            className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm flex items-center gap-2 transition-colors"
          >
            <ArrowLeft size={14} />
            Back to Queue
          </button>
        </div>
      </div>
    )
  }

  const metaItems: { label: string; value: string | number | null | undefined }[] =
    [
      { label: 'Session', value: context?.session_id },
      { label: 'Trace', value: context?.trace_id },
      { label: 'Route', value: context?.route ?? '-' },
      { label: 'Source', value: context?.source ?? '-' },
      { label: 'Job ID', value: context?.job_id ?? '-' },
      { label: 'Profile ID', value: context?.profile_id ?? '-' },
    ]

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-100 transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>
        <div className="h-4 w-px bg-gray-700" />
        <h2 className="text-lg font-semibold text-gray-100">
          Orchestra Context Handoff
        </h2>
        <button
          onClick={fetchBridgeData}
          className="ml-auto flex items-center gap-2 px-3 py-1.5 rounded-md bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-100 text-xs transition-colors"
        >
          <RefreshCw size={13} />
          Refresh
        </button>
      </div>

      {/* Meta grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {metaItems.map((item) => (
          <div
            key={item.label}
            className="rounded-lg bg-gray-800/60 border border-gray-700 px-4 py-3"
          >
            <p className="text-xs text-gray-500 mb-1">{item.label}</p>
            <p className="text-sm text-gray-200 font-mono break-all">
              {String(item.value ?? '-')}
            </p>
          </div>
        ))}
      </div>

      {/* Payload */}
      {context?.payload && (
        <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Payload</h3>
          <pre className="text-xs text-gray-400 bg-gray-900 rounded-lg p-3 overflow-x-auto border border-gray-700 max-h-64">
            {JSON.stringify(context.payload, null, 2)}
          </pre>
        </div>
      )}

      {/* Insights */}
      <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-4">
          Insight Logs ({insights.length})
        </h3>
        {insights.length === 0 ? (
          <p className="text-sm text-gray-600">
            No insights found for this context.
          </p>
        ) : (
          <div className="space-y-3">
            {insights.map((item) => (
              <article
                key={item.insight_id}
                className="rounded-lg bg-gray-900 border border-gray-700 px-4 py-3"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span
                    className={clsx(
                      'px-2 py-0.5 rounded text-xs font-semibold',
                      levelClasses(item.level || 'info'),
                    )}
                  >
                    {(item.level || 'INFO').toUpperCase()}
                  </span>
                  <span className="text-xs font-mono text-gray-500">
                    {item.insight_id}
                  </span>
                </div>
                {item.title && (
                  <h4 className="text-sm font-medium text-gray-200 mb-1">
                    {item.title}
                  </h4>
                )}
                <p className="text-sm text-gray-400">{item.message}</p>
                <div className="mt-2 flex gap-4 text-xs text-gray-600">
                  {item.trace_id && (
                    <span>
                      trace:{' '}
                      <span className="font-mono">{item.trace_id}</span>
                    </span>
                  )}
                  {item.created_at && <span>{item.created_at}</span>}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
