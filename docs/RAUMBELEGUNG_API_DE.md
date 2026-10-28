# MAP-Raumbelegung: aktualisierter API-Vertrag (Dev)

## Aufruf und Aktivierung

Profil → Raumeinstellungen → Öffentliche Belegungs-API aktivieren. GET auf:

`https://dev.map.example.org/api/v1/rooms/occupancy/?start=2026-11-01&end=2026-11-30`

Nach separatem Prod-Deployment kann die Prod-Domain verwendet werden. Dieses Update verändert ausschließlich Dev. Ohne Aktivierung: 404. Ungültige Angaben: 400, andere HTTP-Methoden: 405. Keine Zugangsdaten nötig; `Access-Control-Allow-Origin: *` ermöglicht browserseitige öffentliche GET-Aufrufe.

`start` und `end` sind ISO-Daten `YYYY-MM-DD`, beide Tage eingeschlossen. Standard: heute bis heute + 89 Tage. Maximal 366 Tage, unterstützte Jahre 2000–2100. Nur Tage mit relevanten Belegungen werden zurückgegeben. Auswertung in der MAP-Zeitzone, derzeit Europe/Berlin. Endet eine Buchung genau um Mitternacht, gehört der neue Tag nicht mehr zu ihr.

## Neue Bedeutung von `full` und `partial`

- `full`: **Jeder aktive Raum ist den gesamten lokalen Kalendertag lückenlos belegt.** Zeitabschnitte mehrerer Buchungen werden pro Raum vereinigt. Direkt angrenzende Abschnitte zählen als durchgehend; Überschneidungen werden nicht doppelt gezählt.
- `partial`: Es gibt eine relevante Belegung, aber mindestens ein Raum oder ein Zeitabschnitt des Tages ist frei. Auch eine Buchung aller Räume von 00:00 bis 18:00 bleibt `partial`.
- `none`: Keine entsprechende Belegung. Dieser Wert kommt in den getrennten Statusfeldern vor; komplett leere Tage werden ausgelassen.

Beispiele: Alle Räume 00–12 Uhr und anschließend 12–24 Uhr → zusammen `full`. Alle Räume 00–18 Uhr → `partial`. Ein Raum ganztägig, andere Räume frei → `partial`. Mehrtägige Buchung von Tag 1 mittags bis Tag 3 um 18 Uhr → erster und letzter Tag teilweise, ein vollständig abgedeckter mittlerer Tag gegebenenfalls voll.

Die Berechnung verwendet echte Zeitintervalle und berücksichtigt auch lokale Tage mit 23 oder 25 Stunden bei einer Zeitumstellung. Eine kurze Lücke zwischen zwei Terminen verhindert `full`.

## Antwort

```json
{
  "version": 1,
  "timezone": "Europe/Berlin",
  "start": "2026-11-01",
  "end": "2026-11-30",
  "aggregation": "continuous_full_day",
  "semantics": "full means every active room is continuously occupied for the complete local calendar day across all matching bookings",
  "days": [
    {
      "date": "2026-11-07",
      "occupancy": "partial",
      "statuses": ["approved", "pending"],
      "approved": "partial",
      "pending": "partial",
      "rooms": ["Raum 1", "Raum 2", "Garten"],
      "approved_rooms": ["Raum 1", "Garten"],
      "pending_rooms": ["Raum 2", "Garten"]
    }
  ]
}
```

`rooms` enthält die **Vereinigung aller an diesem Tag betroffenen aktiven Räume**, ohne doppelte Namen, in ihrer konfigurierten Reihenfolge. Eine kurze Teilzeitbuchung genügt für die Aufnahme in dieses Array. `approved_rooms` und `pending_rooms` trennen diese Vereinigung nach Status. Das Array ist keine Aussage über gemeinsame Uhrzeiten.

`occupancy` berücksichtigt genehmigte und schwebende Einträge gemeinsam. `approved` und `pending` beurteilen die jeweilige zeitliche Abdeckung separat. `statuses` enthält `approved` (genehmigt) und/oder `pending` (schwebend).

Offene Änderungsanträge genehmigter Buchungen zählen als schwebend zusätzlich zur weiterhin gültigen genehmigten Fassung. Abgelehnte/stornierte Einträge und archivierte Räume zählen nicht. Personen, Kontaktdaten, Gruppierungen, Veranstaltungszwecke, Buchungs-IDs und konkrete Uhrzeiten werden nicht veröffentlicht. **Raumnamen sind jetzt ausdrücklich öffentliche Daten dieses Endpunkts.**

Diese Änderung ersetzt die frühere Dev-Bedeutung „alle Räume irgendwann an diesem Tag betroffen“. Die URL und Versionsnummer bleiben während dieser Dev-Weiterentwicklung gleich; `aggregation=continuous_full_day` kennzeichnet die neue Berechnung. Bereits angepasste Frontends sollten ihre Erklärungstexte aktualisieren.

## WordPress

Das aktualisierte Beispielplugin `wordpress-map-raumbelegung.php` zeigt zusätzlich die betroffenen Räume an und erklärt `full` als ganztägige lückenlose Belegung aller aktiven Räume. Als eigenes Plugin ablegen/aktivieren und `[map_raumbelegung]` verwenden. Die URL im Plugin zeigt zunächst auf Dev. Der erfolgreiche Abruf wird 60 Sekunden serverseitig gecached. Bei Fehlern erscheint „nicht verfügbar“, niemals „alles frei“.

Die Datei wird durch den MAP-Update-Befehl nicht in WordPress installiert und wurde nicht auf eurer echten WordPress-Seite ausgeführt. Nicht zusätzlich als identischen Code-Snippet einbinden, wenn sie bereits als Plugin aktiv ist.

## Kopierbarer Folgeauftrag

> Baue eine zugängliche, mobil gut lesbare WordPress-Raumbelegungsübersicht für die öffentliche MAP-GET-API `/api/v1/rooms/occupancy/?start=YYYY-MM-DD&end=YYYY-MM-DD`. Dev-Domain: `https://dev.map.example.org`, Prod erst nach separatem Deployment. Beide Grenztage inklusive, höchstens 366 Tage, Europe/Berlin. Antwort enthält `aggregation=continuous_full_day` und `days` mit `date`, `occupancy` (`partial`/`full`), `statuses` (`approved`/`pending`), separaten Abdeckungen `approved`/`pending` (`none`/`partial`/`full`) und den Namensarrays `rooms`, `approved_rooms`, `pending_rooms`. `full` heißt: Jeder aktive Raum ist den ganzen lokalen Tag lückenlos durch die vereinigten Buchungen belegt. Eine Belegung nur bis 18 Uhr ist `partial`. Namensarrays vereinigen alle betroffenen Räume ohne Duplikate und verraten keine konkreten Uhrzeiten. Schwebende Änderungsanträge zählen zusätzlich zur gültigen Fassung. Lade serverseitig, cache kurz, escape alle Ausgaben und zeige API-Fehler ausdrücklich als nicht verfügbar. Gib keine verbindliche Zusage freier Uhrzeiten und zeige keine Personen oder Buchungsdetails.
