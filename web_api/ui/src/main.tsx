import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import AppShell from './components/AppShell'
import './index.css'
import './i18n'

// Lazy load all pages for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Guilds = lazy(() => import('./pages/Guilds'))
const CreateRaid = lazy(() => import('./pages/CreateRaid'))
const Login = lazy(() => import('./pages/Login'))
const Templates = lazy(() => import('./pages/Templates'))
const Analytics = lazy(() => import('./pages/Analytics'))
const RaidDetail = lazy(() => import('./pages/RaidDetail'))
const Settings = lazy(() => import('./pages/Settings'))
const MyScore = lazy(() => import('./pages/MyScore'))
const Members = lazy(() => import('./pages/Members'))

// Types for the global data injected by Jinja
declare global {
  interface Window {
    SERVER_DATA: any;
    PAGE_ID: string;
  }
}

// Loading spinner component
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[400px]">
    <div className="flex flex-col items-center gap-4">
      <div className="w-10 h-10 border-4 border-[var(--primary)]/20 border-t-[var(--primary)] rounded-full animate-spin" />
      <p className="text-[var(--muted)] text-sm font-medium">Loading...</p>
    </div>
  </div>
)

const pageId = window.PAGE_ID || 'dashboard';
const data = window.SERVER_DATA || {};

// Map of page IDs to their lazy-loaded components
const pageComponents: Record<string, React.LazyExoticComponent<React.ComponentType<any>>> = {
  dashboard: Dashboard,
  guilds: Guilds,
  raid_create: CreateRaid,
  raid_edit: RaidDetail,
  settings: Settings,
  templates: Templates,
  analytics: Analytics,
  my_score: MyScore,
  members: Members,
  login: Login,
}

const PageComponent = pageComponents[pageId]
const useShell = pageId !== 'login'

// Fallback for unknown pages
const UnknownPage = () => (
  <div className="p-10 text-center text-[var(--muted)]">
    Page not implemented: {pageId}
  </div>
)

const App = () => {
  const content = PageComponent ? (
    <Suspense fallback={<PageLoader />}>
      <PageComponent data={data} />
    </Suspense>
  ) : (
    <UnknownPage />
  )

  if (useShell) {
    return (
      <AppShell pageId={pageId} data={data}>
        {content}
      </AppShell>
    )
  }

  return content
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
