# Changelog

All notable changes to GuildScout Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - Phase 2: Performance & User Features - 2024-11-14

### 🚀 Added

#### Smart Caching System
- **SQLite-based cache** for message counts with configurable TTL
- **10-100x performance improvement** for repeated analysis
- Automatic cache expiration and cleanup
- Cache statistics tracking (hits, misses, hit rate)
- Support for different cache keys (role, days_lookback, excluded_channels)

#### `/my-score` Command
- Users can check their own ranking score
- Detailed breakdown of score components (days + activity)
- Transparent calculation formula display
- Percentile ranking and visual indicators (medals/emojis)
- Optional role-specific scoring
- Color-coded embeds based on performance

#### Admin Commands
- **`/cache-stats`**: View cache performance statistics
  - Total/valid/expired entries
  - Database size
  - Cache hit rates
- **`/cache-clear`**: Manage cache data
  - Clear guild-specific cache
  - Clear all cache
  - Clear only expired entries
- **`/bot-info`**: System and bot statistics
  - Bot statistics (guilds, users, uptime)
  - System resources (memory, CPU, threads)
  - Cache status
  - Configuration overview

### 🔧 Changed
- **ActivityTracker** now supports optional caching
- **count_messages_for_users** returns tuple with cache statistics
- Bot status updated to show `/analyze /my-score` commands
- Enhanced logging with cache hit/miss indicators (💾/🔍)

### 📦 Dependencies
- Added `psutil>=5.9.0` for system monitoring

### 📚 Documentation
- Updated README.md with Phase 2 features
- Added command documentation for `/my-score` and admin commands
- Added version history section
- Updated troubleshooting guide with cache-related tips

---

## [1.0.0] - Phase 1: MVP - 2024-11-14

### 🚀 Added

#### Core Functionality
- **`/analyze` Command**: Rank users by role
  - Fair scoring algorithm (40% membership, 60% activity)
  - Configurable weights via YAML
  - Optional parameters (days, top_n)
  - Real-time progress updates
- **Discord Embed Output**: Beautiful rankings display
- **CSV Export**: Complete data export
- **Permission System**: Role-based access control

#### Analytics System
- **RoleScanner**: Find members with specific roles
- **ActivityTracker**: Count messages across all channels
- **Scorer**: Calculate normalized weighted scores
- **Ranker**: Sort and organize rankings

#### Configuration
- YAML-based configuration system
- Configurable scoring weights
- Channel exclusion (by ID or name pattern)
- Admin role/user permissions
- Logging configuration

#### Documentation
- Comprehensive README.md
- QUICKSTART.md for fast setup
- TESTING.md with test procedures
- Example configuration file

### 📁 Project Structure
```
src/
├── bot.py              # Main bot
├── commands/           # Slash commands
├── analytics/          # Scoring logic
├── exporters/          # Discord & CSV export
├── utils/              # Config & logging
└── database/           # Future caching
```

### 🔒 Security
- Token and sensitive data in gitignored config
- No message content storage (only counts)
- Role-based permission system

---

## Upgrade Notes

### Upgrading from Phase 1 to Phase 2

1. **Update dependencies:**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

2. **No configuration changes required** - cache works out of the box with default settings

3. **Optional: Adjust cache TTL** in `config/config.yaml`:
   ```yaml
   analytics:
     cache_ttl: 3600  # 1 hour (default)
   ```

4. **Restart the bot** to load new commands

5. **Verify new commands** appear in Discord:
   - `/my-score`
   - `/cache-stats`
   - `/cache-clear`
   - `/bot-info`

### Breaking Changes
- None - Phase 2 is fully backward compatible

### New Permissions Required
- None - uses existing bot permissions

---

## Roadmap

### Phase 3 (Planned)
- Historical tracking of score changes
- Web dashboard for rankings
- Multi-guild support
- Persistent leaderboards
- Custom scoring metrics

### Community Requests
Have a feature request? [Open an issue on GitHub]

---

**Legend:**
- 🚀 Added: New features
- 🔧 Changed: Changes to existing functionality
- 🐛 Fixed: Bug fixes
- 🗑️ Removed: Removed features
- 🔒 Security: Security improvements
- 📚 Documentation: Documentation changes
