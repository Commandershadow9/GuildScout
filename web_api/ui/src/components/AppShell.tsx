import React, { useState, useEffect } from 'react';
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
  Bell,
  Users,
  Trophy,
  Menu,
  X,
  Swords
} from 'lucide-react';
import { cn } from '@/lib/utils';
import PageTransition from './PageTransition';
import AnimatedBackground from './AnimatedBackground';

interface AppShellProps {
  children: React.ReactNode;
  pageId: string;
  data: any;
}

const AppShell: React.FC<AppShellProps> = ({ children, pageId, data }) => {
  const { t, i18n } = useTranslation();
  const [lang, setLang] = useState(i18n.language);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Check for mobile viewport
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
      if (window.innerWidth >= 768) {
        setSidebarOpen(false);
      }
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Close sidebar on navigation (mobile)
  const handleNavClick = () => {
    if (isMobile) {
      setSidebarOpen(false);
    }
  };

  const toggleLang = () => {
    const newLang = lang === 'en' ? 'de' : 'en';
    i18n.changeLanguage(newLang);
    setLang(newLang);
    localStorage.setItem('guildscout_lang', newLang);
  };

  // Only show guild-specific nav items when a guild is selected
  const hasGuild = !!data.guild;

  const navItems = [
    { id: 'guilds', label: t('nav.guilds'), icon: LayoutDashboard, href: '/guilds', alwaysShow: true },
    { id: 'dashboard', label: t('nav.raid_board'), icon: Gamepad2, href: hasGuild ? `/guilds/${data.guild.id}` : '#', alwaysShow: false },
    { id: 'create_raid', label: t('nav.create_raid'), icon: PlusCircle, href: hasGuild ? `/guilds/${data.guild.id}/raids/new` : '#', alwaysShow: false },
    { id: 'templates', label: t('nav.templates'), icon: FileText, href: hasGuild ? `/guilds/${data.guild.id}/templates` : '#', alwaysShow: false },
    { id: 'members', label: t('nav.members'), icon: Users, href: hasGuild ? `/guilds/${data.guild.id}/members` : '#', alwaysShow: false },
    { id: 'my_score', label: t('nav.my_score'), icon: Trophy, href: hasGuild ? `/guilds/${data.guild.id}/my-score` : '#', alwaysShow: false },
    { id: 'analytics', label: t('nav.analytics'), icon: BarChart2, href: hasGuild ? `/guilds/${data.guild.id}/analytics` : '#', alwaysShow: false },
    { id: 'control_center', label: t('nav.control_center'), icon: Sliders, href: hasGuild ? `/guilds/${data.guild.id}/settings` : '#', alwaysShow: false },
  ].filter(item => item.alwaysShow || hasGuild);

  return (
    <div className="flex min-h-screen text-[var(--text)] relative font-sans">
      {/* Animated Background */}
      <AnimatedBackground />

      {/* Mobile Backdrop */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Command Panel */}
      <aside className={cn(
        "fixed left-0 top-0 z-50 h-screen w-[260px] border-r border-[var(--border)] bg-[var(--surface-0)] flex flex-col shadow-2xl transition-transform duration-300 ease-in-out",
        isMobile && !sidebarOpen && "-translate-x-full",
        isMobile && sidebarOpen && "translate-x-0"
      )}>
        <div className="flex h-[64px] items-center justify-between px-6 border-b border-[var(--border)] bg-[var(--bg-1)]">
          <a href="/guilds" className="flex items-center gap-3 group">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-[var(--primary)] to-[var(--primary-dark)] flex items-center justify-center shadow-[var(--glow-primary)] group-hover:scale-105 transition-transform">
              <Swords className="h-5 w-5 text-black" />
            </div>
            <span className="text-lg font-heading font-bold tracking-tight text-white uppercase">GuildScout</span>
          </a>
          {/* Mobile Close Button */}
          {isMobile && (
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-2 -mr-2 text-[var(--muted)] hover:text-white transition-colors"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        <nav className="flex-1 py-6 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isDisabled = item.href === '#' || (!data.guild && item.id !== 'guilds');

            return (
            <a
              key={item.id}
              href={isDisabled ? undefined : item.href}
              onClick={handleNavClick}
              className={cn(
                "flex items-center gap-4 px-6 py-3 text-sm font-medium transition-all relative group",
                // Larger touch target on mobile
                isMobile && "py-4",
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
                <button type="submit" className="flex w-full items-center gap-2 text-xs font-bold text-[var(--muted)] hover:text-[var(--danger)] transition-colors uppercase tracking-wider py-2">
                    <LogOut className="h-4 w-4" />
                    {t('nav.logout')}
                </button>
            </form>
        </div>
      </aside>

      {/* Main Content */}
      <main className={cn(
        "flex-1 flex flex-col min-h-screen transition-all duration-300",
        !isMobile && "ml-[260px]"
      )}>
        {/* Top Bar */}
        <header className="sticky top-0 z-30 flex h-[64px] items-center justify-between border-b border-[var(--border)] bg-[var(--bg-1)]/85 px-4 md:px-8 backdrop-blur-md gap-4">
          {/* Mobile Menu Button */}
          {isMobile && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="p-2 -ml-2 text-[var(--muted)] hover:text-white transition-colors"
              aria-label="Open menu"
            >
              <Menu className="h-6 w-6" />
            </button>
          )}

          {/* Global Search */}
          <div className={cn(
            "flex items-center gap-3 rounded-xl bg-[var(--bg-0)] border border-[var(--border)] px-4 py-2.5 text-sm text-[var(--muted)] focus-within:border-[var(--secondary)]/50 focus-within:ring-1 focus-within:ring-[var(--secondary)]/30 transition-all",
            isMobile ? "flex-1 max-w-[200px]" : "w-full max-w-md"
          )}>
            <Search className="h-4 w-4 opacity-50 flex-shrink-0" />
            <input
              type="text"
              placeholder={isMobile ? t('actions.search_short') || 'Search...' : t('actions.search_placeholder')}
              className="bg-transparent outline-none w-full placeholder:text-[var(--muted)]/50 text-white font-medium min-w-0"
            />
          </div>

          <div className="flex items-center gap-3 md:gap-6 flex-shrink-0">
             {/* Actions */}
             <button className="relative text-[var(--muted)] hover:text-white transition-colors p-2">
                <Bell className="h-5 w-5" />
                <span className="absolute top-1 right-1 h-2 w-2 bg-[var(--danger)] rounded-full" />
             </button>

             {/* Language Switcher - Hidden on very small screens */}
             <button
                onClick={toggleLang}
                className="text-xs font-bold tracking-widest text-[var(--muted)] hover:text-white transition-colors uppercase hidden sm:block p-2"
             >
                {lang}
             </button>

            {/* User Menu */}
            <div className={cn(
              "flex items-center gap-3",
              !isMobile && "pl-6 border-l border-[var(--border)]"
            )}>
               {data.avatar_url && (
                 <img src={data.avatar_url} alt="User" className="h-8 w-8 md:h-9 md:w-9 rounded-full border border-[var(--border)] cursor-pointer hover:border-[var(--primary)] transition-colors" />
               )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 p-4 md:p-8 overflow-y-auto">
           <PageTransition>
              {children}
           </PageTransition>
        </div>
      </main>
    </div>
  );
};

export default AppShell;
