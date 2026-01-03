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

---

## 🧭 Create a Raid (Creator/Admin/Lead)

### Method A: Button
1) In `#raid-info`, click **"Create raid"**.
2) Enter title + description.
3) Pick date and time via dropdowns (page weeks).
4) Choose slots or a template.
5) Click **"Post raid"**.

### Method B: Command
`/raid-create`

---

## 🧩 Slot Templates

In the slot step you can use **"Switch template"**.
Templates are currently defined in code:

File: `src/commands/raid.py`

```py
SLOT_TEMPLATES = [
    ("Standard", {ROLE_TANK: 2, ROLE_HEALER: 2, ROLE_DPS: 6, ROLE_BENCH: 0}),
    ("Small", {ROLE_TANK: 1, ROLE_HEALER: 1, ROLE_DPS: 3, ROLE_BENCH: 0}),
    ("Large", {ROLE_TANK: 3, ROLE_HEALER: 3, ROLE_DPS: 9, ROLE_BENCH: 2}),
]
```

Tell me if you want different templates.

---

## 👥 Participation / Signups

In the raid post you can sign up via reactions.
You will appear in the participant list with your role.

If **Bench** is available:
- Full role -> automatically bench + DM note.

If **Bench** is full:
- Signup is rejected.

---

## 🧾 Participant Role

Optional participant role:
- Default name: **"Raid Teilnehmer"**
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
Default: raid auto-closes at start time.
Optional: auto-close can be disabled (see config).
Safety: optional close after X hours.

## 🧹 Cleanup

If a raid is **closed or cancelled**, the bot deletes the post
so only open raids remain in the channel. Related reminder posts
are also removed.

---

## 🧰 Management (Buttons in the Raid Post)

Only the creator, admins, or creator roles can manage.

Buttons:
- **✏️ Edit**: update title/description/start time
- **🔒 Lock/Unlock**: lock or reopen signups
- **✅ Close**: close raid manually
- **🛑 Cancel**: cancel raid
- **⏭️ Follow-up**: create a new raid with same title/slots (only time needed)
- **⚙️ Slots**: adjust slot counts (bench auto-promotes)

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
  dm_reminder_minutes: [15]
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
