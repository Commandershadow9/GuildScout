import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  ArrowRight,
  Shield,
  Heart,
  Sword,
  Users,
  Zap,
  Radio,
  LayoutGrid,
  Crown,
  Swords
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Guild {
  id: string;
  name: string;
  icon?: string;
  permissions: number;
}

interface GuildsProps {
  data: {
    guilds: Guild[];
    session: any;
  };
}

const Guilds: React.FC<GuildsProps> = ({ data }) => {
  const { t } = useTranslation();
  const { guilds } = data;

  return (
    <div className="max-w-[1200px] mx-auto space-y-10 py-4 md:py-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2 text-[var(--secondary)] mb-3">
            <Crown className="h-5 w-5" />
            <span className="text-xs font-bold uppercase tracking-widest">{t('nav.guilds')}</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-heading font-black text-white tracking-tight">
            Your Guilds
          </h1>
          <p className="text-[var(--muted)] mt-2 max-w-xl">
            Select a guild to access the raid board and manage your operations.
          </p>
        </div>
        <div className="flex gap-4 text-sm font-medium text-[var(--muted)]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[var(--success)] animate-pulse" />
            <span>System Online</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 bg-[var(--surface-0)] rounded-lg border border-[var(--border)]">
            <LayoutGrid className="h-4 w-4 text-[var(--secondary)]" />
            <span>{guilds.length} {guilds.length === 1 ? 'Guild' : 'Guilds'}</span>
          </div>
        </div>
      </div>

      {/* Guild Grid */}
      {guilds.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {guilds.map((guild, index) => (
            <GuildCard key={guild.id} guild={guild} index={index} />
          ))}
        </div>
      )}
    </div>
  );
};

// Empty State Component
const EmptyState: React.FC = () => (
  <div className="panel-glass p-12 md:p-16 flex flex-col items-center justify-center text-center border-dashed relative">
    <div className="w-20 h-20 bg-[var(--bg-1)] rounded-2xl flex items-center justify-center mb-6 relative z-10">
      <Shield className="h-10 w-10 text-[var(--muted)]" />
    </div>
    <h3 className="text-xl font-bold text-white mb-2 relative z-10">No Guilds Found</h3>
    <p className="text-[var(--muted)] mt-2 max-w-md relative z-10">
      You don't have access to any guild command nodes. Make sure you have the required permissions on your Discord server.
    </p>
  </div>
);

// Guild Card Component
const GuildCard: React.FC<{ guild: Guild; index: number }> = ({ guild, index }) => {
  const { t } = useTranslation();

  return (
    <div
      className="panel-glass group relative overflow-hidden transition-all hover:border-[var(--primary)]/50 fade-in"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Background Effects */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--primary)]/5 rounded-full blur-3xl -mr-32 -mt-32" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-[var(--secondary)]/5 rounded-full blur-3xl -ml-24 -mb-24" />
      </div>

      <div className="flex flex-col lg:flex-row relative z-10">
        {/* Left: Identity */}
        <div className="p-6 md:p-8 flex-1 flex items-center gap-6 border-b lg:border-b-0 lg:border-r border-[var(--border)]">
          {/* Guild Icon */}
          {guild.icon ? (
            <img
              src={guild.icon}
              alt={guild.name}
              className="w-16 h-16 md:w-20 md:h-20 rounded-2xl border-2 border-[var(--border)] shadow-lg group-hover:scale-105 group-hover:border-[var(--primary)]/50 transition-all duration-300"
            />
          ) : (
            <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl border-2 border-[var(--border)] bg-[var(--surface-2)] flex items-center justify-center text-2xl font-bold text-[var(--muted)] group-hover:text-white group-hover:border-[var(--primary)]/50 transition-all duration-300">
              {guild.name.substring(0, 2).toUpperCase()}
            </div>
          )}

          {/* Guild Info */}
          <div className="flex-1 min-w-0">
            <h2 className="text-xl md:text-2xl font-heading font-bold text-white group-hover:text-[var(--primary)] transition-colors truncate">
              {guild.name}
            </h2>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className="badge badge-open">
                Ready
              </span>
              <span className="text-xs font-mono text-[var(--muted)]">
                ID: {guild.id.slice(-8)}
              </span>
            </div>
          </div>
        </div>

        {/* Middle: Quick Stats */}
        <div className="p-6 md:p-8 flex-1 bg-[var(--surface-0)]/30 border-b lg:border-b-0 lg:border-r border-[var(--border)]">
          <div className="grid grid-cols-3 gap-4 h-full">
            <RoleIndicator icon={Shield} color="blue" label="Tanks" />
            <RoleIndicator icon={Heart} color="emerald" label="Healers" />
            <RoleIndicator icon={Sword} color="orange" label="DPS" />
          </div>
        </div>

        {/* Right: Actions */}
        <div className="p-6 md:p-8 flex flex-col justify-center gap-3 lg:w-64">
          <a
            href={`/guilds/${guild.id}`}
            className="btn-primary w-full justify-center"
          >
            <Radio className="h-4 w-4" />
            Open Board
          </a>
          <a
            href={`/guilds/${guild.id}/raids/new`}
            className="btn-ghost w-full justify-center"
          >
            <Zap className="h-4 w-4" />
            New Raid
          </a>
        </div>
      </div>
    </div>
  );
};

// Role Indicator Component
const RoleIndicator: React.FC<{
  icon: React.ElementType;
  color: 'blue' | 'emerald' | 'orange';
  label: string;
}> = ({ icon: Icon, color, label }) => {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    orange: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  };

  return (
    <div className={cn(
      "flex flex-col items-center justify-center p-3 rounded-xl border transition-all",
      colorClasses[color]
    )}>
      <Icon className="h-5 w-5 mb-1" />
      <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</span>
    </div>
  );
};

export default Guilds;
