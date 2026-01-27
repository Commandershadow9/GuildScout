# GuildScout Web UI - Concept & Implementation

**Version:** 2.0
**Status:** Phase 1 & 2 Complete
**Last Updated:** 2026-01-27

---

## Goals

- Provide a clean, modern web UI for GuildScout.
- Discord OAuth login with access for Admins + Raid Creator roles.
- Multi-server-ready (per-guild settings and templates stored in DB).
- Full raid overview + creation from the web.
- Member rankings and analytics with real data from the bot's database.
- Real-time updates via WebSocket.
- Mobile-responsive design.

---

## Implementation Status

### Phase 1: Foundation (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| Discord OAuth | ✅ Complete | Login, session management, token handling |
| Guild Selection | ✅ Complete | Shows guilds where user is admin/creator |
| Raid Overview | ✅ Complete | Open/locked raids with quick actions |
| Raid Creation | ✅ Complete | Game/mode/date/time/slots/templates |
| Templates | ✅ Complete | CRUD operations, per-guild storage |
| Settings | ✅ Complete | Channels, roles, toggles per guild |
| Custom UI Theme | ✅ Complete | Dark theme, gaming aesthetic |

### Phase 2: Analytics & Real-time (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| Analytics API | ✅ Complete | Rankings, activity overview |
| Analytics Page | ✅ Complete | Charts, stats, CSV export |
| Members Page | ✅ Complete | Full ranking table, pagination |
| My Score Page | ✅ Complete | Personal score breakdown |
| WebSocket Server | ✅ Complete | Real-time event broadcasting |
| WebSocket Client | ✅ Complete | React hook with auto-reconnect |
| Activity Feed | ✅ Complete | Real data from raids.db |
| Mobile Responsive | ✅ Complete | Collapsible sidebar, touch-friendly |
| Multi-Guild Isolation | ✅ Complete | Guild-filtered queries |

---

## Architecture

### Backend

- **Framework:** FastAPI (`web_api/app.py`)
- **Database:** SQLite for web data (`data/web_ui.db`)
- **Bot Data:** Read-only access to `data/messages.db` and `data/raids.db`
- **Authentication:** Discord OAuth2 with session cookies
- **Real-time:** WebSocket endpoint at `/ws`

### Frontend

- **Framework:** React 19 + TypeScript + Vite
- **Styling:** Tailwind CSS + custom CSS variables
- **Components:** Radix UI primitives
- **i18n:** react-i18next (EN/DE)
- **State:** React Context for WebSocket
- **Charts:** Recharts

### File Structure

```
web_api/
├── app.py                    # FastAPI main application
├── config.py                 # Configuration loading
├── db.py                     # Database models and store
├── discord_client.py         # Discord API wrapper
├── analytics_api.py          # Analytics service (NEW)
├── activity_api.py           # Activity feed service (NEW)
├── websocket_manager.py      # WebSocket handling (NEW)
│
├── templates/                # Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── guilds.html
│   ├── dashboard.html
│   ├── analytics.html
│   ├── members.html          # NEW
│   ├── my_score.html         # NEW
│   ├── templates.html
│   ├── settings.html
│   ├── raid_create.html
│   └── raid_edit.html
│
├── static/
│   └── dist/                 # Built React app
│
└── ui/                       # React frontend source
    ├── src/
    │   ├── main.tsx
    │   ├── index.css
    │   ├── pages/
    │   │   ├── Dashboard.tsx
    │   │   ├── Analytics.tsx
    │   │   ├── Members.tsx    # NEW
    │   │   ├── MyScore.tsx    # NEW
    │   │   ├── Templates.tsx
    │   │   └── Settings.tsx
    │   ├── components/
    │   │   ├── AppShell.tsx
    │   │   ├── PageTransition.tsx
    │   │   └── ui/
    │   ├── hooks/
    │   │   └── useWebSocket.ts  # NEW
    │   ├── context/
    │   │   └── WebSocketContext.tsx  # NEW
    │   ├── lib/
    │   │   └── utils.ts
    │   └── locales/
    │       ├── en.json
    │       └── de.json
    └── package.json
```

---

## Data Model

### web_ui.db

#### web_sessions
| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT PK | UUID session identifier |
| user_id | INTEGER | Discord user ID |
| username | TEXT | Discord username |
| avatar | TEXT | Avatar hash |
| access_token | TEXT | Discord OAuth token |
| refresh_token | TEXT | OAuth refresh token |
| expires_at | INTEGER | Token expiration timestamp |
| created_at | INTEGER | Session creation timestamp |

#### guild_settings
| Column | Type | Description |
|--------|------|-------------|
| guild_id | INTEGER PK | Discord guild ID |
| name | TEXT | Guild name |
| raid_channel_id | INTEGER | Raid post channel |
| guildwar_channel_id | INTEGER | Guild war channel |
| info_channel_id | INTEGER | Info channel |
| log_channel_id | INTEGER | Log channel |
| participant_role_id | INTEGER | Raid participant role |
| creator_roles | JSON | Role IDs that can create raids |
| timezone | TEXT | Guild timezone |
| reminder_hours | JSON | Reminder schedule |
| dm_reminder_minutes | JSON | DM reminder schedule |
| checkin_enabled | BOOLEAN | Check-in feature toggle |
| open_slot_ping_enabled | BOOLEAN | Open slot ping toggle |

#### raid_templates
| Column | Type | Description |
|--------|------|-------------|
| template_id | INTEGER PK | Auto-increment ID |
| guild_id | INTEGER | Discord guild ID |
| name | TEXT | Template name |
| tanks | INTEGER | Number of tanks |
| healers | INTEGER | Number of healers |
| dps | INTEGER | Number of DPS |
| bench | INTEGER | Number of bench |
| is_default | BOOLEAN | Default template flag |

---

## API Routes

### Authentication
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/auth/login` | Redirect to Discord OAuth |
| GET | `/auth/callback` | OAuth callback handler |
| POST | `/auth/logout` | Logout and clear session |

### Pages (HTML)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/guilds` | Guild selection page |
| GET | `/guilds/{id}` | Dashboard with raids |
| GET | `/guilds/{id}/analytics` | Analytics page |
| GET | `/guilds/{id}/members` | Member rankings |
| GET | `/guilds/{id}/my-score` | Personal score |
| GET | `/guilds/{id}/templates` | Template management |
| GET | `/guilds/{id}/settings` | Guild settings |
| GET | `/guilds/{id}/raids/new` | Create raid form |
| GET | `/guilds/{id}/raids/{rid}/edit` | Edit raid form |

### API (JSON)
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/guilds/{id}/analytics/rankings` | Member rankings with scores |
| GET | `/api/guilds/{id}/analytics/overview` | Activity statistics |
| GET | `/api/guilds/{id}/members/{uid}/score` | Specific member score |
| GET | `/api/guilds/{id}/my-score` | Current user's score |
| GET | `/api/guilds/{id}/status` | System status |
| GET | `/api/guilds/{id}/activity` | Activity feed events |

### WebSocket
| Route | Description |
|-------|-------------|
| `/ws` | Real-time event stream |

#### WebSocket Events
```typescript
type EventType =
  | 'raid:created'
  | 'raid:updated'
  | 'raid:signup'
  | 'raid:closed'
  | 'raid:locked'
  | 'raid:unlocked'
  | 'activity:new'
  | 'system:status'
  | 'system:health'
  | 'connection:established'
  | 'ping'
  | 'pong';
```

---

## Security

### Authentication Flow

1. User clicks "Login with Discord"
2. Redirect to Discord OAuth (`/auth/login`)
3. Discord redirects back with code (`/auth/callback`)
4. Server exchanges code for tokens
5. Create session in `web_sessions`
6. Set signed session cookie
7. Subsequent requests validate session

### Guild Access Control

```python
async def _require_guild_access(request, guild_id):
    """Verify user has access to the guild."""
    session = await _require_session(request)
    if not session:
        return None, None, {"error": "Unauthorized"}

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return session, None, {"error": "Guild not accessible"}

    return session, guild, None
```

### Multi-Guild Isolation

- All database queries include `WHERE guild_id = ?`
- WebSocket subscriptions filtered by accessible guilds
- Session validation on every API request
- No cross-guild data leakage

---

## Scoring Algorithm

The web UI displays scores calculated with the same algorithm as the bot:

```
1. Normalize values to 0-100 scale:
   days_score = (user_days / max_days) × 100
   msg_score  = (user_messages / max_messages) × 100
   voice_score = (user_voice_seconds / max_voice_seconds) × 100

2. Apply configured weights (default):
   - 10% Days in Server (loyalty)
   - 55% Message Activity (engagement)
   - 35% Voice Activity (presence)

3. Calculate final score:
   final = (days_score × 0.10) + (msg_score × 0.55) + (voice_score × 0.35)
```

---

## Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm or pnpm

### Setup

```bash
# Backend dependencies
pip install -r web_api/requirements.txt

# Frontend dependencies
cd web_api/ui
npm install

# Development mode
npm run dev  # Frontend dev server on :5173
WEB_UI_DEBUG=1 python -m web_api.app  # Backend on :8080
```

### Build

```bash
cd web_api/ui
npm run build  # Output to ../static/dist/
```

### Production

```bash
uvicorn web_api.app:app --host 0.0.0.0 --port 8090
```

---

## Future Enhancements (Phase 3+)

- [ ] Bulk role assignment from Members page
- [ ] Raid history with statistics
- [ ] PDF export for rankings
- [ ] Custom report templates
- [ ] Docker deployment
- [ ] API rate limiting
- [ ] Audit logging

---

## Documentation

- `README.md` - Project overview and quick start
- `CHANGELOG.md` - Version history
- `DASHBOARD_IMPLEMENTATION_PLAN.md` - Detailed implementation plan
- `WEB_UI_CONCEPT.md` - This document
