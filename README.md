# 🎮 GuildScout Discord Bot

A Discord bot that ranks users based on **membership duration** and **activity** (message count), providing fair and transparent scoring for guild recruitment or community management.

## 📋 Overview

GuildScout analyzes Discord server members with specific roles and generates rankings based on:
- **40%** Membership Duration (days in server)
- **60%** Activity Level (message count)

Perfect for content creators who need to fairly select members for limited guild spots!

## ✨ Features

### Core Features
- **📊 User Ranking**: Analyze users by role with `/analyze` command
- **🏆 Fair Scoring**: Configurable weights for duration vs. activity
- **📈 Discord Embeds**: Beautiful ranking display with top users
- **📥 CSV Export**: Download complete rankings as CSV
- **⚙️ Configurable**: All settings in YAML config file
- **🔒 Permission System**: Role-based access control
- **⚡ Progress Updates**: Real-time progress during analysis

### Performance & Caching
- **💾 Smart Caching**: SQLite-based cache for blazing-fast repeated analysis
- **🚀 5x Faster**: Channel-first algorithm with parallel processing
- **⚡ Batch Progress**: Real-time batch updates during long operations
- **🔄 Auto-Retry**: Robust rate-limit handling with exponential backoff
- **📊 Cache Stats**: 60-70% hit rate on repeated analyses
- **🧵 Thread Coverage**: Counts messages in text channels *and* all threads (active & archived)

### Guild Management (V2.0)
- **🎮 WWM Release Timer**: Auto-updating countdown (every 10s) with dynamic hype text
- **✅ Interactive Role Assignment**: Button confirmation before mass role changes
- **📊 Guild Status**: View all guild members with scores & CSV export
- **🎯 Auto Spot Management**: Correctly counts all exclusion roles
- **💬 Welcome Messages**: Auto-updating channel info with debouncing
- **🔧 Set Max Spots**: Configure maximum guild size

### User Features
- **📊 /my-score**: Users can check their own ranking and detailed breakdown
- **🏆 Transparent Scoring**: See exactly how your score is calculated
- **📈 Percentile Ranking**: Know where you stand compared to others

### Import & Intelligence
- **🔄 Delta Import**: Der Bot erkennt automatisch, wie lange er offline war, und importiert beim Start nur die verpassten Nachrichten (Delta).
- **♻️ Auto Re-Import**: Bei Erstinstallation oder `force=True` wird ein vollständiger historischer Import durchgeführt.
- **📊 Dashboard**: Zentraler Kanal (`/setup-ranking-channel`) für Rankings, Import-Status und Willkommens-Nachricht.
- **🚨 Status Channel**: Fehlermeldungen und Warnungen landen in einem separaten Kanal (konfigurierbar), inkl. "Acknowledge"-Button für Admins.

### Monitoring & Observability (v2.3.0+)
- **🏥 Health Monitoring**: Automatische Systemüberwachung alle 5 Minuten
  - Verifikations-Gesundheit (Ausfälle, Genauigkeit)
  - Rate Limit Monitoring (Discord API)
  - Datenbank-Gesundheit (Wachstum, Korruption)
  - ShadowOps Integration Status
- **📊 Performance Profiling**: `/profile` Command für Admins
  - Langsamste Operationen
  - Meistgenutzte Operationen
  - Bottleneck-Analyse
  - System-Ressourcen (CPU, RAM, Threads)
- **📈 Enhanced Status**: `/status` Command für alle User
  - Bot Uptime, Memory, Database Size
  - Rate Limits, Verifikations-Status
  - Deduplication Stats, ShadowOps Queue
- **📅 Weekly Reports**: Automatische Wochenberichte (Montag 09:00 UTC)
  - Top 5 User & Channels
  - Verifikations-Zusammenfassung
  - System Performance Metriken
- **💾 Database Monitoring**: Tägliche Size-Überwachung
  - Warnung bei > 100 MB
  - Integration mit wöchentlichem VACUUM

### Security & Configuration (v2.3.0+)
- **🔐 Webhook Security**: HMAC-SHA256 Signature Verification
  - Sichere GuildScout → ShadowOps Kommunikation
  - Schutz vor gefälschten Alerts
  - Constant-time Signatur-Vergleich
- **📝 Git Auto-Commit**: Automatische Config-Versionierung
  - Überwacht `config.yaml` alle 60s
  - Intelligente Commit-Messages
  - Einfaches Rollback via Git

## 🎯 Available Commands

### Admin Commands
- **`/analyze <role>`** - Analyze and rank users with specific role
- **`/assign-guild-role <users>`** - Mass-assign guild role (with confirmation)
- **`/set-max-spots <number>`** - Set maximum guild size
- **`/guild-status`** - View all guild members with scores & export CSV
- **`/setup-ranking-channel`** - Create persistent ranking/dashboard channel
- **`/status`** - Comprehensive system status overview
- **`/profile`** - Performance profiling & bottleneck analysis

### User Commands
- **`/my-score`** - Check your own ranking and score breakdown

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Discord Server with Administrator permissions

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd GuildScout
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the bot**
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

4. **Edit `config/config.yaml`** with your settings:
   - Add your Discord Bot Token
   - Add your Guild (Server) ID
   - Add admin role IDs
   - Adjust scoring weights if needed

5. **Run the bot**
   ```bash
   python run.py
   ```

## 🤖 Setting Up Your Discord Bot

### Creating the Bot Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name (e.g., "GuildScout")
3. Go to the "Bot" tab
4. Click "Add Bot"
5. Under "Privileged Gateway Intents", enable:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
6. Click "Reset Token" and copy your bot token
7. Paste the token into `config/config.yaml` under `discord.token`

### Inviting the Bot to Your Server

1. Go to the "OAuth2" > "URL Generator" tab
2. Select scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Select bot permissions:
   - ✅ Read Messages/View Channels
   - ✅ Read Message History
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Attach Files
   - ✅ Use Slash Commands
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### Getting Your Guild ID

1. Enable Developer Mode in Discord:
   - User Settings > Advanced > Developer Mode (toggle ON)
2. Right-click your server icon
3. Click "Copy Server ID"
4. Paste the ID into `config/config.yaml` under `discord.guild_id`

### Getting Role IDs

1. In Discord, type `\@RoleName` (replace RoleName with your role)
2. Send the message - it will show the role ID like `<@&123456789>`
3. Copy the number (123456789)
4. Add it to `config/config.yaml` under `permissions.admin_roles`

## 📖 Usage

### Dashboard & Status

- **Dashboard Channel**: Richte mit `/setup-ranking-channel` den Dashboard-Kanal ein. Hier postet der Bot automatisch:
  - Rankings (`/analyze` Ergebnisse)
  - Import-Status (Fortschrittsbalken bei Importen)
  - Willkommens-Übersicht mit Guild-Status
- **Status Channel**: In der `config.yaml` kannst du eine `status_channel_id` eintragen (oder manuell erstellen).
  - Hier landen Fehler, Warnungen und fehlgeschlagene Verifikationen.
  - Admins können Fehler mit einem Button bestätigen ("Acknowledged"), woraufhin die Nachricht gelöscht wird.
- **Delta Import**: Wenn der Bot neu startet, prüft er den Zeitstempel der letzten bekannten Nachricht. Liegt diese länger als 1 Minute zurück, startet er einen **Delta-Import** für die Zwischenzeit. Fortschritt wird im Dashboard angezeigt.

### `/analyze` Command

Analyze users with a specific role and generate rankings.

**Syntax:**
```
/analyze role:<@Role> [days:<number>] [top_n:<number>]
```

**Parameters:**
- `role` (required): The Discord role to analyze
- `days` (optional): Only count messages from last X days
- `top_n` (optional): Show only top N users

**Examples:**
```
/analyze role:@GuildApplicants
/analyze role:@Members days:30
/analyze role:@Viewers top_n:50
/analyze role:@Community days:90 top_n:100
```

**Output:**
- Discord embed with top users (configurable, default: top 25)
- CSV file with complete rankings
- Statistics (averages, max/min scores)
- Analysis duration
- Cache statistics (hits/misses for performance tracking)

### `/my-score` Command

Check your own ranking score with detailed breakdown.

**Syntax:**
```
/my-score [role:<@Role>]
```

**Parameters:**
- `role` (optional): Check your score within a specific role

**Examples:**
```
/my-score
/my-score role:@Members
```

**Output:**
- Your current rank and percentile
- Detailed score breakdown (days + activity)
- Transparent calculation formula
- Comparison with all users or role-specific users

### `/verify-message-counts`

Vergleicht die gespeicherten MessageStore-Werte mit frischen Discord-API Zählungen (inkl. Threads).

```
/verify-message-counts sample_size:10
```

- Der Command wählt zufällige User mit ≥10 Nachrichten.
- Fortschritt erscheint als Ephemeral Message.
- Fehler/Abweichungen werden im Status-Channel geloggt.

### Automatisierte Verifikationen

Neben dem manuellen Command laufen zwei Scheduler-Jobs im Hintergrund (konfigurierbar im `verification`-Abschnitt der Config):

- **Tägliche Stichprobe** (Standard 25 User, 03:00 UTC)
- **Wöchentliche Tiefenprüfung** (Standard Montag 04:30 UTC, 150 User)

Beide Jobs:
- werden übersprungen, solange ein Import läuft.
- melden Fehler oder Auffälligkeiten in den **Status-Channel**.
- nutzen ein Alert-Ping (`logging.alert_ping`) bei kritischen Fehlern.

### Guild Management Commands (V2.0)

#### `/assign-guild-role`
Assign guild role to top-ranked users (admin only)

**Syntax:**
```
/assign-guild-role ranking_role:<@Role> count:<number>
```

**Features:**
- Interactive button confirmation
- Shows preview of all affected users
- Prevents accidental mass changes
- 60-second timeout

#### `/guild-status`
View current guild members and spot availability (admin only)

**Shows:**
- Total and available spots
- All guild members with scores (sorted highest first)
- CSV export of all members
- Visual progress bar

#### `/setup-ranking-channel`
Einrichten des **Dashboard-Kanals** (ehemals Ranking Channel). Hier werden Rankings und Status-Updates gepostet.

#### `/set-max-spots`
Set maximum guild spots (admin only)

**Syntax:**
```
/set-max-spots value:<number>
```

#### `/setup-wwm-timer`
Setup Where Winds Meet release countdown timer (admin only)

**Features:**
- Auto-creates dedicated countdown channel
- Updates every 10 seconds
- Dynamic hype text based on time remaining
- Shows both GMT and MEZ time zones
- Progress bar to release

### Admin Commands

#### `/cache-stats`
View cache performance statistics (admin only)

#### `/cache-clear`
Clear the message count cache (admin only)

**Options:**
- `This Guild Only`: Clear cache for current server
- `All Guilds`: Clear entire cache
- `Expired Entries Only`: Remove only expired entries

#### `/bot-info`
View bot information and system statistics (admin only)

**Shows:**
- Bot statistics (guilds, users, uptime)
- System resources (memory, CPU)
- Cache statistics
- Configuration settings

## ⚙️ Configuration

Edit `config/config.yaml` to customize the bot:

### Guild Management (V2.0)

```yaml
guild_management:
  guild_role_id: 1234567890    # The role ID for guild members
  max_guild_spots: 60          # Maximum guild size
  exclusion_roles:             # Roles that reserve spots (leaders, etc.)
    - 9876543210
  exclusion_users:             # Specific users to exclude
    - 1111111111
  dashboard_channel_id: null   # Auto-filled by /setup-ranking-channel
  status_channel_id: null      # For errors/warnings (optional)
```

### Scoring Weights

```yaml
scoring:
  weights:
    days_in_server: 0.4      # 40% weight for membership duration
    message_count: 0.6       # 60% weight for activity
  min_messages: 0            # Users with fewer messages are excluded (0 = no minimum)
```

**Important:** Weights should sum to 1.0!

### Channel Exclusions

```yaml
analytics:
  excluded_channels:         # Exclude specific channel IDs
    - 123456789
  excluded_channel_names:    # Exclude channels with these name patterns
    - "nsfw"
    - "bot-spam"
  cache_ttl: null           # Cache time-to-live (null = infinite)
```

### Permissions

```yaml
permissions:
  admin_roles:               # Role IDs that can use admin commands
    - 987654321
  admin_users:               # User IDs that can use admin commands (overrides roles)
    - 123456789
```

### Logging

```yaml
logging:
  level: "INFO"             # DEBUG, INFO, WARNING, ERROR
  file: "logs/guildscout.log"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  alert_ping: "<@123456789012345678>"      # optionaler Ping bei Fehlern/Abweichungen
  enable_discord_service_logs: true        # false wenn ShadowOps Bot das Monitoring übernimmt
  dashboard_update_interval_seconds: 300   # Dashboard update interval
  dashboard_idle_gap_seconds: 120          # Idle gap for updates

verification:
  enable_daily: true
  daily_sample_size: 25
  daily_hour_utc: 3
  daily_minute: 0
  enable_weekly: true
  weekly_sample_size: 150
  weekly_weekday: 0
  weekly_hour_utc: 4
  weekly_minute: 30
```

## 📊 Scoring Algorithm

The bot uses a **normalized weighted scoring system**:

### Formula

```
1. Normalize values to 0-100 scale:
   days_score = (user_days / max_days_in_dataset) × 100
   activity_score = (user_messages / max_messages_in_dataset) × 100

2. Calculate weighted final score:
   final_score = (days_score × weight_days) + (activity_score × weight_messages)
```

### Example

User A:
- 180 days in server (max in dataset: 365 days)
- 1,200 messages (max in dataset: 2,000 messages)

```
days_score = (180 / 365) × 100 = 49.3
activity_score = (1200 / 2000) × 100 = 60.0

final_score = (49.3 × 0.4) + (60.0 × 0.6) = 19.7 + 36.0 = 55.7
```

## 📁 Project Structure

```
guildscout-bot/
├── src/
│   ├── bot.py                      # Main bot entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   └── analyze.py              # /analyze command implementation
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── role_scanner.py         # Scan users by role
│   │   ├── activity_tracker.py     # Count messages
│   │   ├── scorer.py               # Score calculation
│   │   └── ranker.py               # Ranking/sorting
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── discord_exporter.py     # Discord embed creation
│   │   └── csv_exporter.py         # CSV generation
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py               # Configuration loader
│   │   └── logger.py               # Logging setup
│   └── __init__.py
├── config/
│   ├── config.example.yaml         # Example configuration
│   └── config.yaml                 # Your configuration (gitignored)
├── exports/                        # CSV exports (gitignored)
├── logs/                           # Log files (gitignored)
├── requirements.txt                # Python dependencies
├── run.py                          # Bot runner script
├── .gitignore
└── README.md
```

## 🧪 Testing the Bot

### Initial Test

1. **Start the bot**: `python run.py`
2. **Check logs**: Look for "Bot is ready!" message
3. **Verify commands**: Type `/` in Discord to see if `/analyze` appears

### Test Analysis

1. Create a test role (e.g., "TestRole")
2. Assign it to a few users
3. Run `/analyze role:@TestRole`
4. Verify:
   - Progress updates appear
   - Embed shows top users
   - CSV file is attached
   - Scores make sense

### Common Issues

**Bot doesn't respond to commands:**
- Verify bot has "Use Slash Commands" permission
- Check that commands synced successfully in logs
- Try restarting the bot

**"No permission to read history" errors:**
- Give bot "Read Message History" permission
- Check channel-specific permissions

**All scores are 0:**
- Verify "Message Content Intent" is enabled
- Check that users have sent messages

## 📝 Logs

Logs are saved to `logs/guildscout.log` by default.

**Log Levels:**
- `INFO`: General information (default)
- `DEBUG`: Detailed debugging information
- `WARNING`: Warning messages
- `ERROR`: Error messages

Change log level in `config/config.yaml`:
```yaml
logging:
  level: "DEBUG"  # For more detailed logs
```

## 🤝 Integration with ShadowOps Bot (Centralized Monitoring)

GuildScout can be integrated with [ShadowOps Bot](https://github.com/Commandershadow9/shadowops-bot) for centralized monitoring and notifications.

### Centralized Monitoring Setup (Option B)

When using ShadowOps Bot for centralized monitoring:

1. **Disable GuildScout Self-Reporting:**
   ```yaml
   discord:
     discord_service_logs_enabled: false
   ```

2. **ShadowOps Bot handles:**
   - Git push notifications with AI-generated patch notes
   - Bot status monitoring (online/offline)
   - Error alerts
   - Professional customer-facing updates

3. **Benefits:**
   - No duplicate status messages
   - Professional AI-generated patch notes (Ollama llama3.1)
   - Multi-language support (German/English)
   - Centralized monitoring for all projects
   - Automatic channel setup on customer servers

### How It Works

```
GitHub Push → ShadowOps Bot Webhook
    ↓
AI generates patch notes (llama3.1)
    ↓
Internal embed (German, technical) → Dev server
Customer embed (English, friendly) → Customer server
    ↓
GuildScout updates channel (if configured)
```

### Configuration Example

**ShadowOps Bot `config.yaml`:**
```yaml
projects:
  guildscout:
    enabled: true
    patch_notes:
      language: en
      use_ai: true
    external_notifications:
      - guild_id: 1390695394777890897  # Customer Discord server
        channel_id: 1442887630034440426  # Updates channel
        enabled: true
        notify_on:
          git_push: true
          offline: false
          online: false
          errors: false
```

**GuildScout `config.yaml`:**
```yaml
discord:
  token: YOUR_TOKEN
  guild_id: 1390695394777890897
  discord_service_logs_enabled: false  # ShadowOps handles status
```

### Manual Monitoring Mode

To use GuildScout with independent monitoring:

```yaml
discord:
  discord_service_logs_enabled: true  # GuildScout posts own status
```

This is useful for:
- Standalone deployments without ShadowOps
- Development/testing environments
- Separate monitoring requirements

## 🔒 Security & Privacy

- **Bot Token**: Never share your bot token! It's in `config/config.yaml` which is gitignored
- **Data Storage**: Bot doesn't store user messages, only counts them
- **Privacy**: Bot can only read messages in channels it has access to
- **Permissions**: Use role-based permissions to restrict who can run analysis
- **Centralized Monitoring**: When using ShadowOps, only admins see monitoring channels

## 🛠️ Troubleshooting

### "Configuration file not found"
```bash
cp config/config.example.yaml config/config.yaml
# Then edit config/config.yaml with your settings
```

### "Discord token not configured"
- Edit `config/config.yaml`
- Replace `YOUR_BOT_TOKEN_HERE` with your actual bot token

### "Role not found"
- Make sure you're using the role mention (e.g., `@RoleName`)
- Verify the role exists in your server
- Check for typos in role name

### Analysis is very slow
- **First run**: Normal for large servers with many messages (30-60s for 300 users)
- **Subsequent runs**: Use cache for 10-100x faster analysis (<1s)
- Consider using `days` parameter to limit message history
- Use `/cache-clear expired` to remove old cache entries

## 🚀 Version History

### Version 2.2.0 (2025-11-26) - Current ✅
**Delta Import & Dashboard System**

- **Delta Import**: Smarter imports, catching missed messages during downtime.
- **Dashboard**: Centralized ranking and status display.
- **Status Channel**: Dedicated error/warning channel with admin acknowledgment.
- **Cleanup**: Removed old log channel system.

See [CHANGELOG.md](CHANGELOG.md) for full version history.

### Version 2.0.1 (2025-11-25)
**Integration with ShadowOps Bot**

- ✅ **Centralized Monitoring Support**
- ✅ **Documentation Update**

### Version 2.0.0
**Major Performance, Guild Management & Features Update**

- ✅ **5x Faster Analysis**
- ✅ **Smart Caching**
- ✅ **Guild Management Features**

### Phase 1 (Initial Release)
- ✅ `/analyze` command
- ✅ Fair scoring system

## 🛠️ Service Script

Run the bot with auto-restart on crash:

```bash
./scripts/run_bot_service.sh
```

**Features:**
- Automatic restart on bot crash
- PID file management
- Prevents multiple instances
- Logging to `logs/bot-service.log`

## 📄 License

This project is provided as-is for use in Discord servers.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📞 Support

If you encounter issues:
1. Check the logs in `logs/guildscout.log`
2. Verify your configuration in `config/config.yaml`
3. Ensure bot has proper permissions
4. Check Discord Developer Portal for intent settings

---

**Made with ❤️ for fair guild management**