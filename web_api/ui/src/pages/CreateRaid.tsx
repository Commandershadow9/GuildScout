import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Calendar, Users, Copy, Check, ArrowRight, ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CreateRaidProps {
  data: {
    guild: any;
    templates: any[];
    games: any[];
    modes: any[];
    prefill: any;
    settings: any;
  };
}

const CreateRaid: React.FC<CreateRaidProps> = ({ data }) => {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
      title: data.prefill.title || '',
      description: data.prefill.description || '',
      game: data.prefill.game || 'WWM',
      mode: data.prefill.mode || 'raid',
      raid_date: data.prefill.raid_date || '',
      raid_time: data.prefill.raid_time || '',
      tanks: data.prefill.tanks || 0,
      healers: data.prefill.healers || 0,
      dps: data.prefill.dps || 0,
      bench: data.prefill.bench || 0,
  });

  const handleTemplateSelect = (tmpl: any) => {
      setFormData({
          ...formData,
          tanks: tmpl.tanks,
          healers: tmpl.healers,
          dps: tmpl.dps,
          bench: tmpl.bench
      });
  };

  return (
    <div className="max-w-4xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
            <h1 className="text-3xl font-heading font-bold">{t('actions.create_raid')}</h1>
            <div className="flex items-center gap-2">
                <StepIndicator num={1} active={step === 1} done={step > 1} label="Details" />
                <div className="w-10 h-px bg-border" />
                <StepIndicator num={2} active={step === 2} done={step > 2} label="Slots" />
                <div className="w-10 h-px bg-border" />
                <StepIndicator num={3} active={step === 3} done={step > 3} label="Review" />
            </div>
        </div>

        <form action={`/guilds/${data.guild.id}/raids`} method="POST" className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-6">
                {step === 1 && (
                    <div className="space-y-4 animate-in fade-in slide-in-from-left-4">
                        <div className="grid gap-2">
                            <label className="text-sm font-medium">Title</label>
                            <input name="title" className="flex h-10 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" 
                                value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})} required placeholder="e.g. Weekly Reset Clear" />
                        </div>
                        <div className="grid gap-2">
                            <label className="text-sm font-medium">Description</label>
                            <textarea name="description" className="flex min-h-[80px] w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" 
                                value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} placeholder="Optional details..." />
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                             <div className="grid gap-2">
                                <label className="text-sm font-medium">Game</label>
                                <select name="game" className="flex h-10 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                    value={formData.game} onChange={e => setFormData({...formData, game: e.target.value})}>
                                    {data.games.map((g: any) => <option key={g.id} value={g.id}>{g.label}</option>)}
                                </select>
                             </div>
                             <div className="grid gap-2">
                                <label className="text-sm font-medium">Mode</label>
                                <select name="mode" className="flex h-10 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                    value={formData.mode} onChange={e => setFormData({...formData, mode: e.target.value})}>
                                    {data.modes.map((m: any) => <option key={m.id} value={m.id}>{m.label}</option>)}
                                </select>
                             </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                             <div className="grid gap-2">
                                <label className="text-sm font-medium">Date</label>
                                <input type="date" name="raid_date" className="flex h-10 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                    value={formData.raid_date} onChange={e => setFormData({...formData, raid_date: e.target.value})} required />
                             </div>
                             <div className="grid gap-2">
                                <label className="text-sm font-medium">Time</label>
                                <input type="time" name="raid_time" className="flex h-10 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                    value={formData.raid_time} onChange={e => setFormData({...formData, raid_time: e.target.value})} required />
                             </div>
                        </div>
                    </div>
                )}

                {step === 2 && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-right-4">
                        <div>
                            <h3 className="text-sm font-medium mb-3 text-muted-foreground">Load from Template</h3>
                            <div className="grid grid-cols-2 gap-3">
                                {data.templates.map((tmpl: any) => (
                                    <button type="button" key={tmpl.id} onClick={() => handleTemplateSelect(tmpl)}
                                        className="text-left p-3 rounded-lg border border-border bg-card hover:bg-secondary/50 hover:border-primary/50 transition-all">
                                        <div className="font-bold text-sm">{tmpl.name}</div>
                                        <div className="text-xs text-muted-foreground mt-1">
                                            {tmpl.tanks}T / {tmpl.healers}H / {tmpl.dps}D / {tmpl.bench}B
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="h-px bg-border w-full" />

                        <div className="grid grid-cols-4 gap-4">
                            <SlotInput label="Tanks" name="tanks" value={formData.tanks} onChange={(v: any) => setFormData({...formData, tanks: v})} />
                            <SlotInput label="Healers" name="healers" value={formData.healers} onChange={(v: any) => setFormData({...formData, healers: v})} />
                            <SlotInput label="DPS" name="dps" value={formData.dps} onChange={(v: any) => setFormData({...formData, dps: v})} />
                            <SlotInput label="Bench" name="bench" value={formData.bench} onChange={(v: any) => setFormData({...formData, bench: v})} />
                        </div>
                    </div>
                )}

                {step === 3 && (
                    <div className="animate-in fade-in zoom-in-95">
                        <div className="rounded-xl border border-border bg-card p-6 space-y-4">
                            <div>
                                <h3 className="text-xl font-heading font-bold text-primary">{formData.title}</h3>
                                <p className="text-muted-foreground">{formData.description || "No description"}</p>
                            </div>
                            <div className="flex gap-4 text-sm font-mono text-muted-foreground">
                                <span>{formData.raid_date} {formData.raid_time}</span>
                                <span>•</span>
                                <span>{formData.game} ({formData.mode})</span>
                            </div>
                            <div className="grid grid-cols-4 gap-2 pt-4 border-t border-border">
                                <div className="text-center p-2 bg-secondary/30 rounded">
                                    <div className="text-xl font-bold">{formData.tanks}</div>
                                    <div className="text-xs text-muted-foreground">Tanks</div>
                                </div>
                                <div className="text-center p-2 bg-secondary/30 rounded">
                                    <div className="text-xl font-bold">{formData.healers}</div>
                                    <div className="text-xs text-muted-foreground">Healers</div>
                                </div>
                                <div className="text-center p-2 bg-secondary/30 rounded">
                                    <div className="text-xl font-bold">{formData.dps}</div>
                                    <div className="text-xs text-muted-foreground">DPS</div>
                                </div>
                                <div className="text-center p-2 bg-secondary/30 rounded">
                                    <div className="text-xl font-bold">{formData.bench}</div>
                                    <div className="text-xs text-muted-foreground">Bench</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex justify-between pt-6">
                    {step > 1 ? (
                        <button type="button" onClick={() => setStep(step - 1)} className="flex items-center gap-2 px-4 py-2 rounded-md hover:bg-secondary transition-colors">
                            <ArrowLeft className="h-4 w-4" /> Back
                        </button>
                    ) : <div />}
                    
                    {step < 3 ? (
                        <button type="button" onClick={() => setStep(step + 1)} className="flex items-center gap-2 bg-primary text-primary-foreground px-6 py-2 rounded-md hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20">
                            Next <ArrowRight className="h-4 w-4" />
                        </button>
                    ) : (
                        <button type="submit" className="flex items-center gap-2 bg-primary text-primary-foreground px-6 py-2 rounded-md hover:bg-primary/90 transition-colors shadow-lg shadow-primary/20 font-bold">
                            <Check className="h-4 w-4" /> Create Raid
                        </button>
                    )}
                </div>
            </div>

            {/* Preview Panel */}
            <div className="hidden lg:block">
                <div className="sticky top-24 rounded-xl border border-border bg-[#2f3136] p-4 font-sans text-[#dcddde]">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="h-10 w-10 rounded-full bg-indigo-500" />
                        <div>
                            <div className="font-bold text-white">GuildScout <span className="px-1.5 py-0.5 rounded bg-[#5865F2] text-[10px] text-white">BOT</span></div>
                            <div className="text-xs text-[#b9bbbe]">Today at {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                        </div>
                    </div>
                    <div className="pl-[52px]">
                         <div className="rounded border-l-4 border-[#2DE2E6] bg-[#2f3136] p-4 shadow-sm">
                            <div className="font-bold text-white mb-1">{formData.title || "Raid Title"}</div>
                            <div className="text-sm text-[#dcddde] mb-3">{formData.description || "Description..."}</div>
                            
                            <div className="grid grid-cols-2 gap-y-2 text-sm mb-3">
                                <div className="text-[#b9bbbe]">Game</div><div className="text-white text-right">{formData.game}</div>
                                <div className="text-[#b9bbbe]">Start</div><div className="text-white text-right">{formData.raid_date} {formData.raid_time}</div>
                            </div>

                            <div className="text-xs text-[#b9bbbe] uppercase font-bold mb-2 tracking-wide">Composition</div>
                            <div className="space-y-1">
                                <div className="flex justify-between text-sm"><span className="text-blue-400">🛡️ Tank</span> <span>0/{formData.tanks}</span></div>
                                <div className="flex justify-between text-sm"><span className="text-green-400">💚 Healer</span> <span>0/{formData.healers}</span></div>
                                <div className="flex justify-between text-sm"><span className="text-red-400">⚔️ DPS</span> <span>0/{formData.dps}</span></div>
                            </div>
                         </div>
                    </div>
                </div>
            </div>
        </form>
    </div>
  );
};

const StepIndicator = ({ num, active, done, label }: any) => (
    <div className={cn("flex flex-col items-center gap-1", active ? "text-primary" : done ? "text-primary/70" : "text-muted-foreground")}>
        <div className={cn("w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-all", 
            active ? "border-primary bg-primary/20" : done ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card")}>
            {done ? <Check className="h-4 w-4" /> : num}
        </div>
        <span className="text-xs font-medium">{label}</span>
    </div>
)

const SlotInput = ({ label, name, value, onChange }: any) => (
    <div className="grid gap-2 text-center">
        <label className="text-xs font-bold uppercase text-muted-foreground">{label}</label>
        <input type="number" name={name} min="0" max="20" 
            className="flex h-12 w-full rounded-md border border-input bg-secondary/50 px-3 py-2 text-center text-lg font-mono font-bold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={value} onChange={e => onChange(parseInt(e.target.value) || 0)} />
    </div>
)

export default CreateRaid;
