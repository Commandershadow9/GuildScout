import React from 'react'
import ReactDOM from 'react-dom/client'
import AppShell from './components/AppShell'
import Dashboard from './pages/Dashboard'
import Guilds from './pages/Guilds'
import CreateRaid from './pages/CreateRaid'
import Login from './pages/Login'
import Templates from './pages/Templates'
import Analytics from './pages/Analytics'
import RaidDetail from './pages/RaidDetail'
import Settings from './pages/Settings'
import './index.css'
import './i18n'

// Types for the global data injected by Jinja
declare global {
  interface Window {
    SERVER_DATA: any;
    PAGE_ID: string;
  }
}

const pageId = window.PAGE_ID || 'dashboard';
const data = window.SERVER_DATA || {};

let PageComponent;
let useShell = true;

switch (pageId) {
  case 'dashboard':
    PageComponent = <Dashboard data={data} />;
    break;
  case 'guilds':
    PageComponent = <Guilds data={data} />;
    break;
  case 'raid_create':
    PageComponent = <CreateRaid data={data} />;
    break;
  case 'raid_edit':
    PageComponent = <RaidDetail data={data} />;
    break;
  case 'settings':
    PageComponent = <Settings data={data} />;
    break;
  case 'templates':
    PageComponent = <Templates data={data} />;
    break;
  case 'analytics':
    PageComponent = <Analytics data={data} />;
    break;
  case 'login':
    PageComponent = <Login data={data} />;
    useShell = false;
    break;
  default:
    PageComponent = <div className="p-10 text-center text-muted-foreground">Page not implemented in React yet: {pageId}</div>;
}

const content = useShell ? (
    <AppShell pageId={pageId} data={data}>
      {PageComponent}
    </AppShell>
) : PageComponent;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {content}
  </React.StrictMode>,
)
