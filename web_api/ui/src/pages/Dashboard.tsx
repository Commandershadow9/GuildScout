import React, { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Clock,
  CheckCircle,
  Activity,
  Calendar,
  Plus,
  Lock,
  Users,
  MoreHorizontal,
  UserPlus,
  Edit,
  XCircle,
  Wifi,
  WifiOff,
  Loader2,
  Swords,
  Timer,
  TrendingUp,
  Zap,
  Shield,
  Heart,
  Sword
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Raid {
  id: number;
  title: string;
  description: string;
  status: string;
  game: string;
  mode: string;
  start_time: string;
  timestamp: number;
  raid_date: string;
  raid_time: string;
  counts: {
    tank: string;
    healer: string;
    dps: string;
    bench: string;
  };
  open_slots: number;
}

interface ActivityEvent {
  id: string;
  type: string;
  icon: string;
  description: string;
  timestamp: string;
  user_name?: string;
  metadata?: Record<string, any>;
}

interface DashboardProps {
  data: {
    raids: Raid[];
    health: any;
    guild: any;
    settings: any;
  };
}

type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
type FilterTab = 'open' | 'locked' | 'history';

const Dashboard: React.FC<DashboardProps> = ({ data }) => {
  const { t } = useTranslation();
  const { raids: initialRaids, guild } = data;

  const [raids, setRaids] = useState<Raid[]>(initialRaids);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(true);
  const [wsStatus, setWsStatus] = useState<WSStatus>('disconnected');
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [activeTab, setActiveTab] = useState<FilterTab>('open');
  const [countdown, setCountdown] = useState<string>('--:--:--');

  const nextRaid = raids.find(r => r.status === 'open') || (raids.length > 0 ? raids[0] : null);

  // Calculate countdown to next raid
  useEffect(() => {
    if (!nextRaid) {
      setCountdown('--:--:--');
      return;
    }

    const updateCountdown = () => {
      const now = new Date();
      const raidDateTime = new Date(`${nextRaid.raid_date}T${nextRaid.raid_time}`);
      const diff = raidDateTime.getTime() - now.getTime();

      if (diff <= 0) {
        setCountdown('LIVE NOW');
        return;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      if (days > 0) {
        setCountdown(`${days}d ${hours}h ${minutes}m`);
      } else {
        setCountdown(`${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [nextRaid]);

  // Filter raids based on active tab
  const filteredRaids = raids.filter(raid => {
    if (activeTab === 'open') return raid.status === 'open';
    if (activeTab === 'locked') return raid.status === 'locked';
    if (activeTab === 'history') return raid.status === 'closed' || raid.status === 'completed';
    return true;
  });

  // Fetch activities from API
  const fetchActivities = useCallback(async () => {
    if (!guild?.id) return;

    try {
      const response = await fetch(`/api/guilds/${guild.id}/activity?limit=15&hours=48`);
      const json = await response.json();

      if (json.success) {
        setActivities(json.data.activities);
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    } finally {
      setLoadingActivities(false);
    }
  }, [guild?.id]);

  // Initialize WebSocket connection
  useEffect(() => {
    if (!guild?.id) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    let reconnectAttempts = 0;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let pingInterval: NodeJS.Timeout | null = null;

    const connect = () => {
      setWsStatus('connecting');

      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setWsStatus('connected');
        reconnectAttempts = 0;

        pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'pong' || data.type === 'connection:established') {
            return;
          }

          if (data.type === 'activity:new' && data.guild_id === guild.id) {
            setActivities(prev => [{
              id: `ws_${Date.now()}`,
              type: data.data.activity_type,
              icon: getIconForType(data.data.activity_type),
              description: data.data.description,
              timestamp: data.timestamp,
              user_name: data.data.user_name,
              metadata: data.data.metadata,
            }, ...prev].slice(0, 20));
          }

          if (data.type?.startsWith('raid:') && data.guild_id === guild.id) {
            fetchActivities();
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      socket.onclose = (event) => {
        if (pingInterval) {
          clearInterval(pingInterval);
          pingInterval = null;
        }

        if (event.code === 4001) {
          setWsStatus('error');
          return;
        }

        setWsStatus('disconnected');

        if (reconnectAttempts < 5) {
          reconnectAttempts++;
          reconnectTimeout = setTimeout(connect, 3000 * reconnectAttempts);
        }
      };

      socket.onerror = () => {
        setWsStatus('error');
      };

      setWs(socket);
    };

    connect();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (pingInterval) clearInterval(pingInterval);
      if (ws) ws.close(1000, 'Component unmount');
    };
  }, [guild?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

  // Calculate stats
  const totalSlots = raids.reduce((acc, r) => {
    const counts = r.counts;
    return acc + parseInt(counts.tank.split('/')[1] || '0') +
           parseInt(counts.healer.split('/')[1] || '0') +
           parseInt(counts.dps.split('/')[1] || '0');
  }, 0);

  const filledSlots = raids.reduce((acc, r) => {
    const counts = r.counts;
    return acc + parseInt(counts.tank.split('/')[0] || '0') +
           parseInt(counts.healer.split('/')[0] || '0') +
           parseInt(counts.dps.split('/')[0] || '0');
  }, 0);

  return (
    <div className="max-w-[1400px] mx-auto space-y-6">
      {/* Hero Banner with Next Raid */}
      <HeroBanner
        nextRaid={nextRaid}
        countdown={countdown}
        guildId={guild?.id}
      />

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <QuickStat
          icon={Swords}
          label={t('dashboard.active_raids')}
          value={raids.filter(r => r.status === 'open').length.toString()}
          color="primary"
        />
        <QuickStat
          icon={Users}
          label="Total Signups"
          value={`${filledSlots}/${totalSlots}`}
          color="secondary"
        />
        <QuickStat
          icon={Timer}
          label="Open Slots"
          value={raids.reduce((acc, r) => acc + r.open_slots, 0).toString()}
          color="success"
        />
        <QuickStat
          icon={TrendingUp}
          label="This Week"
          value={raids.length.toString()}
          subtext="raids"
          color="info"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* LEFT: Raid Board */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {/* Filter Tabs */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h2 className="text-xl md:text-2xl font-heading font-bold text-white tracking-wide flex items-center gap-3">
              <Swords className="h-6 w-6 text-[var(--primary)]" />
              {t('dashboard.live_raids')}
            </h2>
            <div className="flex bg-[var(--surface-0)] rounded-xl p-1 border border-[var(--border)]">
              <FilterTab
                active={activeTab === 'open'}
                onClick={() => setActiveTab('open')}
                count={raids.filter(r => r.status === 'open').length}
              >
                {t('status.open')}
              </FilterTab>
              <FilterTab
                active={activeTab === 'locked'}
                onClick={() => setActiveTab('locked')}
                count={raids.filter(r => r.status === 'locked').length}
              >
                {t('status.locked')}
              </FilterTab>
              <FilterTab
                active={activeTab === 'history'}
                onClick={() => setActiveTab('history')}
              >
                History
              </FilterTab>
            </div>
          </div>

          {/* Raid Cards */}
          {filteredRaids.length === 0 ? (
            <EmptyState activeTab={activeTab} guildId={guild?.id} />
          ) : (
            <div className="space-y-4">
              {filteredRaids.map((raid, index) => (
                <RaidCard
                  key={raid.id}
                  raid={raid}
                  guildId={guild?.id}
                  index={index}
                />
              ))}
            </div>
          )}
        </div>

        {/* RIGHT: Sidebar */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Quick Actions */}
          <div className="panel-glass p-0 overflow-hidden">
            <div className="bg-[var(--surface-2)] px-4 py-3 border-b border-[var(--border)]">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)] flex items-center gap-2">
                <Zap className="h-4 w-4 text-[var(--primary)]" />
                Quick Actions
              </span>
            </div>
            <div className="p-2 relative z-10">
              <a
                href={`/guilds/${guild?.id}/raids/new`}
                className="flex items-center gap-3 w-full p-3 hover:bg-[var(--bg-1)] rounded-lg transition-colors text-sm font-medium text-[var(--text)] text-left group"
              >
                <div className="w-10 h-10 rounded-lg bg-[var(--primary)]/15 flex items-center justify-center text-[var(--primary)] group-hover:bg-[var(--primary)] group-hover:text-black transition-all">
                  <Plus className="h-5 w-5" />
                </div>
                <div>
                  <span className="block font-bold">{t('actions.create_raid')}</span>
                  <span className="text-xs text-[var(--muted)]">From template</span>
                </div>
              </a>
              <button className="flex items-center gap-3 w-full p-3 hover:bg-[var(--bg-1)] rounded-lg transition-colors text-sm font-medium text-[var(--text)] text-left group">
                <div className="w-10 h-10 rounded-lg bg-[var(--success)]/15 flex items-center justify-center text-[var(--success)] group-hover:bg-[var(--success)] group-hover:text-black transition-all">
                  <CheckCircle className="h-5 w-5" />
                </div>
                <div>
                  <span className="block font-bold">{t('dashboard.check_in')}</span>
                  <span className="text-xs text-[var(--muted)]">Quick attendance</span>
                </div>
              </button>
            </div>
          </div>

          {/* Activity Feed */}
          <div className="panel-glass p-0 overflow-hidden">
            <div className="bg-[var(--surface-2)] px-4 py-3 border-b border-[var(--border)] flex justify-between items-center relative z-10">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)] flex items-center gap-2">
                <Activity className="h-4 w-4 text-[var(--secondary)]" />
                {t('dashboard.activity_feed')}
              </span>
              <ConnectionIndicator status={wsStatus} />
            </div>
            <div className="p-4 space-y-3 max-h-[400px] overflow-y-auto scrollbar-thin relative z-10">
              {loadingActivities ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-[var(--secondary)]" />
                </div>
              ) : activities.length > 0 ? (
                activities.map((activity, index) => (
                  <ActivityItem
                    key={activity.id}
                    activity={activity}
                    index={index}
                  />
                ))
              ) : (
                <div className="text-center py-8 text-[var(--muted)] text-sm">
                  No recent activity
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Hero Banner Component
const HeroBanner: React.FC<{
  nextRaid: Raid | null;
  countdown: string;
  guildId: string;
}> = ({ nextRaid, countdown, guildId }) => {
  const { t } = useTranslation();

  return (
    <div className="panel-gradient relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-r from-[var(--primary)]/10 via-transparent to-[var(--secondary)]/10" />
      <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--primary)]/10 rounded-full blur-3xl -mr-32 -mt-32" />

      <div className="relative p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          {/* Left: Next Raid Info */}
          <div className="flex-1">
            <div className="flex items-center gap-2 text-[var(--primary)] mb-2">
              <Clock className="h-4 w-4" />
              <span className="text-xs font-bold uppercase tracking-widest">{t('dashboard.next_raid')}</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-heading font-bold text-white mb-2">
              {nextRaid ? nextRaid.title : 'No Raids Scheduled'}
            </h2>
            {nextRaid && (
              <div className="flex flex-wrap items-center gap-4 text-sm text-[var(--muted)]">
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-4 w-4" />
                  {nextRaid.raid_date}
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock className="h-4 w-4" />
                  {nextRaid.raid_time}
                </span>
                <span className="badge badge-info">{nextRaid.game} / {nextRaid.mode}</span>
              </div>
            )}
          </div>

          {/* Right: Countdown */}
          <div className="text-center md:text-right">
            <div className="text-xs font-bold uppercase tracking-widest text-[var(--muted)] mb-2">
              T-Minus
            </div>
            <div className={cn(
              "text-4xl md:text-5xl font-mono font-bold tracking-tight",
              countdown === 'LIVE NOW' ? "text-[var(--success)] animate-pulse" : "text-white"
            )}>
              {countdown}
            </div>
            {nextRaid && (
              <a
                href={`/guilds/${guildId}/raids/${nextRaid.id}/edit`}
                className="inline-flex items-center gap-2 mt-4 text-sm font-bold text-[var(--primary)] hover:text-[var(--primary-light)] transition-colors"
              >
                View Details
                <span className="text-lg">&rarr;</span>
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Quick Stat Component
const QuickStat: React.FC<{
  icon: React.ElementType;
  label: string;
  value: string;
  subtext?: string;
  color: 'primary' | 'secondary' | 'success' | 'info';
}> = ({ icon: Icon, label, value, subtext, color }) => {
  const colorClasses = {
    primary: 'stat-icon-primary',
    secondary: 'stat-icon-secondary',
    success: 'stat-icon-success',
    info: 'stat-icon-info',
  };

  return (
    <div className="stat-card">
      <div className={cn("stat-icon", colorClasses[color])}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="relative z-10">
        <p className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</p>
        <p className="text-xl font-bold text-white">
          {value}
          {subtext && <span className="text-sm font-normal text-[var(--muted)] ml-1">{subtext}</span>}
        </p>
      </div>
    </div>
  );
};

// Filter Tab Component
const FilterTab: React.FC<{
  active: boolean;
  onClick: () => void;
  count?: number;
  children: React.ReactNode;
}> = ({ active, onClick, count, children }) => (
  <button
    onClick={onClick}
    className={cn(
      "px-4 py-2 text-xs font-bold uppercase tracking-wide rounded-lg transition-all",
      active
        ? "bg-[var(--primary)] text-black shadow-lg"
        : "text-[var(--muted)] hover:text-white hover:bg-[var(--surface-2)]"
    )}
  >
    {children}
    {count !== undefined && count > 0 && (
      <span className={cn(
        "ml-1.5 px-1.5 py-0.5 rounded text-[10px]",
        active ? "bg-black/20" : "bg-[var(--surface-2)]"
      )}>
        {count}
      </span>
    )}
  </button>
);

// Empty State Component
const EmptyState: React.FC<{ activeTab: FilterTab; guildId: string }> = ({ activeTab, guildId }) => {
  const { t } = useTranslation();

  const messages = {
    open: { title: 'No Active Operations', desc: 'Initialize a new raid to begin planning.', showCta: true },
    locked: { title: 'No Locked Raids', desc: 'Locked raids will appear here.', showCta: false },
    history: { title: 'No Raid History', desc: 'Completed raids will appear here.', showCta: false },
  };

  const { title, desc, showCta } = messages[activeTab];

  return (
    <div className="panel-glass p-12 md:p-16 flex flex-col items-center justify-center text-center border-dashed relative">
      <div className="w-20 h-20 bg-[var(--bg-1)] rounded-2xl flex items-center justify-center mb-6 relative z-10">
        <Swords className="h-10 w-10 text-[var(--muted)]" />
      </div>
      <h3 className="text-xl font-bold text-white mb-2 relative z-10">{title}</h3>
      <p className="text-[var(--muted)] text-sm mb-6 max-w-sm relative z-10">{desc}</p>
      {showCta && (
        <a
          href={`/guilds/${guildId}/raids/new`}
          className="btn-primary relative z-10"
        >
          <Plus className="h-4 w-4" />
          {t('actions.create_raid')}
        </a>
      )}
    </div>
  );
};

// Raid Card Component
const RaidCard: React.FC<{
  raid: Raid;
  guildId: string;
  index: number;
}> = ({ raid, guildId, index }) => {
  const { t } = useTranslation();

  const statusConfig = {
    open: { color: 'border-[var(--success)]', bg: 'bg-[var(--success)]', label: t('status.open'), badge: 'badge-open' },
    locked: { color: 'border-[var(--danger)]', bg: 'bg-[var(--danger)]', label: t('status.locked'), badge: 'badge-locked' },
    closed: { color: 'border-[var(--muted)]', bg: 'bg-[var(--muted)]', label: t('status.closed'), badge: '' },
  };

  const config = statusConfig[raid.status as keyof typeof statusConfig] || statusConfig.closed;

  // Calculate fill percentage
  const getTotalFilled = () => {
    const counts = raid.counts;
    const filled = parseInt(counts.tank.split('/')[0] || '0') +
                   parseInt(counts.healer.split('/')[0] || '0') +
                   parseInt(counts.dps.split('/')[0] || '0');
    const total = parseInt(counts.tank.split('/')[1] || '0') +
                  parseInt(counts.healer.split('/')[1] || '0') +
                  parseInt(counts.dps.split('/')[1] || '0');
    return { filled, total, percent: total > 0 ? (filled / total) * 100 : 0 };
  };

  const { filled, total, percent } = getTotalFilled();

  return (
    <a
      href={`/guilds/${guildId}/raids/${raid.id}/edit`}
      className="block group"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="panel-glass panel-hover relative">
        {/* Status indicator line */}
        <div className={cn("absolute left-0 top-0 bottom-0 w-1 rounded-l-2xl", config.bg)} />

        <div className="p-5 pl-6 relative z-10">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Left: Info */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className={cn("badge", config.badge)}>{config.label}</span>
                <span className="text-[10px] font-mono font-bold text-[var(--muted)] uppercase">
                  {raid.game} // {raid.mode}
                </span>
              </div>
              <h3 className="text-lg font-bold text-white group-hover:text-[var(--primary)] transition-colors truncate">
                {raid.title}
              </h3>
              <div className="flex flex-wrap items-center gap-4 mt-2 text-xs font-medium text-[var(--muted)]">
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" />
                  {raid.raid_date}
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  {raid.raid_time}
                </span>
              </div>
            </div>

            {/* Middle: Progress */}
            <div className="flex-shrink-0 w-full lg:w-40">
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-[var(--muted)]">Roster</span>
                <span className="font-bold text-white">{filled}/{total}</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill progress-fill-primary"
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>

            {/* Right: Role chips */}
            <div className="flex gap-2 flex-shrink-0">
              <RoleChip count={raid.counts.tank} role="tank" icon={Shield} />
              <RoleChip count={raid.counts.healer} role="healer" icon={Heart} />
              <RoleChip count={raid.counts.dps} role="dps" icon={Sword} />
              {raid.counts.bench && parseInt(raid.counts.bench.split('/')[1] || '0') > 0 && (
                <RoleChip count={raid.counts.bench} role="bench" icon={Users} />
              )}
            </div>

            {/* More options */}
            <button
              className="hidden lg:flex btn-icon opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={(e) => e.preventDefault()}
            >
              <MoreHorizontal className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </a>
  );
};

// Role Chip Component
const RoleChip: React.FC<{
  count: string;
  role: string;
  icon: React.ElementType;
}> = ({ count, role, icon: Icon }) => {
  const [curr, max] = count.split('/').map(Number);
  const isFull = max > 0 && curr >= max;

  const roleColors = {
    tank: 'border-blue-500/40 text-blue-400 bg-blue-500/10',
    healer: 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10',
    dps: 'border-orange-500/40 text-orange-400 bg-orange-500/10',
    bench: 'border-violet-500/40 text-violet-400 bg-violet-500/10',
  };

  return (
    <div className={cn(
      "flex flex-col items-center justify-center w-12 h-12 rounded-xl border transition-all",
      roleColors[role as keyof typeof roleColors],
      isFull && "opacity-50"
    )}>
      <Icon className="h-3.5 w-3.5 mb-0.5" />
      <span className="text-[10px] font-mono font-bold leading-none">{curr}/{max}</span>
    </div>
  );
};

// Activity Item Component
const ActivityItem: React.FC<{
  activity: ActivityEvent;
  index: number;
}> = ({ activity, index }) => {
  const iconConfig: Record<string, { icon: React.ElementType; color: string }> = {
    join: { icon: UserPlus, color: 'text-[var(--success)]' },
    signup: { icon: UserPlus, color: 'text-[var(--success)]' },
    create: { icon: Plus, color: 'text-[var(--primary)]' },
    lock: { icon: Lock, color: 'text-[var(--danger)]' },
    close: { icon: XCircle, color: 'text-[var(--warning)]' },
    edit: { icon: Edit, color: 'text-[var(--secondary)]' },
    system: { icon: Activity, color: 'text-[var(--muted)]' },
  };

  const getConfig = () => {
    for (const [key, config] of Object.entries(iconConfig)) {
      if (activity.type.includes(key)) return config;
    }
    return iconConfig.system;
  };

  const { icon: Icon, color } = getConfig();

  return (
    <div
      className="flex gap-3 items-start group cursor-default fade-in"
      style={{ animationDelay: `${index * 30}ms` }}
    >
      <div className={cn("mt-1 p-1.5 rounded-lg bg-[var(--bg-0)]", color)}>
        <Icon className="h-3 w-3" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] font-mono text-[var(--muted)] mb-0.5">
          {formatTime(activity.timestamp)}
        </div>
        <div className="text-sm font-medium text-[var(--text)] group-hover:text-white transition-colors line-clamp-2">
          {activity.description}
        </div>
      </div>
    </div>
  );
};

// Connection Indicator Component
const ConnectionIndicator: React.FC<{ status: WSStatus }> = ({ status }) => {
  const config: Record<WSStatus, { color: string; icon: typeof Wifi; label: string }> = {
    connected: { color: 'bg-[var(--success)]', icon: Wifi, label: 'Live' },
    connecting: { color: 'bg-[var(--warning)] animate-pulse', icon: Wifi, label: 'Connecting' },
    disconnected: { color: 'bg-[var(--muted)]', icon: WifiOff, label: 'Offline' },
    error: { color: 'bg-[var(--danger)]', icon: WifiOff, label: 'Error' },
  };

  const { color, icon: Icon, label } = config[status];

  return (
    <div className="flex items-center gap-1.5" title={`WebSocket: ${status}`}>
      <span className={cn("w-2 h-2 rounded-full", color)} />
      <Icon className="h-3 w-3 text-[var(--muted)]" />
    </div>
  );
};

// Helper functions
function getIconForType(type: string): string {
  const iconMap: Record<string, string> = {
    raid_created: 'plus-circle',
    raid_updated: 'edit',
    raid_closed: 'check-circle',
    raid_locked: 'lock',
    raid_signup: 'user-plus',
  };
  return iconMap[type] || 'activity';
}

function formatTime(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' });
  } catch {
    return timestamp;
  }
}

export default Dashboard;
