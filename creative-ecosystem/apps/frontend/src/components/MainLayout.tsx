import { Outlet, NavLink } from 'react-router-dom'
import {
  FileCheck,
  Video,
  Film,
  BarChart2,
  BookOpen,
  Globe,
} from 'lucide-react'
import clsx from 'clsx'

interface NavItem {
  label: string
  sublabel: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  to: string
}

const navItems: NavItem[] = [
  { label: '校正', sublabel: 'MEKIKI', icon: FileCheck, to: '/mekiki' },
  { label: '動画制作', sublabel: 'FlowForge', icon: Video, to: '/flowforge' },
  { label: '絵コンテ', sublabel: 'Storyboard', icon: Film, to: '/storyboard' },
  { label: '分析', sublabel: 'Analytics', icon: BarChart2, to: '/analytics' },
  { label: 'Vault', sublabel: 'Knowledge', icon: BookOpen, to: '/vault' },
  { label: 'サイト分析', sublabel: 'Sitemap', icon: Globe, to: '/sitemap' },
]

export default function MainLayout() {
  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 bg-gray-950 border-r border-gray-800 flex flex-col">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold text-sm select-none">
              ICC
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-100 leading-tight">
                Integrated Creative
              </p>
              <p className="text-xs text-gray-500 leading-tight">Ecosystem</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-indigo-900/60 text-indigo-300'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    size={18}
                    className={clsx(
                      'flex-shrink-0',
                      isActive ? 'text-indigo-400' : 'text-gray-500',
                    )}
                  />
                  <span className="flex flex-col leading-tight">
                    <span className="font-medium">{item.label}</span>
                    <span className="text-xs opacity-60">{item.sublabel}</span>
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* System status */}
        <div className="px-4 py-4 border-t border-gray-800">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 animate-pulse" />
            <span className="text-xs text-gray-500">System Online</span>
          </div>
          <p className="text-xs text-gray-600 mt-1">v0.1.0 · ICC Monorepo</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-gray-900 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
