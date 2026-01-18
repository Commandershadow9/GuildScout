import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  LayoutDashboard, 
  Gamepad2, 
  PlusCircle, 
  FileText, 
  Sliders, 
  BarChart2, 
  Settings, 
  Search,
  LogOut,
  Globe,
  Bell
} from 'lucide-react';
import { cn } from '@/lib/utils';
import PageTransition from './PageTransition';

interface AppShellProps {
  children: React.ReactNode;
  pageId: string;
  data: any;
}

const AppShell: React.FC<AppShellProps> = ({ children, pageId, data }) => {
  const { t, i18n } = useTranslation();
  const [lang, setLang] = useState(i18n.language);

  const toggleLang = () => {
    const newLang = lang === 'en' ? 'de' : 'en';
    i18n.changeLanguage(newLang);
    setLang(newLang);
    localStorage.setItem('guildscout_lang', newLang);
  };

  const navItems = [
    { id: 'guilds', label: t('nav.guilds'), icon: LayoutDashboard, href: '/guilds' },
    { id: 'dashboard', label: t('nav.raid_board'), icon: Gamepad2, href: data.guild ? `/guilds/${data.guild.id}` : '#' },
    { id: 'create_raid', label: t('nav.create_raid'), icon: PlusCircle, href: data.guild ? `/guilds/${data.guild.id}/raids/new` : '#' },
    { id: 'templates', label: t('nav.templates'), icon: FileText, href: data.guild ? `/guilds/${data.guild.id}/templates` : '#' },
    { id: 'control_center', label: t('nav.control_center'), icon: Sliders, href: data.guild ? `/guilds/${data.guild.id}/settings` : '#' },
    { id: 'analytics', label: t('nav.analytics'), icon: BarChart2, href: data.guild ? `/guilds/${data.guild.id}/analytics` : '#' },
    { id: 'settings', label: t('nav.settings'), icon: Settings, href: data.guild ? `/guilds/${data.guild.id}/settings` : '#' },
  ];

  return (
    <div className="flex min-h-screen text-[var(--text)] relative font-sans">
      {/* Background is now CSS-only in index.css (Raid Board Texture) */}
      
      {/* Sidebar - Command Panel */}
      <aside className="fixed left-0 top-0 z-50 h-screen w-[260px] border-r border-[var(--border)] bg-[var(--surface-0)] flex flex-col shadow-2xl">
        <div className="flex h-[64px] items-center px-6 border-b border-[var(--border)] bg-[var(--bg-1)]">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)] font-bold border border-[var(--primary)]/30">
              GS
            </div>
            <span className="text-lg font-heading font-bold tracking-tight text-white uppercase">GuildScout</span>
          </div>
        </div>

        <nav className="flex-1 py-6 space-y-1">
          {navItems.map((item) => {
            const isDisabled = item.href === '#' || (!data.guild && item.id !== 'guilds');
            
            return (
            <a
              key={item.id}
              href={isDisabled ? undefined : item.href}
              className={cn(
                "flex items-center gap-4 px-6 py-3 text-sm font-medium transition-all relative group",
                pageId === item.id ? "nav-item-active" : "nav-item-inactive",
                isDisabled && "opacity-50 cursor-not-allowed pointer-events-none"
              )}
              aria-disabled={isDisabled}
            >
              <item.icon className={cn("h-5 w-5", pageId === item.id ? "text-[var(--primary)]" : "text-[var(--muted)] group-hover:text-white")} />
              <span>{item.label}</span>
            </a>
          )})}
        </nav>
        
        <div className="p-6 border-t border-[var(--border)] bg-[var(--bg-1)]">
            <div className="flex items-center gap-3 mb-4">
                {data.guild && (
                    <>
                    {data.guild.icon ? 
                      <img src={data.guild.icon} alt={data.guild.name} className="h-8 w-8 rounded-md border border-[var(--border)]" /> :
                      <div className="h-8 w-8 rounded-md bg-[var(--surface-2)] flex items-center justify-center text-xs font-bold">G</div>
                    }
                    <div className="overflow-hidden">
                        <div className="text-sm font-bold truncate text-white">{data.guild.name}</div>
                        <div className="text-[10px] text-[var(--success)] font-mono">ONLINE</div>
                    </div>
                    </>
                )}
            </div>
            <form action="/auth/logout" method="post">
                <button type="submit" className="flex w-full items-center gap-2 text-xs font-bold text-[var(--muted)] hover:text-[var(--danger)] transition-colors uppercase tracking-wider">
                    <LogOut className="h-4 w-4" />
                    {t('nav.logout')}
                </button>
            </form>
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-[260px] flex-1 flex flex-col min-h-screen">
        {/* Top Bar */}
        <header className="sticky top-0 z-40 flex h-[64px] items-center justify-between border-b border-[var(--border)] bg-[rgba(12,20,38,0.85)] px-8 backdrop-blur-md">
          {/* Global Search */}
          <div className="flex w-full max-w-md items-center gap-3 rounded bg-[var(--surface-1)] border border-[var(--border)] px-4 py-2 text-sm text-[var(--muted)] focus-within:border-[var(--primary)]/50 focus-within:ring-1 focus-within:ring-[var(--primary)]/50 transition-all">
            <Search className="h-4 w-4 opacity-50" />
            <input 
              type="text" 
              placeholder={t('actions.search_placeholder')}
              className="bg-transparent outline-none w-full placeholder:text-[var(--muted)]/50 text-white font-medium"
            />
          </div>

          <div className="flex items-center gap-6">
             {/* Actions */}
             <button className="relative text-[var(--muted)] hover:text-white transition-colors">
                <Bell className="h-5 w-5" />
                <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-[var(--danger)] rounded-full" />
             </button>

             {/* Language Switcher */}
             <button 
                onClick={toggleLang}
                className="text-xs font-bold tracking-widest text-[var(--muted)] hover:text-white transition-colors uppercase"
             >
                {lang}
             </button>

            {/* User Menu */}
            <div className="flex items-center gap-3 pl-6 border-l border-[var(--border)]">
               {data.avatar_url && (
                 <img src={data.avatar_url} alt="User" className="h-9 w-9 rounded-full border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors" />
               )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 p-8 overflow-y-auto">
           <PageTransition>
              {children}
           </PageTransition>
        </div>
      </main>
    </div>
  );
};

export default AppShell;
