import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Plus,
  Edit,
  Trash2,
  Star,
  Copy,
  Shield,
  Heart,
  Sword,
  UserPlus,
  Layers,
  X,
  Save
} from 'lucide-react';
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
  const { templates } = data;
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  return (
    <div className="max-w-[1200px] mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-[var(--border)]">
        <div>
          <div className="flex items-center gap-2 text-[var(--secondary)] mb-3">
            <Layers className="h-5 w-5" />
            <span className="text-xs font-bold uppercase tracking-widest">{t('templates.title')}</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-heading font-black text-white tracking-tight">
            {t('templates.title')}
          </h1>
          <p className="text-[var(--muted)] mt-2 max-w-xl">
            {t('templates.subtitle')}
          </p>
        </div>

        {/* Create Button - Always visible */}
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary self-start md:self-auto"
        >
          <Plus className="h-4 w-4" />
          {t('templates.create_new')}
        </button>
      </div>

      {/* Templates Grid */}
      {templates.length === 0 && !showCreate ? (
        <EmptyState onCreateClick={() => setShowCreate(true)} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Create New Template Card */}
          {showCreate && (
            <TemplateForm
              guildId={data.guild.id}
              onCancel={() => setShowCreate(false)}
            />
          )}

          {/* Existing Templates */}
          {templates.map((template, index) => (
            editingId === template.template_id ? (
              <TemplateForm
                key={template.template_id}
                template={template}
                guildId={data.guild.id}
                onCancel={() => setEditingId(null)}
              />
            ) : (
              <TemplateCard
                key={template.template_id}
                template={template}
                guildId={data.guild.id}
                index={index}
                onEdit={() => setEditingId(template.template_id)}
                isDeleting={deleteConfirm === template.template_id}
                onDeleteStart={() => setDeleteConfirm(template.template_id)}
                onDeleteCancel={() => setDeleteConfirm(null)}
              />
            )
          ))}
        </div>
      )}
    </div>
  );
};

// Empty State Component
const EmptyState: React.FC<{ onCreateClick: () => void }> = ({ onCreateClick }) => {
  const { t } = useTranslation();

  return (
    <div className="panel-glass p-12 md:p-16 flex flex-col items-center justify-center text-center border-dashed relative">
      <div className="w-20 h-20 bg-[var(--bg-1)] rounded-2xl flex items-center justify-center mb-6 relative z-10">
        <Layers className="h-10 w-10 text-[var(--muted)]" />
      </div>
      <h3 className="text-xl font-bold text-white mb-2 relative z-10">No Templates Yet</h3>
      <p className="text-[var(--muted)] text-sm mb-6 max-w-sm relative z-10">
        Create your first raid composition template for quick deployment.
      </p>
      <button onClick={onCreateClick} className="btn-primary relative z-10">
        <Plus className="h-4 w-4" />
        {t('templates.create_new')}
      </button>
    </div>
  );
};

// Template Card Component
const TemplateCard: React.FC<{
  template: Template;
  guildId: string;
  index: number;
  onEdit: () => void;
  isDeleting: boolean;
  onDeleteStart: () => void;
  onDeleteCancel: () => void;
}> = ({ template, guildId, index, onEdit, isDeleting, onDeleteStart, onDeleteCancel }) => {
  const { t } = useTranslation();
  const totalSlots = template.tanks + template.healers + template.dps;

  return (
    <div
      className="panel-glass group relative overflow-hidden fade-in"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Delete Confirmation Overlay */}
      {isDeleting && (
        <div className="absolute inset-0 bg-[var(--bg-0)]/95 backdrop-blur-sm z-20 flex flex-col items-center justify-center p-6">
          <Trash2 className="h-8 w-8 text-[var(--danger)] mb-4" />
          <p className="text-white font-bold text-center mb-2">{t('templates.delete_confirm')}</p>
          <p className="text-[var(--muted)] text-sm text-center mb-6">{template.name}</p>
          <div className="flex gap-3">
            <button onClick={onDeleteCancel} className="btn-ghost">
              Cancel
            </button>
            <form action={`/guilds/${guildId}/templates/${template.template_id}/delete`} method="POST">
              <input type="hidden" name="return_to" value="templates" />
              <button type="submit" className="btn-primary bg-[var(--danger)] shadow-none hover:bg-[var(--danger-light)]">
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="p-4 border-b border-[var(--border)] flex items-center justify-between relative z-10">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-[var(--secondary)]/15 flex items-center justify-center text-[var(--secondary)]">
            <Layers className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h3 className="font-bold text-white truncate">{template.name}</h3>
            <div className="flex items-center gap-2">
              {template.is_default && (
                <span className="badge badge-pending">
                  <Star className="h-3 w-3 mr-1" />
                  {t('templates.default_badge')}
                </span>
              )}
              <span className="text-xs text-[var(--muted)] font-mono">{totalSlots} slots</span>
            </div>
          </div>
        </div>

        {/* Actions - Always visible on mobile */}
        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="btn-icon md:opacity-0 md:group-hover:opacity-100 transition-opacity"
            title={t('actions.edit')}
          >
            <Edit className="h-4 w-4" />
          </button>
          <button
            onClick={onDeleteStart}
            className="btn-icon md:opacity-0 md:group-hover:opacity-100 transition-opacity hover:text-[var(--danger)] hover:border-[var(--danger)]"
            title={t('actions.delete')}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Composition Grid */}
      <div className="p-4 grid grid-cols-4 gap-3 relative z-10">
        <RoleDisplay icon={Shield} count={template.tanks} label="Tanks" color="blue" />
        <RoleDisplay icon={Heart} count={template.healers} label="Healers" color="emerald" />
        <RoleDisplay icon={Sword} count={template.dps} label="DPS" color="orange" />
        <RoleDisplay icon={UserPlus} count={template.bench} label="Bench" color="violet" />
      </div>

      {/* Footer Actions */}
      <div className="px-4 pb-4 flex gap-2 relative z-10">
        <a
          href={`/guilds/${guildId}/raids/new?template=${template.template_id}`}
          className="flex-1 btn-ghost text-xs justify-center"
        >
          <Copy className="h-3.5 w-3.5" />
          Use Template
        </a>
        {!template.is_default && (
          <form action={`/guilds/${guildId}/templates/${template.template_id}/default`} method="POST" className="flex-1">
            <input type="hidden" name="return_to" value="templates" />
            <button type="submit" className="w-full btn-ghost text-xs justify-center">
              <Star className="h-3.5 w-3.5" />
              {t('templates.set_default')}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

// Template Form Component
const TemplateForm: React.FC<{
  template?: Template;
  guildId: string;
  onCancel: () => void;
}> = ({ template, guildId, onCancel }) => {
  const { t } = useTranslation();
  const isEdit = !!template;

  const [formData, setFormData] = useState({
    name: template?.name || '',
    tanks: template?.tanks || 2,
    healers: template?.healers || 2,
    dps: template?.dps || 6,
    bench: template?.bench || 0,
  });

  const action = isEdit
    ? `/guilds/${guildId}/templates/${template.template_id}/update`
    : `/guilds/${guildId}/templates`;

  return (
    <div className="panel-gradient relative overflow-hidden">
      <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--primary)]/10 rounded-full blur-3xl -mr-16 -mt-16" />

      <form action={action} method="POST" className="relative z-10">
        <input type="hidden" name="return_to" value="templates" />

        {/* Header */}
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <h3 className="font-bold text-white flex items-center gap-2">
            {isEdit ? <Edit className="h-4 w-4 text-[var(--secondary)]" /> : <Plus className="h-4 w-4 text-[var(--primary)]" />}
            {isEdit ? t('templates.edit_template') : t('templates.create_new')}
          </h3>
          <button type="button" onClick={onCancel} className="btn-icon">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Form Fields */}
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase text-[var(--muted)] tracking-wider mb-2">
              Template Name
            </label>
            <input
              type="text"
              name="name"
              required
              placeholder="e.g. 20-Man Mythic"
              className="input-field"
              value={formData.name}
              onChange={e => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <SlotInput
              label="Tanks"
              name="tanks"
              value={formData.tanks}
              onChange={(v) => setFormData({ ...formData, tanks: v })}
              icon={Shield}
              color="blue"
            />
            <SlotInput
              label="Healers"
              name="healers"
              value={formData.healers}
              onChange={(v) => setFormData({ ...formData, healers: v })}
              icon={Heart}
              color="emerald"
            />
            <SlotInput
              label="DPS"
              name="dps"
              value={formData.dps}
              onChange={(v) => setFormData({ ...formData, dps: v })}
              icon={Sword}
              color="orange"
            />
            <SlotInput
              label="Bench"
              name="bench"
              value={formData.bench}
              onChange={(v) => setFormData({ ...formData, bench: v })}
              icon={UserPlus}
              color="violet"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 pb-4 flex gap-2">
          <button type="button" onClick={onCancel} className="flex-1 btn-ghost justify-center">
            {t('actions.cancel')}
          </button>
          <button type="submit" className="flex-1 btn-primary justify-center">
            <Save className="h-4 w-4" />
            {t('actions.save')}
          </button>
        </div>
      </form>
    </div>
  );
};

// Role Display Component
const RoleDisplay: React.FC<{
  icon: React.ElementType;
  count: number;
  label: string;
  color: 'blue' | 'emerald' | 'orange' | 'violet';
}> = ({ icon: Icon, count, label, color }) => {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    orange: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/30',
  };

  return (
    <div className={cn(
      "flex flex-col items-center justify-center p-3 rounded-xl border transition-all",
      colorClasses[color]
    )}>
      <Icon className="h-4 w-4 mb-1" />
      <span className="text-lg font-bold font-mono text-white">{count}</span>
      <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</span>
    </div>
  );
};

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
    blue: 'text-blue-400',
    emerald: 'text-emerald-400',
    orange: 'text-orange-400',
    violet: 'text-violet-400',
  };

  return (
    <div>
      <label className={cn("block text-xs font-bold uppercase tracking-wider mb-2 flex items-center gap-1.5", colorClasses[color])}>
        <Icon className="h-3.5 w-3.5" />
        {label}
      </label>
      <input
        type="number"
        name={name}
        min="0"
        max="20"
        className="w-full bg-[var(--bg-0)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-center text-lg font-mono font-bold text-white focus:border-[var(--primary)] outline-none transition-colors"
        value={value}
        onChange={e => onChange(parseInt(e.target.value) || 0)}
      />
    </div>
  );
};

export default Templates;
