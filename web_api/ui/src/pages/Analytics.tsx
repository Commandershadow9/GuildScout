import React from 'react';
import { useTranslation } from 'react-i18next';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Download, Users, MessageSquare, Mic } from 'lucide-react';
import { cn } from '@/lib/utils';

// Mock Data for Prototype
const activityData = [
  { time: '00:00', messages: 12, voice: 2 },
  { time: '04:00', messages: 5, voice: 0 },
  { time: '08:00', messages: 45, voice: 12 },
  { time: '12:00', messages: 120, voice: 45 },
  { time: '16:00', messages: 85, voice: 30 },
  { time: '20:00', messages: 210, voice: 85 },
  { time: '23:59', messages: 150, voice: 60 },
];

const rankingData = [
  { name: 'CmdShadow', score: 9850, msg: 1240, voice: 45 },
  { name: 'RaidLead_X', score: 8400, msg: 890, voice: 82 },
  { name: 'HealBot', score: 7200, msg: 1500, voice: 10 },
  { name: 'TankTop', score: 6500, msg: 450, voice: 120 },
  { name: 'DPS_Dave', score: 5100, msg: 600, voice: 20 },
];

interface AnalyticsProps {
  data: {
    guild: any;
  };
}

const Analytics: React.FC<AnalyticsProps> = ({ data }) => {
  const { t } = useTranslation();

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight text-white">{t('analytics.title')}</h1>
          <p className="text-[var(--muted)] mt-1">{t('analytics.subtitle')}</p>
        </div>
        <button className="flex items-center gap-2 bg-[var(--surface-2)] text-white px-4 py-2 rounded-lg font-bold border border-[var(--border)] hover:bg-[var(--bg-1)] transition-all uppercase text-sm">
          <Download className="h-4 w-4" />
          {t('analytics.export_csv')}
        </button>
      </div>

      {/* Main Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 panel-glass p-6">
            <h3 className="font-bold text-lg mb-6 flex items-center gap-2 text-white">
                <MessageSquare className="h-5 w-5 text-[var(--primary)]" />
                {t('analytics.messages_per_minute')}
            </h3>
            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={activityData}>
                        <defs>
                            <linearGradient id="colorMsg" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                        <XAxis dataKey="time" stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border)', borderRadius: '8px', color: 'white' }}
                            itemStyle={{ color: 'var(--primary)' }}
                        />
                        <Area type="monotone" dataKey="messages" stroke="var(--primary)" strokeWidth={2} fillOpacity={1} fill="url(#colorMsg)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>

        <div className="lg:col-span-1 panel-glass p-6">
            <h3 className="font-bold text-lg mb-6 flex items-center gap-2 text-white">
                <Mic className="h-5 w-5 text-[var(--secondary)]" />
                {t('analytics.voice_activity')}
            </h3>
            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={activityData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                        <XAxis dataKey="time" stroke="var(--muted)" fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip 
                            cursor={{fill: 'rgba(255,255,255,0.05)'}}
                            contentStyle={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border)', borderRadius: '8px', color: 'white' }}
                        />
                        <Bar dataKey="voice" fill="var(--secondary)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
      </div>

      {/* Ranking Table */}
      <div className="panel-glass p-0 overflow-hidden">
         <div className="p-6 border-b border-[var(--border)] bg-[var(--surface-2)]">
            <h3 className="font-bold text-lg flex items-center gap-2 text-white">
                <Users className="h-5 w-5 text-[var(--warning)]" />
                {t('analytics.member_ranking')}
            </h3>
         </div>
         <div className="w-full overflow-x-auto">
            <table className="w-full text-sm text-left">
                <thead className="bg-[var(--bg-1)] text-[var(--muted)] uppercase text-xs font-bold">
                    <tr>
                        <th className="px-6 py-4">Rank</th>
                        <th className="px-6 py-4">User</th>
                        <th className="px-6 py-4 text-right">{t('analytics.score')}</th>
                        <th className="px-6 py-4 text-right">{t('analytics.messages')}</th>
                        <th className="px-6 py-4 text-right">{t('analytics.voice')} (h)</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                    {rankingData.map((user, idx) => (
                        <tr key={user.name} className="hover:bg-[var(--bg-1)] transition-colors">
                            <td className="px-6 py-4 font-mono font-bold text-[var(--muted)]">#{idx + 1}</td>
                            <td className="px-6 py-4 font-bold text-white">{user.name}</td>
                            <td className="px-6 py-4 text-right font-mono text-[var(--primary)]">{user.score.toLocaleString()}</td>
                            <td className="px-6 py-4 text-right text-[var(--muted)]">{user.msg.toLocaleString()}</td>
                            <td className="px-6 py-4 text-right text-[var(--muted)]">{user.voice}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
         </div>
      </div>
    </div>
  );
};

export default Analytics;