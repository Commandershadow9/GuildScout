# 🚀 GuildScout Quick Start Guide

## Installation (5 Minutes)

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create Your Config File
```bash
cp config/config.example.yaml config/config.yaml
```

### 3. Get Your Discord Bot Token

1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name it "GuildScout"
3. Go to "Bot" tab → Click "Add Bot"
4. Enable these intents:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Click "Reset Token" → Copy the token

### 4. Edit Config File

Open `config/config.yaml` and set:

```yaml
discord:
  token: "YOUR_BOT_TOKEN_HERE"  # Paste your token
  guild_id: 123456789            # Your server ID (see below)

permissions:
  admin_roles:
    - 987654321                  # Your admin role ID (see below)
```

**Get Server ID:**
- Enable Developer Mode: Discord Settings → Advanced → Developer Mode ON
- Right-click your server → "Copy Server ID"

**Get Role ID:**
- In Discord, type: `\@RoleName` and send
- It shows: `<@&123456789>` → Copy the number

### 5. Invite Bot to Server

1. In Discord Developer Portal → OAuth2 → URL Generator
2. Select: `bot` + `applications.commands`
3. Select permissions:
   - Read Messages/View Channels
   - Read Message History
   - Send Messages
   - Embed Links
   - Attach Files
4. Copy URL → Open in browser → Invite to your server

### 6. Run the Bot

```bash
python run.py
```

Look for: `Bot is ready! Logged in as GuildScout#1234`

## First Test

### Test `/analyze` (Admin Command)
1. In Discord, type `/analyze`
2. Select a role (e.g., `@Members`)
3. Wait for analysis to complete (first run: ~30s)
4. Check the ranking embed and download CSV!

### Test `/my-score` (User Command)
1. Type `/my-score`
2. See your personal ranking with detailed breakdown
3. Try `/my-score role:@Members` for role-specific score

### Test Performance (Cache in Action)
1. Run `/analyze role:@Members` again
2. Notice it completes in <1 second! 💾
3. Use `/cache-stats` to see cache hit rate

## Available Commands

| Command | Who Can Use | Description |
|---------|------------|-------------|
| `/analyze` | Admins | Rank users by role |
| `/my-score` | Everyone | Check your own score |
| `/cache-stats` | Admins | View cache statistics |
| `/cache-clear` | Admins | Clear cache data |
| `/bot-info` | Admins | View bot information |

## Phase 2 Features

### 🚀 Performance
- **First analysis**: 30-60 seconds (counts all messages)
- **Cached analysis**: <1 second (uses cache)
- **10-100x faster** repeated analysis

### 💾 Smart Cache
- Automatically caches message counts for 1 hour
- Use `/cache-clear` to refresh data manually
- `/cache-stats` shows performance metrics

### 📊 User Transparency
- Users can check their own score with `/my-score`
- Detailed breakdown showing calculation
- No admin needed for personal lookup

## Need Help?

- Check `logs/guildscout.log` for errors
- See full documentation in `README.md`
- Verify bot permissions in server settings

---

**Total setup time: ~5 minutes** ⏱️
