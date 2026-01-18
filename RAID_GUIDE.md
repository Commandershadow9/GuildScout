# 🗡️ Raid Guide (Where Winds Meet)

This document explains the full raid system in GuildScout:
creation, participation, management, configuration, and troubleshooting.

---

## ✅ Requirements

- Raid feature is enabled (`raid_management.enabled: true`).
- An info post exists (via `/raid-info-setup` or `/raid-setup`).
- Creators have a proper role (Admin or `creator_roles`).

---

## 📌 Roles and Reactions

Raid roles:
- **Tank** (🛡️)
- **Healer** (💉)
- **DPS** (⚔️)
- **Bench** (🪑)

Reactions:
- **🛡️ / 💉 / ⚔️ / 🪑** = sign up
- **❌** = leave

Rules:
- **One role per person**.
- If a role is full, you are moved to **Bench** (if available).
- If **Locked**, only bench is possible.
- Bench preferences can be set (see below).

---

## 🧭 Create a Raid (Creator/Admin/Lead)

### Method A: Button
1) In `#raid-info`, click **"Create raid"**.
2) Enter title + description.
3) Select game + mode.
4) Pick date and time via dropdowns (page weeks).
5) Choose slots or a template.
6) Click **"Post raid"**.

Notes:
- **Mode = Raid** posts in `#raid-ankuendigungen`.
- **Mode = Guildwar** posts in `#guildwar-ankuendigungen`.

### Method B: Command
`/raid-create`

### Method C: Web UI
1) Open the Web UI and pick your guild.
2) Use **Create raid** in the dashboard.
3) Select template + slots, then post.

---

## 🧩 Slot Templates

In the slot step you can use **"Switch template"**.
Templates are stored in the web UI database (`data/web_ui.db`) and can be edited
from the Web UI (Templates page).

Default templates are seeded from `src/database/raid_template_store.py`:

```py
DEFAULT_TEMPLATE_SPECS = [
    {"name": "Standard", "tanks": 2, "healers": 2, "dps": 6, "bench": 0},
    {"name": "Small", "tanks": 1, "healers": 1, "dps": 3, "bench": 0},
    {"name": "Large", "tanks": 3, "healers": 3, "dps": 9, "bench": 2},
]
```

Changes apply immediately for new raid drafts.

---

## 👥 Participation / Signups

In the raid post you can sign up via reactions.
You will appear in the participant list with your role.

If **Bench** is available:
- Full role -> automatically bench + DM note.
- Locked or full -> bench + preferred role saved.

If **Bench** is full:
- Signup is rejected.

Bench preferences:
- When on bench, react with 🛡️/💉/⚔️ to set your preferred role.
- The bot may DM you with buttons to choose your preference.
- If DMs are closed, the bot posts a short prompt in the raid channel
  (auto-deletes after ~10 minutes).
- The raid embed shows your preference icon next to your name.
  - 🛡️ = Tank, 💉 = Healer, ⚔️ = DPS, 🎲 = Any

---

## 🧾 Participant Role

Optional participant role:
- Default name: **"Raid Participants"**
- Created automatically if missing.
- **Granted on signup**.
- **Removed on leave or after raid end**.

Configure role:
`/raid-set-participant-role @Role`

---

## 🔐 Raid Status

Status in embed:
- **Open**: normal signup
- **Locked**: bench only
- **Closed**: raid started/finished
- **Cancelled**: raid was cancelled

Signup status in title:
- **SIGNUPS OPEN** (green): signup possible
- **ALMOST FULL** (yellow): few slots left
- **SIGNUPS CLOSED** (red): closed or full

Auto-close:
Set `auto_close_at_start` to close automatically at start time.
If disabled, raids stay open until manual close or `auto_close_after_hours`.

## 🧹 Cleanup

If a raid is **closed or cancelled**, the bot deletes the post
so only open raids remain in the channel. Related reminder/open-slot
notices are removed as well. Only the newest reminder/open-slot notice
is kept; older ones are deleted automatically. Open-slot notices are
cleared as soon as all slots are filled.
Restart notices auto-delete after ~2 hours.

---

## 🧰 Management (Buttons in the Raid Post)

Only the creator, admins, or creator roles can manage.

Buttons:
- **✏️ Edit**: update title/description/start time
- **🔒 Lock/Unlock**: lock or reopen signups
- **✅ Close**: close raid manually
- **🛑 Cancel**: cancel raid
- **⏭️ Follow-up**: create a new raid with same title/slots (only time needed)
- **⚙️ Slots**: adjust slot counts
- **🪑 Promote**: select role + bench user to move into the raid
  (sends a DM to the user to contact the raid creator)

Optional logging:
- If `log_channel_id` is set, the bot posts a raid summary
  on close/cancel to the log channel.
  It includes role lists and check-in/no-show info.

Participation stats:
- In `#raid-ankuendigungen` there is a **Raid Participation** embed.
- Shows **all-time** top participants with role counts.
- The list is capped (Top 10) and updates automatically.

---

## ⏰ Reminder System

Reminders before start (default: 24h and 1h):
- Posted in the raid channel
- Optional mention of participant role

Open-slot notices (optional):
- Posted when roles open up
- No role mention
- Replaces older notices and is cleared when all slots are filled

DM reminder (default: 15 minutes before start):
- Bot sends a DM to all signed-up participants.

Check-in (default: 15 minutes before start):
- Bot posts a message with ✅
- Participants confirm with reaction
- Embed shows who is still missing

Check-in reminder (default: 5 minutes before start):
- Only **unconfirmed** participants are pinged

No-show marking:
- After start, unconfirmed participants are marked as **No-Show**

Leave reason (optional):
- When someone reacts ❌, they can DM a short reason
- Reason is logged in the log channel (if set)

Config:
```yaml
raid_management:
  reminder_hours: [24, 1]
  dm_reminder_minutes: [15, 5]
  checkin_enabled: true
  open_slot_ping_enabled: true
  notice_delete_minutes: 60
  auto_close_at_start: true
  auto_close_after_hours: 12
  confirmation_minutes: 15
  confirmation_reminder_minutes: 5
  open_slot_ping_minutes: 30
  log_channel_id: null
```

---

## 🧭 Time Display

In the raid embed:
- Discord timestamp (localized for each user)
- German format line
- English format line

This helps mixed time zones.

---

## 🔄 Restart Behavior

- On restart, the bot refreshes active raid embeds and re-attaches buttons.
- Reactions are reconciled against the DB.
  - If a user reacted to multiple roles while the bot was offline,
    they receive a DM to pick one.
- A short offline notice is posted per channel (auto-deletes after ~2 hours).

---

## 📜 Commands (Overview)

**User / Creator**
- `/raid-create` – create a raid (button alternative)
- `/raid-list` – show upcoming raids

**Admin**
- `/raid-setup` – create raid channels + store IDs
- `/raid-set-channel` – set raid channels
- `/raid-info-setup` – create/update info post
- `/raid-add-creator-role` – add creator role
- `/raid-remove-creator-role` – remove creator role
- `/raid-set-participant-role` – set participant role
- `/raid-user-stats` – participation stats for a user

---

## ⚙️ Configuration (config.yaml)

```yaml
raid_management:
  enabled: true
  post_channel_id: 123
  guildwar_post_channel_id: 124
  manage_channel_id: 456
  info_channel_id: 789
  info_message_id: 111
  history_message_id: 112
  participant_role_id: 222
  log_channel_id: null
  creator_roles:
    - 333
  timezone: "Europe/Berlin"
  reminder_hours: [24, 1]
  dm_reminder_minutes: [15]
  auto_close_at_start: true
  auto_close_after_hours: 12
  confirmation_minutes: 15
  confirmation_reminder_minutes: 5
  notice_delete_minutes: 60
  open_slot_ping_minutes: 30
```

---

## 🩹 Troubleshooting

**"This interaction failed"**
- An update/response was too slow.
- Click the button again.

**No post / no reactions**
- Bot is missing permissions in the channel (send, reactions, manage messages).
- Run `raid-setup` or fix permissions.

**Time in the past**
- Date/time must be in the future.

**Role/Bench full**
- Check slot limits in the embed.

---

If you want more features or changes, let me know.
