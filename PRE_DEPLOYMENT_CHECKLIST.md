# 🚀 Pre-Deployment Checklist - GuildScout Bot

**WICHTIG:** Bitte checke diese Liste BEVOR du den Bot startest! Wir haben nur einen Versuch! ✅

## ✅ 1. Konfiguration - `config/config.yaml`

### Discord Settings
- [ ] **Bot Token** gesetzt in `discord.token`
- [ ] **Guild ID** gesetzt in `discord.guild_id` (deine Server-ID)

### Scoring (Standard: 40% Days, 60% Messages)
- [ ] **Weights** korrekt: `days_in_server: 0.4`, `message_count: 0.6`
- [ ] **Min Messages** sinnvoll gesetzt (Standard: 10)

### Admin Permissions
- [ ] **Admin Role ID** = `1391813795113996408` in `permissions.admin_roles`
- [ ] Nur diese Rolle kann Admin-Commands nutzen

### Guild Management (KRITISCH!)
- [ ] **max_spots** = `50` (oder deine gewünschte Zahl)
- [ ] **guild_role_id** = `1438703780362321991` (die Rolle die vergeben wird)
- [ ] **exclusion_roles** enthält:
  - `1438703780362321991` (Guild-Rolle selbst - User die sie schon haben)
  - `1434664835760783531` (Leader-Rolle - 3 aktuelle Leader)
- [ ] **exclusion_users** = `[]` (leer, außer du hast individuelle User IDs)

### Optional: Analytics
- [ ] **cache_ttl** gesetzt (Standard: 3600 = 1 Stunde)
- [ ] **excluded_channels** falls nötig (z.B. NSFW channels)

---

## ✅ 2. Discord Bot Permissions

### Bot Permissions im Discord Developer Portal
Der Bot braucht folgende Permissions:

#### Privileged Gateway Intents (WICHTIG!)
- [ ] **Server Members Intent** aktiviert
- [ ] **Message Content Intent** aktiviert

#### Bot Permissions
- [ ] **Read Messages/View Channels**
- [ ] **Send Messages**
- [ ] **Embed Links**
- [ ] **Attach Files**
- [ ] **Read Message History**
- [ ] **Manage Channels** (für Auto-Admin-Channel)
- [ ] **Manage Roles** (für `/assign-guild-role`)

#### OAuth2 URL Scopes
- [ ] `bot`
- [ ] `applications.commands`

---

## ✅ 3. Server Setup

### Rollen-Hierarchie
- [ ] **Bot-Rolle ist ÜBER der Guild-Rolle** in der Rollen-Hierarchie
  - Sonst kann der Bot die Rolle nicht vergeben!
  - Discord Server Settings → Roles → Bot-Rolle nach oben ziehen

### Channel Permissions
- [ ] Bot hat Zugriff auf alle relevanten Channels (außer explizit excluded)
- [ ] Bot kann Message History lesen (für Message Count)

### Bestehende Plätze
- [ ] **Manuell vergeben:** Gib die Guild-Rolle `1438703780362321991` an:
  - Deine reservierten Plätze (die du schon versprochen hast)
  - Die 3 Leader mit Rolle `1434664835760783531` (falls sie noch keine Guild-Rolle haben)

  **→ Diese User werden automatisch vom Ranking ausgeschlossen!**

---

## ✅ 4. Funktionsweise verstehen

### Workflow
1. **Bot joined Server** → Erstellt automatisch `#guild-rankings` Channel (nur Admins sehen)
2. **Du gibst manuell** die Guild-Rolle an reserved spots (z.B. 10 von 50)
3. **Du führst aus:** `/analyze role:@Gilden-Interessenten`
   - Bot excludes alle mit Guild-Rolle oder Leader-Rolle
   - Zeigt Top-Liste der verbleibenden Kandidaten
   - Exportiert CSV mit allen Daten
4. **Du prüfst** die Liste im `#guild-rankings` Channel
5. **Du führst aus:** `/assign-guild-role ranking_role:@Gilden-Interessenten count:40`
   - Bot zeigt Preview der Top 40
   - Du bestätigst mit Button
   - Bot vergibt die Rolle automatisch
6. **Ergebnis:** 50 User haben die Guild-Rolle (10 manuell + 40 automatisch)

### Exclusion Logic (WICHTIG!)
**Excluded werden:**
- ✅ User mit Guild-Rolle `1438703780362321991`
- ✅ User mit Leader-Rolle `1434664835760783531`
- ✅ User in `exclusion_users` Liste (falls angegeben)

**Geranked werden:**
- ✅ Alle anderen User mit der analysierten Rolle
- ✅ Sortiert nach Score (40% Days, 60% Messages)

---

## ✅ 5. Commands Übersicht

### Admin Commands (nur für Admin-Rolle)
| Command | Beschreibung |
|---------|-------------|
| `/analyze` | Analysiert und rankt User nach Rolle |
| `/guild-status` | Zeigt aktuelle Guild-Mitglieder (wer hat die Rolle) |
| `/set-max-spots` | Ändert das Max-Limit (z.B. von 50 auf 60) |
| `/assign-guild-role` | Vergibt Guild-Rolle an Top N User |
| `/setup-ranking-channel` | Erstellt/setzt Ranking-Channel (optional, wird automatisch erstellt) |
| `/bot-info` | Bot Information |
| `/cache-stats` | Cache Performance |
| `/cache-clear` | Cache leeren |

### User Commands (für alle)
| Command | Beschreibung |
|---------|-------------|
| `/my-score` | User kann eigenen Score checken |

---

## ✅ 6. Erwartete Outputs

### `/analyze role:@Gilden-Interessenten`
**Im Ranking Channel:**
```
📊 Guild Selection Ranking: @Gilden-Interessenten

🎯 Guild Spot Management:
   • Total Spots: 50
   • Already Filled: 13 (reserved/manual)
   • Available: 37
   • Candidates Ranked: 127

🏆 Top 10 Detailed Rankings:
1. @User1 - Score: 95.4
   Days: 234 (Score: 94.2) | Messages: 1,523 (Score: 96.1)
...

🔒 Reserved Spots (13):
• @ReservedUser1 - Has guild role (manual)
• @Leader1 - Has reserved spot role (@Leader)
...

📊 CSV Export attached
```

### `/guild-status`
```
📊 Guild Status Overview

🎯 Spot Availability:
Total Spots: 50
Filled: 13 (26.0%)
Available: 37

📈 Fill Status:
███░░░░░░░ 26.0%

👥 Current Guild Members (13):
1. @User1 (`username1`)
2. @Leader1 (`leader1`)
...

📊 CSV Export attached
```

### `/assign-guild-role ranking_role:@Role count:37`
**Preview:**
```
🎯 Guild Role Assignment Preview

📊 Selection Details:
• Role to Assign: @Guild-Mitglied
• Users Selected: 37
• Current Available Spots: 37
• Remaining After: 0

👥 Users to Receive Role:
1. @User1 (Score: 95.4)
2. @User2 (Score: 94.1)
...

[✅ Confirm & Assign Roles] [❌ Cancel]
```

**Nach Bestätigung:**
```
✅ Role Assignment Complete!

Successfully Assigned: 37 users
Failed: 0 users

CSV Export attached
```

---

## ✅ 7. Safety Checks

### Der Bot verhindert automatisch:
- ✅ **Über-Vergabe:** Warnt wenn du mehr Spots vergibst als verfügbar
- ✅ **Doppel-Vergabe:** User mit Guild-Rolle werden nicht nochmal geranked
- ✅ **Permissions:** Nur Admins können kritische Commands nutzen
- ✅ **Bestätigung:** `/assign-guild-role` braucht Button-Bestätigung
- ✅ **Logging:** Alles wird geloggt in `logs/guildscout.log`

---

## ✅ 8. Testing Plan

### Test 1: Bot Start
1. [ ] Bot startet ohne Errors
2. [ ] Bot erstellt `#guild-rankings` Channel
3. [ ] Channel ist nur für Admins sichtbar
4. [ ] Welcome Message erscheint im Channel

### Test 2: Guild Status
1. [ ] `/guild-status` zeigt korrekte Anzahl
2. [ ] CSV Download funktioniert
3. [ ] Alle User mit Guild-Rolle werden gelistet

### Test 3: Analyze
1. [ ] `/analyze role:@TestRole` funktioniert
2. [ ] Excluded members werden angezeigt
3. [ ] Spot calculation ist korrekt (Total - Filled = Available)
4. [ ] Top 10 Breakdown wird angezeigt
5. [ ] CSV Export funktioniert

### Test 4: Set Max Spots
1. [ ] `/set-max-spots count:60` funktioniert
2. [ ] Config wird updated
3. [ ] Neue Werte erscheinen in `/guild-status`

### Test 5: Assign Guild Role (KRITISCH!)
1. [ ] Preview zeigt korrekte User
2. [ ] Spot availability check funktioniert
3. [ ] Nur Requester kann bestätigen
4. [ ] Nach Bestätigung: Rollen werden vergeben
5. [ ] Success/Failure wird gemeldet
6. [ ] CSV Export funktioniert

---

## ✅ 9. Rollback Plan

### Falls etwas schief geht:
1. **Bot stoppen:** `Ctrl+C` im Terminal
2. **Rollen manuell entfernen:** Discord → Server Settings → Members → Bulk remove role
3. **Config zurücksetzen:** `git checkout config/config.yaml`
4. **Logs prüfen:** `tail -f logs/guildscout.log`

### Logs Location
- **Bot Logs:** `logs/guildscout.log`
- **CSV Exports:** `output/*.csv`

---

## ✅ 10. Finale Checks vor Start

- [ ] **Alle Python Files** syntax-checked ✅
- [ ] **Config.yaml** vollständig ausgefüllt
- [ ] **Bot Permissions** im Discord Developer Portal aktiviert
- [ ] **Bot-Rolle** ist ÜBER Guild-Rolle in Hierarchie
- [ ] **Manuelle Plätze** sind vergeben (falls nötig)
- [ ] **Backup** der aktuellen Member-Liste (falls vorhanden)
- [ ] **Terminal offen** für Log-Output
- [ ] **Discord offen** für sofortige Checks

---

## 🚀 Start Command

```bash
cd /home/user/GuildScout
python3 -m src.bot
```

**Oder mit Poetry:**
```bash
cd /home/user/GuildScout
poetry run python -m src.bot
```

---

## 📞 Support & Troubleshooting

### Häufige Probleme:

**Bot joined aber kein Channel erstellt:**
→ Bot braucht "Manage Channels" Permission

**Bot kann Rolle nicht vergeben:**
→ Bot-Rolle muss ÜBER der Guild-Rolle sein

**"Missing Permissions" Error:**
→ Server Members Intent & Message Content Intent aktivieren

**Falsche User excluded:**
→ Prüfe `exclusion_roles` und `exclusion_users` in config.yaml

**Cache zu alt:**
→ `/cache-clear` Command nutzen

---

## ✅ Final Verification

**ICH BESTÄTIGE:**
- [ ] Ich habe config.yaml vollständig ausgefüllt
- [ ] Ich habe alle Bot Permissions aktiviert
- [ ] Ich verstehe die Exclusion Logic
- [ ] Ich habe manuelle Plätze bereits vergeben
- [ ] Ich bin bereit für Deployment

**→ Wenn alle Checkboxen ✅ sind: GO FOR LAUNCH! 🚀**

---

**Status:** Ready for Deployment ✅
**Last Updated:** 2025-11-14
**Version:** Phase 4 - Guild Management System
