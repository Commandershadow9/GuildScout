# 🗺️ GuildScout Roadmap

Dieses Dokument sammelt Ideen und geplante Features für die zukünftige Entwicklung von GuildScout.

**Last Updated:** 2026-01-27

---

## ✅ Abgeschlossene Features

### v2.6.0 - Web Dashboard Complete

- [x] **Analytics API**: Member rankings mit echten Scores aus messages.db
- [x] **Analytics Page**: Tägliche/stündliche Charts, Statistiken, CSV-Export
- [x] **Members Page**: Vollständige Ranking-Tabelle mit Pagination und Suche
- [x] **My Score Page**: Persönlicher Score-Breakdown mit Percentile
- [x] **WebSocket Server**: Real-time Updates für Raid-Events
- [x] **WebSocket Client**: React Hook mit Auto-Reconnect
- [x] **Activity Feed**: Echte Events statt Mock-Daten
- [x] **Mobile Responsive**: Collapsible Sidebar, Touch-freundliche Buttons
- [x] **Multi-Guild Isolation**: Guild-gefilterte Queries für Public Release

### v2.5.0 - Web UI Foundation

- [x] **FastAPI Backend**: Grundstruktur für Web-Interface
- [x] **Discord OAuth**: Authentifizierung über Discord
- [x] **Raid Management**: Erstellen, Bearbeiten, Lock/Unlock/Close über Browser
- [x] **Templates**: Wiederverwendbare Raid-Vorlagen
- [x] **Settings**: Guild-spezifische Einstellungen

### v2.4.0 - Activity & Visuals Update

- [x] **Voice Tracking**: Exakte Erfassung von Sprachzeiten
- [x] **3-Säulen-Scoring**: Faire Gewichtung von Tagen (10%), Nachrichten (55%) und Voice (35%)
- [x] **Visual Rank Cards**: Grafische Auswertung mit `/my-score`
- [x] **Interaktives Dashboard**: Buttons zum Verwalten von Wackelkandidaten

### v2.3.0 - Advanced Monitoring & Security

- [x] **Health Monitoring**: Automatische System-Überwachung alle 5 Minuten
- [x] **Performance Profiling**: `/profile` Command für Bottleneck-Analyse
- [x] **Webhook Security**: HMAC-SHA256 Signatur-Verifizierung
- [x] **Weekly Reports**: Automatische Wochenberichte

---

## 🚀 Geplante Features

### Phase 3: Enhanced User Features (Nächste Priorität)

#### 3.1 Bulk Role Assignment
- [ ] Admins können mehrere User gleichzeitig Rollen zuweisen
- [ ] Auswahl über Checkboxen in der Members-Tabelle
- [ ] Bestätigungs-Dialog vor Ausführung

#### 3.2 Raid History Page
- [ ] Übersicht aller vergangenen Raids
- [ ] Statistiken (Teilnehmer, Fill-Rate, Absagen)
- [ ] Filterung nach Datum/Spiel/Modus
- [ ] Export als CSV

#### 3.3 Advanced Export
- [ ] PDF-Export für Rankings mit Guild-Branding
- [ ] Custom Report Templates
- [ ] Scheduled Reports (täglich/wöchentlich)

### Phase 4: Deployment & Security

#### 4.1 Docker Support
- [ ] Dockerfile für Bot + Web UI
- [ ] docker-compose.yml für einfaches Deployment
- [ ] Environment Variables für alle Secrets

#### 4.2 API Security
- [ ] Rate Limiting für alle API-Endpoints
- [ ] API-Keys für externe Integrationen
- [ ] Audit Logging für Admin-Aktionen

#### 4.3 Monitoring
- [ ] Prometheus Metrics Export
- [ ] Grafana Dashboard Templates
- [ ] Custom Alerting Rules

### Phase 5: Community Features (Langfristig)

#### 5.1 Qualitäts-Filter für Nachrichten (Anti-Spam Scoring)
- [ ] **Mindestlänge**: Nachrichten unter X Zeichen zählen nicht
- [ ] **Gewichtung**: Lange Nachrichten geben leicht mehr Punkte (capped)
- [ ] **Wiederholungsschutz**: Gleiche Nachrichten hintereinander ignorieren

#### 5.2 Erweiterte Voice-Analyse
- [ ] Erkennung von Mute/Deafen (weniger Punkte als aktive Sprecher)
- [ ] Optional: Speech Activity (nur wenn grüner Ring leuchtet)

#### 5.3 Gamification
- [ ] Achievements für Meilensteine (1000 Nachrichten, 100h Voice, etc.)
- [ ] Leaderboard-Seasons (monatliche Resets)
- [ ] Activity Streaks

---

## 📊 Priorisierung

| Feature | Priorität | Aufwand | Status |
|---------|-----------|---------|--------|
| Bulk Role Assignment | Hoch | Mittel | Geplant |
| Raid History | Hoch | Mittel | Geplant |
| Docker Support | Mittel | Niedrig | Geplant |
| API Rate Limiting | Mittel | Niedrig | Geplant |
| PDF Export | Niedrig | Mittel | Backlog |
| Anti-Spam Scoring | Niedrig | Hoch | Backlog |
| Gamification | Niedrig | Hoch | Idee |

---

## 📝 Anmerkungen

- Dieser Roadmap wird regelmäßig aktualisiert
- Feedback und Feature-Requests sind willkommen
- Prioritäten können sich basierend auf Community-Feedback ändern

---

**Version:** 2.6.0
**Nächstes Release:** Phase 3 Features
