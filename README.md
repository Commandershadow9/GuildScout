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

### Phase 2 Features (NEW!)
- **💾 Smart Caching**: SQLite-based cache for blazing-fast repeated analysis
- **📊 /my-score**: Users can check their own ranking and detailed breakdown
- **⚙️ Admin Commands**: Cache management and bot statistics
- **🚀 Performance**: 10-100x faster analysis with cache (first run: 30s, cached: <1s)

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

### Admin Commands (Phase 2)

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

### Scoring Weights

```yaml
scoring:
  weights:
    days_in_server: 0.4      # 40% weight for membership duration
    message_count: 0.6       # 60% weight for activity
```

**Important:** Weights should sum to 1.0!

### Minimum Requirements

```yaml
scoring:
  min_messages: 10           # Users with fewer messages are excluded
```

### Channel Exclusions

```yaml
analytics:
  excluded_channels:         # Exclude specific channel IDs
    - 123456789
  excluded_channel_names:    # Exclude channels with these name patterns
    - "nsfw"
    - "bot-spam"
```

### Permissions

```yaml
permissions:
  admin_roles:               # Role IDs that can use /analyze
    - 987654321
  admin_users:               # User IDs that can use /analyze (overrides roles)
    - 123456789
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

### Phase 2 (Current) ✅
**Major Performance & User Features Update**

- ✅ **SQLite Caching**: Smart cache system for 10-100x faster analysis
- ✅ **`/my-score` Command**: Users can check their own ranking
- ✅ **Admin Commands**: `/cache-stats`, `/cache-clear`, `/bot-info`
- ✅ **Performance Metrics**: Cache hit rate tracking and statistics
- ✅ **System Monitoring**: Resource usage and uptime tracking

### Phase 1 (Initial Release) ✅
- ✅ `/analyze` command with role-based ranking
- ✅ Fair scoring system (configurable weights)
- ✅ Discord embed + CSV export
- ✅ Progress updates during analysis
- ✅ Role-based permissions

## 🚀 Future Enhancements (Phase 3+)

Potential future features:

- **Historical Tracking**: Track score changes over time
- **Web Dashboard**: View rankings in a web interface
- **Multi-Guild Support**: Manage multiple servers from one bot
- **Leaderboards**: Persistent leaderboards with auto-updates
- **Custom Metrics**: Add custom scoring factors (reactions, voice time, etc.)

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