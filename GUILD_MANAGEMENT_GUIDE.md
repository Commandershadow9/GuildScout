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

### 3. Gewichtung anpassen (Optional)

Du kannst bestimmen, was dir wichtiger ist (Treue oder Aktivität).
Standard-Empfehlung für aktive Gilden:

```yaml
scoring:
  weights:
    days_in_server: 0.1      # 10% - Treue (Loyalty)
    message_count: 0.55      # 55% - Chat-Aktivität
    voice_activity: 0.35     # 35% - Voice-Aktivität
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
- Zählt Messages & Voice-Minuten der übrigen User
- Berechnet Fair Score (Activity + Voice + Loyalty)
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
```

### Schritt 2: Rankings ansehen

Du siehst das komplette Ranking der **verfügbaren** User:

```
🏆 Rankings 1-25 of 156

🥇 TomMeyer
    Score: 95.2 | Msg: 1,850 | Voice: 12h | Days: 245

🥈 SaraLee
    Score: 92.8 | Msg: 1,230 | Voice: 45h | Days: 120

... (und so weiter)
```

### Schritt 3: Rollen automatisch vergeben

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

---

## ⚠️ Inaktive User entfernen (Dashboard)

Im `#guild-rankings` Channel siehst du ständig aktualisiert:

**⚠️ Wackelkandidaten (Bottom 5)**
Hier stehen die 5 User, die zwar die Gilden-Rolle haben, aber am inaktivsten sind (wenig Score).

**Aktion:**
1. Klicke auf den Button **`[⚠️ Wackelkandidaten verwalten]`**.
2. Wähle einen User aus dem Dropdown-Menü aus.
3. Der Bot **entfernt** diesem User sofort die Gilden-Rolle.
4. Der Platz wird frei für neue, aktive Bewerber!

---

## 🔒 Sicherheits-Features

### Spot-Limit Checking

Wenn du versuchst zu viele Plätze zu vergeben:

```
⚠️ Warning: You're trying to assign 45 spots, but only 42 are available!
```

**Der Bot verhindert Überbelegung!** ✅

### Confirmation Required

Bevor Rollen vergeben werden, siehst du Preview:

```
⚠️ Confirm Guild Role Assignment
You are about to assign @Gilde to the following 42 users:
...
[✅ Confirm & Assign Roles]  [❌ Cancel]
```

**Nur du** kannst bestätigen.

---

## ❓ Häufige Fragen

### Q: Zählt Voice-Zeit, wenn ich gemutet bin?
**A:** Ja, aktuell zählt die reine Anwesenheit im Voice-Channel. AFK-Channel werden (wenn konfiguriert) ignoriert.

### Q: Kann ich die Gewichtung ändern?
**A:** Ja! In der `config.yaml` unter `scoring.weights`. Du kannst z.B. Voice höher gewichten oder Loyalität (Days) komplett entfernen (0.0).

### Q: Was sehen die User?
**A:** Jeder User kann `/my-score` eingeben und erhält eine **persönliche Grafik (Rank Card)** mit seinem Fortschrittsbalken für Nachrichten, Voice und Tage.

---

**Viel Erfolg bei der Gilden-Auswahl! 🎯✨**