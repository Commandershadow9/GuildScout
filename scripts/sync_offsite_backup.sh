#!/usr/bin/env bash
set -euo pipefail

# GuildScout Off-site Backup Sync Script
# Synct lokale Backups zu Backblaze B2

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

LOG_FILE="logs/offsite-backup.log"
BACKUP_DIR="backups"
RCLONE_REMOTE="b2backup:guildscout-backups"  # Anpassen an deinen Bucket-Namen!

# Ensure log directory exists
mkdir -p logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "🚀 Starting off-site backup sync..."

# Check if rclone is configured
if ! rclone listremotes | grep -q "b2backup"; then
    log "❌ ERROR: rclone remote 'b2backup' not configured!"
    log "   Run: ./scripts/setup_offsite_backup.sh"
    exit 1
fi

# Check if backups exist
if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A $BACKUP_DIR)" ]; then
    log "⚠️  No backups found in $BACKUP_DIR - skipping"
    exit 0
fi

# Count local backups
LOCAL_COUNT=$(ls -1 "$BACKUP_DIR"/*.db 2>/dev/null | wc -l)
log "📦 Found $LOCAL_COUNT local backups"

# Sync to cloud with progress
log "☁️  Syncing to Backblaze B2..."

# Use rclone sync (deletes files in dest that don't exist in source - keeps it clean)
# Alternative: use 'copy' instead of 'sync' to keep all old backups
rclone sync \
    "$BACKUP_DIR" \
    "$RCLONE_REMOTE" \
    --progress \
    --transfers 4 \
    --checkers 8 \
    --stats-one-line \
    --stats 5s \
    --log-level INFO \
    2>&1 | tee -a "$LOG_FILE"

# Verify sync
REMOTE_COUNT=$(rclone ls "$RCLONE_REMOTE" 2>/dev/null | wc -l)
log "✅ Sync complete! Remote backups: $REMOTE_COUNT"

# Check total size
TOTAL_SIZE=$(rclone size "$RCLONE_REMOTE" --json 2>/dev/null | grep -o '"bytes":[0-9]*' | cut -d':' -f2)
if [ -n "$TOTAL_SIZE" ]; then
    SIZE_MB=$((TOTAL_SIZE / 1024 / 1024))
    log "💾 Total cloud backup size: ${SIZE_MB}MB"
fi

log "🎉 Off-site backup sync finished successfully"
