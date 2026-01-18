# GuildScout Web UI - Concept

## Goals
- Provide a clean, modern web UI for GuildScout.
- Discord OAuth login with access for Admins + Raid Creator roles.
- Multi-server-ready (per-guild settings and templates stored in DB).
- Full raid overview + creation from the web.
- Optional future: audit logs, exports, advanced analytics.

## Scope (Phase 1)
- Discord OAuth login.
- Guild selection (only guilds where bot is present and user is Admin/Creator).
- Raid overview (open/locked/closed/cancelled), quick actions (lock, close, cancel).
- Raid creation (game/mode/date/time/slots/bench/template).
- Templates management (per guild).
- Settings management (channels, role IDs, toggles) per guild.
- Clean UI (non-default typography, custom styles, responsive layout).

## Architecture

### Backend
- **FastAPI** under `web_api/`.
- SQLite DB for web UI data: `data/web_ui.db`.
- Uses bot token from `config/config.yaml` to query guild membership/roles.
- Uses OAuth `client_id/secret` from `.env`.

### Frontend
- **Server-rendered Jinja templates** under `web_api/templates/`.
- Lightweight JS enhancements under `web_api/static/`.
- React/Vue can be layered in a future phase if desired.

## Data Model (web_ui.db)

### web_sessions
- id (text, primary key)
- user_id (int)
- username (text)
- access_token (text)
- refresh_token (text)
- expires_at (int)
- created_at (int)

### guild_settings
- guild_id (int, primary key)
- name (text)
- raid_channel_id (int)
- guildwar_channel_id (int)
- info_channel_id (int)
- log_channel_id (int)
- participant_role_id (int)
- creator_roles (json)
- timezone (text)
- reminder_hours (json)
- dm_reminder_minutes (json)
- checkin_enabled (bool)
- open_slot_ping_enabled (bool)

### raid_templates
- id (int, primary key)
- guild_id (int)
- name (text)
- tanks (int)
- healers (int)
- dps (int)
- bench (int)
- is_default (bool)

## OAuth Flow
1) User hits `/auth/login`.
2) Redirect to Discord OAuth.
3) Callback `/auth/callback` exchanges code for tokens.
4) Store session in `web_sessions` and set cookie.
5) `/api/me` + `/api/guilds` determine accessible guilds.

## Routes (Phase 1)

Auth
- `GET /auth/login`
- `GET /auth/callback`
- `POST /auth/logout`

Guild UI
- `GET /guilds`
- `GET /guilds/{guild_id}`
- `GET /guilds/{guild_id}/raids/new`
- `POST /guilds/{guild_id}/raids`
- `GET /guilds/{guild_id}/templates`
- `POST /guilds/{guild_id}/templates`
- `POST /guilds/{guild_id}/templates/{template_id}/update`
- `POST /guilds/{guild_id}/templates/{template_id}/delete`
- `GET /guilds/{guild_id}/settings`
- `POST /guilds/{guild_id}/settings`

## UI Pages

- **Login**: Hero panel + OAuth button.
- **Guild Picker**: Cards for each accessible guild.
- **Dashboard**:
  - Upcoming raids list (status chips, quick actions).
  - Create raid button.
- **Create Raid**:
  - Game + Mode.
  - Title + Description.
  - Date/Time picker.
  - Slots and templates.
  - Preview panel.
- **Templates**:
  - Add/edit/delete templates.
  - Set default template.
- **Settings**:
  - Channels and toggles.
  - Roles and reminder settings.

## Milestones

1) **Foundation & Auth**
   - FastAPI app, sessions table, OAuth flow.
   - Guild access checks.

2) **Raid API + Settings**
   - CRUD for raids.
   - Settings + templates endpoints.

3) **Frontend MVP**
   - Login, Guild picker, Dashboard, Create Raid.

4) **Polish & Docs**
   - UI polish, responsive refinements.
   - README + run instructions.

## TODO (Phase 1)
- [x] Create `web_api/` with FastAPI skeleton.
- [x] Implement Discord OAuth + session cookie.
- [x] Implement guild access checks (admin or creator role).
- [x] Implement raid creation + overview pages.
- [x] Implement templates UI and storage.
- [x] Implement settings UI and config sync.
- [x] Design a custom UI theme.
- [x] Add docs and run instructions.
