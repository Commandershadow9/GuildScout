import React from 'react';
import { useTranslation } from 'react-i18next';
import { Clock, CheckCircle, Activity, Calendar, Sword, Shield, Heart, Plus, Lock, Unlock, AlertTriangle, Users, Copy, MoreHorizontal } from 'lucide-react';
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

interface DashboardProps {
  data: {
    raids: Raid[];
    health: any;
    guild: any;
    settings: any;
  };
}

const Dashboard: React.FC<DashboardProps> = ({ data }) => {
  const { t } = useTranslation();
  const { raids } = data;

  const nextRaid = raids.length > 0 ? raids[0] : null;

  return (
    <div className="max-w-[1400px] mx-auto grid grid-cols-12 gap-8">
      {/* LEFT COLUMN: LIVE BOARD (8 cols) */}
      <div className="col-span-12 lg:col-span-8 space-y-6">
        <div className="flex items-center justify-between">
            <h2 className="text-2xl font-heading font-bold text-white tracking-wide">Live Board</h2>
            <div className="flex bg-[var(--surface-0)] rounded-lg p-1 border border-[var(--border)]">
                <button className="px-4 py-1 text-xs font-bold bg-[var(--surface-2)] text-white rounded shadow-sm">OPEN</button>
                <button className="px-4 py-1 text-xs font-bold text-[var(--muted)] hover:text-white transition-colors">LOCKED</button>
                <button className="px-4 py-1 text-xs font-bold text-[var(--muted)] hover:text-white transition-colors">HISTORY</button>
            </div>
        </div>

        {raids.length === 0 ? (
            <div className="panel-glass p-16 flex flex-col items-center justify-center text-center border-dashed border-[var(--border)]">
                <div className="w-16 h-16 bg-[var(--bg-1)] rounded-full flex items-center justify-center mb-4">
                    <Calendar className="h-8 w-8 text-[var(--muted)]" />
                </div>
                <h3 className="text-lg font-bold text-white mb-1">No Active Operations</h3>
                <p className="text-[var(--muted)] text-sm mb-6">Initialize a new raid to begin planning.</p>
                <a href={`/guilds/${data.guild?.id}/raids/new`} className="px-6 py-2 bg-[var(--primary)] text-black font-bold text-sm rounded hover:bg-[var(--primary)]/90 transition-colors uppercase tracking-wide">
                    Initialize Raid
                </a>
            </div>
        ) : (
            <div className="space-y-4">
                {raids.map((raid) => (
                    <RaidCard key={raid.id} raid={raid} guildId={data.guild?.id} />
                ))}
            </div>
        )}
      </div>

      {/* RIGHT COLUMN: OPERATIONS PANEL (4 cols) */}
      <div className="col-span-12 lg:col-span-4 space-y-6">
        
        {/* Next Raid Countdown */}
        <div className="panel-glass p-6 relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-1 h-full bg-[var(--warning)]" />
            <div className="flex justify-between items-start mb-4">
                <div>
                    <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)] mb-1">Next Operation</div>
                    <div className="text-xl font-bold text-white truncate max-w-[200px]">{nextRaid ? nextRaid.title : "No Ops Scheduled"}</div>
                </div>
                <div className="w-8 h-8 rounded bg-[var(--warning)]/10 flex items-center justify-center text-[var(--warning)]">
                    <Clock className="h-4 w-4" />
                </div>
            </div>
            {nextRaid ? (
                <div className="text-4xl font-mono font-bold text-white tracking-tight mb-2">
                    {nextRaid.raid_time}
                </div>
            ) : (
                <div className="text-4xl font-mono font-bold text-[var(--muted)]/30 tracking-tight mb-2">
                    --:--
                </div>
            )}
            <div className="flex items-center gap-2 text-xs font-bold text-[var(--muted)]">
                <span className="text-[var(--warning)]">T-MINUS</span>
                <span>{nextRaid ? nextRaid.raid_date : "STANDBY"}</span>
            </div>
        </div>

        {/* Quick Actions */}
        <div className="panel-glass p-0 overflow-hidden">
            <div className="bg-[var(--surface-2)] px-4 py-3 border-b border-[var(--border)] text-xs font-bold uppercase tracking-wider text-[var(--muted)]">
                Quick Actions
            </div>
            <div className="p-2">
                <a href={`/guilds/${data.guild?.id}/raids/new`} className="flex items-center gap-3 w-full p-3 hover:bg-[var(--bg-1)] rounded transition-colors text-sm font-medium text-[var(--text)] text-left group">
                    <div className="w-8 h-8 rounded bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)] group-hover:bg-[var(--primary)] group-hover:text-black transition-colors">
                        <Plus className="h-4 w-4" />
                    </div>
                    <span>Create from Template</span>
                </a>
                <button className="flex items-center gap-3 w-full p-3 hover:bg-[var(--bg-1)] rounded transition-colors text-sm font-medium text-[var(--text)] text-left group">
                    <div className="w-8 h-8 rounded bg-[var(--success)]/10 flex items-center justify-center text-[var(--success)] group-hover:bg-[var(--success)] group-hover:text-black transition-colors">
                        <CheckCircle className="h-4 w-4" />
                    </div>
                    <span>Open Check-in</span>
                </button>
            </div>
        </div>

        {/* Activity Feed */}
        <div className="panel-glass p-0 overflow-hidden">
            <div className="bg-[var(--surface-2)] px-4 py-3 border-b border-[var(--border)] flex justify-between items-center">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Log</span>
                <div className="w-2 h-2 rounded-full bg-[var(--success)] animate-pulse" />
            </div>
            <div className="p-4 space-y-4 max-h-[300px] overflow-y-auto">
                <ActivityItem text="Raid 'Molten Core' created" time="09:42" type="create" />
                <ActivityItem text="User joined 'Onyxia'" time="09:30" type="join" />
                <ActivityItem text="System check complete" time="09:00" type="system" />
                <ActivityItem text="Raid 'BWL' locked" time="08:15" type="lock" />
            </div>
        </div>

      </div>
    </div>
  );
};

const RaidCard = ({ raid, guildId }: { raid: Raid, guildId: number }) => {
    const { t } = useTranslation();
    
    // Status Logic
    let statusColor = "text-[var(--muted)] border-[var(--muted)]/30";
    let statusBg = "bg-[var(--muted)]/10";
    let statusLabel = "UNKNOWN";

    if (raid.status === 'open') {
        statusColor = "text-[var(--primary)] border-[var(--primary)]/30";
        statusBg = "bg-[var(--primary)]/10";
        statusLabel = "OPEN";
    } else if (raid.status === 'locked') {
        statusColor = "text-[var(--danger)] border-[var(--danger)]/30";
        statusBg = "bg-[var(--danger)]/10";
        statusLabel = "LOCKED";
    }

    return (
        <a href={`/guilds/${guildId}/raids/${raid.id}/edit`} className="block group">
            <div className="panel-glass panel-hover p-0 relative overflow-hidden">
                {/* Status Bar Left */}
                <div className={cn("absolute left-0 top-0 bottom-0 w-1", raid.status === 'open' ? "bg-[var(--primary)]" : "bg-[var(--danger)]")} />
                
                <div className="p-5 pl-7 flex items-center justify-between">
                    <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                            <span className={cn("text-[10px] font-black uppercase tracking-widest px-2 py-0.5 rounded border", statusColor, statusBg)}>
                                {statusLabel}
                            </span>
                            <span className="text-[10px] font-bold text-[var(--muted)] font-mono uppercase">{raid.game} // {raid.mode}</span>
                        </div>
                        <h3 className="text-lg font-bold text-white group-hover:text-[var(--primary)] transition-colors">{raid.title}</h3>
                        <div className="flex items-center gap-4 mt-3 text-xs font-mono font-bold text-[var(--muted)]">
                            <span className="flex items-center gap-1.5"><Calendar className="h-3 w-3" /> {raid.raid_date}</span>
                            <span className="flex items-center gap-1.5"><Clock className="h-3 w-3" /> {raid.raid_time}</span>
                            <span className="text-[var(--primary)]">{raid.open_slots} SLOTS OPEN</span>
                        </div>
                    </div>

                    {/* Mini Slot Grid Preview */}
                    <div className="hidden md:grid grid-cols-4 gap-1">
                        <RoleChip count={raid.counts.tank} role="tank" label="TN" />
                        <RoleChip count={raid.counts.healer} role="healer" label="HL" />
                        <RoleChip count={raid.counts.dps} role="dps" label="DPS" />
                        <RoleChip count={raid.counts.bench} role="bench" label="BN" />
                    </div>

                    <div className="ml-6">
                        <button className="p-2 hover:bg-[var(--bg-1)] rounded text-[var(--muted)] hover:text-white transition-colors">
                            <MoreHorizontal className="h-5 w-5" />
                        </button>
                    </div>
                </div>
            </div>
        </a>
    )
}

const RoleChip = ({ count, role, label }: { count: string, role: string, label: string }) => {
    // Parse "2/2"
    const [curr, max] = count.split('/').map(Number);
    const isFull = max > 0 && curr >= max;
    const colorClass = `role-${role}`; // Maps to CSS classes defined in index.css

    return (
        <div className={cn("flex flex-col items-center justify-center w-10 h-10 rounded border bg-[var(--bg-0)]", 
            isFull ? "border-[var(--muted)] opacity-50" : `border-[var(--border)] ${colorClass.replace('role-', 'border-opacity-50 text-')}`
        )}>
            <span className={cn("text-[8px] font-black uppercase", isFull ? "text-[var(--muted)]" : "")}>{label}</span>
            <span className="text-[10px] font-mono font-bold leading-none">{curr}</span>
        </div>
    )
}

const ActivityItem = ({ text, time, type }: { text: string, time: string, type: 'create'|'join'|'system'|'lock' }) => {
    let icon = Activity;
    let color = "text-[var(--primary)]";
    
    if (type === 'lock') { icon = Lock; color = "text-[var(--danger)]"; }
    if (type === 'join') { icon = Users; color = "text-[var(--success)]"; }

    const Icon = icon;

    return (
        <div className="flex gap-3 items-start group cursor-default">
            <div className={cn("mt-0.5", color)}>
                <Icon className="h-3 w-3" />
            </div>
            <div className="flex-1">
                <div className="text-xs font-mono text-[var(--muted)] mb-0.5">{time}</div>
                <div className="text-sm font-medium text-[var(--text)] group-hover:text-white transition-colors">{text}</div>
            </div>
        </div>
    )
}

export default Dashboard;
