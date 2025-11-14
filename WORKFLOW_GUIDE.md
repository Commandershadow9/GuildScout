# 🎮 GuildScout Workflow Guide - Faire Gilden-Auswahl

## 📋 Dein Use Case

Du bist Content Creator und hast **zu vielen Zuschauern Gildenzugang versprochen**, aber es gibt **weniger Plätze als erwartet**.

Du möchtest **fair** entscheiden, wer die Plätze bekommt, basierend auf:
- ⏱️ Wie lange ist jemand schon im Discord?
- 💬 Wie aktiv ist jemand (Messages)?

---

## 🚀 Schritt-für-Schritt Anleitung

### 1️⃣ Einmalige Einrichtung (5 Minuten)

#### A) Bot einladen
1. Hol dir den Bot-Invite-Link von deinem Dev
2. Lade den Bot in deinen Discord ein
3. Gib ihm diese Permissions:
   - Read Messages/View Channels
   - Read Message History
   - Send Messages
   - Embed Links
   - Attach Files
   - Manage Channels (für Ranking-Channel)

#### B) Ranking-Channel erstellen
```
/setup-ranking-channel
```

**Was passiert:**
- Bot erstellt automatisch Channel `#guild-rankings`
- Nur für Admins sichtbar
- Dort werden alle Rankings gepostet

**Alternativ:** Bestehenden Channel nutzen:
```
/setup-ranking-channel channel:#dein-admin-channel
```

---

### 2️⃣ Analyse durchführen

#### Wenn du eine bestimmte Rolle hast (z.B. @Gilden-Interessenten):
```
/analyze role:@Gilden-Interessenten
```

#### Wenn du alle aktiven Member analysieren willst:
```
/analyze role:@Members
```

#### Wenn du nur die Top 50 sehen willst:
```
/analyze role:@Gilden-Interessenten top_n:50
```

**Was passiert:**
1. Bot scannt alle User mit der Rolle
2. Zählt Messages pro User (erste Run: ~30-60s)
3. Berechnet Score:
   - **40% = Tage im Server** (Loyalität)
   - **60% = Nachrichtenanzahl** (Aktivität)
4. Postet Ergebnis in `#guild-rankings`

---

### 3️⃣ Ergebnisse im Ranking-Channel ansehen

Im `#guild-rankings` Channel siehst du:

#### 📊 Übersicht
- Gesamtzahl gescannter User
- Durchschnittswerte
- Scoring-Formel

#### 🏆 Komplettes Ranking
- Alle User sortiert nach Score
- Angezeigt in 25er-Blöcken
- Mit Medals für Top 3

#### 🔍 Transparenz-Breakdown (Top 10)
Detaillierte Berechnung zeigt GENAU wie der Score zustande kam:
```
🥇 MaxMustermann
Days Score:     85.2/100 × 0.4 = 34.1
Activity Score: 92.3/100 × 0.6 = 55.4
                            ───────────
Final Score:                  89.5
```

#### 📥 CSV-Download
Vollständige Daten zum Download für Excel/Google Sheets

---

### 4️⃣ Entscheidung treffen

#### A) Im Discord ansehen:
```
Schau dir das Ranking an und entscheide:
- "Ich habe 50 Plätze" → Die Top 50 User bekommen Zugang
- "Ich nehme nur User mit Score >75" → Ziehe die Linie bei Score 75
```

#### B) In Excel analysieren:
1. CSV runterladen
2. In Excel/Sheets öffnen
3. Sortieren, filtern, analysieren
4. Entscheidung treffen

#### C) Scoring-Gewichtung anpassen (optional):
```yaml
# In config/config.yaml
scoring:
  weights:
    days_in_server: 0.5     # 50% Mitgliedsdauer
    message_count: 0.5      # 50% Aktivität
```

Dann Bot neu starten und `/analyze` erneut ausführen.

---

### 5️⃣ User informieren (Transparent!)

#### Die User können ihren eigenen Score checken:
```
/my-score
```

**User sehen:**
- Ihren aktuellen Rang
- Ihre genaue Score-Berechnung
- Warum der Score so ist
- Perzentil (Top X%)

#### Beispiel-Ankündigung:
```
📢 Gilden-Plätze Vergabe

Aufgrund der hohen Nachfrage vergeben wir Plätze fair nach Score:

🎯 Score-Berechnung:
- 40% = Wie lange bist du im Discord?
- 60% = Wie aktiv warst du?

✅ Checke deinen Score mit: /my-score

Die Top 50 User bekommen einen Platz!
Cutoff-Score: 75.0

Fragen? Der Score ist transparent und fair berechnet!
```

---

## 💡 Beispiel-Szenario

### Ausgangssituation:
- 250 User haben Interesse (@Gilden-Interessenten)
- Du hast nur 40 Plätze
- Du willst die 40 treuesten & aktivsten User

### Vorgehen:

1. **Setup** (einmalig):
   ```
   /setup-ranking-channel
   ```

2. **Analyse**:
   ```
   /analyze role:@Gilden-Interessenten
   ```

3. **Ergebnisse ansehen** in #guild-rankings:
   - Rankings 1-25
   - Rankings 26-50
   - Rankings 51-75
   - ... bis 250

4. **Entscheidung**:
   - Top 40 User haben Score zwischen 95.2 und 82.1
   - User auf Platz 40 hat Score 82.1
   - **Cutoff: 82.1** → Alle mit Score ≥82.1 bekommen Platz

5. **Kommunikation**:
   ```
   @Gilden-Interessenten

   Die Gilden-Plätze wurden fair vergeben!

   ✅ Kriterien:
   - Wie lange im Discord (40%)
   - Wie aktiv (60%)

   📊 Checke deinen Score: /my-score

   🏆 Cutoff-Score: 82.1
   Wenn dein Score ≥82.1 ist, bist du dabei!

   DM an @Admin für Fragen!
   ```

---

## 🎯 Erweiterte Features

### Wiederholte Analysen (Cache!)
```
/analyze role:@Gilden-Interessenten
# Erste Run: 45 Sekunden
# Zweite Run (5 Minuten später): <1 Sekunde! ⚡
```

### Cache-Verwaltung:
```
/cache-stats              # Zeige Cache-Performance
/cache-clear expired      # Lösche abgelaufene Einträge
/cache-clear guild        # Lösche gesamten Cache (für fresh Analyse)
```

### Zeitbasierte Analyse:
```
/analyze role:@Members days:30
# Nur Messages der letzten 30 Tage zählen
```

---

## ❓ Häufige Fragen (FAQ)

### **Q: Kann ich die Gewichtung ändern?**
**A:** Ja! In `config/config.yaml`:
```yaml
scoring:
  weights:
    days_in_server: 0.3    # 30% Tage
    message_count: 0.7     # 70% Aktivität
```

### **Q: Was wenn User nach "Unfairness" schreien?**
**A:**
- User können mit `/my-score` SELBST ihren Score sehen
- Vollständige Transparenz der Berechnung
- Objektive Kriterien (keine Willkür)
- CSV zum Nachprüfen

### **Q: Zählt der Bot auch alte Messages?**
**A:** Ja, standardmäßig ALLE Messages. Mit `days:X` kannst du limitieren.

### **Q: Was ist mit Usern die viel Spam schreiben?**
**A:** Messages = Engagement. Du kannst aber:
- Spam-Channels excludieren in config
- Minimum-Threshold setzen
- Gewichtung anpassen (mehr Days, weniger Messages)

### **Q: Wie oft kann ich analysieren?**
**A:** So oft du willst! Der Cache macht wiederholte Analysen blitzschnell.

### **Q: Kann ich mehrere Rollen analysieren?**
**A:** Ja, führe `/analyze` mehrmals aus für verschiedene Rollen.

---

## 🔧 Troubleshooting

### Bot postet nicht in Ranking-Channel
**Lösung:**
1. Check `/ranking-channel-info`
2. Verify Bot hat Permissions
3. Re-run `/setup-ranking-channel`

### Analysen sind langsam
**Lösung:**
- Erste Analyse ist immer langsam (zählt alles)
- Wiederholungen sind schnell (Cache!)
- Use `days:30` für schnellere Analysen

### User beschweren sich
**Lösung:**
1. Erkläre die Kriterien klar
2. Zeige Transparenz (`/my-score`)
3. Lade CSV hoch als Beweis
4. Fair = objektiv, nicht subjektiv

---

## ✅ Checkliste für faire Vergabe

- [ ] Ranking-Channel erstellt (`/setup-ranking-channel`)
- [ ] Analyse durchgeführt (`/analyze role:@YourRole`)
- [ ] Ergebnisse im Ranking-Channel geprüft
- [ ] CSV heruntergeladen (Backup)
- [ ] Cutoff-Score festgelegt
- [ ] User informiert über Kriterien
- [ ] `/my-score` Command kommuniziert
- [ ] Fragen-Channel für Feedback

---

## 📊 Beispiel-Output

### Im Ranking-Channel siehst du:

```
📊 Ranking Results: @Gilden-Interessenten
Analysis completed at 2024-11-14 15:30:00 UTC

🔍 Total Users Scanned: 250
⏱️ Analysis Duration: 42.3s
💾 Cache Hit Rate: 0.0%

📐 Scoring Formula
Score = (Days × 40%) + (Messages × 60%)

📈 Statistics
Average Score: 68.4
Average Days: 145.2
Average Messages: 823.6
Highest Score: 95.2
Lowest Score: 12.3

Scroll down for complete ranking list ⬇️
```

```
🏆 Rankings 1-25 of 250

🥇 MaxMustermann
    Score: 95.2 | Days: 245 | Messages: 1,850

🥈 AnnaSchmidt
    Score: 92.8 | Days: 380 | Messages: 1,230

🥉 TomMeyer
    Score: 89.4 | Days: 290 | Messages: 1,450

...
```

```
🔍 Score Breakdown (Top 10)
Detailed calculation for transparency

🥇 MaxMustermann
Days Score:     82.1/100 × 0.4 = 32.8
Activity Score: 95.2/100 × 0.6 = 57.1
                            ───────────
Final Score:                  89.9
```

---

**Du bist jetzt bereit für eine faire, transparente Gilden-Auswahl! 🎯✨**

Fragen? Schau in die vollständige Dokumentation: `README.md`
