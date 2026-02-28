import { Video, Zap } from 'lucide-react'

export default function FlowForgeModule() {
  return (
    <div className="p-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="w-16 h-16 rounded-2xl bg-violet-900/40 border border-violet-700/50 flex items-center justify-center mb-5">
        <Video size={28} className="text-violet-400" />
      </div>

      <h1 className="text-2xl font-bold text-gray-100 mb-2">FlowForge 動画制作</h1>
      <p className="text-gray-400 text-sm max-w-sm leading-relaxed">
        Express サイドカー (:3001) 経由で動画生成パイプラインを管理します。
      </p>

      <div className="mt-8 flex items-center gap-2 text-xs text-gray-600">
        <Zap size={13} className="text-gray-600" />
        <span>FlowForge server endpoint: <span className="font-mono text-gray-500">localhost:3001</span></span>
      </div>
    </div>
  )
}
