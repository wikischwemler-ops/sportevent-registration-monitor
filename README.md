# SportEvent Registration Monitor v0.2

Enthält Dashboard, dynamische Prüfintervalle und die Grundlage für iPhone/APNs-Push.

## Start
`docker compose up --build`

Dashboard: `http://localhost:8000/`
API-Doku: `http://localhost:8000/docs`

## Monitoring
Der Worker startet alle 5 Minuten, prüft aber nur aktive Events, deren `next_check_at` erreicht ist. Neue Events ohne Prüfzeitpunkt werden beim nächsten Lauf geprüft. Danach wird der Zeitpunkt anhand des Eventdatums neu gesetzt: mehr als 6 Monate vorher wöchentlich, 3–6 Monate alle 3 Tage, 1–3 Monate täglich, unter 30 Tagen alle 2 Stunden. Eine bekannte Öffnung innerhalb von 48 Stunden sowie offene oder knapp werdende Anmeldungen werden alle 5 Minuten geprüft. Fehlgeschlagene Abrufe erhalten ebenfalls einen nächsten Prüfzeitpunkt.

Beim Start ergänzt der Worker `next_check_at` automatisch in bestehenden PostgreSQL-Datenbanken.

GitHub Actions bleibt der Hintergrund-Taktgeber. Geplante Workflows können mindestens alle 5 Minuten laufen, sind aber keine Echtzeitgarantie.

## Dashboard im Browser
Der Monitoring-Workflow veröffentlicht nach jedem Lauf eine responsive Statusseite über GitHub Pages. Die Daten werden nach dem Lauf aus PostgreSQL exportiert und als Pages-Artefakt bereitgestellt; sie werden nicht in den Git-Branch committet. Aktiviere unter **Settings > Pages** als Quelle **GitHub Actions**. Die Veröffentlichungs-URL und der letzte Lauf stehen anschließend im Workflow-Run. Die Seite kann je nach Repository-Einstellungen öffentlich sein.

## iPhone
Normale APNs-Pushes werden als nächster Schritt angebunden. Kritische Alerts benötigen Apples spezielle Berechtigung.
