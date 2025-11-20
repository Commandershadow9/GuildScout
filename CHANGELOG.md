# Changelog - GuildScout Bot

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
