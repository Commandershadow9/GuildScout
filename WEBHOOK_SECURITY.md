# Webhook Security - HMAC Signature Verification

Dokumentation der Webhook-Sicherheit zwischen GuildScout und ShadowOps Bot.

## Inhaltsverzeichnis

1. [Übersicht](#übersicht)
2. [Wie es funktioniert](#wie-es-funktioniert)
3. [Setup & Konfiguration](#setup--konfiguration)
4. [Implementierung](#implementierung)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)
7. [Security Best Practices](#security-best-practices)

---

## Übersicht

### Was ist Webhook Signature Verification?

GuildScout sendet Alerts und Events an den ShadowOps Bot via HTTP Webhooks. Um sicherzustellen, dass diese Nachrichten:
- ✅ **Authentisch** sind (wirklich von GuildScout kommen)
- ✅ **Integer** sind (nicht unterwegs verändert wurden)
- ✅ **Autorisiert** sind (nicht von Angreifern gefälscht)

...verwendet GuildScout **HMAC-SHA256 Signaturen**.

### Das Problem ohne Signaturen

Jeder, der die Webhook-URL kennt, könnte gefälschte Alerts senden:

```bash
# ⚠️ UNSICHER - Ohne Signatur-Verifizierung
curl -X POST http://localhost:9091/guildscout-alerts \
  -H "Content-Type: application/json" \
  -d '{
    "source": "guildscout",
    "alert_type": "verification",
    "title": "FAKE ALERT",
    "description": "Diese Nachricht ist gefälscht!"
  }'
```

### Die Lösung: HMAC-SHA256

Mit Signaturen wird jede Nachricht kryptographisch signiert:

```bash
# ✅ SICHER - Mit Signatur
curl -X POST http://localhost:9091/guildscout-alerts \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=a3f8d9e2b1c4..." \
  -d '{...}'
```

ShadowOps verifiziert die Signatur und lehnt ungültige Requests ab (HTTP 403).

---

## Wie es funktioniert

### Schritt-für-Schritt Ablauf

```
┌─────────────┐                           ┌──────────────┐
│  GuildScout │                           │  ShadowOps   │
└──────┬──────┘                           └──────┬───────┘
       │                                         │
       │ 1. Event tritt ein                     │
       │    (z.B. Verification Complete)        │
       │                                         │
       │ 2. Erstelle JSON Payload               │
       │    payload = {"title": "...", ...}     │
       │                                         │
       │ 3. Berechne HMAC-SHA256                │
       │    signature = hmac(secret, payload)   │
       │                                         │
       │ 4. Sende HTTP POST                     │
       │────────────────────────────────────────>│
       │    Header: X-Webhook-Signature         │
       │    Body: JSON Payload                  │
       │                                         │
       │                                 5. Empfange Request
       │                                         │
       │                                 6. Berechne eigene Signatur
       │                                    expected = hmac(secret, payload)
       │                                         │
       │                                 7. Vergleiche Signaturen
       │                                    if received == expected:
       │                                      ✅ Akzeptieren
       │                                    else:
       │                                      ❌ HTTP 403 Forbidden
       │                                         │
       │<─────────────── 200 OK ─────────────────│
       │                 (oder 403)              │
```

### HMAC-SHA256 im Detail

**HMAC** = Hash-based Message Authentication Code
**SHA256** = Secure Hash Algorithm 256-bit

```python
import hmac
import hashlib

# Shared Secret (nur GuildScout & ShadowOps kennen ihn!)
secret = "guildscout_shadowops_secure_key_2024"

# JSON Payload (sortierte Keys für Konsistenz)
payload = '{"alert_type":"verification","title":"Test"}'

# Berechne Signatur
signature = hmac.new(
    secret.encode('utf-8'),
    payload.encode('utf-8'),
    hashlib.sha256
)

hex_signature = signature.hexdigest()
# Ergebnis: "a3f8d9e2b1c4567890abcdef..."
```

---

## Setup & Konfiguration

### 1. GuildScout Konfiguration

**Datei:** `/home/cmdshadow/GuildScout/config/config.yaml`

```yaml
shadowops:
  enabled: true
  webhook_url: http://localhost:9091/guildscout-alerts
  webhook_secret: guildscout_shadowops_secure_key_2024  # ← Shared Secret
  notify_on_verification: true
  notify_on_errors: true
  notify_on_health: false
```

**Wichtig:**
- ✅ `webhook_secret` muss **identisch** in beiden Bots sein
- ✅ Mindestens 32 Zeichen lang empfohlen
- ✅ Keine Sonderzeichen, die URL-Encoding brauchen

### 2. ShadowOps Konfiguration

**Datei:** `/home/cmdshadow/shadowops-bot/config/config.yaml`

```yaml
projects:
  guildscout:
    enabled: true
    tag: ⚡ [GUILDSCOUT]
    path: /home/cmdshadow/GuildScout
    webhook_secret: guildscout_shadowops_secure_key_2024  # ← Muss identisch sein!
    # ... weitere Config ...
```

### 3. Secret rotieren (Sicherheits-Best-Practice)

**Wann rotieren:**
- Bei Verdacht auf Kompromittierung
- Regelmäßig (z.B. alle 90 Tage)
- Bei Mitarbeiter-Wechsel

**Wie rotieren:**

1. **Neues Secret generieren:**
   ```bash
   # Starkes, zufälliges Secret
   openssl rand -base64 32
   # Ergebnis: "xK7pQ2m9N5vL8wR3tY6zU4aS1bC0..."
   ```

2. **In beiden Configs aktualisieren:**
   ```yaml
   # GuildScout UND ShadowOps
   webhook_secret: xK7pQ2m9N5vL8wR3tY6zU4aS1bC0...
   ```

3. **Beide Bots neu starten:**
   ```bash
   systemctl --user restart guildscout-bot.service
   # ShadowOps startet automatisch neu bei Config-Änderung
   ```

---

## Implementierung

### GuildScout Seite (Signatur-Generierung)

**Datei:** `src/utils/shadowops_notifier.py`

```python
import hmac
import hashlib
import json

class ShadowOpsNotifier:
    def __init__(self, webhook_url: str, webhook_secret: str = ""):
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret

    def _generate_signature(self, payload: str) -> str:
        """
        Generiert HMAC-SHA256 Signatur für Webhook Payload.

        Args:
            payload: JSON payload als String

        Returns:
            Hex-kodierte HMAC Signatur
        """
        if not self.webhook_secret:
            return ""  # Kein Secret = keine Signatur

        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        )
        return signature.hexdigest()

    async def _send_alert_direct(self, payload: dict) -> bool:
        """Sendet Alert mit Signatur."""
        # JSON mit sortierten Keys für Konsistenz
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)

        # Generiere Signatur
        signature = self._generate_signature(payload_str)

        # Füge Header hinzu
        headers = {}
        if signature:
            headers['X-Webhook-Signature'] = f"sha256={signature}"

        # HTTP POST
        async with self.session.post(
            self.webhook_url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            return response.status == 200
```

### ShadowOps Seite (Signatur-Verifizierung)

**Datei:** `src/integrations/guildscout_alerts.py`

```python
import hmac
import hashlib
import json
from aiohttp import web

class GuildScoutAlertsHandler:
    def __init__(self, bot, config):
        self.bot = bot
        self.webhook_secret = config.get('guildscout', {}).get('webhook_secret', '')

    def _verify_signature(self, payload: str, signature: str) -> bool:
        """
        Verifiziert HMAC Signatur des Webhook Payloads.

        Args:
            payload: Empfangener JSON Payload als String
            signature: Signatur aus X-Webhook-Signature Header

        Returns:
            True wenn Signatur gültig
        """
        # Kein Secret = keine Verifizierung (Legacy-Modus)
        if not self.webhook_secret:
            return True

        # Signatur fehlt = ungültig
        if not signature:
            return False

        # Format prüfen: "sha256=<hex>"
        if not signature.startswith('sha256='):
            return False

        received_hash = signature[7:]  # "sha256=" entfernen

        # Erwartete Signatur berechnen
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        )
        expected_hash = expected_signature.hexdigest()

        # Constant-time Vergleich (verhindert Timing-Attacks)
        return hmac.compare_digest(received_hash, expected_hash)

    async def webhook_handler(self, request: web.Request) -> web.Response:
        """Webhook-Handler mit Signatur-Verifizierung."""
        try:
            # Raw Body für Signatur-Verifizierung
            body = await request.read()
            body_str = body.decode('utf-8')

            # Signatur aus Header
            signature = request.headers.get('X-Webhook-Signature', '')

            # Verifizierung
            if not self._verify_signature(body_str, signature):
                self.logger.warning("❌ Invalid webhook signature - request rejected")
                return web.Response(text='Invalid signature', status=403)

            # JSON parsen
            payload = json.loads(body_str)

            # Weiterverarbeiten...
            await self._process_alert(payload)

            return web.Response(text='Alert received', status=200)

        except Exception as e:
            self.logger.error(f"Error processing alert: {e}")
            return web.Response(text='Internal error', status=500)
```

### Wichtige Details

#### JSON Key Sorting

Beide Seiten **müssen** die JSON-Keys sortieren:

```python
# ✅ RICHTIG - Sortierte Keys
json.dumps(payload, sort_keys=True)
# {"alert_type":"test","title":"Alert"}

# ❌ FALSCH - Unsortiert
json.dumps(payload)
# {"title":"Alert","alert_type":"test"}
# ^ Andere Reihenfolge = andere Signatur!
```

#### Constant-Time Comparison

**NICHT verwenden:**
```python
# ❌ Anfällig für Timing-Attacks
if received_hash == expected_hash:
    return True
```

**Stattdessen:**
```python
# ✅ Sicher gegen Timing-Attacks
return hmac.compare_digest(received_hash, expected_hash)
```

---

## Testing

### Manueller Test mit curl

#### 1. Signatur berechnen (Python)

```python
import hmac
import hashlib
import json

secret = "guildscout_shadowops_secure_key_2024"
payload = {
    "source": "guildscout",
    "alert_type": "verification",
    "title": "Test Alert"
}

# JSON mit sortierten Keys
payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
print("Payload:", payload_str)

# Signatur berechnen
signature = hmac.new(
    secret.encode('utf-8'),
    payload_str.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print("Signature:", f"sha256={signature}")
```

#### 2. Request senden

```bash
curl -X POST http://localhost:9091/guildscout-alerts \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=DEINE_BERECHNETE_SIGNATUR" \
  -d '{"alert_type":"verification","source":"guildscout","title":"Test Alert"}'
```

**Erwartete Antwort:**
- `200 OK` - Signatur gültig ✅
- `403 Forbidden` - Signatur ungültig ❌

### Automatisierter Test

**Datei:** `tests/test_webhook_security.py`

```python
import hmac
import hashlib
import json
import pytest
from aiohttp import web
from src.integrations.guildscout_alerts import GuildScoutAlertsHandler

@pytest.mark.asyncio
async def test_valid_signature():
    """Test mit gültiger Signatur."""
    secret = "test_secret_123"
    handler = GuildScoutAlertsHandler(None, {'guildscout': {'webhook_secret': secret}})

    payload = '{"alert_type":"test","source":"guildscout"}'
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    assert handler._verify_signature(payload, f"sha256={signature}") == True

@pytest.mark.asyncio
async def test_invalid_signature():
    """Test mit ungültiger Signatur."""
    handler = GuildScoutAlertsHandler(None, {'guildscout': {'webhook_secret': 'secret'}})

    payload = '{"alert_type":"test"}'
    fake_signature = "sha256=invalidhash"

    assert handler._verify_signature(payload, fake_signature) == False

@pytest.mark.asyncio
async def test_missing_signature():
    """Test ohne Signatur."""
    handler = GuildScoutAlertsHandler(None, {'guildscout': {'webhook_secret': 'secret'}})

    assert handler._verify_signature('{"test":1}', '') == False

@pytest.mark.asyncio
async def test_no_secret_configured():
    """Test Legacy-Modus ohne Secret."""
    handler = GuildScoutAlertsHandler(None, {'guildscout': {}})

    # Ohne Secret wird nicht verifiziert (Abwärtskompatibilität)
    assert handler._verify_signature('{"test":1}', '') == True
```

---

## Troubleshooting

### Problem: Alle Webhooks werden mit 403 abgelehnt

**Symptome:**
```
❌ Invalid webhook signature - request rejected
```

**Mögliche Ursachen:**

1. **Secrets stimmen nicht überein**
   ```bash
   # GuildScout Config prüfen
   grep webhook_secret /home/cmdshadow/GuildScout/config/config.yaml

   # ShadowOps Config prüfen
   grep webhook_secret /home/cmdshadow/shadowops-bot/config/config.yaml

   # Müssen IDENTISCH sein!
   ```

2. **JSON Key Sorting fehlt**
   - Prüfe dass beide Seiten `sort_keys=True` verwenden
   - Teste mit curl (siehe oben)

3. **Encoding-Probleme**
   ```python
   # Beide Seiten müssen UTF-8 verwenden
   secret.encode('utf-8')
   payload.encode('utf-8')
   ```

4. **Whitespace in Secret**
   ```yaml
   # ❌ FALSCH - Trailing Whitespace
   webhook_secret: "my_secret "

   # ✅ RICHTIG
   webhook_secret: my_secret
   ```

### Problem: Signaturen manchmal gültig, manchmal nicht

**Symptome:** Intermittierende 403 Errors

**Lösung:**
- Prüfe auf Race Conditions bei Config-Reload
- Stelle sicher dass Secret nicht während Laufzeit geändert wird
- Prüfe Logs auf Encoding-Warnungen

### Problem: Legacy-Webhooks (ohne Secret) funktionieren nicht mehr

**Symptome:** Alte Webhooks ohne Signatur werden abgelehnt

**Lösung:**

**Temporär (Entwicklung):**
```yaml
# ShadowOps Config - Secret entfernen
guildscout:
  # webhook_secret: ""  # Auskommentieren = keine Verifizierung
```

**Produktiv (empfohlen):**
```yaml
# Secret in beiden Configs setzen
webhook_secret: guildscout_shadowops_secure_key_2024
```

### Debug-Logging aktivieren

**GuildScout:**
```python
# In src/utils/shadowops_notifier.py
logger.debug(f"Generated signature: {signature}")
logger.debug(f"Payload: {payload_str}")
```

**ShadowOps:**
```python
# In src/integrations/guildscout_alerts.py
self.logger.debug(f"Received signature: {signature}")
self.logger.debug(f"Expected signature: sha256={expected_hash}")
self.logger.debug(f"Payload: {payload}")
```

---

## Security Best Practices

### 1. Secret Management

✅ **DO:**
- Verwende starke, zufällige Secrets (min. 32 Zeichen)
- Rotiere Secrets regelmäßig (alle 90 Tage)
- Verwende unterschiedliche Secrets für Prod/Dev
- Speichere Secrets nie in Git (nur in Config-Files)

❌ **DON'T:**
- Hardcode Secrets im Code
- Verwende einfache/vorhersagbare Secrets
- Teile Secrets öffentlich (Logs, Screenshots)
- Verwende dasselbe Secret für mehrere Services

### 2. HTTPS für Produktiv-Umgebungen

**Localhost/Development:**
```yaml
webhook_url: http://localhost:9091/guildscout-alerts  # OK für lokale Tests
```

**Produktion (Internet):**
```yaml
webhook_url: https://shadowops.example.com/guildscout-alerts  # ✅ HTTPS!
```

**Warum HTTPS:**
- Verschlüsselt Webhook-Payload (selbst wenn Secret kompromittiert)
- Verhindert Man-in-the-Middle Attacks
- Best Practice für alle Produktions-Webhooks

### 3. Rate Limiting

Implementiere Rate Limiting im Webhook-Handler:

```python
from aiohttp import web
from collections import defaultdict
from datetime import datetime, timedelta

class GuildScoutAlertsHandler:
    def __init__(self, bot, config):
        # ...
        self.request_counts = defaultdict(list)
        self.rate_limit = 100  # Max 100 requests
        self.rate_period = 3600  # Pro Stunde

    def _check_rate_limit(self, ip: str) -> bool:
        """Prüfe Rate Limit für IP."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.rate_period)

        # Entferne alte Requests
        self.request_counts[ip] = [
            t for t in self.request_counts[ip] if t > cutoff
        ]

        # Prüfe Limit
        if len(self.request_counts[ip]) >= self.rate_limit:
            return False

        # Request zählen
        self.request_counts[ip].append(now)
        return True

    async def webhook_handler(self, request: web.Request):
        ip = request.remote

        if not self._check_rate_limit(ip):
            return web.Response(text='Rate limit exceeded', status=429)

        # ... normaler Handler
```

### 4. Monitoring

**Überwache:**
- Anzahl erfolgreicher Webhooks
- Anzahl abgelehnter Webhooks (403)
- Response-Zeiten
- Retry-Queue Größe

**Alert bei:**
- Plötzlicher Anstieg von 403 Errors
- Retry-Queue > 10 Items
- Keine erfolgreichen Webhooks in 1h

### 5. Incident Response Plan

**Bei Verdacht auf kompromittierten Secret:**

1. **Sofort:** Secret rotieren (siehe oben)
2. **Logs prüfen:** Ungewöhnliche Webhook-Requests?
3. **IPs blocken:** Verdächtige IPs im Firewall sperren
4. **Monitoring:** Erhöhte Überwachung für 48h
5. **Post-Mortem:** Wie kam es zur Kompromittierung?

---

## Weiterführende Informationen

### Standards & RFCs

- **RFC 2104:** HMAC: Keyed-Hashing for Message Authentication
- **FIPS 180-4:** SHA-256 Secure Hash Standard
- **OWASP:** Webhook Security Guidelines

### Ähnliche Implementierungen

Andere Services die HMAC-Signaturen verwenden:

- **GitHub Webhooks:** `X-Hub-Signature-256`
- **Stripe Webhooks:** `Stripe-Signature`
- **Discord Webhooks:** (keine Signaturen, daher URLs mit Tokens)
- **Slack Webhooks:** `X-Slack-Signature`

### Tools

**Online Signature Generator:**
- https://www.freeformatter.com/hmac-generator.html

**Testing Tools:**
- Postman mit Pre-Request Scripts
- Insomnia mit Code Snippets
- curl + Python Script (siehe Testing Sektion)

---

**Version:** 2.3.0
**Letzte Aktualisierung:** 2025-12-01
**Autor:** GuildScout Development Team
