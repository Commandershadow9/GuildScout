# 🗡️ Raid Guide (Where Winds Meet)

Dieses Dokument erklaert das komplette Raid-System in GuildScout:
Erstellung, Teilnahme, Verwaltung, Konfiguration und Troubleshooting.

---

## ✅ Voraussetzungen

- Raid-Funktion ist aktiviert (`raid_management.enabled: true`).
- Ein Info-Post existiert (per `/raid-info-setup` oder `/raid-setup`).
- Ersteller haben eine passende Rolle (Admin oder `creator_roles`).

---

## 📌 Rollen und Reaktionen

Rollen im Raid:
- **Tank** (🛡️)
- **Healer** (💉)
- **DPS** (⚔️)
- **Reserve** (🪑)

Reaktionen:
- **🛡️ / 💉 / ⚔️ / 🪑** = Anmeldung
- **❌** = Abmelden

Regeln:
- **Nur eine Rolle pro Person**.
- Wenn eine Rolle voll ist, wirst du automatisch auf **Reserve** gesetzt (sofern frei).
- In **Gesperrt**-Status ist nur Reserve moeglich.

---

## 🧭 Raid erstellen (Ersteller/Admin/Lead)

### Methode A: Button
1) Im `#raid-info` auf **"Raid erstellen"** klicken.  
2) Titel + Beschreibung eingeben.  
3) Datum und Uhrzeit ueber Dropdowns waehlen (Wochen blättern).  
4) Slots waehlen oder Vorlage nutzen.  
5) **"Raid posten"** klicken.  

### Methode B: Command
`/raid-create`

---

## 🧩 Slot-Vorlagen (Templates)

Im Slot-Schritt kannst du **"Vorlage wechseln"** nutzen.  
Die Vorlagen sind aktuell im Code definiert:

Datei: `src/commands/raid.py`

```py
SLOT_TEMPLATES = [
    ("Standard", {ROLE_TANK: 2, ROLE_HEALER: 2, ROLE_DPS: 6, ROLE_BENCH: 0}),
    ("Klein", {ROLE_TANK: 1, ROLE_HEALER: 1, ROLE_DPS: 3, ROLE_BENCH: 0}),
    ("Gross", {ROLE_TANK: 3, ROLE_HEALER: 3, ROLE_DPS: 9, ROLE_BENCH: 2}),
]
```

Sag Bescheid, wenn du andere Vorlagen willst, dann passe ich sie an.

---

## 👥 Teilnahme / Anmeldung

Im Raid-Post kannst du dich per Reaktion anmelden.  
Du erscheinst in der Teilnehmerliste mit deiner Rolle.

Wenn **Reserve** frei ist:
- Voller Slot -> automatisch Reserve + Hinweis per DM.

Wenn **Reserve** ebenfalls voll ist:
- Anmeldung wird abgelehnt.

---

## 🧾 Teilnehmerrolle

Optional kann eine Teilnehmerrolle genutzt werden:
- Standardname: **"Raid Teilnehmer"**
- Wird automatisch erstellt, falls sie fehlt.
- **Beim Anmelden vergeben**.
- **Beim Abmelden oder Raid-Ende entfernt**.

Rolle konfigurieren:
`/raid-set-participant-role @Rolle`

---

## 🔐 Raid-Status

Status im Embed:
- **Offen**: normale Anmeldung moeglich
- **Gesperrt**: nur Reserve moeglich
- **Geschlossen**: Raid ist gestartet/abgeschlossen
- **Abgesagt**: Raid wurde abgesagt

Signups-Status im Titel:
- **SIGNUPS OPEN** (gruen): Anmeldung moeglich
- **ALMOST FULL** (gelb): wenige Slots frei
- **SIGNUPS CLOSED** (rot): geschlossen oder voll

Auto-Close:
Standard: Der Raid wird automatisch zur Startzeit geschlossen.
Optional: Auto-Close kann deaktiviert werden (siehe Config).
Sicherung: Optional nach X Stunden automatisch schliessen.

## 🧹 Aufraeumen

Wenn ein Raid **geschlossen oder abgesagt** wird, loescht der Bot den Post
automatisch aus dem Channel, damit nur offene Raids sichtbar sind.
Zusatz: Erinnerungsposts zum Raid werden ebenfalls entfernt.

---

## 🧰 Verwaltung (Buttons im Raid-Post)

Nur Ersteller, Admins oder Creator-Rollen koennen verwalten.

Buttons:
- **✏️ Bearbeiten**: Titel/Beschreibung/Startzeit anpassen
- **🔒 Sperren/Oeffnen**: Anmeldung sperren oder wieder oeffnen
- **✅ Abschliessen**: Raid manuell schliessen
- **🛑 Absagen**: Raid absagen
- **⏭️ Folge-Raid**: Neuen Raid mit gleichem Titel/Slots erstellen (nur Zeit waehlen)
- **⚙️ Slots**: Slotzahlen anpassen (Reserve wird automatisch hochgezogen)

Optionales Logging:
- Wenn `log_channel_id` gesetzt ist, postet der Bot beim Abschluss/Abbruch
  eine kurze Raid-Zusammenfassung in den Log-Channel.

---

## ⏰ Erinnerungssystem

Erinnerungen vor Start (Default: 24h und 1h):
- Wird im Raid-Channel gepostet
- Optional mit Teilnehmerrolle erwaehnen

DM-Erinnerung (Default: 15 Minuten vor Start):
- Der Bot schickt eine DM an alle angemeldeten Teilnehmer.

Check-in (Default: 15 Minuten vor Start):
- Der Bot postet eine Nachricht mit ✅.
- Teilnehmer bestaetigen ihre Teilnahme per Reaktion.
- Im Raid-Embed siehst du, wer noch offen ist.

Slots frei Ping (Cooldown: 30 Minuten):
- Wenn Slots frei werden, pingt der Bot @Raid Teilnehmer.

Check-in Reminder (Default: 5 Minuten vor Start):
- Nur die **unbestaetigten** Teilnehmer werden nochmal gepingt.

No-Show Markierung:
- Nach Start werden nicht bestaetigte Teilnehmer als **No-Show** markiert.

Config:
```yaml
raid_management:
  reminder_hours: [24, 1]
  dm_reminder_minutes: [15]
  auto_close_at_start: true
  auto_close_after_hours: 12
  confirmation_minutes: 15
  confirmation_reminder_minutes: 5
  open_slot_ping_minutes: 30
  log_channel_id: null
```

---

## 🧭 Zeit-Anzeige (DE + EN)

Im Raid-Embed steht:
- Discord Timestamp (lokal fuer jeden User)
- Deutsche Zeile
- Englische Zeile

Das hilft bei gemischten Zeitzonen.

---

## 📜 Commands (Uebersicht)

**User / Creator**
- `/raid-create` – Raid erstellen (Button-Alternative)
- `/raid-list` – kommende Raids anzeigen

**Admin**
- `/raid-setup` – Raid-Channels + Teilnehmerrolle erstellen
- `/raid-set-channel` – Raid-Channel setzen
- `/raid-info-setup` – Info-Post neu erstellen
- `/raid-add-creator-role` – Creator-Rolle hinzufuegen
- `/raid-remove-creator-role` – Creator-Rolle entfernen
- `/raid-set-participant-role` – Teilnehmerrolle setzen

---

## ⚙️ Konfiguration (config.yaml)

```yaml
raid_management:
  enabled: true
  post_channel_id: 123
  manage_channel_id: 456
  info_channel_id: 789
  info_message_id: 111
  participant_role_id: 222
  log_channel_id: null
  creator_roles:
    - 333
  timezone: "Europe/Berlin"
  reminder_hours: [24, 1]
  dm_reminder_minutes: [15]
  auto_close_at_start: true
  auto_close_after_hours: 12
  confirmation_minutes: 15
  confirmation_reminder_minutes: 5
  open_slot_ping_minutes: 30
```

---

## 🩹 Troubleshooting

**"Diese Interaktion ist fehlgeschlagen"**
- Ein Update/Antwort kam zu spaet.
- Bitte den Button nochmal nutzen.

**Kein Post / kein Reaction**
- Bot fehlt die Rechte im Channel (Posten, Reactions, Manage Messages).
- In `raid-setup` den Channel neu erstellen oder Rechte pruefen.

**Zeit in der Vergangenheit**
- Datum/Uhrzeit muessen in der Zukunft liegen.

**Reserve oder Rollen voll**
- Siehe Slot-Limits im Embed.

---

Wenn du neue Features oder Anpassungen willst, sag Bescheid.
