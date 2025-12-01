# GuildScout Monitoring & Observability

Umfassende Dokumentation aller Monitoring- und Performance-Features von GuildScout v2.3.0+

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Health Monitoring](#health-monitoring)
3. [Performance Profiling](#performance-profiling)
4. [Status & Reporting](#status--reporting)
5. [Database Monitoring](#database-monitoring)
6. [Alerts & Notifications](#alerts--notifications)
7. [Troubleshooting](#troubleshooting)

---

## Übersicht

GuildScout bietet ein vollständiges Monitoring-System für Produktionsumgebungen:

- ✅ **Automated Health Checks** alle 5 Minuten
- ✅ **Performance Profiling** mit `/profile` Command
- ✅ **Echtzeit-Status** mit `/status` Command
- ✅ **Wöchentliche Berichte** jeden Montag
- ✅ **Database Monitoring** täglich
- ✅ **Multi-Channel Alerts** (Discord + ShadowOps)

---

## Health Monitoring

### Automatisches Health Monitoring System

**Datei:** `src/tasks/health_monitor.py`
**Intervall:** Alle 5 Minuten
**Start:** Automatisch beim Bot-Start

### Überwachte Bereiche

#### 1. Verifikations-Gesundheit

**Was wird geprüft:**
- Letzte Verifikation nicht älter als 8 Stunden
- Verifikations-Genauigkeit ≥ 95%
- Anzahl aufeinanderfolgender Fehler

**Alerts:**
```
⚠️ Verifikation überfällig
Letzte Verifikation war vor 10.5h.
Erwartet: alle 6 Stunden
Möglicherweise ist der Scheduler ausgefallen.
```

```
❌ Verifikation schlägt fehl
Genauigkeit: 89.3% (< 95%)
Fehlschläge: 2 aufeinanderfolgend
Überprüfe Discord API oder Netzwerkverbindung.
```

#### 2. Rate Limit Monitoring

**Was wird geprüft:**
- Requests pro Sekunde
- Anzahl Rate Limit Hits
- Status: healthy / warning / critical

**Schwellenwerte:**
- **Healthy:** < 10 req/s, < 5 hits
- **Warning:** 10-20 req/s, 5-20 hits
- **Critical:** > 20 req/s, > 20 hits

**Alerts:**
```
🚨 Rate Limit kritisch
Requests/s: 25.3
Limit Hits: 45
Bot könnte verlangsamt oder geblockt werden.
Erwäge Reduzierung der API-Aufrufe.
```

#### 3. Datenbank-Gesundheit

**Was wird geprüft:**
- Schnelles Wachstum (>50MB seit letztem Check)
- Datenbank-Integrität (PRAGMA integrity_check)
- Gesamtgröße und Status

**Alerts:**
```
📈 Datenbank wächst schnell
Wachstum: +75.3 MB (seit letztem Check)
Aktuelle Größe: 234.7 MB
Ungewöhnlich schnelles Wachstum erkannt.
Überprüfe auf Anomalien oder erwäge VACUUM.
```

```
🔴 Datenbank-Korruption
PRAGMA integrity_check: page 142 corrupt
Datenbank könnte beschädigt sein!
Erwäge Backup und Reparatur.
```

#### 4. ShadowOps Integration

**Was wird geprüft:**
- Retry Queue Größe
- Letzter erfolgreicher Health-Check
- Webhook-Erreichbarkeit

**Alerts:**
```
📡 ShadowOps Warteschlange voll
Wartende Events: 15
ShadowOps könnte offline oder überlastet sein.
Events werden weiter versucht, aber verzögert.
```

```
🔴 ShadowOps nicht erreichbar
Letzter Kontakt: vor 45 Minuten
Health Check schlägt fehl.
Überprüfe ShadowOps-Bot Status.
```

### Alert Cooldowns

Um Spam zu vermeiden, haben Alerts Cooldown-Perioden:

| Alert-Typ | Cooldown |
|-----------|----------|
| `verification_failure` | 1 Stunde |
| `rate_limit_critical` | 30 Minuten |
| `db_growth` | 6 Stunden |
| `shadowops_offline` | 1 Stunde |

### Täglicher Gesundheitsbericht

**Zeitpunkt:** Alle 24 Stunden
**Format:** Discord Embed im Status-Channel

**Inhalt:**
- Systemstatus (Gesund / Eingeschränkt / Kritisch)
- Verifikations-Gesundheit mit Genauigkeit
- Rate Limit Status
- Datenbank-Status
- Deduplizierungs-Effektivität
- ShadowOps Verbindungsstatus

**Beispiel:**
```
📊 Täglicher Gesundheitsbericht
Zusammenfassung der letzten 24 Stunden

🏥 Systemstatus: ✅ Gesund

🔍 Verifikation: ✅ 97.8%
📊 Rate Limits: ✅ Healthy
💾 Datenbank: ✅ Normal
🔄 Deduplizierung: 127 blockiert (0.85%)
📡 ShadowOps: ✅ Verbunden

Nächster Bericht in 24 Stunden
```

---

## Performance Profiling

### `/profile` Command

**Berechtigung:** Nur Admins (konfiguriert in `config.yaml`)
**Verwendung:** `/profile` im Discord

### Angezeigte Metriken

#### 1. System Ressourcen
```
💻 System Ressourcen
CPU: 3.2%
Speicher: 234.5 MB
Threads: 12
```

#### 2. Tracking Info
```
📈 Tracking Info
Uptime: 2d 14h 32m
Operationen: 45,892
Fehler: 3
```

#### 3. Langsamste Operationen
Sortiert nach Durchschnittszeit, zeigt die Top 5:

```
🐌 Langsamste Operationen (Durchschnitt)

verification_job
⏱️ Ø 847.2ms | Max 1245.8ms | Calls 28

database.vacuum
⏱️ Ø 523.4ms | Max 892.1ms | Calls 7

message_import.channel_scan
⏱️ Ø 312.7ms | Max 678.9ms | Calls 156
```

#### 4. Meistgenutzte Operationen
Sortiert nach Call-Count, zeigt die Top 5:

```
🔥 Meistgenutzte Operationen

message_tracking.on_message
📞 12,345 Calls | ⏱️ Ø 2.3ms | Gesamt 28.4s

dashboard.update
📞 3,456 Calls | ⏱️ Ø 15.7ms | Gesamt 54.3s

cache.get_user
📞 2,890 Calls | ⏱️ Ø 0.8ms | Gesamt 2.3s
```

#### 5. Bottleneck-Analyse
Identifiziert automatisch kritische Engpässe:

```
⚠️ Identifizierte Engpässe

🔴 verification_job: Langsam (847ms) UND häufig (28 Calls)
🐌 database.vacuum: Sehr langsam (Ø 0.5s)

✅ Keine kritischen Engpässe erkannt  (wenn keine vorhanden)
```

### Performance Tracking Implementation

#### Automatisches Tracking mit Decorator

**Verwendung:**
```python
from src.utils.performance_decorator import track_performance

@track_performance("verification_job")
async def _run_verification_job(self, ...):
    # Code wird automatisch getrackt
    pass

@track_performance()  # Nutzt Funktionsname
async def my_function(self):
    pass
```

#### Manuelles Tracking

```python
from src.commands.profile import get_tracker

tracker = get_tracker()

# Start tracking
import time
start = time.perf_counter()

try:
    # Dein Code
    result = await some_operation()
    error = False
except Exception:
    error = True
    raise
finally:
    duration = time.perf_counter() - start
    tracker.record_execution("my_operation", duration, error=error)
```

#### Statistiken abrufen

```python
from src.commands.profile import get_tracker

tracker = get_tracker()

# Einzelne Operation
stats = tracker.get_stats("verification_job")
print(f"Average: {stats['avg']}s")
print(f"Max: {stats['max']}s")
print(f"Calls: {stats['count']}")
print(f"Errors: {stats['errors']}")

# Alle Operationen (sortiert)
all_ops = tracker.get_all_operations()

# Langsamste Operationen
slowest = tracker.get_slowest_operations(limit=10)

# Meist-aufgerufene Operationen
most_called = tracker.get_most_called(limit=10)
```

---

## Status & Reporting

### `/status` Command

**Berechtigung:** Alle User
**Verwendung:** `/status` im Discord

**Ausgabe:** Umfassende System-Übersicht

```
🤖 GuildScout System Status

⚙️ Bot Status
Uptime: 2d 14h 32m
Memory: 234.5 MB
Guilds: 1

💾 Database
Size: 45.7 MB
Status: ✅ OK

📊 Rate Limits
Current: 3.2 req/s
Limit Hits: 12
Status: healthy

🔍 Last Verification
Time: vor 2h 15m
Result: 97.8% accuracy

🔄 Message Deduplication
Seen: 45,892
Blocked: 389
Rate: 0.85%

📡 ShadowOps Integration
Queue: ✅ Empty
Enabled: ✅ Yes

Use /profile for performance metrics
```

### Wöchentliche Berichte

**Zeitpunkt:** Jeden Montag, 09:00 UTC
**Versand:** Status-Channel + ShadowOps
**Datei:** `src/tasks/weekly_reporter.py`

**Inhalt:**

#### Aktivitäts-Übersicht
```
📈 Aktivität
Nachrichten: 45,892
Aktive User: 234
Durchschnitt: 6,556 msg/Tag
```

#### Datenbank & Verifikation
```
💾 Datenbank
Größe: 45.7 MB ✅
Status: Gesund

🔍 Verifikation
Durchläufe: ~28
Genauigkeit: 97.8% ✅
Status: Optimal
```

#### Top User & Channels
```
🏆 Top 5 User
1. MaxMustermann: 2,345 msg
2. JaneSmith: 1,890 msg
3. UserXYZ: 1,456 msg
4. TestUser: 1,234 msg
5. AnotherUser: 987 msg

📺 Top 5 Channels
1. #general: 12,345 msg
2. #guild-chat: 8,901 msg
3. #off-topic: 5,678 msg
4. #memes: 3,456 msg
5. #voice: 2,345 msg
```

#### System Performance
```
⚙️ System Performance
Deduplizierung: 389 blockiert (0.85%)
Rate Limit Hits: 12
Status: ✅ Stabil
```

---

## Database Monitoring

### Tägliche Size-Überwachung

**Datei:** `src/tasks/db_maintenance.py`
**Intervall:** Alle 24 Stunden

**Schwellenwerte:**
- **< 50 MB:** Debug Log
- **50-100 MB:** Info Log
- **> 100 MB:** Warning + Discord Alert

**Discord Alert Beispiel:**
```
⚠️ Datenbank wird groß

Aktuelle Größe: 123.4 MB

Die Datenbank überschreitet 100 MB.
Nächstes VACUUM wird automatisch Speicher freigeben.
```

### Wöchentliche Wartung

**Zeitpunkt:** Jeden Montag, 04:00 UTC
**Operationen:**
1. **VACUUM:** Defragmentierung, Speicherfreigabe
2. **ANALYZE:** Query Optimizer Updates

**Status-Benachrichtigung:**
```
🔧 Datenbank-Wartung abgeschlossen

VACUUM & ANALYZE erfolgreich durchgeführt

Vorher: 123.4 MB
Nachher: 87.6 MB
Gespart: 35.8 MB (29.0%)
Dauer: 3.2s
```

### Database Integrity Check

Wird automatisch vom Health Monitor durchgeführt:

```python
# Prüft Korruption
PRAGMA integrity_check
```

Bei Fehlern wird sofort ein kritischer Alert gesendet.

---

## Alerts & Notifications

### Multi-Channel Alerts

Alerts werden an **zwei Ziele** gesendet:

1. **Discord Status-Channel** (konfiguriert in `config.yaml`)
2. **ShadowOps Bot** (wenn aktiviert)

### Alert-Typen und Severity Levels

| Severity | Farbe | Verwendung |
|----------|-------|------------|
| `low` | Grün | Informativ, keine Aktion nötig |
| `medium` | Gelb | Aufmerksamkeit empfohlen |
| `high` | Orange | Aktion empfohlen |
| `critical` | Rot | Sofortige Aktion erforderlich |

### Alert-Format

**Discord Embed:**
```
⚠️ Alert Title

Description text here
with multiple lines

Field Name 1: Value
Field Name 2: Value

Footer text
```

**ShadowOps JSON:**
```json
{
  "event_type": "health_alert",
  "severity": "warning",
  "title": "⚠️ Alert Title",
  "description": "Description text",
  "timestamp": "2025-12-01T10:30:00",
  "metadata": {
    "additional": "data"
  }
}
```

### Webhook Retry-Mechanismus

Wenn ShadowOps nicht erreichbar ist:

1. Alert wird in **Retry Queue** gespeichert (max 100)
2. Queue wird persistent gespeichert in `data/shadowops_queue.json`
3. Retry alle **5 Minuten** automatisch
4. Bei erfolgreicher Zustellung: Entfernung aus Queue

---

## Troubleshooting

### Health Monitor läuft nicht

**Symptome:** Keine Health Checks im Log

**Lösung:**
```bash
# Prüfe Bot-Logs
tail -f logs/guildscout.log | grep health_monitor

# Sollte zeigen:
# "🏥 Health monitoring system started"

# Prüfe ob Cog geladen wurde
journalctl --user -u guildscout-bot.service | grep health_monitor
```

### Performance Tracking funktioniert nicht

**Symptome:** `/profile` zeigt keine Daten

**Lösung:**
```python
# Prüfe ob Decorator importiert wird
from src.utils.performance_decorator import track_performance

# Prüfe ob Tracker initialisiert ist
from src.commands.profile import get_tracker
tracker = get_tracker()
print(tracker.call_counts)  # Sollte nicht leer sein
```

### Alerts werden nicht gesendet

**Symptome:** Keine Discord/ShadowOps Alerts trotz Problemen

**Prüfe:**
1. Status-Channel konfiguriert?
   ```yaml
   guild_management:
     status_channel_id: YOUR_CHANNEL_ID
   ```

2. ShadowOps aktiviert?
   ```yaml
   shadowops:
     enabled: true
     webhook_url: http://localhost:9091/guildscout-alerts
   ```

3. Alert Cooldown aktiv?
   - Alerts haben Cooldowns (siehe oben)
   - Warte bis Cooldown abgelaufen ist

4. Logs prüfen:
   ```bash
   tail -f logs/guildscout.log | grep -E "Alert|health_monitor"
   ```

### Wöchentlicher Bericht wird nicht gesendet

**Symptome:** Kein Bericht am Montag 09:00 UTC

**Prüfe:**
1. Ist Bot zu dieser Zeit online?
2. Logs checken:
   ```bash
   journalctl --user -u guildscout-bot.service --since "today" | grep weekly_reporter
   ```

3. Zeitzone korrekt? (UTC vs. Lokal)
4. Weekly Reporter läuft?
   ```bash
   tail -f logs/guildscout.log | grep "Weekly reporter scheduled"
   ```

### Database Size Warning trotz kleiner DB

**Symptome:** Warnung trotz < 100 MB

**Lösung:**
```bash
# Prüfe tatsächliche Größe
ls -lh data/messages.db

# Prüfe Log
tail -f logs/guildscout.log | grep "Database size"

# Falls falsch: Bot neu starten
systemctl --user restart guildscout-bot.service
```

---

## Best Practices

### 1. Regelmäßig `/profile` checken
- Mindestens wöchentlich
- Nach Code-Changes
- Bei Performance-Problemen

### 2. Health Alerts ernst nehmen
- Kritische Alerts sofort adressieren
- Warnings innerhalb 24h prüfen
- Trends beobachten

### 3. Wöchentliche Berichte reviewen
- Top User/Channels analysieren
- Performance-Trends erkennen
- Verifikations-Genauigkeit überwachen

### 4. Database Maintenance
- Automatisches VACUUM läuft Montags
- Bei > 200 MB manuelles VACUUM erwägen
- Regelmäßig Backups prüfen

### 5. Performance Optimierung
- Bottlenecks aus `/profile` identifizieren
- Langsame Operationen optimieren
- Error-Rates überwachen

---

## Weiterführende Dokumentation

- **WEBHOOK_SECURITY.md** - Webhook-Sicherheit und Signatur-Verifizierung
- **README.md** - Allgemeine Bot-Dokumentation
- **CHANGELOG.md** - Version History
- **GUILD_MANAGEMENT_GUIDE.md** - Guild Management Features

---

**Version:** 2.3.0
**Letzte Aktualisierung:** 2025-12-01
