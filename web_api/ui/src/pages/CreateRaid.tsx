import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Calendar,
  Users,
  Check,
  ArrowRight,
  ArrowLeft,
  Swords,
  Clock,
  FileText,
  Sparkles,
  Shield,
  Heart,
  Sword,
  UserPlus
} from 'lucide-react';
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
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
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
    setSelectedTemplate(tmpl.template_id || tmpl.id);
    setFormData({
      ...formData,
      tanks: tmpl.tanks,
      healers: tmpl.healers,
      dps: tmpl.dps,
      bench: tmpl.bench
    });
  };

  const totalSlots = formData.tanks + formData.healers + formData.dps;
  const canProceed = step === 1
    ? formData.title && formData.raid_date && formData.raid_time
    : step === 2
    ? totalSlots > 0
    : true;

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 text-[var(--primary)] mb-2">
          <Swords className="h-5 w-5" />
          <span className="text-xs font-bold uppercase tracking-widest">{t('actions.create_raid')}</span>
        </div>
        <h1 className="text-3xl font-heading font-bold text-white">New Operation</h1>
      </div>

      {/* Progress Bar */}
      <div className="mb-10">
        <div className="flex items-center justify-between mb-4">
          {[
            { num: 1, label: 'Details', icon: FileText },
            { num: 2, label: 'Composition', icon: Users },
            { num: 3, label: 'Review', icon: Check },
          ].map((s, i) => (
            <React.Fragment key={s.num}>
              <StepIndicator
                num={s.num}
                label={s.label}
                icon={s.icon}
                active={step === s.num}
                done={step > s.num}
                onClick={() => step > s.num && setStep(s.num)}
              />
              {i < 2 && (
                <div className={cn(
                  "flex-1 h-0.5 mx-4 rounded transition-colors",
                  step > s.num ? "bg-[var(--primary)]" : "bg-[var(--border)]"
                )} />
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      <form action={`/guilds/${data.guild.id}/raids`} method="POST">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Form Area */}
          <div className="lg:col-span-2">
            {/* Step 1: Details */}
            {step === 1 && (
              <div className="space-y-6 fade-in">
                <div className="panel-glass p-6 relative">
                  <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                    <FileText className="h-5 w-5 text-[var(--secondary)]" />
                    Raid Details
                  </h3>

                  <div className="space-y-5 relative z-10">
                    <div>
                      <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
                        Title *
                      </label>
                      <input
                        name="title"
                        type="text"
                        required
                        placeholder="e.g. Weekly Reset Clear"
                        className="input-field"
                        value={formData.title}
                        onChange={e => setFormData({...formData, title: e.target.value})}
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
                        Description
                      </label>
                      <textarea
                        name="description"
                        rows={3}
                        placeholder="Optional details about this raid..."
                        className="input-field resize-none"
                        value={formData.description}
                        onChange={e => setFormData({...formData, description: e.target.value})}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
                          Game
                        </label>
                        <select
                          name="game"
                          className="input-field"
                          value={formData.game}
                          onChange={e => setFormData({...formData, game: e.target.value})}
                        >
                          {data.games.map((g: any) => (
                            <option key={g.id} value={g.id}>{g.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
                          Mode
                        </label>
                        <select
                          name="mode"
                          className="input-field"
                          value={formData.mode}
                          onChange={e => setFormData({...formData, mode: e.target.value})}
                        >
                          {data.modes.map((m: any) => (
                            <option key={m.id} value={m.id}>{m.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
                          <Calendar className="h-3.5 w-3.5 inline mr-1.5" />
                          Date *
                        </label>
                        <input
                          type="date"
                          name="raid_date"
                          required
                          className="input-field"
                          value={formData.raid_date}
                          onChange={e => setFormData({...formData, raid_date: e.target.value})}
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
                          <Clock className="h-3.5 w-3.5 inline mr-1.5" />
                          Time *
                        </label>
                        <input
                          type="time"
                          name="raid_time"
                          required
                          className="input-field"
                          value={formData.raid_time}
                          onChange={e => setFormData({...formData, raid_time: e.target.value})}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Composition */}
            {step === 2 && (
              <div className="space-y-6 fade-in">
                {/* Template Selection */}
                {data.templates.length > 0 && (
                  <div className="panel-glass p-6 relative">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-[var(--primary)]" />
                      Load from Template
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 relative z-10">
                      {data.templates.map((tmpl: any) => (
                        <button
                          type="button"
                          key={tmpl.template_id || tmpl.id}
                          onClick={() => handleTemplateSelect(tmpl)}
                          className={cn(
                            "text-left p-4 rounded-xl border transition-all",
                            selectedTemplate === (tmpl.template_id || tmpl.id)
                              ? "border-[var(--primary)] bg-[var(--primary)]/10 shadow-[var(--glow-primary)]"
                              : "border-[var(--border)] bg-[var(--surface-0)] hover:border-[var(--secondary)]"
                          )}
                        >
                          <div className="font-bold text-sm text-white mb-1">{tmpl.name}</div>
                          <div className="text-xs text-[var(--muted)] font-mono">
                            {tmpl.tanks}T / {tmpl.healers}H / {tmpl.dps}D
                            {tmpl.bench > 0 && ` / ${tmpl.bench}B`}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Manual Slot Configuration */}
                <div className="panel-glass p-6 relative">
                  <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                    <Users className="h-5 w-5 text-[var(--secondary)]" />
                    Slot Configuration
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 relative z-10">
                    <SlotInput
                      label="Tanks"
                      name="tanks"
                      value={formData.tanks}
                      onChange={(v) => setFormData({...formData, tanks: v})}
                      icon={Shield}
                      color="blue"
                    />
                    <SlotInput
                      label="Healers"
                      name="healers"
                      value={formData.healers}
                      onChange={(v) => setFormData({...formData, healers: v})}
                      icon={Heart}
                      color="emerald"
                    />
                    <SlotInput
                      label="DPS"
                      name="dps"
                      value={formData.dps}
                      onChange={(v) => setFormData({...formData, dps: v})}
                      icon={Sword}
                      color="orange"
                    />
                    <SlotInput
                      label="Bench"
                      name="bench"
                      value={formData.bench}
                      onChange={(v) => setFormData({...formData, bench: v})}
                      icon={UserPlus}
                      color="violet"
                    />
                  </div>

                  <div className="mt-6 pt-4 border-t border-[var(--border)] flex items-center justify-between relative z-10">
                    <span className="text-sm text-[var(--muted)]">Total roster size</span>
                    <span className="text-2xl font-bold font-mono text-white">
                      {totalSlots}
                      {formData.bench > 0 && (
                        <span className="text-sm font-normal text-[var(--muted)] ml-1">
                          (+{formData.bench} bench)
                        </span>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Review */}
            {step === 3 && (
              <div className="fade-in">
                <div className="panel-gradient p-6 relative overflow-hidden">
                  {/* Background decoration */}
                  <div className="absolute top-0 right-0 w-48 h-48 bg-[var(--primary)]/10 rounded-full blur-3xl -mr-24 -mt-24" />

                  <div className="relative z-10 space-y-6">
                    <div>
                      <span className="badge badge-open mb-2">Ready to Deploy</span>
                      <h2 className="text-2xl font-heading font-bold text-white">{formData.title}</h2>
                      {formData.description && (
                        <p className="text-[var(--muted)] mt-2">{formData.description}</p>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-4 text-sm">
                      <div className="flex items-center gap-2 text-[var(--muted)]">
                        <Calendar className="h-4 w-4" />
                        {formData.raid_date}
                      </div>
                      <div className="flex items-center gap-2 text-[var(--muted)]">
                        <Clock className="h-4 w-4" />
                        {formData.raid_time}
                      </div>
                      <div className="badge badge-info">{formData.game} / {formData.mode}</div>
                    </div>

                    <div className="grid grid-cols-4 gap-3 pt-4 border-t border-[var(--border)]">
                      <RolePreview label="Tanks" count={formData.tanks} color="blue" icon={Shield} />
                      <RolePreview label="Healers" count={formData.healers} color="emerald" icon={Heart} />
                      <RolePreview label="DPS" count={formData.dps} color="orange" icon={Sword} />
                      <RolePreview label="Bench" count={formData.bench} color="violet" icon={UserPlus} />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="flex justify-between mt-8">
              {step > 1 ? (
                <button
                  type="button"
                  onClick={() => setStep(step - 1)}
                  className="btn-ghost"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back
                </button>
              ) : (
                <div />
              )}

              {step < 3 ? (
                <button
                  type="button"
                  onClick={() => setStep(step + 1)}
                  disabled={!canProceed}
                  className={cn(
                    "btn-primary",
                    !canProceed && "opacity-50 cursor-not-allowed"
                  )}
                >
                  Next
                  <ArrowRight className="h-4 w-4" />
                </button>
              ) : (
                <button
                  type="submit"
                  className="btn-primary"
                >
                  <Check className="h-4 w-4" />
                  Create Raid
                </button>
              )}
            </div>
          </div>

          {/* Preview Panel (Desktop) */}
          <div className="hidden lg:block">
            <div className="sticky top-24">
              <div className="text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-3">
                Discord Preview
              </div>
              <DiscordPreview formData={formData} />
            </div>
          </div>
        </div>
      </form>
    </div>
  );
};

// Step Indicator Component
const StepIndicator: React.FC<{
  num: number;
  label: string;
  icon: React.ElementType;
  active: boolean;
  done: boolean;
  onClick?: () => void;
}> = ({ num, label, icon: Icon, active, done, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={!done}
    className={cn(
      "flex flex-col items-center gap-2 transition-all",
      done && "cursor-pointer",
      active ? "text-[var(--primary)]" : done ? "text-[var(--primary)]" : "text-[var(--muted)]"
    )}
  >
    <div className={cn(
      "w-12 h-12 rounded-xl flex items-center justify-center font-bold transition-all",
      active && "bg-[var(--primary)] text-black shadow-[var(--glow-primary)]",
      done && !active && "bg-[var(--primary)]/20 text-[var(--primary)] border border-[var(--primary)]/30",
      !active && !done && "bg-[var(--surface-0)] border border-[var(--border)]"
    )}>
      {done ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
    </div>
    <span className="text-xs font-bold uppercase tracking-wide">{label}</span>
  </button>
);

// Slot Input Component
const SlotInput: React.FC<{
  label: string;
  name: string;
  value: number;
  onChange: (v: number) => void;
  icon: React.ElementType;
  color: 'blue' | 'emerald' | 'orange' | 'violet';
}> = ({ label, name, value, onChange, icon: Icon, color }) => {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    orange: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/30',
  };

  return (
    <div className="text-center">
      <div className={cn(
        "w-12 h-12 mx-auto mb-3 rounded-xl flex items-center justify-center border",
        colorClasses[color]
      )}>
        <Icon className="h-5 w-5" />
      </div>
      <label className={cn("block text-xs font-black uppercase tracking-wider mb-2", `text-${color}-400`)}>
        {label}
      </label>
      <input
        type="number"
        name={name}
        min="0"
        max="20"
        className="w-full bg-[var(--bg-0)] border border-[var(--border)] rounded-lg px-3 py-3 text-center text-xl font-mono font-bold text-white focus:border-[var(--primary)] outline-none transition-colors"
        value={value}
        onChange={e => onChange(parseInt(e.target.value) || 0)}
      />
    </div>
  );
};

// Role Preview Component
const RolePreview: React.FC<{
  label: string;
  count: number;
  color: 'blue' | 'emerald' | 'orange' | 'violet';
  icon: React.ElementType;
}> = ({ label, count, color, icon: Icon }) => {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/10',
    emerald: 'text-emerald-400 bg-emerald-500/10',
    orange: 'text-orange-400 bg-orange-500/10',
    violet: 'text-violet-400 bg-violet-500/10',
  };

  return (
    <div className={cn(
      "text-center p-3 rounded-xl",
      colorClasses[color]
    )}>
      <Icon className="h-4 w-4 mx-auto mb-1" />
      <div className="text-xl font-bold font-mono text-white">{count}</div>
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</div>
    </div>
  );
};

// Discord Preview Component
const DiscordPreview: React.FC<{ formData: any }> = ({ formData }) => (
  <div className="rounded-xl border border-[var(--border)] bg-[#2f3136] p-4 font-sans text-[#dcddde] shadow-xl">
    <div className="flex items-center gap-3 mb-4">
      <div className="h-10 w-10 rounded-full bg-[var(--secondary)] flex items-center justify-center">
        <Swords className="h-5 w-5 text-white" />
      </div>
      <div>
        <div className="font-bold text-white flex items-center gap-2">
          GuildScout
          <span className="px-1.5 py-0.5 rounded bg-[#5865F2] text-[9px] font-bold text-white">BOT</span>
        </div>
        <div className="text-xs text-[#b9bbbe]">
          Today at {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
        </div>
      </div>
    </div>

    <div className="pl-[52px]">
      <div className="rounded border-l-4 border-[var(--primary)] bg-[#36393f] p-4">
        <div className="font-bold text-white mb-1">{formData.title || "Raid Title"}</div>
        <div className="text-sm text-[#dcddde] mb-3 line-clamp-2">
          {formData.description || "Your description will appear here..."}
        </div>

        <div className="grid grid-cols-2 gap-y-2 text-sm mb-3">
          <div className="text-[#b9bbbe]">Game</div>
          <div className="text-white text-right">{formData.game}</div>
          <div className="text-[#b9bbbe]">Start</div>
          <div className="text-white text-right">
            {formData.raid_date || '--'} {formData.raid_time || '--:--'}
          </div>
        </div>

        <div className="text-[10px] text-[#b9bbbe] uppercase font-bold mb-2 tracking-wide">
          Composition
        </div>
        <div className="space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="text-blue-400 flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5" /> Tank
            </span>
            <span className="font-mono">0/{formData.tanks}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-emerald-400 flex items-center gap-1.5">
              <Heart className="h-3.5 w-3.5" /> Healer
            </span>
            <span className="font-mono">0/{formData.healers}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-orange-400 flex items-center gap-1.5">
              <Sword className="h-3.5 w-3.5" /> DPS
            </span>
            <span className="font-mono">0/{formData.dps}</span>
          </div>
          {formData.bench > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-violet-400 flex items-center gap-1.5">
                <UserPlus className="h-3.5 w-3.5" /> Bench
              </span>
              <span className="font-mono">0/{formData.bench}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  </div>
);

export default CreateRaid;
