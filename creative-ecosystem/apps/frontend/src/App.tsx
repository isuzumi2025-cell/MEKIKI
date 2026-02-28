import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from '@/components/MainLayout'
import MekikiModule from '@/modules/mekiki'
import FlowForgeModule from '@/modules/flowforge'
import StoryboardModule from '@/modules/storyboard'
import AnalyticsModule from '@/modules/analytics'
import VaultModule from '@/modules/vault'
import SitemapModule from '@/modules/sitemap'

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<Navigate to="/mekiki" replace />} />
        <Route path="/mekiki/*" element={<MekikiModule />} />
        <Route path="/flowforge/*" element={<FlowForgeModule />} />
        <Route path="/storyboard/*" element={<StoryboardModule />} />
        <Route path="/analytics/*" element={<AnalyticsModule />} />
        <Route path="/vault/*" element={<VaultModule />} />
        <Route path="/sitemap/*" element={<SitemapModule />} />
      </Route>
    </Routes>
  )
}
