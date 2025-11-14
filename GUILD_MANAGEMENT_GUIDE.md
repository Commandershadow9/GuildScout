# 🎯 Guild Management Guide - Spot Reservationen & Faire Auswahl

## 📋 Dein Szenario

Du bist Content Creator und hast:
- **50 Gilden-Plätze** verfügbar
- **Einige Plätze bereits manuell vergeben** (Freunde, Supporter, etc.)
- **Viele Bewerber** die um die restlichen Plätze konkurrieren
- **Bedarf nach fairer, transparenter Auswahl**

Dieses System löst genau das! 🎯

---

## 🚀 Setup (Einmalig)

### 1. Rolle für manuelle Reservierungen erstellen

Erstelle in Discord eine Rolle für Leute die schon einen Platz haben:
```
Rollenname: "Gilde-Platz-Reserviert"
Farbe: Orange (damit du sie leicht erkennst)
```

### 2. Config anpassen

Öffne `config/config.yaml` und füge hinzu:

```yaml
guild_management:
  # Total number of guild spots you have
  max_spots: 50

  # The actual guild role to assign
  guild_role_id: 987654321012345678    # Replace with your guild role ID

  # Roles that indicate reserved spots (exclude from ranking)
  exclusion_roles:
    - 123456789012345678    # "Gilde-Platz-Reserviert" role ID

  # Individual user IDs to exclude (optional)
  exclusion_users:
    - 111222333444555666    # User ID of specific person
```

**Wie bekommst du die IDs?**
- Enable Developer Mode in Discord
- Rechtsklick auf Rolle → "Copy Role ID"
- Rechtsklick auf User → "Copy User ID"

### 3. Manuelle Plätze vergeben

Gib den Leuten die bereits einen Platz haben die Rolle `@Gilde-Platz-Reserviert`:
```
Rechtsklick auf User → Rollen → Gilde-Platz-Reserviert aktivieren
```

**Wichtig:** Diese User werden dann NICHT im Ranking erscheinen!

### 4. Ranking-Channel einrichten

```
/setup-ranking-channel
```

---

## 📊 Workflow: Faire Auswahl treffen

### Schritt 1: Analyse durchführen

```
/analyze role:@Gilden-Interessenten
```

**Was passiert:**
- Bot scannt ALLE User mit `@Gilden-Interessenten`
- **Filtert automatisch** alle mit `@Gilde-Platz-Reserviert` heraus
- Zählt Messages der übrigen User
- Berechnet Fair Score
- Postet alles im `#guild-rankings` Channel

**Im #guild-rankings siehst du:**

```
📊 Guild Selection Ranking: @Gilden-Interessenten

🎯 Guild Spot Management:
   • Total Spots: 50
   • Already Filled: 8 (reserved/manual)
   • Available: 42
   • Candidates Ranked: 156

⏱️ Analysis Duration: 34.2s
💾 Cache Hit Rate: 15.3%
```

### Schritt 2: Excluded Members ansehen

Der Bot zeigt dir GENAU wer ausgeschlossen wurde:

```
🔒 Reserved Spots (8)

These users already have reserved guild spots and were not included in the ranking:

• MaxMustermann (ID: 123456789)
  └ Reason: Has reserved spot role (@Gilde-Platz-Reserviert)

• AnnaSchmidt (ID: 987654321)
  └ Reason: Manual reservation (User ID)

... (und so weiter)
```

**So siehst du:**
- Wer bereits einen Platz hat
- Warum (Rolle oder User-ID)
- Keine doppelten Vergaben möglich!

### Schritt 3: Rankings ansehen

Du siehst das komplette Ranking der **verfügbaren** User:

```
🏆 Rankings 1-25 of 156

🥇 TomMeyer
    Score: 95.2 | Days: 245 | Messages: 1,850

🥈 SaraLee
    Score: 92.8 | Days: 380 | Messages: 1,230

... (und so weiter)
```

### Schritt 4: Entscheidung treffen

Du hast **42 verfügbare Plätze**. Optionen:

**Option A: Top 42 nehmen**
```
Die besten 42 User aus dem Ranking bekommen die Plätze
```

**Option B: Score-Cutoff setzen**
```
Alle mit Score ≥ 85.0 bekommen einen Platz
(Musst dann nachzählen ob es <= 42 sind)
```

**Option C: Excel-Analyse**
```
CSV runterladen und in Excel/Sheets analysieren
```

### Schritt 5: Rollen automatisch vergeben

**DAS IST DER GAME-CHANGER!** 🚀

Anstatt 42 User manuell die Rolle zu geben, macht der Bot das:

```
/assign-guild-role ranking_role:@Gilden-Interessenten count:42
```

**Was passiert:**
1. Bot re-analysiert um aktuelles Ranking zu haben
2. Nimmt die Top 42 User
3. Zeigt dir Preview mit Bestätigung
4. Du klickst "✅ Confirm & Assign Roles"
5. **Bot gibt automatisch allen die Gilden-Rolle!**

**Mit Score-Cutoff:**
```
/assign-guild-role ranking_role:@Gilden-Interessenten count:50 score_cutoff:85.0
```
Nimmt max. 50 User, aber NUR die mit Score ≥ 85.0

---

## 🔒 Sicherheits-Features

### Spot-Limit Checking

Wenn du versuchst zu viele Plätze zu vergeben:

```
⚠️ Warning: You're trying to assign 45 spots, but only 42 are available!

Total spots: 50
Already filled: 8
Available: 42

Please reduce the count or use /cache-clear to update reserved spots.
```

**Der Bot verhindert Überbelegung!** ✅

### Confirmation Required

Bevor Rollen vergeben werden, siehst du Preview:

```
⚠️ Confirm Guild Role Assignment

You are about to assign @Gilde to the following 42 users:

Score cutoff: None (Top 42)
Spots remaining after: 0/50

Selected Users (showing 10 of 42):
#01 TomMeyer - Score: 95.2
#02 SaraLee - Score: 92.8
...

[✅ Confirm & Assign Roles]  [❌ Cancel]
```

**Nur du** kannst bestätigen (nicht andere Admins die zufällig im Channel sind).

### Logging

Alle Actions werden geloggt:
```
INFO - Assigned @Gilde to TomMeyer
INFO - Assigned @Gilde to SaraLee
...
ERROR - Failed to assign role to User123 (User left server)
```

---

## 💡 Beispiel-Szenario

### Ausgangssituation:
- 50 Gilden-Plätze total
- 12 Plätze bereits manuell vergeben (Freunde, Mods, Top-Supporter)
- 200 Bewerber mit `@Gilden-Interessenten`
- Du willst die restlichen 38 Plätze fair vergeben

### Vorgehen:

**1. Setup (einmalig)**
```
Rolle "Gilde-Platz-Reserviert" erstellen
Den 12 Leuten diese Rolle geben
Config anpassen (max_spots: 50, exclusion_roles)
/setup-ranking-channel
```

**2. Analyse**
```
/analyze role:@Gilden-Interessenten
```

**3. Results im #guild-rankings:**
```
Total Spots: 50
Already Filled: 12 (reserved/manual)
Available: 38
Candidates Ranked: 188

(12 excluded members werden separat angezeigt)
```

**4. Rankings prüfen:**
```
🏆 Rankings 1-38 of 188 ansehen
CSV runterladen für Backup
Entscheidung: Top 38 bekommen Platz
```

**5. Rollen vergeben:**
```
/assign-guild-role ranking_role:@Gilden-Interessenten count:38

[Preview ansehen]
[✅ Confirm & Assign Roles]

✅ Successfully assigned @Gilde to 38 users!
```

**6. Kommunikation:**
```
@Gilden-Interessenten

Die Gilden-Plätze wurden fair vergeben! 🏆

🎯 Kriterien:
- 40% Mitgliedsdauer
- 60% Aktivität

📊 Spots vergeben: 50/50 (alle voll!)

✅ Wenn du @Gilde hast, bist du dabei!
❌ Leider konnten nicht alle berücksichtigt werden.

User konnten mit /my-score ihren Score sehen.
Alles transparent & fair berechnet!
```

---

## 🔧 Advanced Features

### Mehrere Exclusion-Rollen

Du kannst mehrere Rollen für Reservierungen haben:

```yaml
exclusion_roles:
  - 111222333444555666    # "Gilde-Platz-Reserviert"
  - 777888999000111222    # "VIP-Gilde-Zugang"
  - 333444555666777888    # "Mod-Gilde-Platz"
```

### Individual User Exclusions

Specific User-IDs direkt ausschließen:

```yaml
exclusion_users:
  - 123456789012345678    # User1
  - 987654321098765432    # User2
```

### Cache Management

Wenn du Exclusions änderst, update den Cache:

```
/cache-clear guild
/analyze role:@Gilden-Interessenten  # Fresh analysis
```

### Partial Assignment

Du musst nicht alle verfügbaren Plätze vergeben:

```
/assign-guild-role ranking_role:@Gilden-Interessenten count:20
```
Vergibt nur 20 von 38 verfügbaren Plätzen. Rest bleibt offen.

---

## ❓ Häufige Fragen

### Q: Was wenn ich nachträglich jemandem einen Platz gebe?

**A:**
1. Gib dem User die Rolle `@Gilde-Platz-Reserviert`
2. Gib dem User die Rolle `@Gilde` (manuelle Vergabe)
3. Bei nächster `/analyze` wird er automatisch excluded
4. Verfügbare Plätze reduzieren sich um 1

### Q: Kann ich Exclusions auch nachträglich entfernen?

**A:**
1. Entferne `@Gilde-Platz-Reserviert` Rolle vom User
2. Laufe `/cache-clear guild`
3. Run `/analyze` erneut
4. User erscheint jetzt im Ranking

### Q: Was wenn jemand nach Vergabe den Server verlässt?

**A:**
- Spot wird nicht automatisch frei
- Du musst manuell entscheiden ob nachzubesetzen
- Kannst `/assign-guild-role count:1` laufen für nächsten im Ranking

### Q: Wie sehe ich wer alles bereits die Gilde-Rolle hat?

**A:**
In Discord:
```
Rechtsklick auf @Gilde Rolle → "Mitglieder anzeigen"
```

Oder im Bot:
```
/analyze role:@Gilde
```
Zeigt alle die bereits die Rolle haben.

### Q: Kann ich die Gewichtung ändern (z.B. mehr Loyalität, weniger Aktivität)?

**A:** Ja!
```yaml
scoring:
  weights:
    days_in_server: 0.6    # 60% Loyalität
    message_count: 0.4     # 40% Aktivität
```

### Q: Was wenn User sagen "Das ist unfair!"?

**A:**
- User können mit `/my-score` SELBST ihren Score sehen
- Vollständige Transparenz über Berechnung
- Objektive Kriterien (keine Willkür)
- Excluded members werden separat gezeigt (transparent wer reserviert hat)
- CSV als Nachweis/Backup

---

## 📋 Checkliste: Faire Gilden-Vergabe

- [ ] Rolle "Gilde-Platz-Reserviert" erstellt
- [ ] Config angepasst (max_spots, exclusion_roles, guild_role_id)
- [ ] Manuelle Plätze vergeben (Rolle zugewiesen)
- [ ] Ranking-Channel erstellt (`/setup-ranking-channel`)
- [ ] Analyse durchgeführt (`/analyze`)
- [ ] Exclusions geprüft (richtige User ausgeschlossen?)
- [ ] Verfügbare Plätze bestätigt
- [ ] CSV heruntergeladen (Backup)
- [ ] Entscheidung getroffen (Top X oder Score-Cutoff)
- [ ] Rollen vergeben (`/assign-guild-role`)
- [ ] Community informiert (transparent!)

---

## 🎯 Vorteile des Systems

✅ **Automatische Exclusion** - Keine doppelten Vergaben
✅ **Spot-Tracking** - Immer Übersicht wieviele Plätze frei
✅ **Faire Berechnung** - Objektive Kriterien
✅ **Transparenz** - User können Score selber sehen
✅ **Audit Trail** - Alle exclusions werden geloggt & angezeigt
✅ **Safety Checks** - Bot verhindert Überbelegung
✅ **Automatische Vergabe** - Spart ENORM Zeit
✅ **Bestätigung** - Preview vor finaler Vergabe

---

## 🚀 Commands Übersicht

| Command | Was macht es | Wer kann es nutzen |
|---------|--------------|-------------------|
| `/setup-ranking-channel` | Erstellt Admin-Channel für Rankings | Admins |
| `/analyze role:@Role` | Analysiert User (auto-excludes reservierte) | Admins |
| `/assign-guild-role role:@Role count:X` | Vergibt Gilde-Rolle an Top X | Admins |
| `/my-score` | User sieht eigenen Score | Alle |
| `/cache-clear` | Refresh Cache nach Exclusion-Änderungen | Admins |

---

**Mit diesem System hast du:**
- 100% Fairness
- 100% Transparenz
- 0% manuelle Arbeit bei Rollen-Vergabe
- Vollständige Kontrolle über Reservierungen

**Viel Erfolg bei der Gilden-Auswahl! 🎯✨**
