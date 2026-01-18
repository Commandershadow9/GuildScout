import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2, Star, Save, X, Edit2, Shield, Heart, Sword, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Template {
  template_id: number;
  name: string;
  tanks: number;
  healers: number;
  dps: number;
  bench: number;
  is_default: boolean;
}

interface TemplatesProps {
  data: {
    guild: any;
    templates: Template[];
  };
}

const Templates: React.FC<TemplatesProps> = ({ data }) => {
  const { t } = useTranslation();
  const [templates, setTemplates] = useState<Template[]>(data.templates);
  const [isCreating, setIsCreating] = useState(false);
  
  // New template state
  const [newTmpl, setNewTmpl] = useState({ name: '', tanks: 2, healers: 2, dps: 6, bench: 0, is_default: false });

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-heading font-bold tracking-tight text-white">{t('templates.title')}</h1>
          <p className="text-[var(--muted)] mt-1">{t('templates.subtitle')}</p>
        </div>
        <button 
          onClick={() => setIsCreating(true)}
          className="flex items-center gap-2 bg-[var(--primary)] text-black px-4 py-2 rounded-lg font-bold shadow-[var(--glow-primary)] hover:bg-[var(--primary)]/90 transition-all uppercase text-sm tracking-wide"
        >
          <Plus className="h-5 w-5" />
          {t('templates.create_new')}
        </button>
      </div>

      {/* Creation Form */}
      {isCreating && (
        <form action={`/guilds/${data.guild.id}/templates`} method="POST" className="animate-in fade-in slide-in-from-top-4 panel-glass p-6 border-[var(--primary)]/30 shadow-[var(--glow-primary)]">
            <input type="hidden" name="return_to" value="templates" />
            <div className="flex items-center justify-between mb-6 border-b border-[var(--border)] pb-4">
               <h3 className="font-bold text-lg text-white flex items-center gap-2">
                  <span className="w-2 h-6 bg-[var(--primary)] rounded-sm" />
                  {t('templates.create_new')}
               </h3>
               <button type="button" onClick={() => setIsCreating(false)} className="text-[var(--muted)] hover:text-white transition-colors">
                 <X className="h-6 w-6" />
               </button>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
                <div className="lg:col-span-4 space-y-2">
                    <label className="text-xs font-bold uppercase text-[var(--muted)] tracking-wider">Name</label>
                    <input 
                      name="name" 
                      type="text" 
                      required
                      placeholder="e.g. Mythic Standard"
                      className="w-full bg-[var(--bg-0)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-white focus:ring-2 focus:ring-[var(--primary)]/50 focus:border-[var(--primary)] outline-none transition-all font-medium"
                      value={newTmpl.name}
                      onChange={e => setNewTmpl({...newTmpl, name: e.target.value})}
                    />
                </div>

                <div className="lg:col-span-6 grid grid-cols-4 gap-4">
                     <SlotInput label="Tank" name="tanks" value={newTmpl.tanks} onChange={(v:any) => setNewTmpl({...newTmpl, tanks: v})} color="text-blue-400" />
                     <SlotInput label="Heal" name="healers" value={newTmpl.healers} onChange={(v:any) => setNewTmpl({...newTmpl, healers: v})} color="text-green-400" />
                     <SlotInput label="DPS" name="dps" value={newTmpl.dps} onChange={(v:any) => setNewTmpl({...newTmpl, dps: v})} color="text-orange-400" />
                     <SlotInput label="Bench" name="bench" value={newTmpl.bench} onChange={(v:any) => setNewTmpl({...newTmpl, bench: v})} color="text-violet-400" />
                </div>

                <div className="lg:col-span-2 flex items-center justify-end pb-1 gap-4">
                    <label className="flex items-center gap-2 cursor-pointer group">
                        <input type="checkbox" name="is_default" className="peer sr-only" checked={newTmpl.is_default} onChange={e => setNewTmpl({...newTmpl, is_default: e.target.checked})} />
                        <div className="w-4 h-4 border border-[var(--border)] rounded bg-[var(--bg-0)] peer-checked:bg-[var(--primary)] peer-checked:border-[var(--primary)] flex items-center justify-center transition-colors">
                            <Star className="h-3 w-3 text-black opacity-0 peer-checked:opacity-100" />
                        </div>
                        <span className="text-sm font-bold text-[var(--muted)] group-hover:text-white transition-colors">Default</span>
                    </label>
                    <button type="submit" className="bg-[var(--primary)] text-black p-2.5 rounded-lg hover:bg-[var(--primary)]/90 shadow-lg">
                        <Save className="h-5 w-5" />
                    </button>
                </div>
            </div>
        </form>
      )}

      {/* Grid of Templates */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {templates.map((tmpl) => (
            <TemplateCard key={tmpl.template_id} tmpl={tmpl} guildId={data.guild.id} />
        ))}
      </div>
    </div>
  );
};

const SlotInput = ({ label, name, value, onChange, color }: any) => (
    <div className="space-y-2 text-center">
        <label className={cn("text-[10px] font-black uppercase tracking-widest", color)}>{label}</label>
        <input name={name} type="number" min="0" className="w-full bg-[var(--bg-0)] border border-[var(--border)] rounded-md px-2 py-2 text-center font-mono font-bold text-lg text-white focus:border-[var(--primary)] outline-none transition-colors" value={value} onChange={e => onChange(parseInt(e.target.value))} />
    </div>
)

const TemplateCard = ({ tmpl, guildId }: { tmpl: Template, guildId: number }) => {
    const { t } = useTranslation();
    const [isEditing, setIsEditing] = useState(false);
    // Local edit state
    const [editData, setEditData] = useState({...tmpl});

    if (isEditing) {
        return (
            <form action={`/guilds/${guildId}/templates/${tmpl.template_id}/update`} method="POST" className="relative panel-glass p-5 flex flex-col gap-4 border-[var(--primary)]/50">
                <input type="hidden" name="return_to" value="templates" />
                
                <div className="flex items-center justify-between">
                   <input 
                      name="name" 
                      className="bg-[var(--bg-0)] border border-[var(--border)] rounded px-3 py-1.5 text-sm font-bold w-full mr-2 text-white focus:border-[var(--primary)] outline-none" 
                      value={editData.name} 
                      onChange={e => setEditData({...editData, name: e.target.value})}
                   />
                   <button type="button" onClick={() => setIsEditing(false)}><X className="h-5 w-5 text-[var(--muted)] hover:text-white" /></button>
                </div>

                <div className="grid grid-cols-4 gap-2">
                     <SlotEdit label="T" name="tanks" value={editData.tanks} onChange={(v:any) => setEditData({...editData, tanks: v})} color="text-blue-400" />
                     <SlotEdit label="H" name="healers" value={editData.healers} onChange={(v:any) => setEditData({...editData, healers: v})} color="text-green-400" />
                     <SlotEdit label="D" name="dps" value={editData.dps} onChange={(v:any) => setEditData({...editData, dps: v})} color="text-orange-400" />
                     <SlotEdit label="B" name="bench" value={editData.bench} onChange={(v:any) => setEditData({...editData, bench: v})} color="text-violet-400" />
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
                   <label className="flex items-center gap-2 text-xs font-bold text-[var(--muted)] cursor-pointer hover:text-white">
                      <input type="checkbox" name="is_default" checked={editData.is_default} onChange={e => setEditData({...editData, is_default: e.target.checked})} className="accent-[var(--primary)]" />
                      Default
                   </label>
                   <button type="submit" className="bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/30 px-4 py-1 rounded text-xs font-bold hover:bg-[var(--primary)] hover:text-black transition-all uppercase">Save</button>
                </div>
            </form>
        )
    }

    return (
        <div className="group relative panel-glass panel-hover p-6">
            {tmpl.is_default && (
                <div className="absolute top-0 right-0 p-2 bg-[var(--warning)]/10 rounded-bl-xl border-b border-l border-[var(--warning)]/30">
                    <Star className="h-4 w-4 text-[var(--warning)] fill-current" />
                </div>
            )}
            
            <h3 className="font-heading font-bold text-lg mb-4 pr-8 truncate text-white group-hover:text-[var(--primary)] transition-colors">{tmpl.name}</h3>

            <div className="grid grid-cols-4 gap-2 mb-6">
                <SlotBadge icon={Shield} count={tmpl.tanks} color="text-blue-400" bg="bg-blue-400/10 border-blue-400/20" />
                <SlotBadge icon={Heart} count={tmpl.healers} color="text-green-400" bg="bg-green-400/10 border-green-400/20" />
                <SlotBadge icon={Sword} count={tmpl.dps} color="text-orange-400" bg="bg-orange-400/10 border-orange-400/20" />
                <SlotBadge icon={Users} count={tmpl.bench} color="text-violet-400" bg="bg-violet-400/10 border-violet-400/20" />
            </div>

            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity translate-y-2 group-hover:translate-y-0 duration-300">
                <button onClick={() => setIsEditing(true)} className="flex-1 flex items-center justify-center gap-2 bg-[var(--surface-2)] hover:bg-[var(--bg-1)] border border-[var(--border)] py-2 rounded text-xs font-bold transition-all uppercase text-white">
                    <Edit2 className="h-3 w-3" /> {t('actions.edit')}
                </button>
                
                <form action={`/guilds/${guildId}/templates/${tmpl.template_id}/delete`} method="POST" onSubmit={(e) => !confirm(n("templates.delete_confirm")) && e.preventDefault()}>
                    <input type="hidden" name="return_to" value="templates" />
                    <button type="submit" className="p-2 bg-[var(--danger)]/10 text-[var(--danger)] hover:bg-[var(--danger)] hover:text-white border border-[var(--danger)]/30 rounded transition-all">
                        <Trash2 className="h-4 w-4" />
                    </button>
                </form>

                {!tmpl.is_default && (
                    <form action={`/guilds/${guildId}/templates/${tmpl.template_id}/default`} method="POST">
                        <button type="submit" className="p-2 bg-[var(--warning)]/10 text-[var(--warning)] hover:bg-[var(--warning)] hover:text-black border border-[var(--warning)]/30 rounded transition-all" title={t('templates.set_default')}>
                            <Star className="h-4 w-4" />
                        </button>
                    </form>
                )}
            </div>
        </div>
    )
}

const SlotBadge = ({ icon: Icon, count, color, bg }: any) => (
    <div className={cn("flex flex-col items-center justify-center rounded-lg p-2 border", bg)}>
        <Icon className={cn("h-4 w-4 mb-1", color)} />
        <span className="font-mono font-bold text-sm text-white">{count}</span>
    </div>
)

const SlotEdit = ({ label, name, value, onChange, color }: any) => (
    <div className="text-center">
        <label className={cn("block text-[10px] font-black mb-1", color)}>{label}</label>
        <input 
            type="number" name={name} 
            className="w-full bg-[var(--bg-0)] border border-[var(--border)] rounded text-center text-xs font-bold py-1.5 text-white outline-none focus:border-[var(--primary)]"
            value={value} onChange={e => onChange(parseInt(e.target.value))}
        />
    </div>
)

export default Templates;