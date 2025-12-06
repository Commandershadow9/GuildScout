# 🗺️ GuildScout Roadmap

Dieses Dokument sammelt Ideen und geplante Features für die zukünftige Entwicklung von GuildScout.

## 🚀 Geplante Features

### 1. Qualitäts-Filter für Nachrichten (Anti-Spam Scoring)
Aktuell zählt jede Nachricht gleich viel, egal ob "lol" oder ein langer Absatz. Um Spam zu vermeiden und Qualität zu belohnen:
*   **Mindestlänge:** Nachrichten unter X Zeichen (z.B. 3) zählen gar nicht.
*   **Gewichtung:** Lange Nachrichten geben leicht mehr Punkte (capped, um "Wall of Text"-Spam zu vermeiden).
*   **Wiederholungsschutz:** Gleiche Nachrichten hintereinander werden ignoriert.

### 2. Web-Dashboard
Ein einfaches Web-Interface (lokal gehostet durch den Bot), um:
*   Statistiken live zu sehen (besser als Discord Embeds).
*   Konfigurationen zu ändern ohne `config.yaml` editieren zu müssen.
*   Manuelle Imports/Exports zu starten.

### 3. Erweiterte Voice-Analyse
*   Erkennung von "Mute/Deafen": Wer nur zuhört (oder AFK ist), bekommt weniger Punkte als aktive Sprecher.
*   "Speech Activity": Wenn technisch möglich (Discord API Limitierungen beachten), nur belohnen, wenn tatsächlich gesprochen wird (grüner Ring leuchtet).

## ✅ Erledigt (v2.4.0)
*   [x] **Voice Tracking:** Exakte Erfassung von Sprachzeiten.
*   [x] **3-Säulen-Scoring:** Faire Gewichtung von Tagen (40%), Nachrichten (40%) und Voice (20%).
*   [x] **Visual Rank Cards:** Grafische Auswertung mit `/my-score`.
*   [x] **Interaktives Dashboard:** Buttons zum Verwalten von Wackelkandidaten direkt im Channel.
