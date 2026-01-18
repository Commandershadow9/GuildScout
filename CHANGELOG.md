# Changelog - GuildScout Bot

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