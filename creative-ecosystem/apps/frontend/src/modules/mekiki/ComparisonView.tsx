import { useState } from 'react'
import { ArrowLeft, CheckCircle, XCircle, MinusCircle, Save } from 'lucide-react'
import clsx from 'clsx'
import { api, type MekikiIssue } from '@/api/client'

type IssueStatus = 'OPEN' | 'CONFIRMED' | 'RESOLVED' | 'IGNORED'

interface ComparisonViewProps {
  issue: MekikiIssue
  onBack: () => void
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

export default function ComparisonView({ issue, onBack }: ComparisonViewProps) {
  const [status, setStatus] = useState<IssueStatus>(
    (issue.status as IssueStatus) || 'OPEN',
  )
  const [comment, setComment] = useState(issue.comment ?? '')
  const [overlayOpacity, setOverlayOpacity] = useState(0.5)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [feedbackSaved, setFeedbackSaved] = useState(false)

  const handleStatusChange = async (newStatus: IssueStatus) => {
    setSaving(true)
    setSaveError(null)
    try {
      await api.mekiki.updateIssue(issue.issue_id, {
        status: newStatus,
        comment,
      })
      setStatus(newStatus)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to update status')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveFeedback = async () => {
    setSaving(true)
    setSaveError(null)
    setFeedbackSaved(false)
    try {
      await api.mekiki.saveFeedback({
        issue_id: issue.issue_id,
        left_text: issue.left_text_norm,
        right_text: issue.right_text_norm,
        user_verdict: status,
        comment,
      })
      setFeedbackSaved(true)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save feedback')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-100 transition-colors"
        >
          <ArrowLeft size={16} />
          Back to Queue
        </button>
        <div className="h-4 w-px bg-gray-700" />
        <h2 className="text-lg font-semibold text-gray-100">Issue Detail</h2>
        <span
          className={clsx(
            'ml-auto px-2.5 py-0.5 rounded text-xs font-semibold',
            severityClasses(issue.severity),
          )}
        >
          {issue.severity}
        </span>
      </div>

      {/* Three-panel comparison */}
      <div className="grid grid-cols-3 gap-4">
        {/* Left panel */}
        <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">
            Left (Reference)
          </h3>
          <div className="rounded-lg bg-gray-900 border border-gray-700 px-3 py-2 text-sm text-gray-300 min-h-[80px] whitespace-pre-wrap">
            {issue.left_text_norm || '(empty)'}
          </div>
          {issue.evidence_left_crop && (
            <img
              src={issue.evidence_left_crop}
              alt="Left evidence crop"
              className="mt-3 w-full rounded-lg border border-gray-700"
            />
          )}
        </div>

        {/* Center - Diff */}
        <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Diff</h3>
          <div
            className="rounded-lg bg-gray-900 border border-gray-700 px-3 py-2 text-sm min-h-[80px] diff-content"
            dangerouslySetInnerHTML={{
              __html: issue.diff_html ?? 'No diff available',
            }}
          />
          {(issue.risk_reason?.length ?? 0) > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Risk Reasons
              </h4>
              <ul className="space-y-1">
                {issue.risk_reason.map((reason, i) => (
                  <li
                    key={i}
                    className="text-xs text-orange-300 flex items-start gap-1.5"
                  >
                    <span className="mt-0.5">-</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(issue.field_types?.length ?? 0) > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Fields
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {issue.field_types!.map((type, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded bg-gray-700 text-gray-300 text-xs"
                  >
                    {type}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">
            Right (Target)
          </h3>
          <div className="rounded-lg bg-gray-900 border border-gray-700 px-3 py-2 text-sm text-gray-300 min-h-[80px] whitespace-pre-wrap">
            {issue.right_text_norm || '(empty)'}
          </div>
          {issue.evidence_right_crop && (
            <img
              src={issue.evidence_right_crop}
              alt="Right evidence crop"
              className="mt-3 w-full rounded-lg border border-gray-700"
            />
          )}
        </div>
      </div>

      {/* Overlay */}
      {issue.evidence_overlay && (
        <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4">
          <h3 className="text-sm font-medium text-gray-300 mb-3">Overlay</h3>
          <div className="flex items-center gap-3 mb-3">
            <label className="text-xs text-gray-400">
              Opacity: {(overlayOpacity * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={overlayOpacity}
              onChange={(e) => setOverlayOpacity(parseFloat(e.target.value))}
              className="w-40 accent-indigo-500"
            />
          </div>
          <img
            src={issue.evidence_overlay}
            alt="Overlay"
            className="max-w-full rounded-lg border border-gray-700"
            style={{ opacity: overlayOpacity }}
          />
        </div>
      )}

      {/* Actions */}
      <div className="rounded-xl bg-gray-800/60 border border-gray-700 p-4 space-y-4">
        <h3 className="text-sm font-medium text-gray-300">Actions</h3>

        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => handleStatusChange('CONFIRMED')}
            disabled={saving}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
              status === 'CONFIRMED'
                ? 'bg-emerald-700 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600',
            )}
          >
            <CheckCircle size={15} />
            Confirm Issue
          </button>
          <button
            onClick={() => handleStatusChange('RESOLVED')}
            disabled={saving}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
              status === 'RESOLVED'
                ? 'bg-blue-700 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600',
            )}
          >
            <CheckCircle size={15} />
            Mark Resolved
          </button>
          <button
            onClick={() => handleStatusChange('IGNORED')}
            disabled={saving}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50',
              status === 'IGNORED'
                ? 'bg-gray-500 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600',
            )}
          >
            <XCircle size={15} />
            Ignore
          </button>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Comment</label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Add your notes here..."
            rows={3}
            className="w-full rounded-lg bg-gray-900 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-600 resize-none"
          />
        </div>

        {saveError && (
          <div className="text-red-400 text-xs flex items-center gap-1.5">
            <MinusCircle size={13} />
            {saveError}
          </div>
        )}
        {feedbackSaved && (
          <div className="text-emerald-400 text-xs flex items-center gap-1.5">
            <CheckCircle size={13} />
            Feedback saved to training dataset.
          </div>
        )}

        <button
          onClick={handleSaveFeedback}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white text-sm font-medium transition-colors disabled:opacity-50"
        >
          <Save size={15} />
          Save Feedback (Training Data)
        </button>
      </div>
    </div>
  )
}
