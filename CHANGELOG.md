# Changelog - GuildScout Bot

## Version 2.6.0 - Web Dashboard Complete (2026-01-27)

> **Major Update:** Vollständiges Web-Dashboard mit Analytics, Member Rankings, WebSocket-Echtzeit-Updates und Multi-Guild-Support.

### 🎯 Dashboard Features

#### Analytics & Rankings
- **Member Rankings API**: Vollständige Integration mit `messages.db` für echte Scoring-Daten.
- **Analytics Page**: Tägliche/stündliche Aktivitätscharts, Statistiken, CSV-Export.
- **Members Page**: Paginierte Mitglieder-Tabelle mit Sortierung und Suche.
- **My Score Page**: Persönliche Score-Anzeige mit Breakdown (Days/Messages/Voice).

#### Echtzeit-Updates
- **WebSocket Server**: `/ws` Endpoint für Live-Updates (FastAPI).
- **Event Types**: `raid:created`, `raid:updated`, `raid:signup`, `raid:closed`, `activity:new`.
- **Auto-Reconnect**: Automatische Wiederverbindung bei Verbindungsabbruch.
- **Ping/Pong**: Keep-Alive für stabile Verbindungen.

#### Activity Feed
- **Echte Daten**: Activity Feed lädt jetzt echte Events aus `raids.db`.
- **Event-Typen**: Raid-Erstellung, Sign-ups, Lock/Close-Events.
- **Live-Updates**: Neue Events erscheinen via WebSocket in Echtzeit.

### 📱 Mobile Responsive Design

- **Collapsible Sidebar**: Hamburger-Menü auf Mobile (< 768px).
- **Touch-Friendly**: Buttons mit min. 44px Touch-Target.
- **Responsive Tabellen**: Spalten werden auf kleinen Bildschirmen ausgeblendet.
- **Safe-Area-Support**: Padding für Geräte mit Notches.

### 🔒 Multi-Guild Database Isolation

- **Zentrale Zugriffsprüfung**: `_require_guild_access()` Hilfsfunktion.
- **Guild-Filter**: Alle Datenbank-Queries filtern nach `guild_id`.
- **WebSocket-Subscriptions**: Benutzer erhalten nur Events ihrer Guilds.
- **Session-Validierung**: Strenge Prüfung auf Guild-Mitgliedschaft.

### 📁 Neue Dateien

**Backend:**
- `web_api/analytics_api.py` - Analytics Service mit Score-Berechnung
- `web_api/activity_api.py` - Activity Feed Service
- `web_api/websocket_manager.py` - WebSocket-Verbindungsverwaltung

**Frontend:**
- `ui/src/pages/Members.tsx` - Mitglieder-Ranking Page
- `ui/src/pages/MyScore.tsx` - Persönliche Score Page
- `ui/src/hooks/useWebSocket.ts` - WebSocket React Hook
- `ui/src/context/WebSocketContext.tsx` - WebSocket Context Provider
- `ui/templates/members.html` - Jinja Template
- `ui/templates/my_score.html` - Jinja Template

### 🛠️ API Endpoints

```
GET  /api/guilds/{guild_id}/analytics/rankings
GET  /api/guilds/{guild_id}/analytics/overview
GET  /api/guilds/{guild_id}/members/{user_id}/score
GET  /api/guilds/{guild_id}/my-score
GET  /api/guilds/{guild_id}/status
GET  /api/guilds/{guild_id}/activity
WS   /ws
```

### ⚡ Performance-Optimierungen

- **Bundle-Größe reduziert**: Main Bundle von **842 KB** auf **194 KB** (-77%) durch Code-Splitting.
- **Lazy Loading**: Alle Pages werden erst bei Bedarf geladen (4-11 KB pro Page).
- **Vendor Chunks**: Große Bibliotheken (recharts, framer-motion) werden in separate Chunks aufgeteilt.
- **Unbenutzte Dependencies entfernt**: Three.js (3D-Bibliothek) wurde entfernt - war nie verwendet.
- **Vite Manifest**: Hash-basierte Asset-URLs für optimales Browser-Caching.
- **ES2020 Target**: Moderner JavaScript-Output für kleinere Dateien.

### 🐛 Bugfixes

- **JavaScript BigInt Safety**: Discord Guild-IDs (64-bit Integers) werden jetzt als Strings an das Frontend übertragen, um JavaScript-Rundungsfehler zu vermeiden (JavaScript kann Integers > 2^53-1 nicht sicher darstellen).
- **Navigation Menu**: Guild-spezifische Menüpunkte werden jetzt nur angezeigt, wenn eine Guild ausgewählt ist.
- **WebSocket Guild IDs**: WebSocket-Events senden `guild_id` als String für konsistente Vergleiche.
- **Template Typo**: `n()` zu `t()` in Templates.tsx korrigiert.

### 🔧 Änderungen

- `web_api/app.py` - Neue API-Endpunkte, WebSocket, Multi-Guild, BigInt-Fix mit `_guild_for_frontend()`
- `web_api/websocket_manager.py` - Guild-IDs als Strings für BigInt-Sicherheit
- `ui/src/pages/Analytics.tsx` - Echte API-Daten statt Mock, String-IDs
- `ui/src/pages/Dashboard.tsx` - WebSocket-Integration, Activity Feed, String-IDs
- `ui/src/components/AppShell.tsx` - Mobile Responsive Sidebar, Guild-Filter für Navigation
- `ui/src/hooks/useWebSocket.ts` - String-IDs für BigInt-Sicherheit
- `ui/src/index.css` - Mobile Utilities

---

## Version 2.5.0 - Web UI Foundation & Templates (2026-01-18)

> **Major Update:** Grundsteinlegung für das Web-Interface und Einführung eines Template-Systems für Raids.

### 🌐 Web UI (Preview)
- **FastAPI Backend**: Neuer `web_api/` Ordner mit Backend-Logik für das kommende Web-Interface.
- **Discord OAuth**: Authentifizierung via Discord für sicheren Zugriff.
- **Raid Management**: Vorbereitung für das Erstellen und Verwalten von Raids über den Browser.
- **Konzept**: Detailliertes Konzept in `WEB_UI_CONCEPT.md` hinterlegt.

### 📋 Raid Templates
- **Template Store**: Neues Datenbanksystem (`RaidTemplateStore`) zum Speichern von Raid-Aufstellungen (Tanks, Healers, DPS).
- **Wiederverwendbarkeit**: Raids können künftig basierend auf gespeicherten Vorlagen erstellt werden.

### 🛠️ Infrastructure
- **Web UI Script**: Neues Start-Skript `scripts/run_web_ui.sh`.
- **Database**: Erweiterung der Datenbank-Module in `src/database/`.

---

## Version 2.4.0 - Activity & Visuals Update (2025-12-06)

> **Major Update:** Einführung von Voice Tracking, visuellen Rank Cards und einem fairen 3-Säulen-Scoring-System.

### 🎤 Voice Tracking
- **Voice Activity Monitoring**: Der Bot erfasst nun automatisch die Zeit, die Nutzer in Voice-Kanälen verbringen.
- **Präzise Erfassung**: Tracking startet sofort bei Channel-Beitritt und endet beim Verlassen/Wechseln.
- **Configurable**: Mindestdauer (default 10s) und AFK-Channel-Ausschluss konfigurierbar.
- **Integration**: Voice-Minuten werden im Dashboard, in `/my-score` und in der Analyse angezeigt.

### 📊 3-Säulen-Scoring (Fairness Update)
- **Neues Berechnungsmodell**: Statt nur Nachrichten und Tage gibt es nun drei gewichtete Faktoren.
- **Standard-Gewichtung**:
  - **10%** Days in Server (Loyalität) - _Reduziert, damit Inaktive nicht nur durch Alter gewinnen._
  - **55%** Message Activity (Engagement)
  - **35%** Voice Activity (Präsenz)
- **Flexibel**: Gewichte sind in `config.yaml` frei anpassbar.

### 🖼️ Visual Rank Cards
- **Grafische Auswertung**: Der Befehl `/my-score` generiert nun eine schicke PNG-Grafik (Rank Card).
- **Features**:
  - Avatar des Nutzers
  - Kreis-Diagramm für Gesamt-Score
  - Balken-Diagramme für Nachrichten, Voice und Tage
  - Modernes Dark-Theme Design mit Gitter-Hintergrund

### ⚡ Interactive Dashboard
- **Action-Buttons**: Admins können "Wackelkandidaten" (inaktive User mit Rolle) nun direkt per Button verwalten.
- **Smart Scanner**: Der Scanner für Wackelkandidaten ignoriert nun Exclusion-Roles korrekt, um auch "geschützte" User auf Inaktivität zu prüfen.
- **Live-Status**: Anzeige der Gesamt-Voice-Stunden des Servers im Dashboard.

### 🔧 Improvements & Fixes
- **Scorer Refactoring**: Kompletter Umbau der `Scorer`-Klasse für das neue Modell.
- **Config Patch**: Automatische Anpassung alter Config-Dateien auf die neuen Standardwerte.
- **Bugfix**: `NameError: Optional` in `scorer.py` behoben.
- **Bugfix**: Dashboard-Button fand keine User (Scanner-Logik korrigiert).

---

## Version 2.3.0 - Advanced Monitoring & Security (2025-12-01)
... (Rest wie zuvor)