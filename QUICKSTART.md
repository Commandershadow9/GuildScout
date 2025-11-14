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

1. In Discord, type `/analyze`
2. Select a role (e.g., `@Members`)
3. Wait for analysis to complete
4. Check the ranking embed and download CSV!

## Need Help?

- Check `logs/guildscout.log` for errors
- See full documentation in `README.md`
- Verify bot permissions in server settings

---

**Total setup time: ~5 minutes** ⏱️
