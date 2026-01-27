import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Download, Users, MessageSquare, Mic, Loader2, AlertCircle, Trophy, Clock, Hash, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RankingEntry {
  rank: number;
  user_id: string;
  display_name: string;
  final_score: number;
  days_score: number;
  message_score: number;
  voice_score: number;
  message_count: number;
  voice_minutes: number;
  days_in_server: number;
}

interface DailyActivity {
  date: string;
  messages: number;
}

interface HourlyActivity {
  hour: number;
  messages: number;
}

interface Stats {
  total_messages: number;
  active_users: number;
  total_members: number;
  total_voice_hours: number;
  total_channels: number;
}

interface AnalyticsData {
  rankings: RankingEntry[];
  total: number;
  weights?: {
    days: number;
    messages: number;
    voice: number;
  };
}

interface OverviewData {
  daily_activity: DailyActivity[];
  hourly_activity: HourlyActivity[];
  stats: Stats;
}

interface AnalyticsProps {
  data: {
    guild: { id: string; name: string };  // String for JavaScript BigInt safety
  };
}

const Analytics: React.FC<AnalyticsProps> = ({ data }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rankings, setRankings] = useState<AnalyticsData | null>(null);
  const [overview, setOverview] = useState<OverviewData | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch rankings and overview in parallel
        const [rankingsRes, overviewRes] = await Promise.all([
          fetch(`/api/guilds/${data.guild.id}/analytics/rankings?limit=50`),
          fetch(`/api/guilds/${data.guild.id}/analytics/overview?days=14`)
        ]);

        const rankingsJson = await rankingsRes.json();
        const overviewJson = await overviewRes.json();

        if (rankingsJson.success) {
          setRankings(rankingsJson.data);
        } else {
          throw new Error(rankingsJson.error || 'Failed to load rankings');
        }

        if (overviewJson.success) {
          setOverview(overviewJson.data);
        } else {
          throw new Error(overviewJson.error || 'Failed to load overview');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [data.guild.id]);

  const handleExport = () => {
    if (!rankings) return;

    // Create CSV content
    const headers = ['Rank', 'User', 'Score', 'Messages', 'Voice (min)', 'Days'];
    const rows = rankings.rankings.map(r => [
      r.rank,
      r.display_name,
      r.final_score,
      r.message_count,
      r.voice_minutes,
      r.days_in_server
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `guildscout_rankings_${data.guild.name}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--primary)] mx-auto mb-4" />
          <p className="text-[var(--muted)]">{t('analytics.loading')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="h-8 w-8 text-[var(--danger)] mx-auto mb-4" />
          <p className="text-[var(--danger)] font-bold mb-2">Error Loading Data</p>
          <p className="text-[var(--muted)]">{error}</p>
        </div>
      </div>
    );
  }

  const stats = overview?.stats;
  const dailyData = overview?.daily_activity || [];
  const hourlyData = overview?.hourly_activity || [];
  const rankingList = rankings?.rankings || [];

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2 text-[var(--secondary)] mb-3">
            <BarChart3 className="h-5 w-5" />
            <span className="text-xs font-bold uppercase tracking-widest">{t('analytics.title')}</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-heading font-black text-white tracking-tight">{t('analytics.title')}</h1>
          <p className="text-[var(--muted)] mt-2 max-w-xl">{t('analytics.subtitle')}</p>
        </div>
        <button
          onClick={handleExport}
          disabled={!rankings}
          className="btn-ghost self-start md:self-auto disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          {t('analytics.export_csv')}
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={MessageSquare}
            label="Total Messages"
            value={stats.total_messages.toLocaleString()}
            color="primary"
          />
          <StatCard
            icon={Users}
            label="Active Users"
            value={stats.active_users.toLocaleString()}
            color="success"
          />
          <StatCard
            icon={Mic}
            label="Voice Hours"
            value={stats.total_voice_hours.toLocaleString()}
            color="secondary"
          />
          <StatCard
            icon={Hash}
            label="Channels"
            value={stats.total_channels.toLocaleString()}
            color="warning"
          />
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 panel-glass p-6">
          <h3 className="font-bold text-lg mb-6 flex items-center gap-2 text-white">
            <MessageSquare className="h-5 w-5 text-[var(--primary)]" />
            {t('analytics.messages_per_minute')}
          </h3>
          <div className="h-[300px] w-full">
            {dailyData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dailyData}>
                  <defs>
                    <linearGradient id="colorMsg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    stroke="var(--muted)"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => {
                      const date = new Date(value);
                      return `${date.getDate()}.${date.getMonth() + 1}`;
                    }}
                  />
                  <YAxis stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border)', borderRadius: '8px', color: 'white' }}
                    labelFormatter={(value) => `Date: ${value}`}
                  />
                  <Area type="monotone" dataKey="messages" stroke="var(--primary)" strokeWidth={2} fillOpacity={1} fill="url(#colorMsg)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-[var(--muted)]">
                No activity data available
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-1 panel-glass p-6">
          <h3 className="font-bold text-lg mb-6 flex items-center gap-2 text-white">
            <Clock className="h-5 w-5 text-[var(--secondary)]" />
            Hourly Activity
          </h3>
          <div className="h-[300px] w-full">
            {hourlyData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourlyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                  <XAxis
                    dataKey="hour"
                    stroke="var(--muted)"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${value}h`}
                  />
                  <Tooltip
                    cursor={{fill: 'rgba(255,255,255,0.05)'}}
                    contentStyle={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border)', borderRadius: '8px', color: 'white' }}
                    labelFormatter={(value) => `${value}:00 - ${value}:59`}
                  />
                  <Bar dataKey="messages" fill="var(--secondary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-[var(--muted)]">
                No hourly data available
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Ranking Table */}
      <div className="panel-glass p-0 overflow-hidden">
        <div className="p-4 md:p-6 border-b border-[var(--border)] bg-[var(--surface-2)] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <h3 className="font-bold text-base md:text-lg flex items-center gap-2 text-white">
            <Trophy className="h-5 w-5 text-[var(--warning)]" />
            {t('analytics.member_ranking')}
          </h3>
          {rankings && (
            <span className="text-xs sm:text-sm text-[var(--muted)]">
              {rankingList.length} / {rankings.total} members
            </span>
          )}
        </div>
        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-1)] text-[var(--muted)] uppercase text-xs font-bold">
              <tr>
                <th className="px-3 md:px-6 py-3 md:py-4"><span className="hidden sm:inline">Rank</span><span className="sm:hidden">#</span></th>
                <th className="px-3 md:px-6 py-3 md:py-4">User</th>
                <th className="px-3 md:px-6 py-3 md:py-4 text-right">{t('analytics.score')}</th>
                <th className="hidden md:table-cell px-6 py-4 text-right">{t('analytics.messages')}</th>
                <th className="hidden lg:table-cell px-6 py-4 text-right">{t('analytics.voice')} (min)</th>
                <th className="hidden sm:table-cell px-6 py-4 text-right">Days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {rankingList.length > 0 ? (
                rankingList.map((user) => (
                  <tr key={user.user_id} className="hover:bg-[var(--bg-1)] transition-colors">
                    <td className="px-3 md:px-6 py-3 md:py-4">
                      <span className={cn(
                        "font-mono font-bold text-sm",
                        user.rank === 1 && "text-yellow-400",
                        user.rank === 2 && "text-gray-300",
                        user.rank === 3 && "text-amber-600",
                        user.rank > 3 && "text-[var(--muted)]"
                      )}>
                        {user.rank === 1 && "🥇 "}
                        {user.rank === 2 && "🥈 "}
                        {user.rank === 3 && "🥉 "}
                        #{user.rank}
                      </span>
                    </td>
                    <td className="px-3 md:px-6 py-3 md:py-4 font-bold text-white text-sm truncate max-w-[100px] md:max-w-none">{user.display_name}</td>
                    <td className="px-3 md:px-6 py-3 md:py-4 text-right">
                      <span className="font-mono text-[var(--primary)] font-bold text-sm">
                        {user.final_score.toFixed(1)}
                      </span>
                    </td>
                    <td className="hidden md:table-cell px-6 py-4 text-right text-[var(--muted)] text-sm">
                      {user.message_count.toLocaleString()}
                    </td>
                    <td className="hidden lg:table-cell px-6 py-4 text-right text-[var(--muted)] text-sm">
                      {user.voice_minutes.toLocaleString()}
                    </td>
                    <td className="hidden sm:table-cell px-6 py-4 text-right text-[var(--muted)] text-sm">
                      {user.days_in_server}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-[var(--muted)]">
                    No ranking data available. Make sure the bot has imported message history.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Scoring Weights Info */}
      {rankings?.weights && (
        <div className="panel-glass p-4">
          <p className="text-sm text-[var(--muted)]">
            <strong>Scoring Formula:</strong>{' '}
            Days ({(rankings.weights.days * 100).toFixed(0)}%) +
            Messages ({(rankings.weights.messages * 100).toFixed(0)}%) +
            Voice ({(rankings.weights.voice * 100).toFixed(0)}%)
          </p>
        </div>
      )}
    </div>
  );
};

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: string;
  color: 'primary' | 'success' | 'secondary' | 'warning';
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, label, value, color }) => {
  const colorClasses = {
    primary: 'stat-icon-primary',
    success: 'stat-icon-success',
    secondary: 'stat-icon-secondary',
    warning: 'stat-icon-primary', // Uses primary (gold/amber) for warning
  };

  return (
    <div className="stat-card">
      <div className={cn("stat-icon", colorClasses[color])}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="relative z-10">
        <p className="text-xs text-[var(--muted)] uppercase tracking-wide">{label}</p>
        <p className="text-xl font-bold text-white">{value}</p>
      </div>
    </div>
  );
};

export default Analytics;
