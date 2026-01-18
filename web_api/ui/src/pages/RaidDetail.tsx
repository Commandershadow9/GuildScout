import React from 'react';
import { useTranslation } from 'react-i18next';
import { Shield, Heart, Sword, Users, Copy, Lock, UserPlus, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

// Mock Data for Prototype
const slots = [
  { id: 1, role: 'tank', label: 'Main Tank', user: { name: 'CmdShadow', avatar: 'https://cdn.discordapp.com/embed/avatars/0.png' }, status: 'ready' },
  { id: 2, role: 'tank', label: 'Off Tank', user: null, status: 'open' },
  { id: 3, role: 'healer', label: 'Heal 1', user: { name: 'HealBot', avatar: 'https://cdn.discordapp.com/embed/avatars/1.png' }, status: 'ready' },
  { id: 4, role: 'healer', label: 'Heal 2', user: null, status: 'open' },
  { id: 5, role: 'dps', label: 'DPS 1', user: { name: 'BigCrits', avatar: 'https://cdn.discordapp.com/embed/avatars/2.png' }, status: 'ready' },
  { id: 6, role: 'dps', label: 'DPS 2', user: null, status: 'open' },
  { id: 7, role: 'dps', label: 'DPS 3', user: null, status: 'locked' },
  { id: 8, role: 'dps', label: 'DPS 4', user: null, status: 'open' },
];

const RaidDetail = () => {
  const { t } = useTranslation();

  return (
    <div className="max-w-[1400px] mx-auto space-y-8">
      {/* Header */}
      <div className="panel-glass p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
            <div className="flex items-center gap-3 mb-1">
                <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/30">
                    RAID - WWM
                </span>
                <span className="text-[var(--muted)] text-xs font-mono font-bold">#1284</span>
            </div>
            <h1 className="text-3xl font-heading font-bold text-white">Weekly Reset Clear</h1>
            <div className="flex items-center gap-4 mt-2 text-sm font-medium text-[var(--muted)]">
                <span>Oct 24, 2026</span>
                <span className="w-1 h-1 rounded-full bg-[var(--border)]" />
                <span>20:00 CET</span>
            </div>
        </div>
        <div className="flex gap-3">
            <button className="px-4 py-2 bg-[var(--surface-2)] border border-[var(--border)] rounded text-sm font-bold text-white hover:bg-[var(--bg-1)] transition-colors flex items-center gap-2">
                <Copy className="h-4 w-4" /> Copy Link
            </button>
            <button className="px-4 py-2 bg-[var(--danger)]/10 border border-[var(--danger)]/30 rounded text-sm font-bold text-[var(--danger)] hover:bg-[var(--danger)]/20 transition-colors flex items-center gap-2">
                <Lock className="h-4 w-4" /> Lock Raid
            </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left: Slot Board */}
        <div className="col-span-12 lg:col-span-8">
            <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-bold text-white">Composition</h3>
                <div className="text-xs font-mono text-[var(--muted)]">5/8 ASSIGNED</div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {slots.map(slot => (
                    <SlotTile key={slot.id} slot={slot} />
                ))}
            </div>
        </div>

        {/* Right: Roster & Reserves */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
            <div className="panel-glass p-0 overflow-hidden h-full">
                <div className="bg-[var(--surface-2)] px-4 py-3 border-b border-[var(--border)] font-bold text-xs uppercase tracking-wider text-[var(--muted)]">
                    Reserves / Bench
                </div>
                <div className="p-4 text-center text-[var(--muted)] text-sm italic">
                    No reserves signed up yet.
                </div>
            </div>
        </div>

      </div>
    </div>
  );
};

const SlotTile = ({ slot }: any) => {
    const isAssigned = !!slot.user;
    const isLocked = slot.status === 'locked';
    
    let roleColor = "border-[var(--border)]";
    let Icon = Users;
    
    if (slot.role === 'tank') { roleColor = "border-blue-500/30 bg-blue-500/5"; Icon = Shield; }
    if (slot.role === 'healer') { roleColor = "border-green-500/30 bg-green-500/5"; Icon = Heart; }
    if (slot.role === 'dps') { roleColor = "border-orange-500/30 bg-orange-500/5"; Icon = Sword; }

    return (
        <div className={cn(
            "relative p-4 rounded-xl border-2 transition-all group",
            isLocked ? "border-[var(--border)] bg-[var(--bg-1)] opacity-60" : 
            isAssigned ? "bg-[var(--surface-1)] border-[var(--primary)]/20 shadow-[var(--shadow-soft)] hover:border-[var(--primary)]/50" : 
            `border-dashed hover:border-solid hover:bg-[var(--surface-1)] ${roleColor}`
        )}>
            <div className="flex justify-between items-start mb-3">
                <div className={cn("text-[10px] font-black uppercase px-1.5 py-0.5 rounded", `role-${slot.role}`)}>
                    {slot.label}
                </div>
                <Icon className="h-4 w-4 opacity-30" />
            </div>

            {isAssigned ? (
                <div className="flex items-center gap-3">
                    <img src={slot.user.avatar} className="w-8 h-8 rounded border border-[var(--border)]" />
                    <div className="overflow-hidden">
                        <div className="text-sm font-bold text-white truncate">{slot.user.name}</div>
                        <div className="text-[10px] text-[var(--success)] font-mono flex items-center gap-1">
                            <Check className="h-2 w-2" /> READY
                        </div>
                    </div>
                </div>
            ) : isLocked ? (
                <div className="flex flex-col items-center justify-center py-2 text-[var(--muted)]">
                    <Lock className="h-6 w-6 mb-1 opacity-50" />
                    <span className="text-xs font-bold">LOCKED</span>
                </div>
            ) : (
                <button className="w-full py-2 flex flex-col items-center justify-center text-[var(--muted)] group-hover:text-white transition-colors">
                    <UserPlus className="h-6 w-6 mb-1 opacity-50 group-hover:opacity-100" />
                    <span className="text-xs font-bold uppercase">Assign</span>
                </button>
            )}
        </div>
    )
}

export default RaidDetail;
