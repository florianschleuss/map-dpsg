# MAP – Mailstatus, Raum-Löschdialog und ganztägige Belegungs-API

## Dev-Update

1. `MAP-Mailstatus-Raumdialog-Dev-Update-Befehl.txt` vollständig öffnen und in die Remote-Konsole des Servers kopieren, als root ausführen. Das aktuelle Verzeichnis ist egal.
2. Ausschließlich `/opt/dev/map` wird aktualisiert. Produktion, `.env`, Zugangsdaten und Caddy bleiben unverändert; kein Commit oder Push und keine Installation auf deinem PC.
3. Vor Änderungen prüft der Befehl den bekannten Quellstand und die getrennte Dev-/Prod-Konfiguration. Bei Abweichungen bricht er ab; bitte die vollständige Dateiliste weitergeben.
4. Dev-Web und Dev-Worker werden angehalten, Quellen/Images gesichert und neue Images gebaut. Die vollständigen Tests laufen vor PostgreSQL-Sicherung, Migration und Neustart. Im Testdienst werden auch die lokal übersprungenen PostgreSQL-Prüfungen ausgeführt.
5. Bei Fehlern werden vorherige Quellen und Image-Tags wiederhergestellt. Bereits ausgeführte Datenbankänderungen werden nicht automatisch zurückgenommen; die Datenbanksicherung steht im ausgegebenen Sicherungsordner bereit.
6. Nach Erfolg Strg+F5 im Browser.

Nur ältere Sicherungsordner der eigenen Dev-Updater (`sso-dev-*`, `rooms-dev-*`, `ui-sso-dev-*`, `rooms-api-dev-*`, `mail-ui-dev-*`) werden innerhalb des geprüften Dev-Sicherungsordners wie zuvor erlaubt entfernt. Andere Sicherungen bleiben erhalten.

## Anmeldungsübersicht

Die Eintragszahl steht direkt hinter der Überschrift **Anmeldungen**, statt zwischen den Statistik-/Exportbuttons. Die Schaltflächen bleiben gemeinsam rechts bzw. umbrechen auf kleinen Bildschirmen. Die Zahl und die bestehenden Filter-/Zählregeln selbst bleiben unverändert.

## Räume: ein Löschvorgang mit verständlicher Bestätigung

Neben Bearbeiten gibt es nur noch **Löschen**. Ein echtes Popup erklärt vor der Bestätigung, was passiert:

- Ohne Buchungen oder Änderungsanträge: endgültig löschen.
- Mit Buchungen oder Änderungsanträgen: archivieren; bestehende Daten bleiben erhalten, der Raum steht nicht mehr für neue Buchungen zur Auswahl.

Die Entscheidung wird beim Bestätigen serverseitig nochmals anhand des aktuellen Stands geprüft. Eigenständige Aktivieren-/Archivieren-Aktionen entfallen. Archivierte Räume erscheinen nur noch in einer aufklappbaren historischen Liste. Beim Bearbeiten sind Speichern und Abbrechen als gleich ausgerichtete Buttons zusammengefasst. Abbrechen im Löschdialog oder Escape schließt das Popup ohne Änderung.

## Mailvorlagen aktivieren und deaktivieren

In den Veranstaltungs-, System- und Raum-Mailvorlagen zeigen Statusfelder den Versandzustand:

- **Aktiv**: Anklicken deaktiviert den Nachrichtentyp.
- **Deaktiviert**: Anklicken aktiviert ihn wieder.
- **Erforderlich · aktiv**: bleibt eingeschaltet und ist nicht anklickbar.

Geschützt sind Passwort-Reset, Eingang einer Anmeldung einschließlich Bestätigungslink, erneut angeforderte Anmeldelinks, Wartelisten-Nachrücken, ausdrücklich angeforderte Zahlungsaufforderungen und manuelle Testmails. Damit können Kontozugang, notwendige Bestätigung und bewusst ausgelöste Tests nicht durch einen globalen Schalter unterbrochen werden. Bestätigungsbestätigung, Ablauf-, Stornierungs- und Änderungsnachrichten sind optional. Die Raum-Mailvorlagen können einzeln geschaltet werden. Rollen und Rechte für das jeweilige Modul gelten weiter; der Vorstand darf Raumvorlagen schalten, ohne dadurch Veranstaltungs-Mailrechte zu erhalten.

Der Schalter ist von den bearbeiteten Texten unabhängig. Zurücksetzen auf einen Standardtext aktiviert eine zuvor deaktivierte Vorlage nicht wieder.

### Wirkung auf die Warteschlange

Neue optionale Nachrichten deaktivierter Typen werden nicht erzeugt. Neu erzeugte Aufträge erhalten eine eindeutige Vorlagenkennung. Der Worker prüft den Schalter unmittelbar vor dem Versand erneut; dadurch stoppt eine spätere Deaktivierung auch bereits zugeordnete, noch nicht versendete Aufträge.

Solche gestoppten Aufträge tragen in der Warteschlange eine deutsche Erklärung zur deaktivierten Vorlage. Nach erneutem Aktivieren erfolgt **kein automatisches Nachsenden** alter gestoppter Nachrichten. Bei Bedarf in der Warteschlange bewusst erneut freigeben; bestehende Prüfungen auf überholte Buchungs-/Zahlungsdaten gelten weiter.

**Grenze:** Bereits vor diesem Update erzeugte Aufträge ohne Vorlagenkennung lassen sich nicht sicher einem Mailtyp zuordnen und bleiben unverändert. Bei Bedarf diese alten Aufträge gezielt in der Warteschlange löschen. Bereits an den Anbieter übergebene oder zugestellte Mails lassen sich nicht zurückrufen. Die Übersicht weist auf diese Grenze hin.

## API: Teilzeit bleibt teilweise, Raumlisten werden vereinigt

`GET /api/v1/rooms/occupancy/` verwendet jetzt `aggregation=continuous_full_day`.

- Nur bis 18 Uhr belegt → `partial`, selbst wenn alle Räume betroffen sind.
- `full` nur, wenn **alle aktiven Räume den gesamten lokalen Tag lückenlos belegt** sind.
- Mehrere Buchungen werden zeitlich je Raum vereinigt. 00–12 Uhr plus 12–24 Uhr kann einen ganzen Tag ergeben; eine Lücke verhindert `full`.
- `rooms` liefert die eindeutige Namensliste aller am Tag betroffenen aktiven Räume. `approved_rooms` und `pending_rooms` liefern diese Liste zusätzlich getrennt nach Status.
- Es erscheinen weiterhin keine Personen, Kontakte, Veranstaltungszwecke, Buchungs-IDs oder konkreten Uhrzeiten.

Das öffentliche Veröffentlichen von Raumnamen ist Bestandteil dieser ausdrücklich gewünschten Erweiterung. Der bisherige Aktivierungsschalter der API bleibt erhalten. Die ausführliche Beschreibung und ein kopierbarer WordPress-Auftrag stehen in `MAP-Raumbelegung-API-DE.md`.

Das aktualisierte WordPress-Beispiel zeigt eine Raumspalte und die neue Ganztagsbedeutung. Es erkennt die neue Aggregation; bei einer noch alten API zeigt es einen Updatehinweis statt einer falschen Ganztagsaussage. WordPress-Dateien werden durch den MAP-Befehl nicht automatisch installiert. Das Beispiel ist weiterhin nicht in eurer echten WordPress-Installation ausgeführt worden.

## Kurze Prüfung nach dem Einspielen

Eintragszahl hinter Anmeldungen ansehen; einen benutzten und einen unbenutzten Raum-Löschdialog öffnen und jeweils abbrechen; Bearbeiten/Abbrechen prüfen. Eine optionale Mail deaktivieren und wieder aktivieren, eine Pflichtmail als nicht schaltbar prüfen. Eine API-Abfrage mit einer Belegung bis 18 Uhr ausführen: `partial` und die betroffenen Raumnamen erwarten. Für einen Ganztagstest müssen alle aktiven Räume lückenlos abgedeckt sein.
