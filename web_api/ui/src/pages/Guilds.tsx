import React from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowRight, Shield, Heart, Sword, Users, Zap, Activity, Radio, LayoutGrid } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Guild {
  id: number;
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
    <div className="max-w-[1200px] mx-auto space-y-10 py-8">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-[var(--border)] pb-6">
        <div>
            <div className="flex items-center gap-2 text-[var(--primary)] mb-2">
                <LayoutGrid className="h-5 w-5" />
                <span className="text-xs font-bold uppercase tracking-widest">Command Center Selection</span>
            </div>
            <h1 className="text-4xl font-heading font-black text-white tracking-tight">
               Operational Units
            </h1>
            <p className="text-[var(--muted)] mt-2 max-w-xl text-lg">
               Select a guild node to access the raid board and tactical configurations.
            </p>
        </div>
        <div className="flex gap-4 text-sm font-medium text-[var(--muted)]">
            <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[var(--success)] animate-pulse"></span>
                <span>System Online</span>
            </div>
            <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[var(--primary)]"></span>
                <span>{guilds.length} Units Connected</span>
            </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {guilds.length === 0 ? (
          <div className="panel-glass p-16 flex flex-col items-center justify-center text-center border-dashed border-[var(--border)]">
             <Shield className="h-16 w-16 text-[var(--muted)]/20 mb-4" />
             <h3 className="text-xl font-bold text-white">No Assigned Units</h3>
             <p className="text-[var(--muted)] mt-2">You don't have access to any guild command nodes.</p>
          </div>
        ) : (
          guilds.map((guild) => (
            <CommandNode key={guild.id} guild={guild} />
          ))
        )}
      </div>
    </div>
  );
};

const CommandNode = ({ guild }: { guild: Guild }) => {
    // Mock Data for "Readiness" visuals since backend doesn't provide it yet
    const activeRaids = Math.floor(Math.random() * 3);
    const readiness = 80 + Math.floor(Math.random() * 20);
    const membersOnline = 12 + Math.floor(Math.random() * 40);

    return (
        <div className="panel-glass group relative overflow-hidden transition-all hover:border-[var(--primary)]/50">
            {/* Background Texture for Node */}
            <div className="absolute inset-0 opacity-[0.03] pointer-events-none bg-[radial-gradient(circle_at_top_right,_var(--primary),transparent_60%)]" />
            
            <div className="flex flex-col lg:flex-row">
                {/* Left: Identity & Status */}
                <div className="p-8 flex-1 flex flex-col justify-center border-b lg:border-b-0 lg:border-r border-[var(--border)] bg-[var(--bg-1)]/50 relative">
                    <div className="absolute top-4 left-4 text-[10px] font-mono font-bold text-[var(--muted)] opacity-50">ID: {guild.id}</div>
                    
                    <div className="flex items-center gap-6 mb-6">
                        {guild.icon ? (
                            <img src={guild.icon} alt={guild.name} className="w-20 h-20 rounded-2xl border-2 border-[var(--border)] shadow-lg group-hover:scale-105 transition-transform duration-500" />
                        ) : (
                            <div className="w-20 h-20 rounded-2xl border-2 border-[var(--border)] bg-[var(--surface-2)] flex items-center justify-center text-2xl font-bold text-[var(--muted)] group-hover:text-white transition-colors">
                                {guild.name.substring(0, 2)}
                            </div>
                        )}
                        <div>
                            <h2 className="text-3xl font-heading font-bold text-white group-hover:text-[var(--primary)] transition-colors mb-2">
                                {guild.name}
                            </h2>
                            <div className="flex items-center gap-2">
                                <span className="px-2 py-0.5 rounded bg-[var(--success)]/10 text-[var(--success)] border border-[var(--success)]/20 text-[10px] font-black uppercase tracking-wider">
                                    Ready for Ops
                                </span>
                                <span className="px-2 py-0.5 rounded bg-[var(--surface-2)] text-[var(--muted)] border border-[var(--border)] text-[10px] font-black uppercase tracking-wider">
                                    EU-Central
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Role Breakdown (Visual Cue) */}
                    <div className="flex gap-2">
                        <RoleIndicator icon={Shield} color="text-blue-400" bg="bg-blue-400/10" label="Tanks" value="OK" />
                        <RoleIndicator icon={Heart} color="text-green-400" bg="bg-green-400/10" label="Healers" value="OK" />
                        <RoleIndicator icon={Sword} color="text-orange-400" bg="bg-orange-400/10" label="DPS" value="High" />
                    </div>
                </div>

                {/* Middle: Readiness Overview */}
                <div className="p-8 flex-1 flex flex-col justify-center bg-[var(--surface-0)]/30">
                    <h4 className="text-xs font-bold uppercase tracking-widest text-[var(--muted)] mb-6 flex items-center gap-2">
                        <Activity className="h-4 w-4" /> Unit Readiness
                    </h4>
                    
                    <div className="grid grid-cols-2 gap-6">
                        <div>
                            <div className="text-3xl font-mono font-bold text-white">{activeRaids}</div>
                            <div className="text-xs text-[var(--muted)] font-medium uppercase">Active Raids</div>
                        </div>
                        <div>
                            <div className="text-3xl font-mono font-bold text-white">{membersOnline}</div>
                            <div className="text-xs text-[var(--muted)] font-medium uppercase">Members Online</div>
                        </div>
                        <div className="col-span-2">
                            <div className="flex justify-between text-xs mb-1">
                                <span className="font-bold text-[var(--primary)]">Roster Efficiency</span>
                                <span className="font-mono text-white">{readiness}%</span>
                            </div>
                            <div className="h-1.5 w-full bg-[var(--bg-0)] rounded-full overflow-hidden">
                                <div className="h-full bg-[var(--primary)] shadow-[0_0_10px_var(--primary)]" style={{ width: `${readiness}%` }} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right: Actions */}
                <div className="p-8 w-full lg:w-72 flex flex-col justify-center gap-3 bg-[var(--surface-1)]">
                    <a href={`/guilds/${guild.id}`} className="w-full py-4 bg-[var(--primary)] hover:bg-[var(--primary)]/90 text-black font-black text-sm uppercase tracking-wider rounded-xl flex items-center justify-center gap-2 transition-all hover:scale-[1.02] shadow-[var(--glow-primary)]">
                        <Radio className="h-4 w-4" />
                        Open Board
                    </a>
                    <a href={`/guilds/${guild.id}/raids/new`} className="w-full py-4 bg-[var(--surface-2)] hover:bg-[var(--surface-0)] text-white font-bold text-sm uppercase tracking-wider rounded-xl flex items-center justify-center gap-2 border border-[var(--border)] transition-all hover:border-[var(--primary)]/50">
                        <Zap className="h-4 w-4 text-[var(--warning)]" />
                        Create Raid
                    </a>
                </div>
            </div>
        </div>
    )
}

const RoleIndicator = ({ icon: Icon, color, bg, label, value }: any) => (
    <div className={cn("flex items-center gap-2 px-3 py-1.5 rounded border border-[var(--border)]", bg)}>
        <Icon className={cn("h-3 w-3", color)} />
        <div className="flex flex-col leading-none">
            <span className="text-[8px] font-bold uppercase text-[var(--muted)]">{label}</span>
            <span className="text-[10px] font-bold text-white">{value}</span>
        </div>
    </div>
)

export default Guilds;