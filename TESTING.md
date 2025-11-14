# 🧪 Testing Guide for GuildScout

## Pre-Installation Testing

### 1. Verify Python Version
```bash
python3 --version
# Should be 3.11 or higher
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Test Imports
```bash
python3 tests/test_imports.py
```

Expected output:
```
Testing imports...
✓ Utils imported successfully
✓ Analytics imported successfully
✓ Exporters imported successfully
✓ Commands imported successfully

✅ All imports successful!
```

## Configuration Testing

### 1. Create Config File
```bash
cp config/config.example.yaml config/config.yaml
```

### 2. Edit Config
Replace placeholders in `config/config.yaml`:
- `YOUR_BOT_TOKEN_HERE` → Your actual bot token
- `123456789012345678` → Your guild ID
- `987654321012345678` → Your admin role ID

### 3. Validate Config (Optional)
```bash
python3 -c "from src.utils import Config; c = Config(); print('Config OK!')"
```

## Bot Testing

### 1. Start the Bot
```bash
python3 run.py
```

Expected log output:
```
==================================================
GuildScout Bot Starting...
==================================================
INFO - Setting up bot...
INFO - Synced commands to guild 123456789
INFO - Bot is ready! Logged in as GuildScout#1234
INFO - Connected to 1 guild(s)
```

### 2. Verify Bot is Online
- Check Discord
- Bot should show as "Online"
- Status should show "Watching guild activity | /analyze"

### 3. Test Commands
In Discord:
1. Type `/` - you should see `/analyze` in the command list
2. Type `/analyze` and select a test role
3. Verify the bot responds

## Integration Testing

### Test Scenario 1: Small Role Analysis

1. Create a test role "TestRole"
2. Assign to 2-3 users
3. Run: `/analyze role:@TestRole`
4. Verify:
   - Progress message appears
   - Analysis completes in <10 seconds
   - Embed shows user rankings
   - CSV file is uploaded

### Test Scenario 2: Large Role Analysis

1. Use an existing large role (e.g., @Members)
2. Run: `/analyze role:@Members top_n:10`
3. Verify:
   - Progress updates every 10 users
   - Shows only top 10 in embed
   - CSV contains all users

### Test Scenario 3: Time-Limited Analysis

1. Run: `/analyze role:@Members days:30`
2. Verify:
   - Only counts messages from last 30 days
   - Scores reflect recent activity

## Permission Testing

### Test 1: Admin Access
1. Login as user with admin role
2. Run `/analyze` - should work

### Test 2: Non-Admin Access
1. Login as user without admin role
2. Run `/analyze` - should show permission error

## Error Handling Testing

### Test 1: Invalid Role
```
/analyze role:@NonExistentRole
```
Expected: Error message "Role not found"

### Test 2: Role with No Members
1. Create empty role
2. Run `/analyze role:@EmptyRole`
3. Expected: "No members found with role"

### Test 3: Missing Permissions
1. Remove "Read Message History" from bot
2. Run `/analyze`
3. Expected: Warning messages in logs

## Performance Testing

### Measure Analysis Time
For 100 users:
- Expected: <60 seconds
- Acceptable: <120 seconds

For 300 users:
- Expected: <180 seconds
- Acceptable: <300 seconds

## Troubleshooting Tests

### Issue: Bot doesn't start
1. Check `logs/guildscout.log`
2. Verify token in config
3. Check intents in Discord Developer Portal

### Issue: Commands don't appear
1. Verify bot has "applications.commands" scope
2. Check logs for "Synced commands" message
3. Try restarting Discord client

### Issue: Permission errors
1. Verify admin role IDs in config
2. Check user has correct roles
3. Check bot has necessary permissions

## Automated Testing (Future)

Phase 2 will include:
- Unit tests for all modules
- Integration tests with mock Discord API
- Performance benchmarks
- CI/CD pipeline

---

**Current Status:** Phase 1 MVP - Manual testing required
