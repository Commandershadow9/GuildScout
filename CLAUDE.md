# GuildScout - Project Instructions for AI Assistants

**Version:** 2.7.0
**Last Updated:** 2026-01-27
**Owner:** cmdshadow

This file contains important project-specific instructions, conventions, and constraints for AI assistants working on GuildScout.

---

## 🎯 Project Overview

**GuildScout** is a production Discord bot for guild management and member ranking based on activity and membership duration, with a full web dashboard for raid management and analytics.

**Core Purpose:**
- Rank Discord users by activity (55% messages, 35% voice, 10% days)
- Manage guild roles and spots
- Track messages across all channels and threads
- Verify data accuracy with scheduled checks
- Web dashboard for raid planning and analytics

**Tech Stack:**
- Python 3.11+
- discord.py 2.3+
- aiosqlite (async SQLite)
- FastAPI (Web API)
- React 19 + TypeScript + Vite (Frontend)
- systemd service management

**Production Status:** ✅ LIVE on JustMemplex Community Discord (1390695394777890897)

---

## 🌐 Web Dashboard

The web dashboard (`web_api/`) provides a full-featured interface for raid management and analytics.

### Architecture

```
web_api/
├── app.py                 # FastAPI main application
├── analytics_api.py       # Score calculation service
├── activity_api.py        # Activity feed service
├── websocket_manager.py   # WebSocket connection handling
├── templates/             # Jinja2 templates
└── ui/                    # React frontend (src/)
```

### Key Files

| File | Purpose | Modify? |
|------|---------|---------|
| `web_api/app.py` | API endpoints, routes | ✅ Add endpoints |
| `web_api/analytics_api.py` | Score calculation | ⚠️ Match bot algorithm |
| `web_api/websocket_manager.py` | Real-time events | ✅ Add event types |
| `web_api/ui/src/pages/*.tsx` | React pages | ✅ UI changes |
| `web_api/ui/src/hooks/useWebSocket.ts` | WS client | ✅ Event handling |

### API Endpoints

```
GET  /api/guilds/{guild_id}/analytics/rankings
GET  /api/guilds/{guild_id}/analytics/overview
GET  /api/guilds/{guild_id}/my-score
GET  /api/guilds/{guild_id}/activity
GET  /api/guilds/{guild_id}/status
WS   /ws
```

### Multi-Guild Security

All API endpoints must use `_require_guild_access()` for consistent access control:

```python
session, guild, error = await _require_guild_access(request, guild_id)
if error:
    return error
```

### Frontend Development

```bash
cd web_api/ui
npm install
npm run dev    # Development server
npm run build  # Production build
```

### Design System - Zentrale Farbverwaltung

Das gesamte UI-Design wird **zentral über CSS-Variablen** in `web_api/ui/src/index.css` gesteuert.

**Datei:** `web_api/ui/src/index.css` (`:root` Sektion)

#### Struktur der Variablen

```
:root
├── CORE PALETTE (5 Basis-Farben - hier ändern für globales Theme)
│   ├── --color-base        #0a0908   Basis-Schwarz
│   ├── --color-dark        #12100d   Dunkler Ton
│   ├── --color-mid         #1a1510   Mittlerer Ton
│   ├── --color-light       #2a1f15   Heller Ton
│   └── --color-highlight   #3d2a1a   Highlight-Ton
│
├── UI COLORS (abgeleitet von Core)
│   ├── --bg-0, --bg-1              Hintergründe
│   ├── --surface-0/1/2             Karten, Panels, Glass-Effekte
│   ├── --border, --border-hover    Ränder
│   ├── --primary, --secondary      Akzentfarben (Gold, Violett)
│   └── --text, --muted             Textfarben
│
├── SCENE COLORS (Hintergrund-Szene mit Kriegern)
│   ├── --scene-sky-top/mid/bottom  Himmel-Gradient
│   ├── --scene-mountain-far/mid/near  Berge (3 Ebenen)
│   ├── --scene-silhouette          Krieger-Silhouetten
│   ├── --scene-castle              Burg
│   ├── --scene-torch-color         Fackel-Licht
│   └── --scene-moon-color          Mond/Sonne
│
└── PARTICLE COLORS (Animationen)
    ├── --ember-color-1/2/3         Funken/Glut
    └── --dust-color                Staubpartikel
```

#### Theme ändern

**Schnelle Änderung:** Ändere die 5 `--color-*` Variablen in der CORE PALETTE - der Rest leitet sich davon ab.

**Feintuning:** Überschreibe spezifische Variablen (Scene, Particles, UI) für detaillierte Kontrolle.

#### Komponenten

| Datei | Verwendet Variablen für |
|-------|------------------------|
| `AnimatedBackground.tsx` | Szene, Partikel (alle `--scene-*`, `--ember-*`) |
| `AppShell.tsx` | Navigation, Layout |
| `pages/*.tsx` | UI-Komponenten, Cards, Buttons |

#### Hintergrund-Szene

Die epische Hintergrund-Illustration (`AnimatedBackground.tsx`) zeigt:
- Berglandschaft mit Burg
- 6 Krieger-Silhouetten (Samurai, Ritter, Bogenschütze, etc.)
- Fackel-Lichteffekte
- Aufsteigende Funken
- Atmosphärischer Nebel

Alle Farben werden über CSS-Variablen gesteuert - keine hardcodierten Werte.

---

## 🚨 CRITICAL: DO NOT TOUCH

These areas are **production-critical** and should NOT be modified without explicit approval:

### 1. Database Schema
**File:** `src/database/message_store.py`

**DO NOT:**
- Change table structure without migration
- Modify indexes without performance testing
- Remove or rename columns
- Change primary keys

**Reason:** 45+ MB production database with historical data

### 2. Message Deduplication
**File:** `src/events/message_tracking.py`
**Lines:** 257-275 (deduplication logic)

```python
# DO NOT MODIFY THIS SECTION
async with self._dedup_lock:
    self._total_messages_seen += 1

    if message.id in self._recent_message_ids:
        self._duplicates_blocked += 1
        # ... deduplication logic
```

**Reason:** Prevents double-counting. 1M message ID cache is carefully tuned.

### 3. Verification Algorithm
**File:** `src/tasks/verification_scheduler.py`
**Function:** `_run_verification_job()`

**DO NOT:**
- Change channel-first algorithm (10x performance)
- Modify self-healing logic without testing
- Change accuracy thresholds (<95% triggers alerts)

**Reason:** Production-tested for accuracy. Self-healing prevents data corruption.

### 4. Config File
**File:** `config/config.yaml`

**DO NOT:**
- Commit config.yaml to Git (contains secrets!)
- Change structure without updating Config class
- Remove backward compatibility

**Protected by:** `.gitignore` and Git Auto-Commit watcher

### 5. Systemd Service
**File:** `scripts/run_bot_service.sh`

**DO NOT:**
- Remove single-instance lock
- Change restart behavior without testing
- Modify environment variables

**Reason:** Prevents duplicate bot instances. Production-critical.

---

## 📐 Coding Standards & Conventions

### 1. Async/Await

**ALWAYS use async:**
```python
# ✅ CORRECT
async def my_function():
    await asyncio.sleep(1)

# ❌ WRONG
def my_function():
    time.sleep(1)  # Blocks event loop!
```

**Reason:** discord.py is async. Blocking calls freeze the bot.

### 2. Error Handling

**Use try/except for external calls:**
```python
# ✅ CORRECT
try:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(query)
except Exception as e:
    logger.error(f"Database error: {e}", exc_info=True)
    return None

# ❌ WRONG
async with aiosqlite.connect(db_path) as db:
    cursor = await db.execute(query)  # Unhandled exceptions!
```

**NEVER catch:**
- `Exception` without re-raising critical errors
- `BaseException` (catches KeyboardInterrupt!)

### 3. Logging

**Use structured logging:**
```python
# ✅ CORRECT
logger.info(f"Verification completed: {accuracy:.1f}% accuracy, {total_users} users")

# ❌ WRONG
print("Verification done")  # Not logged, no context
```

**Log Levels:**
- `DEBUG`: Verbose details (deduplication hits, cache lookups)
- `INFO`: Important events (verification start/end, alerts sent)
- `WARNING`: Issues that don't stop execution (health alerts)
- `ERROR`: Failures requiring attention (database errors)

### 4. Performance Tracking

**Use @track_performance for important operations:**
```python
from src.utils.performance_decorator import track_performance

@track_performance("verification_job")
async def _run_verification_job(self, ...):
    # Automatically tracked in /profile command
    pass
```

**Track these:**
- Verification jobs
- Database operations >100ms
- API calls (Discord, webhooks)
- Heavy computations

**DON'T track:**
- Event handlers (on_message - too frequent)
- Getters/setters
- Simple functions <10ms

### 5. Type Hints

**Use type hints for clarity:**
```python
# ✅ CORRECT
async def get_user_score(self, user_id: int) -> Optional[float]:
    return score

# ⚠️ ACCEPTABLE (complex types)
async def complex_function(self, data: dict) -> dict:
    return result
```

### 6. Database Transactions

**ALWAYS use async context managers:**
```python
# ✅ CORRECT
async with aiosqlite.connect(db_path) as db:
    await db.execute(query, params)
    await db.commit()

# ❌ WRONG
db = await aiosqlite.connect(db_path)
await db.execute(query)
# Forgot to close!
```

### 7. Discord Rate Limits

**Be mindful of rate limits:**
```python
# ✅ CORRECT - Batch operations
await channel.send(embed=combined_embed)

# ❌ WRONG - Multiple rapid calls
for user in users:
    await channel.send(f"{user.name}")  # Rate limit!
```

**Use:**
- `discord.utils.sleep_until()` for scheduled tasks
- Batch embeds when possible
- Monitor with Rate Limit Monitor

---

## 🏗️ Architecture Principles

### 1. Separation of Concerns

**Structure:**
```
src/
  commands/       # Slash commands (user interaction)
  events/         # Discord event handlers
  tasks/          # Background tasks (@tasks.loop)
  database/       # Database layer
  analytics/      # Business logic (scoring, ranking)
  utils/          # Utilities, helpers
```

**NEVER:**
- Put business logic in commands (use analytics/)
- Put database code in event handlers (use database/)
- Mix concerns (e.g., sending Discord messages in database layer)

### 2. Cog Pattern

**ALL features are Cogs:**
```python
class MyFeature(commands.Cog):
    def __init__(self, bot: commands.Bot, config: Config):
        self.bot = bot
        self.config = config

    def cog_unload(self):
        # Cleanup resources
        pass

async def setup(bot: commands.Bot, config: Config):
    await bot.add_cog(MyFeature(bot, config))
```

**Benefits:**
- Hot-reload support
- Resource cleanup
- Modular architecture

### 3. Configuration

**Access config via self.config:**
```python
# ✅ CORRECT
if self.config.shadowops_enabled:
    await self.send_alert()

# ❌ WRONG
import yaml
config = yaml.load(...)  # Don't reload config!
```

**Config is singleton, loaded once at startup.**

### 4. State Management

**Avoid global state:**
```python
# ❌ WRONG - Global variable
message_count = 0

class MyCog:
    async def on_message(self):
        global message_count
        message_count += 1

# ✅ CORRECT - Instance variable
class MyCog:
    def __init__(self):
        self.message_count = 0

    async def on_message(self):
        self.message_count += 1
```

---

## 🔐 Security Best Practices

### 1. Secrets Management

**NEVER commit secrets:**
```python
# ❌ WRONG
TOKEN = "MTQzODc3Mzk3NDM0Njc2MDI4Ng.Gfai9D..."

# ✅ CORRECT
TOKEN = config.discord_token  # From config.yaml (gitignored)
```

**Secrets in:**
- `config/config.yaml` (gitignored)
- Environment variables (systemd service)

### 2. Input Validation

**Validate all user input:**
```python
# ✅ CORRECT
if not isinstance(spot_count, int) or spot_count < 1 or spot_count > 1000:
    await interaction.response.send_message("Invalid spot count", ephemeral=True)
    return

# ❌ WRONG
self.max_spots = spot_count  # No validation!
```

### 3. SQL Injection Prevention

**Use parameterized queries:**
```python
# ✅ CORRECT
await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# ❌ WRONG
await db.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### 4. Webhook Security

**Always verify HMAC signatures:**
- GuildScout → ShadowOps uses HMAC-SHA256
- Secret: `webhook_secret` in config
- Header: `X-Webhook-Signature: sha256=<hex>`

**See:** `WEBHOOK_SECURITY.md`

---

## 🧪 Testing Guidelines

### 1. Before Major Changes

**Test locally:**
```bash
# Start bot in test mode
python run.py

# Check logs
tail -f logs/guildscout.log

# Test commands in Discord
/status
/profile
/my-score
```

### 2. Verification Testing

**After verification changes:**
```bash
# Manual verification trigger (if implemented)
# Or wait for scheduled run

# Check accuracy
# Must be ≥95%
```

### 3. Database Changes

**Test with backup:**
```bash
# Backup first
cp data/messages.db data/messages.db.backup

# Test change
python test_migration.py

# Restore if needed
mv data/messages.db.backup data/messages.db
```

### 4. Performance Testing

**Use /profile command:**
- Check for slow operations (>500ms avg)
- Monitor error rates
- Verify bottlenecks are addressed

---

## 📊 Monitoring & Alerts

### Health Monitoring

**Monitor every 5 minutes:**
- Verification health (>8h since last = alert)
- Rate limits (critical if >20 req/s)
- Database size (warn if >100MB)
- ShadowOps integration (warn if offline >30min)

**Alert Cooldowns:**
- Prevent spam with cooldown periods
- Defined in `src/tasks/health_monitor.py`

### Performance Profiling

**Use /profile to find:**
- Slowest operations (optimize if >1s avg)
- Most called operations (optimize if >10k calls)
- Bottlenecks (slow + frequent = critical)

### Weekly Reports

**Every Monday 09:00 UTC:**
- Activity summary
- Top users/channels
- System performance
- Database health

---

## 🔄 Deployment Process

### 1. Pre-Deployment Checklist

Before deploying to production:

- [ ] All tests pass
- [ ] Documentation updated (CHANGELOG.md, README.md)
- [ ] Config changes documented
- [ ] Database migrations tested
- [ ] Breaking changes noted
- [ ] Rollback plan prepared

### 2. Deployment Steps

```bash
# 1. Pull latest code
cd /home/cmdshadow/GuildScout
git pull origin main

# 2. Update dependencies (if changed)
pip install -r requirements.txt

# 3. Run migrations (if any)
# python scripts/migrate.py

# 4. Restart service
systemctl --user restart guildscout-bot.service

# 5. Verify startup
tail -f logs/guildscout.log

# 6. Test critical commands
# /status, /my-score
```

### 3. Rollback Procedure

```bash
# 1. Stop service
systemctl --user stop guildscout-bot.service

# 2. Checkout previous version
git checkout HEAD~1

# 3. Restore database (if needed)
cp backups/messages.db.YYYY-MM-DD data/messages.db

# 4. Restart
systemctl --user start guildscout-bot.service
```

---

## 📝 Documentation Standards

### Code Comments

**When to comment:**
```python
# ✅ GOOD - Explains WHY
# Deduplicate messages to prevent double-counting when Discord
# sends duplicate events during high load
if message.id in self._recent_message_ids:
    return

# ❌ BAD - Explains WHAT (code already shows this)
# Check if message ID is in recent message IDs
if message.id in self._recent_message_ids:
    return
```

### Docstrings

**Use for public methods:**
```python
async def run_verification(self, sample_size: int) -> dict:
    """
    Run verification check comparing DB with Discord API.

    Args:
        sample_size: Number of random users to verify

    Returns:
        dict: {
            'accuracy_percent': float,
            'total_checked': int,
            'discrepancies': int,
            'healed': int
        }
    """
```

### File Headers

**Include purpose for new files:**
```python
"""
Health monitoring system for GuildScout.

Monitors system health every 5 minutes:
- Verification health
- Rate limits
- Database size
- ShadowOps integration

Sends alerts to Discord and ShadowOps on issues.
"""
```

---

## 🎨 Discord UI Guidelines

### Embeds

**Use colors consistently:**
```python
# Success / Healthy
discord.Color.green()

# Warning / Attention needed
discord.Color.orange()

# Error / Critical
discord.Color.red()

# Info / Neutral
discord.Color.blue()
```

**Limit fields:**
- Max 25 fields per embed
- Max 1024 chars per field value
- Max 6000 chars total

### Ephemeral Messages

**Use ephemeral for:**
- Errors (user mistakes)
- Personal data (/my-score)
- Admin confirmations

**Public for:**
- Status updates
- Rankings
- Reports

---

## 🐛 Common Pitfalls & Solutions

### 1. Race Conditions

**Problem:** Bot starts tasks before ready
**Solution:** Use `await bot.wait_until_ready()` in @tasks.loop

```python
@tasks.loop(hours=6)
async def verification_task(self):
    await self.bot.wait_until_ready()  # ← Essential!
    # ... rest of task
```

### 2. Memory Leaks

**Problem:** Deques/caches grow unbounded
**Solution:** Use `maxlen` parameter

```python
# ✅ CORRECT
self._recent_ids = deque(maxlen=1_000_000)

# ❌ WRONG
self._recent_ids = deque()  # Grows forever!
```

### 3. Blocking Calls

**Problem:** Sync operations block event loop
**Solution:** Use `run_in_executor` for sync code

```python
# ✅ CORRECT
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, sync_function, arg)

# ❌ WRONG
result = sync_function(arg)  # Blocks!
```

### 4. Config Caching

**Problem:** Config changes not applied without restart
**Solution:** Git Auto-Commit tracks changes, but restart needed

**Note:** Hot-reload not supported for config changes.

---

## 🔧 Useful Commands & Snippets

### Debugging

```bash
# Live logs
tail -f logs/guildscout.log

# Service status
systemctl --user status guildscout-bot.service

# Restart bot
systemctl --user restart guildscout-bot.service

# Database size
ls -lh data/messages.db

# Git history
git log --oneline -10

# Config diff
git diff config/config.yaml
```

### Database Queries

```bash
# Open database
sqlite3 data/messages.db

# Count messages
SELECT COUNT(*) FROM messages;

# Top users
SELECT user_id, COUNT(*) as count
FROM messages
GROUP BY user_id
ORDER BY count DESC
LIMIT 10;

# Database size
SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb
FROM pragma_page_count(), pragma_page_size();
```

---

## 📚 Key Documentation Files

**Read these first:**
- `README.md` - Project overview, features
- `CHANGELOG.md` - Version history
- `MONITORING.md` - Health monitoring, performance profiling
- `WEBHOOK_SECURITY.md` - Webhook security implementation

**For specific tasks:**
- `GUILD_MANAGEMENT_GUIDE.md` - Guild management features
- `PRE_DEPLOYMENT_CHECKLIST.md` - Deployment checklist
- `RELEASE_NOTES_v2.3.0.md` - Latest version details

---

## ⚡ Quick Reference

### Most Important Files (Bot)

| File | Purpose | Modify? |
|------|---------|---------|
| `src/bot.py` | Main bot entry point | ⚠️ Carefully |
| `src/events/message_tracking.py` | Message counting | 🚫 Core logic |
| `src/tasks/verification_scheduler.py` | Verification | 🚫 Algorithm |
| `src/database/message_store.py` | Database layer | 🚫 Schema |
| `src/tasks/health_monitor.py` | Health checks | ✅ Add checks |
| `config/config.yaml` | Configuration | ✅ Settings only |

### Most Important Files (Web API)

| File | Purpose | Modify? |
|------|---------|---------|
| `web_api/app.py` | FastAPI endpoints | ✅ Add routes |
| `web_api/analytics_api.py` | Score calculation | ⚠️ Match bot |
| `web_api/websocket_manager.py` | Real-time events | ✅ Add events |
| `web_api/ui/src/pages/*.tsx` | React pages | ✅ UI changes |
| `web_api/ui/src/components/AppShell.tsx` | Navigation | ✅ Add pages |

### Performance Targets

| Metric | Target | Alert At |
|--------|--------|----------|
| Verification Accuracy | ≥95% | <95% |
| Database Size | <100 MB | >100 MB |
| Rate Limits | <10 req/s | >20 req/s |
| Memory Usage | <250 MB | >500 MB |
| Verification Time | <60s | >120s |

### Support Channels

**Logs:** `/home/cmdshadow/GuildScout/logs/`
**Database:** `/home/cmdshadow/GuildScout/data/`
**Backups:** `/home/cmdshadow/GuildScout/backups/`
**Config:** `/home/cmdshadow/GuildScout/config/`
**Web UI:** `/home/cmdshadow/GuildScout/web_api/`

---

**Remember:** This is a production bot serving real users. Prioritize stability over new features. Test thoroughly. Monitor actively. Document everything.

**Version:** 2.6.0 | **Last Updated:** 2026-01-27
