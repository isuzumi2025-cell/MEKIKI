import { useState, useEffect } from 'react'
import clsx from 'clsx'
import { api, type MekikiIssue } from '@/api/client'

interface ReviewQueueProps {
  onSelect: (issue: MekikiIssue) => void
}

type FilterType = 'all' | 'CRITICAL' | 'MAJOR' | 'MINOR'

function truncate(text: string | undefined, len = 50): string {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

function severityClasses(severity: string): string {
  switch (severity) {
    case 'CRITICAL':
      return 'bg-red-900/60 text-red-300 border border-red-700'
    case 'MAJOR':
      return 'bg-orange-900/60 text-orange-300 border border-orange-700'
    case 'MINOR':
      return 'bg-yellow-900/60 text-yellow-300 border border-yellow-700'
    default:
      return 'bg-gray-700 text-gray-300 border border-gray-600'
  }
}

function rowAccent(severity: string): string {
  switch (severity) {
    case 'CRITICAL':
      return 'border-l-2 border-l-red-600'
    case 'MAJOR':
      return 'border-l-2 border-l-orange-500'
    case 'MINOR':
      return 'border-l-2 border-l-yellow-500'
    default:
      return ''
  }
}

const FILTERS: { label: string; value: FilterType }[] = [
  { label: 'All', value: 'all' },
  { label: 'CRITICAL', value: 'CRITICAL' },
  { label: 'MAJOR', value: 'MAJOR' },
  { label: 'MINOR', value: 'MINOR' },
]

export default function ReviewQueue({ onSelect }: ReviewQueueProps) {
  const [issues, setIssues] = useState<MekikiIssue[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<FilterType>('all')

  useEffect(() => {
    fetchQueue()
  }, [filter])

  const fetchQueue = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.mekiki.getQueue(filter)
      const items =
        'queue' in data ? data.queue : 'issues' in data ? data.issues : []
      setIssues(items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch queue')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-100">Review Queue</h2>
        <div className="flex gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                filter === f.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-100',
              )}
            >
              {f.label}
            </button>
          ))}
          <button
            onClick={fetchQueue}
            className="px-3 py-1.5 rounded-md text-xs bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-100 transition-colors ml-2"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* States */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-gray-500 text-sm">
          <span className="animate-pulse">Loading...</span>
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg bg-red-900/30 border border-red-700/50 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && issues.length === 0 && (
        <div className="text-center py-16 text-gray-500 text-sm">
          No issues to review.
        </div>
      )}

      {/* Table */}
      {!loading && !error && issues.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-800/60">
                <th className="text-left px-4 py-3 text-gray-400 font-medium">
                  Severity
                </th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">
                  Left Text
                </th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">
                  Right Text
                </th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">
                  Risk Reason
                </th>
                <th className="text-right px-4 py-3 text-gray-400 font-medium">
                  Score
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {issues.map((issue) => (
                <tr
                  key={issue.issue_id}
                  className={clsx(
                    'hover:bg-gray-800/40 transition-colors',
                    rowAccent(issue.severity),
                  )}
                >
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        'px-2 py-0.5 rounded text-xs font-semibold',
                        severityClasses(issue.severity),
                      )}
                    >
                      {issue.severity}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300">{issue.diff_type}</td>
                  <td
                    className="px-4 py-3 text-gray-400"
                    title={issue.left_text_norm}
                  >
                    {truncate(issue.left_text_norm)}
                  </td>
                  <td
                    className="px-4 py-3 text-gray-400"
                    title={issue.right_text_norm}
                  >
                    {truncate(issue.right_text_norm)}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {(issue.risk_reason || []).join(', ')}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-300 tabular-nums">
                    {(issue.score_total * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onSelect(issue)}
                      className="px-3 py-1.5 rounded-md bg-indigo-700 hover:bg-indigo-600 text-white text-xs font-medium transition-colors"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
