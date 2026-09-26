# SportEvent Registration Monitor v0.2

Enthält Dashboard, dynamische Prüfintervalle und die Grundlage für iPhone/APNs-Push.

## Start
`docker compose up --build`

Dashboard: `http://localhost:8000/`
API-Doku: `http://localhost:8000/docs`

## Monitoring
>90 Tage: wöchentlich; 30–90 Tage: täglich; <30 Tage: alle 2 Stunden; bekannte Anmeldung <48h: 5 Minuten; offene Anmeldung: 5 Minuten.

GitHub Actions bleibt der Hintergrund-Taktgeber. Geplante Workflows können mindestens alle 5 Minuten laufen, sind aber keine Echtzeitgarantie.

## iPhone
Normale APNs-Pushes werden als nächster Schritt angebunden. Kritische Alerts benötigen Apples spezielle Berechtigung.
