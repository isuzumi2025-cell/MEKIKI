import { BarChart2 } from 'lucide-react'

export default function AnalyticsModule() {
  return (
    <div className="p-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="w-16 h-16 rounded-2xl bg-emerald-900/40 border border-emerald-700/50 flex items-center justify-center mb-5">
        <BarChart2 size={28} className="text-emerald-400" />
      </div>

      <h1 className="text-2xl font-bold text-gray-100 mb-2">Marketing Analytics</h1>
      <p className="text-gray-400 text-sm max-w-sm leading-relaxed">
        GA4連携・Decision Unitスコアリングは Phase 5 で実装予定
      </p>
    </div>
  )
}
