import React from 'react';
import { useTranslation } from 'react-i18next';
import { Gamepad2, ArrowRight } from 'lucide-react';

interface LoginProps {
  data: {
    client_id: string;
  };
}

const Login: React.FC<LoginProps> = ({ data }) => {
  const { t, i18n } = useTranslation();

  const toggleLang = () => {
    const newLang = i18n.language === 'en' ? 'de' : 'en';
    i18n.changeLanguage(newLang);
    localStorage.setItem('guildscout_lang', newLang);
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden font-sans">
      {/* Background is handled globally by GamingBackground component if mounted, 
          but Login page might be standalone. 
          Assuming GamingBackground is rendered in AppShell or we import it here. 
          The AppShell logic handles pageId='login' by NOT rendering AppShell (sidebar), 
          so we need to render GamingBackground here manually or ensure it's in the root. 
          
          Based on main.tsx logic: 
          if (pageId === 'login') useShell = false; 
          
          So we render GamingBackground here.
      */}
      
      {/* Import dynamically if possible, or just duplicate structure for now since imports might be tricky without full context */}
      <div className="fixed inset-0 z-[-10] overflow-hidden bg-[var(--bg-0)]">
        <div className="absolute inset-0 z-0">
            <video autoPlay loop muted playsInline className="w-full h-full object-cover">
            <source src="/static/video/background.mp4" type="video/mp4" />
            </video>
            <div className="absolute inset-0 bg-[var(--bg-0)] -z-10" />
        </div>
        <div className="absolute inset-0 z-10" style={{ background: 'rgba(3, 6, 16, 0.65)' }} />
        <div className="absolute inset-0 z-20" style={{ background: 'radial-gradient(circle at center, rgba(0,0,0,0.0) 0%, rgba(0,0,0,0.55) 70%, rgba(0,0,0,0.75) 100%)' }} />
        <div className="absolute inset-0 z-40 bg-[var(--primary)]/5 mix-blend-overlay pointer-events-none" />
      </div>

      {/* Lang Switcher */}
      <button onClick={toggleLang} className="absolute top-8 right-8 z-50 text-xs font-bold tracking-widest text-[var(--muted)] hover:text-white border border-white/10 px-3 py-1 rounded-full bg-black/20 backdrop-blur-sm transition-all hover:bg-white/10">
         {i18n.language.toUpperCase()}
      </button>

      {/* Hero Content - Glass Panel */}
      <div className="relative z-10 max-w-2xl mx-auto px-6 w-full">
        <div className="glass-panel p-12 md:p-16 text-center border-t border-white/10 relative overflow-hidden group">
            {/* Top Glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-1 bg-[var(--primary)]/20 blur-xl" />

            <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-[var(--primary)]/10 border border-[var(--primary)]/20 mb-8 shadow-[0_0_30px_rgba(45,226,230,0.15)] ring-1 ring-white/5">
                <Gamepad2 className="h-12 w-12 text-[var(--primary)]" />
            </div>

            <h1 className="text-5xl md:text-7xl font-heading font-black mb-6 text-white tracking-tight drop-shadow-lg">
                Guild<span className="text-transparent bg-clip-text bg-gradient-to-r from-[var(--primary)] to-white">Scout</span>
            </h1>
            
            <p className="text-xl md:text-2xl font-medium mb-10 text-[var(--muted)] leading-relaxed max-w-lg mx-auto">
                {t('hero.subline')}
            </p>

            <a 
            href="/auth/login"
            className="inline-flex items-center gap-3 px-10 py-5 rounded-2xl bg-[#5865F2] hover:bg-[#4752C4] text-white font-bold text-lg transition-all hover:scale-105 hover:shadow-[0_0_40px_rgba(88,101,242,0.4)] relative overflow-hidden"
            >
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
                <img src="https://assets-global.website-files.com/6257adef93867e56f84d3092/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png" className="w-6 h-6 brightness-0 invert" alt="Discord" />
                {t('hero.cta')}
                <ArrowRight className="h-5 w-5 opacity-70" />
            </a>

            <div className="mt-12 pt-8 border-t border-white/5 grid grid-cols-3 gap-4 text-center opacity-60">
                <div>
                    <div className="text-xl font-bold text-white mb-1">100%</div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Uptime</div>
                </div>
                <div>
                    <div className="text-xl font-bold text-white mb-1">Secure</div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">OAuth2</div>
                </div>
                <div>
                    <div className="text-xl font-bold text-white mb-1">Fast</div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Sync</div>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
};

export default Login;