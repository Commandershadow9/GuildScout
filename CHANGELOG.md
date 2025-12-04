# Changelog - GuildScout Bot

## Version 2.4.0 - Historical Data & Advanced Analytics (2025-12-04)

> **Major Update:** Umfassende Erweiterung der Analyse-Fähigkeiten mit historischen Trends, visuellen Charts und Dashboard 2.0.

### 📊 Dashboard 2.0 & Visual Analytics
- **Activity Charts**: Automatisch generierte Grafiken visualisieren die Server-Aktivität der letzten 14 Tage direkt im Dashboard.
- **Trend-Analyse**: Intelligente Berechnung von Aktivitätstrends mit Indikatoren (📈/📉):
  - **Daily Trend**: Vergleich Heute vs. Gestern
  - **Weekly Trend**: Letzte 7 Tage vs. Vorwoche
  - **Monthly Trend**: Letzte 30 Tage vs. Vormonat
- **Prime Time Analyse**: Ermittelt automatisch die aktivste Uhrzeit des Servers (Peak Hour).
- **Real-Time Status**: Verifikations-Jobs zeigen ihren Status ("Läuft...", "Abgeschlossen") nun live im Dashboard an.

### 💾 Advanced Message Tracking
- **Granulare Statistiken**: `MessageStore` erfasst nun Nachrichten-Counts auf täglicher und stündlicher Basis.
- **Präziser Historischer Import**: Der `HistoricalImporter` wurde komplett überarbeitet, um exakte Zeitstempel zu erfassen, was eine korrekte Rückrechnung historischer Statistiken ermöglicht.
- **Performance**: Batch-Processing beim Import optimiert für geringeren Speicherverbrauch und schnellere Datenbank-Writes.

### 🐛 Bug Fixes
- **Critical Fix**: `NameError: name 'defaultdict' is not defined` im `MessageStore` behoben, der den historischen Import (Bulk-Increment) zum Absturz brachte.
- **Dashboard Update Fix**: Korrektur eines `TypeError` beim Aktualisieren von Nachrichten mit Anhängen (Charts) unter discord.py 2.0+.

### 📦 New Dependencies
- `matplotlib` & `seaborn`: Hinzugefügt für die Generierung von serverseitigen Aktivitäts-Charts.

---

## Version 2.3.0 - Advanced Monitoring & Security (2025-12-01)

> **Major Update:** Umfassende Monitoring-, Performance- und Sicherheits-Features für Produktionsumgebungen.

### 🏥 Health Monitoring System
- **Automated Health Alerts**: Kontinuierliche Systemüberwachung alle 5 Minuten
  - Verifikations-Gesundheit: Erkennt ausgefallene oder fehlerhafte Verifikations-Zyklen (> 8h keine Verifikation)
  - Rate Limit Monitoring: Warnt bei kritischer Discord API Auslastung
  - Datenbank-Gesundheit: Überwacht schnelles Wachstum (>50MB in kurzer Zeit) und Korruption
  - ShadowOps Integration: Prüft Erreichbarkeit und Queue-Status
- **Täglicher Gesundheitsbericht**: Automatische 24h-Zusammenfassung mit allen Metriken
- **Alert Cooldowns**: Intelligente Spam-Prävention für wiederholte Alerts
- **Multi-Channel Benachrichtigungen**: Alerts sowohl über Discord Status-Channel als auch ShadowOps

### 📊 Performance Profiling
- **`/profile` Command**: Umfassendes Performance-Profiling für Administratoren
  - Langsamste Operationen (sortiert nach Durchschnittszeit)
  - Meistgenutzte Operationen (Call-Counts und Gesamtzeit)
  - Bottleneck-Analyse: Identifiziert kritische Engpässe (langsam + häufig)
  - System-Ressourcen: CPU, RAM, Thread-Count
- **Performance Decorator**: `@track_performance()` für automatisches Tracking
  - Async/Sync Unterstützung
  - Fehler-Tracking
  - Warnung bei langsamen Operationen (>1s)
- **PerformanceTracker Singleton**: Zentrales Tracking über alle Cogs hinweg
  - 100 letzte Ausführungen pro Operation
  - Statistiken: Min, Max, Average, Total, Error-Count

### 📈 Enhanced Status & Reporting
- **`/status` Command**: Verbesserte System-Übersicht
  - Bot-Status: Uptime, Memory, Guild-Count
  - Datenbank: Größe, Status-Indicator
  - Rate Limits: Aktuelle req/s, Hit-Count, Status
  - Letzte Verifikation: Zeitpunkt, Genauigkeit
  - Message Deduplication: Gesamt gesehen, blockiert, Rate
  - ShadowOps: Queue-Status, Enabled/Disabled
- **Message Deduplication Stats**: Echtzeit-Tracking
  - Gesamt gesehene Messages
  - Blockierte Duplikate
  - Deduplizierungs-Rate in %
- **Weekly Reports**: Automatische Wochenberichte (Montag 09:00 UTC)
  - Aktivitäts-Zusammenfassung (Messages, User, Durchschnitt/Tag)
  - Top 5 User und Channels
  - Verifikations-Statistiken
  - System Performance Metriken
  - Versand an Status-Channel und ShadowOps

### 🔐 Webhook Security
- **HMAC-SHA256 Signature Verification**: Sichere Webhook-Kommunikation mit ShadowOps
  - Shared Secret: `guildscout_shadowops_secure_key_2024`
  - Signatur-Header: `X-Webhook-Signature: sha256=<hash>`
  - Schutz vor gefälschten Alerts und Replay-Attacks
  - Constant-time Signatur-Vergleich gegen Timing-Attacks
- **ShadowOps Integration**: Erweiterte Webhook-Features
  - Health-Check vor Versand
  - Retry-Queue bei Fehlschlägen
  - Last-Health-Check Tracking für Monitoring

### 📝 Configuration Management
- **Git Auto-Commit**: Automatische Versionierung von Config-Änderungen
  - Überwacht `config.yaml` alle 60 Sekunden (SHA256-Hash)
  - Intelligente Commit-Messages zeigen geänderte Keys
  - Einfaches Rollback: `git checkout HEAD~1 config/config.yaml`
  - Behält letzte 10 Config-Versionen in Git History

### 💾 Database Monitoring
- **Daily Size Monitoring**: Tägliche Überwachung der Datenbankgröße
  - Warnung via Discord bei > 100 MB
  - Status-Indicator im `/status` Command
  - Integration mit wöchentlichem VACUUM (Montag 04:00 UTC)

### 🔧 Technical Improvements
- **Performance Tracking**: Verifikations-Jobs werden automatisch getrackt
- **Enhanced Logging**: Strukturiertes Logging für alle neuen Module
- **Error Handling**: Robuste Fehlerbehandlung in Health Checks
- **Async Optimization**: Non-blocking Git-Operationen via Thread-Pool

### 📚 Documentation
- Neue `MONITORING.md`: Umfassende Monitoring-Dokumentation
- Neue `WEBHOOK_SECURITY.md`: Webhook-Sicherheit und Setup
- Aktualisiertes `README.md`: Neue Commands und Features
- Changelog erweitert mit allen neuen Features

### 🐛 Bug Fixes
- Fix: `inspect.iscoroutinefunction` statt `functools.iscoroutinefunction` in Performance Decorator
- Fix: Korrekte Signatur-Generierung mit sortierten JSON-Keys

### ⚙️ Configuration Changes
**Neue Config-Option in `config.yaml`:**
```yaml
shadowops:
  webhook_secret: guildscout_shadowops_secure_key_2024  # NEU: HMAC Secret
```

### 📦 New Files
**Core Features:**
- `src/tasks/health_monitor.py` - Health Monitoring System
- `src/tasks/weekly_reporter.py` - Wöchentliche Berichte
- `src/commands/status.py` - `/status` Command
- `src/commands/profile.py` - `/profile` Command
- `src/utils/config_watcher.py` - Git Auto-Commit
- `src/utils/performance_decorator.py` - Performance Tracking

**Modified Files:**
- `src/tasks/db_maintenance.py` - Size Monitoring hinzugefügt
- `src/events/message_tracking.py` - Deduplication Stats
- `src/utils/shadowops_notifier.py` - Signatur-Generierung
- `src/tasks/verification_scheduler.py` - Performance Tracking

---

## Version 2.2.0 - Resilience & Dashboard Update (2025-11-26)

> **Note:** Detaillierte Patch Notes mit verbessertem AI-System verfügbar im Discord Update-Channel.

### 🛡️ Resilience & Maintenance
- **Single Instance Lock**: Verhindert zuverlässig, dass mehrere Bot-Instanzen gleichzeitig laufen. Nutzt File-Locking für maximale Sicherheit.
- **Automatisierte Backups**: Tägliches Backup der Datenbank (05:00 UTC) in `backups/`. Rotation behält die letzten 7 Tage.
- **Datenbank-Optimierung**: Indizes für `user_id` und `channel_id` hinzugefügt für schnellere Abfragen bei großen Datenmengen.
- **Robuster Startprozess**: Neue Startsequenz verhindert Race Conditions zwischen Aufräum-Skripten, Delta-Import und Verifikations-Tasks.
- **Self-Cleaning Status**: Der Status-Kanal räumt sich bei jedem Neustart selbst auf (löscht alte Erfolgsmeldungen, behält Fehler).

### 🔄 Intelligent Delta Import
- **Keine verlorenen Nachrichten mehr**: Erkennt automatisch Downtime des Bots.
- **Delta-Import**: Importiert beim Start nur die Nachrichten, die während der Offline-Zeit verpasst wurden.
- **Performance**: Spart Zeit, da nicht mehr bei jedem Neustart komplett neu importiert werden muss.

### 📊 Dashboard & Status System
- **Persistentes Dashboard**: Die Dashboard-Nachricht wird nun wiederverwendet (ID gespeichert), statt ständig neu erstellt zu werden.
- **Lifetime Stats**: "Lifetime Nachrichten" kommen jetzt direkt aus der Datenbank (akkurat) statt aus dem RAM.
- **Live-Fortschritt**: Verifikations-Tasks zeigen nun einen Live-Fortschrittsbalken im Status-Kanal.
- **Error Acknowledgment**: Fehler im Status-Channel haben einen "Acknowledge"-Button für Admins.

### 🛠️ Bugfixes
- Fix: `command_prefix` Fehler behoben.
- Fix: Restart-Counter zählt jetzt korrekt hoch.
- Fix: Race Condition beim Bot-Start behoben (Verifikation wartet nun 10s auf Initialisierung).
- Cleanup: Log-Channel Code komplett entfernt.

---

## Version 2.1.0 - Production Features & Reliability (2025-11-19)

### 🟢 Live Tracking & Verification System

#### Live Message Tracking Embed
- **Dauerhafte Live-Embed** im Log-Channel zeigt:
  - Gesamtzahl aller Messages in der Datenbank
  - Anzahl live getrackter Messages seit Bot-Start
  - Letzte 10 Nachrichten mit Sprunglinks zu Discord
  - Automatische Aktualisierung nach Idle-Gap oder festem Intervall
- Konfigurierbare Update-Intervalle (idle_gap & interval)
- Thread-safe mit Debouncing für Performance

#### Automatisierte Verification
- **Tägliche Stichprobe** (Standard: 25 User, 03:00 UTC)
  - Prüft zufällige User (≥10 Messages) gegen Discord API
  - Postet Start/Ergebnis als Embed im Log-Channel
- **Wöchentliche Tiefenprüfung** (Standard: 150 User, Montag 04:30 UTC)
  - Größere Stichprobe für maximale Genauigkeit
- Lock-System verhindert gleichzeitige Verifikationen
- Automatisches Überspringen während laufender Imports
- Detaillierte Ergebnisse: Accuracy, Max Difference, Abweichungen

#### `/verify-message-counts` Command
- Manueller Verification-Command für Admins
- Wählbare Stichprobengröße
- Live-Fortschritt in Ephemeral Messages & Log-Channel
- Automatischer Fallback bei abgelaufenen Follow-ups
- Rate-Limit Hinweise während Prüfung

#### Auto Re-Import bei Bot-Start
- **Automatischer vollständiger Re-Import** bei jedem Bot-Neustart
- Hält MessageStore immer auf aktuellem Stand
- Live-Updates im Log-Channel (aktueller Kanal, Fortschritt, Laufzeit)
- Concurrent-safe: Neue Messages während Import werden korrekt getracked

#### Log-Channel System
- `/setup-log-channel` Command für Admin-only Channel
- Auto-Erstellung falls Channel fehlt
- Alle Bot-Events werden geloggt:
  - Bot-Start/Reconnect
  - Import-Status (Start, Fortschritt, Abschluss)
  - Verification-Ergebnisse
  - Fehler und Warnungen
- Konfigurierbar: `enable_discord_service_logs`

### 🐛 Bugfixes

#### SQLite Concurrency (Bug #11)
- **SQLite WAL-Modus aktiviert** für bessere Concurrency
- Verhindert "database is locked" Fehler
- Erlaubt gleichzeitiges Lesen während Schreibvorgängen

#### Permission & Role Hierarchy Checks (Bug #12)
- **Bot überprüft jetzt Permissions** vor Role-Assignment
- Prüft ob Bot die Rolle überhaupt verwalten kann
- Warnt wenn Bot-Rolle unter Ziel-Rolle in Hierarchie
- Verhindert fehlgeschlagene Rollenvergaben

#### Rate-Limit Protection
- Zusätzliche `defer()` Calls in Commands
- Verhindert "Interaction expired" Fehler
- Auto-retry für Discord API Calls

#### Thread-Aware Tracking
- Messages in Threads werden jetzt korrekt erfasst
- Auto-Reimport berücksichtigt alle Thread-Typen
- Historische Threads werden nicht vergessen

### 🔧 Improvements

- Bessere Fehlerbehandlung in allen Commands
- Optimierte Logging-Ausgaben
- Performance-Verbesserungen bei großen Servern
- Stabilere Discord API Integration

---

## Version 2.0.0 - Major Performance & Feature Update (2025-11-14)

### 🚀 Performance Optimierungen

#### Channel-First Message Counting Algorithm
- **MASSIV verbesserte Performance** beim Zählen von Nachrichten
- Alte Methode: User-first (langsam bei vielen Usern)
- Neue Methode: Channel-first mit paralleler Verarbeitung
- **5x schneller** bei großen Analysen (z.B. 100+ User)
- Intelligentes Batch-Processing mit konfigurierbarer Parallelität

#### Caching System
- **Infinite TTL Cache** für dauerhafte Speicherung
- Vermeidet wiederholtes Zählen derselben User
- Cache-Hit-Rate typisch 60-70% bei wiederholten Analysen
- Automatisches Cache-Management

#### Rate Limiting Handling
- Robuste Behandlung von Discord Rate Limits
- Automatische Retry-Logik mit exponential backoff
- Wartet so lange wie nötig, um vollständige Daten zu garantieren

### ✨ Neue Features

#### 1. Where Winds Meet Release Countdown Timer
- **Automatischer Countdown-Timer** für Game-Release
- Release: 14. November 2025, 22:00 GMT / 23:00 MEZ
- Updates **alle 10 Sekunden** für maximale Dynamik
- Features:
  - ASCII-Timer-Box mit großer Anzeige
  - Dynamische Hype-Texte basierend auf verbleibender Zeit
  - Farbwechsel von Blau → Violett → Orange → Rot
  - Progress Bar zum Release
  - Beide Zeitzonen (GMT & MEZ) angezeigt
  - Steam-Banner-Image
  - Automatischer Start beim Bot-Start
- Admin-Command: `/setup-wwm-timer`

#### 2. Interactive Role Assignment
- **Button-basierte Bestätigung** vor Rollenvergabe
- Verhindert versehentliche Massen-Rollenvergabe
- Zeigt Preview aller betroffenen User
- "Confirm" und "Cancel" Buttons
- Timeout nach 60 Sekunden

#### 3. Welcome Message System
- Automatische Welcome-Message im Ranking-Channel
- Zeigt aktuelle Guild-Besetzung
- Erklärt alle Commands
- **Debouncing**: Nur 1 Update alle 3 Sekunden (verhindert Spam)
- Auto-Pin der Welcome-Message

#### 4. Guild Status Command
- **Neuer Command**: `/guild-status`
- Zeigt ALLE aktuellen Guild-Members mit Scores
- Sortierung nach höchstem Score
- Automatische Field-Aufteilung (max 8 User pro Field)
- CSV-Export aller Members
- Spot-Verfügbarkeit Visualisierung
- Progress Bar für Fill-Status

#### 5. Enhanced Logging
- **Detaillierte Batch-Progress-Logs** beim Message-Counting
- Zeigt: "📊 Batch X/Y: Processing channels..."
- Echtzeit-Fortschritt für lange Operationen
- Bessere Transparenz für User

### 🔧 Bugfixes

#### Role Counting Bug
- **Problem**: Nur Guild-Role gezählt, Leader-Role ignoriert
- **Fix**: Neue Methode `count_all_excluded_members()`
- Zählt ALLE Exclusion-Roles korrekt

#### Embed Field Length Error
- **Problem**: Zu viele User (62+) führten zu >1024 Zeichen
- **Fix**: Automatische Aufteilung in Multiple Fields

#### Welcome Message Spam
- **Problem**: 50+ Role-Changes = 50+ Welcome-Message-Updates
- **Fix**: Debouncing mit 3-Sekunden-Verzögerung

#### Datetime Timezone Issues
- **Problem**: Naive datetime vs. timezone-aware
- **Fix**: Alle datetimes nutzen `timezone.utc`

### 📊 Verbesserte Analytics

- Scores sortiert nach **höchstem Score first**
- Ranking-Nummern (#1, #2, #3...)
- Message-Count pro User angezeigt
- Tage im Server angezeigt
- Vollständige CSV-Exports mit allen Daten

### 🎨 UI/UX Verbesserungen

- Bessere Embed-Formatierung mit Emojis
- Farbcodierung für verschiedene Status
- Progress Bars für visuelle Darstellung
- Field-Strukturierung für bessere Lesbarkeit

### 🔐 Security & Stability

- Admin-Only Commands mit Permission-Checks
- Error Handling für alle Discord API Calls
- Graceful Degradation bei fehlenden Permissions
- Input Validation für alle User-Inputs

---

## Commands Übersicht

### User Commands
- `/my-score [role]` - Eigenen Score anzeigen

### Admin Commands
- `/analyze role:<@Rolle> [days] [top_n]` - Analyse starten
- `/assign-guild-role ranking_role:<@Rolle> count:<Anzahl>` - Guild-Rollen vergeben
- `/guild-status` - Aktuelle Guild-Besetzung anzeigen
- `/setup-ranking-channel` - Ranking-Channel einrichten
- `/set-max-spots value:<Zahl>` - Max. Spots festlegen
- `/setup-wwm-timer` - WWM Release Timer einrichten
- `/cache-stats` - Cache-Statistiken
- `/cache-clear` - Cache leeren
- `/bot-info` - Bot-Informationen

---

## Performance Benchmarks

### Message Counting (100 Users, 33 Channels)
- **Alte Methode**: ~15 Minuten
- **Neue Methode**: ~3 Minuten
- **Mit Cache (66% Hit Rate)**: ~1 Minute

---

## Mitwirkende
- CommanderShadow - Projektleitung & Hauptentwicklung
- Claude (Anthropic) - AI-Assisted Development
