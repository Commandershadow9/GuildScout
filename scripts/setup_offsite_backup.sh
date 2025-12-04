#!/usr/bin/env bash
set -euo pipefail

# GuildScout Off-site Backup Setup Script
# Setzt Backblaze B2 + rclone für automatische Cloud-Backups ein

echo "🚀 GuildScout Off-site Backup Setup"
echo "===================================="
echo ""

# 1. Install rclone if not present
if ! command -v rclone &> /dev/null; then
    echo "📦 Installing rclone..."
    curl https://rclone.org/install.sh | sudo bash
    echo "✅ rclone installed"
else
    echo "✅ rclone already installed"
fi

echo ""
echo "📋 NÄCHSTE SCHRITTE:"
echo ""
echo "1. Backblaze B2 Account erstellen (falls noch nicht vorhanden):"
echo "   → https://www.backblaze.com/b2/sign-up.html"
echo ""
echo "2. Application Key erstellen:"
echo "   → Login → App Keys → Add a New Application Key"
echo "   → Name: 'GuildScout Backups'"
echo "   → Allow access to Bucket(s): All"
echo "   → Kopiere: keyID und applicationKey"
echo ""
echo "3. Bucket erstellen:"
echo "   → Buckets → Create a Bucket"
echo "   → Name: 'guildscout-backups' (oder eigener Name)"
echo "   → Files in Bucket: Private"
echo ""
echo "4. rclone konfigurieren:"
echo "   $ rclone config"
echo "   → n (New remote)"
echo "   → Name: b2backup"
echo "   → Type: b2"
echo "   → account: <deine keyID>"
echo "   → key: <dein applicationKey>"
echo "   → Enter für alle anderen Optionen"
echo ""
echo "5. Test der Verbindung:"
echo "   $ rclone lsd b2backup:"
echo "   (sollte dein Bucket zeigen)"
echo ""
echo "6. Cronjob aktivieren:"
echo "   $ crontab -e"
echo "   # Täglich um 06:00 UTC Backups hochladen"
echo "   0 6 * * * /home/cmdshadow/GuildScout/scripts/sync_offsite_backup.sh >> /home/cmdshadow/GuildScout/logs/offsite-backup.log 2>&1"
echo ""
echo "💡 Alternative: ShadowOps Bot kann das Monitoring übernehmen!"
echo ""
