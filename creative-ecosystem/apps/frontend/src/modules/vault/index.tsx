import { useState } from 'react'
import { BookOpen, Search, Loader2, AlertCircle, Tag } from 'lucide-react'
import { api, type VaultSearchResult } from '@/api/client'

export default function VaultModule() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<VaultSearchResult[]>([])
  const [searched, setSearched] = useState(false)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setLoading(true)
    setError(null)
    setSearched(false)
    try {
      const data = await api.vault.search(q)
      setResults(data.results ?? [])
      setSearched(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Module header */}
      <div className="border-b border-gray-800 bg-gray-900/80 px-6 py-4 flex items-center gap-3 flex-shrink-0">
        <BookOpen size={18} className="text-amber-400" />
        <h1 className="text-base font-semibold text-gray-100">Vault — Knowledge RAG</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Search form */}
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="ドキュメントを検索..."
                className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-600"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Search size={15} />
              )}
              検索
            </button>
          </form>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          {/* No results */}
          {!loading && searched && results.length === 0 && (
            <div className="text-center py-12 text-gray-600 text-sm">
              "{query}" に一致するドキュメントが見つかりませんでした。
            </div>
          )}

          {/* Results */}
          {!loading && results.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs text-gray-600">
                {results.length} 件のドキュメント
              </p>
              {results.map((item) => (
                <article
                  key={item.id}
                  className="rounded-xl bg-gray-800/60 border border-gray-700 px-5 py-4 hover:border-gray-600 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-gray-200 leading-snug">
                      {item.title}
                    </h3>
                    {item.score !== undefined && (
                      <span className="text-xs text-gray-600 flex-shrink-0 font-mono">
                        {(item.score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>

                  <p className="text-sm text-gray-400 mt-2 leading-relaxed">
                    {item.excerpt}
                  </p>

                  {item.tags.length > 0 && (
                    <div className="flex items-center gap-2 mt-3 flex-wrap">
                      <Tag size={11} className="text-gray-600" />
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 rounded bg-gray-700 text-gray-400 text-xs"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}

          {/* Initial state */}
          {!loading && !searched && (
            <div className="flex flex-col items-center py-16 text-center">
              <BookOpen size={36} className="text-gray-700 mb-3" />
              <p className="text-sm text-gray-600">
                キーワードを入力してVaultを検索
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
