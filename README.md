# SportEvent Registration Monitor v0.2

Enthält Dashboard, dynamische Prüfintervalle und die Grundlage für iPhone/APNs-Push.

## Start
`docker compose up --build`

Dashboard: `http://localhost:8000/`
API-Doku: `http://localhost:8000/docs`

## Monitoring
GitHub Actions startet alle 5 Minuten und lädt die Eventliste aus `events.json` im Projektstamm. Der Worker liest den zuletzt über GitHub Pages veröffentlichten `status.json`-Snapshot und prüft nur Events, deren `next_check_at` erreicht ist. Neue Events ohne vorherigen Status werden beim nächsten Lauf geprüft. Der nächste Prüfzeitpunkt folgt dem Eventdatum: mehr als 6 Monate vorher wöchentlich, 3–6 Monate alle 3 Tage, 1–3 Monate täglich, unter 30 Tagen alle 2 Stunden. Eine bekannte Öffnung innerhalb von 48 Stunden sowie offene oder knapp werdende Anmeldungen werden alle 5 Minuten geprüft.

Events werden in `events.json` gepflegt. Beispiel:

```json
[
	{
		"id": 1,
		"name": "Mein Laufevent",
		"sport": "Laufen",
		"location": "Berlin",
		"event_date": "2027-05-01",
		"official_url": "https://example.com/event",
		"registration_url": "https://example.com/register",
		"priority": "high"
	}
]
```

Die dauerhaften Laufdaten werden über Pages zwischen den GitHub-Actions-Läufen weitergereicht. PostgreSQL und ein `DATABASE_URL`-Secret sind für den Actions-Worker nicht erforderlich. Der Snapshot liegt nur im Pages-Deployment, nicht als Statusdatei im Git-Branch.

GitHub Actions bleibt der Hintergrund-Taktgeber. Geplante Workflows können mindestens alle 5 Minuten laufen, sind aber keine Echtzeitgarantie.

## Dashboard im Browser
Der Monitoring-Workflow veröffentlicht nach jedem Lauf `dashboard/index.html` und `status.json` gemeinsam über GitHub Pages. Aktiviere unter **Settings > Pages** als Quelle **GitHub Actions**. Die Veröffentlichungs-URL und der letzte Lauf stehen anschließend im Workflow-Run. Da Pages-Statusdaten öffentlich abrufbar sein können, keine privaten Informationen in `events.json` eintragen.

## iPhone
Normale APNs-Pushes werden als nächster Schritt angebunden. Kritische Alerts benötigen Apples spezielle Berechtigung.

## Telegram-Benachrichtigungen
Telegram ist der kostenlose primäre Alarmkanal.

1. In Telegram mit `@BotFather` einen Bot anlegen und den Bot-Token kopieren.
2. Den Bot in Telegram starten oder zu einer Gruppe hinzufügen.
3. Die Chat-ID des Ziel-Chats ermitteln.
4. In GitHub Actions folgende Repository-Secrets hinterlegen:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

Der Worker prüft die Antwort der Telegram Bot API. Nicht konfigurierte Telegram-Werte werden als optionaler, nicht konfigurierter Kanal behandelt und stoppen den Monitoring-Lauf nicht.
