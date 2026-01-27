# GuildScout Dashboard - Implementierungsplan

**Erstellt:** 2026-01-27
**Version:** 2.0 Final
**Status:** Phase 1-5 abgeschlossen

---

## Übersicht

Dieses Dokument beschreibt den vollständigen Implementierungsplan für das GuildScout Web-Dashboard. Alle Kernfunktionen sind implementiert und bereit für den Release.

---

## Fortschritt

| Phase | Status | Beschreibung |
|-------|--------|--------------|
| Phase 1 | ✅ Abgeschlossen | Backend API Erweiterung |
| Phase 2 | ✅ Abgeschlossen | Frontend Pages |
| Phase 3 | ✅ Abgeschlossen | WebSocket Integration |
| Phase 4 | ✅ Abgeschlossen | UX & Mobile Design |
| Phase 5 | ✅ Abgeschlossen | Multi-Guild Isolation |
| Phase 6 | ⏳ Ausstehend | Release & Dokumentation |

---

## Implementierte Features

### Backend API Endpoints

```
GET  /api/guilds/{guild_id}/analytics/rankings    # Mitglieder-Rankings
GET  /api/guilds/{guild_id}/analytics/overview    # Aktivitäts-Statistiken
GET  /api/guilds/{guild_id}/members/{user_id}/score  # Member Score
GET  /api/guilds/{guild_id}/my-score              # Eigener Score
GET  /api/guilds/{guild_id}/status                # System-Status
GET  /api/guilds/{guild_id}/activity              # Activity Feed
WS   /ws                                          # WebSocket Endpoint
```

### Frontend Pages

| Seite | Route | Beschreibung |
|-------|-------|--------------|
| Dashboard | `/guilds/{id}` | Live Board + Activity Feed |
| Analytics | `/guilds/{id}/analytics` | Charts + Ranking Table |
| Members | `/guilds/{id}/members` | Vollständige Mitglieder-Tabelle |
| My Score | `/guilds/{id}/my-score` | Persönlicher Score-Breakdown |
| Templates | `/guilds/{id}/templates` | Template-Verwaltung |
| Settings | `/guilds/{id}/settings` | Guild-Einstellungen |

### WebSocket Events

```typescript
type EventType =
  | 'raid:created'
  | 'raid:updated'
  | 'raid:signup'
  | 'raid:closed'
  | 'raid:locked'
  | 'raid:unlocked'
  | 'activity:new'
  | 'system:status'
  | 'system:health'
  | 'connection:established'
  | 'ping' | 'pong';
```

### Mobile Responsive Features

- Collapsible Sidebar mit Hamburger-Menü (< 768px)
- Touch-freundliche Buttons (min. 44px)
- Responsive Tabellen mit ausgeblendeten Spalten
- Safe-Area-Padding für Notches
- Scrollbare Filter-Buttons

### Multi-Guild Isolation

- Zentrale Zugriffsprüfung: `_require_guild_access()`
- Alle DB-Queries filtern nach `guild_id`
- WebSocket-Subscriptions pro Guild
- Session-basierte Authentifizierung

---

## Erstellte Dateien

### Backend (Python)

| Datei | Beschreibung |
|-------|--------------|
| `web_api/analytics_api.py` | Analytics Service mit Score-Berechnung |
| `web_api/activity_api.py` | Activity Feed Service |
| `web_api/websocket_manager.py` | WebSocket Connection Manager |

### Frontend (TypeScript/React)

| Datei | Beschreibung |
|-------|--------------|
| `ui/src/pages/Members.tsx` | Mitglieder-Ranking Page |
| `ui/src/pages/MyScore.tsx` | Persönliche Score Page |
| `ui/src/hooks/useWebSocket.ts` | WebSocket React Hook |
| `ui/src/context/WebSocketContext.tsx` | WebSocket Context Provider |

### Templates (Jinja2)

| Datei | Beschreibung |
|-------|--------------|
| `templates/members.html` | Member Rankings Template |
| `templates/my_score.html` | My Score Template |

### Geänderte Dateien

| Datei | Änderungen |
|-------|------------|
| `web_api/app.py` | Neue Endpoints, WebSocket, Multi-Guild |
| `ui/src/pages/Analytics.tsx` | Echte API-Daten statt Mock |
| `ui/src/pages/Dashboard.tsx` | WebSocket + Activity Feed |
| `ui/src/components/AppShell.tsx` | Mobile Responsive Sidebar |
| `ui/src/index.css` | Mobile Utilities |
| `ui/src/locales/en.json` | Neue Übersetzungen |
| `ui/src/locales/de.json` | Neue Übersetzungen |
| `ui/src/main.tsx` | Neue Page Imports |

---

## Technische Details

### Analytics Service

Der Analytics Service (`analytics_api.py`) berechnet Scores mit demselben Algorithmus wie der Bot:

```python
# Normalisierung auf 0-100 Skala
days_score = (user_days / max_days) × 100
msg_score = (user_messages / max_messages) × 100
voice_score = (user_voice_seconds / max_voice_seconds) × 100

# Gewichteter Gesamtscore
final = (days_score × 0.10) + (msg_score × 0.55) + (voice_score × 0.35)
```

### WebSocket Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Client    │────▶│  WebSocket       │────▶│   Events    │
│  (Browser)  │◀────│  Manager         │◀────│  (Bot/API)  │
└─────────────┘     └──────────────────┘     └─────────────┘
      │                     │
      │    subscribe        │    broadcast
      │    unsubscribe      │    to_guild
      │    ping/pong        │
```

### Guild Access Control

```python
async def _require_guild_access(request, guild_id):
    session = await _require_session(request)
    if not session:
        return None, None, {"error": "Unauthorized"}

    guilds = await _accessible_guilds(session)
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return session, None, {"error": "Guild not accessible"}

    return session, guild, None
```

---

## Datenfluss

### Rankings Abruf

```
1. User öffnet /guilds/{id}/members
2. Frontend ruft GET /api/guilds/{id}/analytics/rankings
3. Backend prüft Session + Guild Access
4. AnalyticsService lädt Daten aus messages.db
5. Scores werden berechnet und sortiert
6. JSON Response mit paginierten Rankings
7. Frontend rendert Tabelle
```

### Real-time Updates

```
1. User verbindet zu /ws
2. Server validiert Session Cookie
3. Client subscribed zu Guild(s)
4. Bei Raid-Event: Bot/API sendet an WebSocketManager
5. Manager broadcastet an alle subscribed Clients
6. Frontend aktualisiert UI
```

---

## Nächste Schritte (Phase 6)

### Release Vorbereitung

- [ ] End-to-End Testing aller Features
- [ ] Performance-Tests unter Last
- [ ] Security Review (OWASP Top 10)
- [ ] API-Dokumentation (OpenAPI/Swagger)

### Deployment

- [ ] Docker-Support (optional)
- [ ] Deployment-Anleitung finalisieren
- [ ] Backup-Strategie dokumentieren

### Post-Release

- [ ] Monitoring einrichten
- [ ] Feedback-Kanal einrichten
- [ ] Bug-Tracking vorbereiten

---

## Dokumentation

| Datei | Beschreibung |
|-------|--------------|
| `README.md` | Projekt-Übersicht und Quick Start |
| `CHANGELOG.md` | Version History |
| `WEB_UI_CONCEPT.md` | Architektur und API-Referenz |
| `ROADMAP.md` | Geplante Features |
| `DASHBOARD_IMPLEMENTATION_PLAN.md` | Dieses Dokument |

---

**Version:** 2.6.0
**Build Status:** ✅ Stable
**Production Ready:** ✅ Yes
