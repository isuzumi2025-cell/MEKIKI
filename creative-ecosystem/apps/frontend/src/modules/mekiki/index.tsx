import { useState, useEffect } from 'react'
import clsx from 'clsx'
import { api, type MekikiIssue } from '@/api/client'
import ReviewQueue from './ReviewQueue'
import ComparisonView from './ComparisonView'
import OrchestraBridge from './OrchestraBridge'

type MekikiView = 'queue' | 'comparison' | 'orchestra'

interface Stats {
  critical: number
  major: number
  minor: number
  total: number
}

const MEKIKI_BASE = 'http://localhost:8000/api/v1/mekiki'

export default function MekikiModule() {
  const [currentView, setCurrentView] = useState<MekikiView>('queue')
  const [selectedIssue, setSelectedIssue] = useState<MekikiIssue | null>(null)
  const [stats, setStats] = useState<Stats>({
    critical: 0,
    major: 0,
    minor: 0,
    total: 0,
  })

  // Check URL for orchestra session
  const orchestraSessionId =
    new URLSearchParams(window.location.search).get('session_id') ??
    new URLSearchParams(window.location.search).get('orchestra_session_id')

  useEffect(() => {
    if (orchestraSessionId) setCurrentView('orchestra')
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      const data = await api.mekiki.getStats()
      const issues = data.queue ?? []
      setStats({
        critical: issues.filter((i) => i.severity === 'CRITICAL').length,
        major: issues.filter((i) => i.severity === 'MAJOR').length,
        minor: issues.filter((i) => i.severity === 'MINOR').length,
        total: data.total ?? issues.length,
      })
    } catch {
      // stats are non-critical
    }
  }

  const handleIssueSelect = (issue: MekikiIssue) => {
    setSelectedIssue(issue)
    setCurrentView('comparison')
  }

  const handleBack = () => {
    setSelectedIssue(null)
    setCurrentView('queue')
    fetchStats()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Module header */}
      <div className="border-b border-gray-800 bg-gray-900/80 px-6 py-4 flex items-center gap-6 flex-shrink-0">
        <div>
          <h1 className="text-base font-semibold text-gray-100">
            MEKIKI 校正システム
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Advanced Proofing System &nbsp;·&nbsp;
            <span className="font-mono text-gray-600">{MEKIKI_BASE}</span>
          </p>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-3 ml-auto">
          {orchestraSessionId && (
            <button
              onClick={() => setCurrentView('orchestra')}
              className={clsx(
                'px-3 py-1 rounded-md text-xs font-medium transition-colors',
                currentView === 'orchestra'
                  ? 'bg-indigo-700 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700',
              )}
            >
              Orchestra
            </button>
          )}
          <button
            onClick={() => setCurrentView('queue')}
            className={clsx(
              'px-3 py-1 rounded-md text-xs font-medium transition-colors',
              currentView === 'queue'
                ? 'bg-indigo-700 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700',
            )}
          >
            Queue
          </button>

          <div className="h-4 w-px bg-gray-700" />

          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              <span className="text-gray-400">
                CRITICAL: <span className="text-red-400 font-medium">{stats.critical}</span>
              </span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              <span className="text-gray-400">
                MAJOR: <span className="text-orange-400 font-medium">{stats.major}</span>
              </span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-yellow-500" />
              <span className="text-gray-400">
                MINOR: <span className="text-yellow-400 font-medium">{stats.minor}</span>
              </span>
            </span>
            <span className="text-gray-600">
              Total: <span className="text-gray-300">{stats.total}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Module body */}
      <div className="flex-1 overflow-y-auto">
        {currentView === 'orchestra' && orchestraSessionId && (
          <OrchestraBridge sessionId={orchestraSessionId} onBack={handleBack} />
        )}
        {currentView === 'queue' && (
          <ReviewQueue onSelect={handleIssueSelect} />
        )}
        {currentView === 'comparison' && selectedIssue && (
          <ComparisonView issue={selectedIssue} onBack={handleBack} />
        )}
      </div>
    </div>
  )
}
