import React from 'react';
import { useTranslation } from 'react-i18next';
import { Settings as SettingsIcon, Save, Database, Shield, BarChart, Server, Bell, Key, Users, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SettingsProps {
  data: {
    guild: any;
    settings: any;
    control: any;
  };
}

const Settings: React.FC<SettingsProps> = ({ data }) => {
  const { t } = useTranslation();
  const { guild, settings, control } = data;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between pb-6 border-b border-[var(--border)]">
        <div>
          <h1 className="text-3xl font-heading font-bold text-white tracking-tight">Control Center</h1>
          <p className="text-[var(--muted)] mt-1">Manage raid operations and system configurations.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8">
        
        {/* Raid Operations */}
        <ConfigSection title="Raid Operations" icon={Database} description="Channels, roles, and scheduling logic.">
            <form action={`/guilds/${guild.id}/settings`} method="POST" className="space-y-6">
                <input type="hidden" name="return_to" value="settings" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Input label="Raid Channel ID" name="raid_channel_id" defaultValue={settings.raid_channel_id} />
                    <Input label="Guildwar Channel ID" name="guildwar_channel_id" defaultValue={settings.guildwar_channel_id} />
                    <Input label="Info Channel ID" name="info_channel_id" defaultValue={settings.info_channel_id} />
                    <Input label="Log Channel ID" name="log_channel_id" defaultValue={settings.log_channel_id} />
                    <Input label="Participant Role ID" name="participant_role_id" defaultValue={settings.participant_role_id} />
                    <Input label="Creator Role IDs (comma)" name="creator_roles" defaultValue={settings.creator_roles?.join(', ')} />
                    <Input label="Timezone" name="timezone" defaultValue={settings.timezone} />
                    <Input label="Auto-close (hours)" name="auto_close_after_hours" defaultValue={settings.auto_close_after_hours} type="number" />
                </div>
                
                <div className="flex flex-wrap gap-6 pt-4 border-t border-[var(--border)]">
                    <Toggle label="Enable Check-in Flow" name="checkin_enabled" defaultChecked={settings.checkin_enabled} />
                    <Toggle label="Enable Open-slot Pings" name="open_slot_ping_enabled" defaultChecked={settings.open_slot_ping_enabled} />
                    <Toggle label="Auto-close at Start" name="auto_close_at_start" defaultChecked={settings.auto_close_at_start} />
                </div>

                <div className="flex justify-end pt-4">
                    <SaveButton />
                </div>
            </form>
        </ConfigSection>

        {/* Raid System (Advanced) */}
        <ConfigSection title="Raid System (Advanced)" icon={Server} description="Enable/disable raids and control stored message IDs.">
            <form action={`/guilds/${guild.id}/config`} method="POST" className="space-y-6">
                <input type="hidden" name="section" value="raid_system" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Input label="Manage Channel ID" name="manage_channel_id" defaultValue={control.raid_system.manage_channel_id} />
                    <Input label="Info Message ID" name="info_message_id" defaultValue={control.raid_system.info_message_id} />
                    <Input label="History Message ID" name="history_message_id" defaultValue={control.raid_system.history_message_id} />
                </div>
                <div className="pt-4 border-t border-[var(--border)]">
                    <Toggle label="Raid System Enabled" name="raid_enabled" defaultChecked={control.raid_system.enabled} />
                </div>
                <div className="flex justify-end pt-4">
                    <SaveButton />
                </div>
            </form>
        </ConfigSection>

        {/* Scoring */}
        <ConfigSection title="Scoring Weights" icon={BarChart} description="Weights should sum to 1.0 for ranking accuracy.">
            <form action={`/guilds/${guild.id}/config`} method="POST" className="space-y-6">
                <input type="hidden" name="section" value="scoring" />
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Input label="Days Weight" name="weight_days" defaultValue={control.scoring.days_in_server} />
                    <Input label="Messages Weight" name="weight_messages" defaultValue={control.scoring.message_count} />
                    <Input label="Voice Weight" name="weight_voice" defaultValue={control.scoring.voice_activity} />
                    <Input label="Min Messages" name="min_messages" defaultValue={control.scoring.min_messages} />
                    <Input label="Max Lookback (days)" name="max_days_lookback" defaultValue={control.scoring.max_days_lookback} />
                </div>
                <div className="flex justify-end pt-4">
                    <SaveButton />
                </div>
            </form>
        </ConfigSection>

        {/* Permissions */}
        <ConfigSection title="Permissions" icon={Shield} description="Admins and override users for system commands.">
            <form action={`/guilds/${guild.id}/config`} method="POST" className="space-y-6">
                <input type="hidden" name="section" value="permissions" />
                <div className="grid grid-cols-1 gap-6">
                    <Input label="Admin Role IDs (comma)" name="admin_roles" defaultValue={control.permissions.admin_roles} />
                    <Input label="Admin User IDs (comma)" name="admin_users" defaultValue={control.permissions.admin_users} />
                </div>
                <div className="flex justify-end pt-4">
                    <SaveButton />
                </div>
            </form>
        </ConfigSection>

      </div>
    </div>
  );
};

const ConfigSection = ({ title, icon: Icon, description, children }: any) => (
    <div className="panel-glass p-0 overflow-hidden">
        <div className="bg-[var(--surface-2)] px-6 py-4 border-b border-[var(--border)] flex items-center gap-3">
            <div className="p-2 rounded bg-[var(--primary)]/10 text-[var(--primary)]">
                <Icon className="h-5 w-5" />
            </div>
            <div>
                <h3 className="font-bold text-white text-lg">{title}</h3>
                <p className="text-[var(--muted)] text-sm">{description}</p>
            </div>
        </div>
        <div className="p-6">
            {children}
        </div>
    </div>
)

const Input = ({ label, name, defaultValue, type = "text" }: any) => (
    <div className="space-y-2">
        <label className="text-xs font-bold uppercase text-[var(--muted)] tracking-wider">{label}</label>
        <input 
            type={type} 
            name={name} 
            defaultValue={defaultValue} 
            className="w-full bg-[var(--bg-0)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-white focus:ring-2 focus:ring-[var(--primary)]/50 focus:border-[var(--primary)] outline-none transition-all font-mono text-sm"
        />
    </div>
)

const Toggle = ({ label, name, defaultChecked }: any) => (
    <label className="flex items-center gap-3 cursor-pointer group">
        <div className="relative">
            <input type="checkbox" name={name} defaultChecked={defaultChecked} className="peer sr-only" />
            <div className="w-11 h-6 bg-[var(--bg-0)] border border-[var(--border)] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-[var(--muted)] after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--primary)] peer-checked:after:bg-white group-hover:border-[var(--primary)]/50"></div>
        </div>
        <span className="text-sm font-medium text-white group-hover:text-[var(--primary)] transition-colors">{label}</span>
    </label>
)

const SaveButton = () => (
    <button type="submit" className="flex items-center gap-2 bg-[var(--primary)] text-black px-6 py-2.5 rounded-lg font-bold shadow-[var(--glow-primary)] hover:bg-[var(--primary)]/90 hover:scale-105 transition-all uppercase tracking-wide text-sm">
        <Save className="h-4 w-4" />
        Save Changes
    </button>
)

export default Settings;
