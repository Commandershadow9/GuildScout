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

### Import & Logging
- **♻️ Auto Re-Import**: On every bot start, GuildScout performs a full historical re-import so counts stay 100% accurate.
- **🧾 Log Channel**: Setup once with `/setup-log-channel` – all lifecycle events and import progress get posted automatically.
- **🟢 Live-Tracking Embed**: Jede neue Nachricht landet sofort in einer dauerhaften Embed im Log-Channel (inkl. Gesamtzähler, letzte Messages, Sprunglinks).
- **🔍 Verifikation**: `/verify-message-counts` samples real Discord API counts mit Live-Fortschritt und automatischem Fallback bei abgelaufenen Follow-ups.
- **📆 Geplante Checks**: Tägliche Stichprobe + wöchentliche Tiefenprüfung laufen im Hintergrund und posten ihre Ergebnisse automatisch ins Log (konfigurierbar).

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

### Historische Importe & Logs

- **Auto-Re-Import**: Bei jedem Bot-Neustart wird automatisch `/import-messages force:true` ausgeführt. Dadurch sind die Datenbank (`data/messages.db`) und der MessageStore immer auf aktuellem Stand (inkl. Threads).
- **Log-Channel**: Richte mit `/setup-log-channel` einen Admin-only Kanal wie `#guildscout-logs` ein. GuildScout erstellt ihn automatisch, falls er fehlt, und postet dort:
  - `🤖 GuildScout gestartet` / `♻️ Reconnected`
  - `📥 Re-Import gestartet` mit Live-Updates (aktueller Kanal, Fortschritt X/Y, importierte Nachrichten, Laufzeit)
  - `✅ Import abgeschlossen` inklusive Dauer und Gesamtnachrichten
- **Live-Update Embed**: Sobald der Import durch ist, bleibt eine Embed „🟢 Live-Tracking aktiv“ im Log-Channel sichtbar. Sie zeigt:
  - Gesamtzahl aller Nachrichten in der Datenbank (`MessageStore`)
  - Anzahl live getrackter Messages seit letztem Bot-Neustart
  - Die letzten 10 Nachrichten inkl. Sprunglink direkt in Discord
  - Automatische Aktualisierung: sofort nach Ruhephasen (konfigurierbarer Idle-Gap), sonst spätestens nach dem eingestellten Intervall.

> Hinweis: Solange der Auto-Import läuft, reagiert das manuelle `/import-status` nicht (Discord blockiert doppelte Commands). Prüfe stattdessen den Log-Channel – dort steht der Fortschritt in Echtzeit.

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

### `/my-score` Command (Phase 2)

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
- Fortschritt erscheint sowohl im Command (Ephemeral Message) als auch im Log-Channel (aktueller User, Kanal, Rate-Limit Hinweise).
- Das Ergebnis-Embed zeigt Accuracy, Max/Average-Differenz und eine Liste aller Abweichungen. Läuft der ursprüngliche Follow-up-Webhook ab (z. B. bei langen Läufen), sendet der Bot automatisch eine neue Embed und loggt das Ergebnis dennoch.

### Automatisierte Verifikationen

Neben dem manuellen Command laufen zwei Scheduler-Jobs im Hintergrund (konfigurierbar im `verification`-Abschnitt der Config):

- **Tägliche Stichprobe** (Standard 25 User, 03:00 UTC): prüft eine zufällige Auswahl aktiver User (≥10 Nachrichten) gegen die Discord-API und postet Start/Ergebnis als Embed.
- **Wöchentliche Tiefenprüfung** (Standard Montag 04:30 UTC, 150 User): größere Stichprobe für maximale Sicherheit.

Beide Jobs:
- werden übersprungen, solange ein Import läuft oder noch keine Daten vorliegen,
- sperren sich gegenseitig per Lock, damit nie zwei Prüfungen parallel laufen,
- loggen sämtliche Statuswechsel (`gestartet`, `übersprungen`, `erfolgreich`, `abweichungen`, `fehler`) im Log-Channel inkl. Accuracy, Max Difference und auffälligen Usern.

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
Create or update the ranking channel (admin only)

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
  ranking_channel_id: null     # Auto-filled by /setup-ranking-channel
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
  discord_channel_id: 123456789012345678   # setzt der Bot via /setup-log-channel
  enable_discord_service_logs: true
  live_tracking_interval_seconds: 3600     # spätestens alle 60 Min. aktualisieren
  live_tracking_idle_gap_seconds: 180      # nach 3 Min. Ruhe sofortiges Update

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

Wenn ein Discord-Log-Channel konfiguriert ist (`/setup-log-channel`), erhältst du zusätzlich:
- Dauerhafte **🟢 Live-Tracking**-Embed mit Gesamtzählung + letzten Nachrichten
- Automatische Embeds für `📥` Re-Import, `🔍` tägliche/ wöchentliche Verifikationen sowie Fehlermeldungen
- Manuelle `/verify-message-counts`-Ergebnisse inklusive Fallback, falls das Follow-up abläuft

## 🔒 Security & Privacy

- **Bot Token**: Never share your bot token! It's in `config/config.yaml` which is gitignored
- **Data Storage**: Bot doesn't store user messages, only counts them
- **Privacy**: Bot can only read messages in channels it has access to
- **Permissions**: Use role-based permissions to restrict who can run analysis

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

### Version 2.0.0 (Current) ✅
**Major Performance, Guild Management & Features Update**

See [CHANGELOG.md](CHANGELOG.md) for detailed changes.

**Performance:**
- ✅ **5x Faster**: Channel-first message counting algorithm
- ✅ **Smart Caching**: Infinite TTL SQLite cache (60-70% hit rate)
- ✅ **Parallel Processing**: Configurable batch parallelism
- ✅ **Robust Rate Limiting**: Auto-retry with exponential backoff

**Guild Management:**
- ✅ **WWM Release Timer**: Auto-updating countdown (10s intervals)
- ✅ **Interactive Role Assignment**: Button confirmation system
- ✅ **Guild Status Command**: Full member overview with CSV
- ✅ **Welcome Messages**: Auto-updating with debouncing
- ✅ **Spot Management**: Correct exclusion role counting

**User Features:**
- ✅ **`/my-score`**: Personal score checking
- ✅ **Enhanced Logging**: Batch progress updates
- ✅ **Better UI**: Improved embeds and formatting

### Phase 1 (Initial Release) ✅
- ✅ `/analyze` command with role-based ranking
- ✅ Fair scoring system (configurable weights)
- ✅ Discord embed + CSV export
- ✅ Progress updates during analysis
- ✅ Role-based permissions

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
