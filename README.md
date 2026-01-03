# 🎮 GuildScout Discord Bot

A Discord bot that ranks users based on **membership duration**, **message activity**, and **voice activity**, providing fair and transparent scoring for guild recruitment or community management.

## 📋 Overview

GuildScout analyzes Discord server members with specific roles and generates rankings based on a configurable 3-component system (Default):
- **10%** Membership Duration (days in server) - Loyalty
- **55%** Message Activity (message count) - Engagement
- **35%** Voice Activity (time in voice) - Presence

Perfect for communities who need to fairly select members for limited guild spots or identify inactive users.

## ✨ Features

### Core Features
- **📊 User Ranking**: Analyze users by role with `/analyze` command
- **🏆 Fair Scoring**: Configurable weights for duration vs. activity vs. voice
- **📈 Visual Rank Cards**: Beautiful generated images showing user stats
- **🎤 Voice Tracking**: Accurately tracks voice activity (time in voice channels)
- **📥 CSV Export**: Download complete rankings as CSV
- **⚙️ Configurable**: All settings in YAML config file
- **🔒 Permission System**: Role-based access control

### Performance & Caching
- **💾 Smart Caching**: SQLite-based cache for blazing-fast repeated analysis
- **🚀 5x Faster**: Channel-first algorithm with parallel processing
- **⚡ Batch Progress**: Real-time batch updates during long operations
- **🔄 Auto-Retry**: Robust rate-limit handling with exponential backoff
- **📊 Cache Stats**: 60-70% hit rate on repeated analyses
- **🧵 Thread Coverage**: Counts messages in text channels *and* all threads (active & archived)

### Guild Management
- **🎮 WWM Release Timer**: Auto-updating countdown (every 10s) with dynamic hype text
- **✅ Interactive Role Assignment**: Button confirmation before mass role changes
- **📊 Guild Status**: View all guild members with scores & CSV export
- **🎯 Auto Spot Management**: Correctly counts all exclusion roles
- **💬 Welcome Messages**: Auto-updating channel info with debouncing
- **🔧 Set Max Spots**: Configure maximum guild size
- **⚠️ Interactive Dashboard**: Manage "at-risk" users directly with buttons
- **🗡️ Raid Planner**: Interactive raid flow with templates, role limits, bench,
  lock/close, reminders, and auto-cleanup

### User Features
- **📊 /my-score**: Users receive a generated graphical card with their ranking
- **🏆 Transparent Scoring**: See exactly how your score is calculated
- **📈 Percentile Ranking**: Know where you stand compared to others

### Import & Intelligence
- **🔄 Delta Import**: Bot catches up on missed messages after downtime.
- **♻️ Auto Re-Import**: Full historical import on first run.
- **📊 Dashboard**: Central channel (`/setup-ranking-channel`) for live stats.
- **🚨 Status Channel**: Error reporting channel with admin controls.

### Monitoring & Analytics
- **📊 Visual Analytics**: Dashboard with daily/weekly trends & Prime-Time analysis.
- **🏥 Health Monitoring**: Automated system checks (Database, API, Rate Limits).
- **📊 Performance Profiling**: `/profile` command to find bottlenecks.
- **📈 Enhanced Status**: `/status` command for system vitals.
- **📅 Weekly Reports**: Automated stats every Monday.

## 🎯 Available Commands

### Admin Commands
- **`/analyze <role>`** - Analyze and rank users with specific role
- **`/assign-guild-role <users>`** - Mass-assign guild role (with confirmation)
- **`/set-max-spots <number>`** - Set maximum guild size
- **`/guild-status`** - View all guild members with scores & export CSV
- **`/setup-ranking-channel`** - Create persistent ranking/dashboard channel
- **`/raid-create`** - Create a raid with role limits
- **`/raid-list`** - List upcoming raids
- **`/raid-setup`** - Create default raid channels and store IDs
- **`/raid-set-channel`** - Set raid post/manage channels
- **`/raid-info-setup`** - Create/update the raid info post
- **`/raid-add-creator-role`** - Allow another role to create raids
- **`/raid-remove-creator-role`** - Remove a role from raid creators
- **`/raid-set-participant-role`** - Set the raid participant role
- **`/raid-user-stats`** - Show raid participation stats for a user
- **`/status`** - Comprehensive system status overview
- **`/profile`** - Performance profiling & bottleneck analysis

### User Commands
- **`/my-score`** - Generate your personal ranking card
- **`/raid-list`** - Show upcoming raids

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

## ⚙️ Configuration

Edit `config/config.yaml` to customize the bot:

### Scoring Weights (New v2.4.0)

```yaml
scoring:
  weights:
    days_in_server: 0.1      # 10% - Loyalty
    message_count: 0.55      # 55% - Chat Activity
    voice_activity: 0.35     # 35% - Voice Activity
  min_messages: 10           # Minimum messages to be ranked
```

**Important:** Weights should sum to 1.0!

### Guild Management

```yaml
guild_management:
  guild_role_id: 1234567890    # The role ID for guild members
  max_guild_spots: 60          # Maximum guild size
  exclusion_roles:             # Roles that reserve spots (leaders, etc.)
    - 9876543210
```

### Raid Management

See `RAID_GUIDE.md` for the full raid workflow and configuration.

## 📊 Scoring Algorithm

The bot uses a **normalized weighted scoring system**:

### Formula

```
1. Normalize values to 0-100 scale (relative to the top user):
   days_score = (user_days / max_days) × 100
   msg_score  = (user_messages / max_messages) × 100
   voice_score = (user_voice_seconds / max_voice_seconds) × 100

2. Calculate weighted final score:
   final_score = (days_score × weight_days) + 
                 (msg_score × weight_msgs) + 
                 (voice_score × weight_voice)
```

## 🚀 Version History

### Version 2.4.0 (2025-12-06) - Current ✅
**Activity & Visuals Update**

- **🎤 Voice Tracking**: Bot now tracks time spent in voice channels.
- **📊 3-Pillar Scoring**: New fair scoring based on Days, Messages, and Voice.
- **🖼️ Visual Rank Cards**: `/my-score` now generates a beautiful image.
- **⚡ Interactive Dashboard**: Manage "at-risk" users via buttons directly in the dashboard.
- **📈 Improved Analytics**: Better trends and stats display.

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## 📄 License

This project is provided as-is for use in Discord servers.

---

**Made with ❤️ for fair guild management**
