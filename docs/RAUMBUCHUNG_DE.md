# Raumbuchung in MAP – Dev-Update

## Installation und erste Schritte

1. Den gesamten Inhalt von `MAP-Raumbuchung-Dev-Update-Befehl.txt` als root auf dem Server ausführen. Erwartet `/opt/dev/map`. Der Versionsschutz prüft alle betroffenen Dateien in einem Durchgang; unbekannte Abweichungen werden vollständig aufgelistet und nicht überschrieben. Produktion wird abgelehnt. `.env`, Caddy und Zugangsdaten werden nicht ersetzt.
2. Das Paket enthält die bisherigen SSO-Quellen als Voraussetzung und akzeptiert die bekannten Quellstände vor oder nach dem SSO-Update. Eine vorhandene SSO-Konfiguration bleibt erhalten. Es richtet keinen neuen Tenant ein und aktiviert SSO nicht automatisch. Unbekannte Serveränderungen werden nicht übernommen oder überschrieben.
3. Dev-Web und Dev-Worker werden für das Update vorübergehend gestoppt, damit keine alte Anwendung neue Templates oder umgekehrt verwendet. Die Dev-Website ist während Build und Tests nicht erreichbar; Prod läuft weiter. Bei einem Fehler wird der vorherige Dev-Stand wieder gestartet. Build, Paketprüfung und alle Tests für `map` und `rooms` laufen im isolierten Server-Testdienst, bevor die Dev-Datenbank migriert und die Container ersetzt werden.
4. Vor der Migration entsteht eine geschützte Datenbanksicherung. Die neuen Migrationen ergänzen Raumtabellen und optionale Felder der gemeinsamen Mail-Warteschlange. Bestehende Veranstaltungen, Anmeldungen und Konten bleiben bestehen. Bei Fehlern werden Quellen und gegebenenfalls Images zurückgesetzt; bereits ergänzte Tabellen werden nicht automatisch gelöscht. Aus Platzgründen entfernt der Updater nur seine älteren Sicherungsordner `sso-dev-*` und `rooms-dev-*` innerhalb des überprüften Dev-`backups`-Verzeichnisses; die neue aktuelle Sicherung bleibt erhalten. Er entfernt keine Docker-Volumes und keine Prod-Sicherungen.
5. Nach erfolgreichem Abschluss im Browser **Strg+F5**. Als Admin unter **Benutzer** den gewünschten Personen die neue Rolle **Vorstand** zuweisen. Diese Rolle verleiht keine Veranstaltungs- oder technischen Adminrechte.
6. Unter **Profil → Einstellungen → Raumbuchung** die E-Mail-Adressen für Anfragen und Stornierungen eintragen. Der Vorstand prüft offene Anfragen in der Genehmigungsübersicht; interne Benachrichtigungen sind entfernt.
7. Mit einem normalen Leitendenkonto eine Anfrage erstellen und mit einem Vorstandsaccount genehmigen. Eine zweite überlappende Buchung anlegen, die zusätzliche Konfliktbestätigung prüfen und danach einen Änderungsantrag testen.

Es wird nichts auf dem Windows-Rechner installiert. Kein Commit oder Push, kein Prod-Rollout.

## Räume und Buchungsdaten

Die sechs Standardräume werden nach der Migration automatisch bereitgestellt: **Raum 1, Raum 2, Raum 3, Raum 4, Raum 5 und Garten**. Der Button **Alle Räume auswählen** markiert alle gemeinsam.

Eine Anfrage enthält Von-/Bis-Datum, bei zeitlich begrenzten Buchungen zusätzlich Uhrzeiten, die Option **Ganztägig**, einen oder mehrere Räume, Gruppierung, Veranstaltung/Zweck, Ansprechperson und freien Kontakttext. Externe Personen und Gruppierungen können stellvertretend eingetragen werden. Die buchende MAP-Person bleibt dabei für die Anfrage und ihre Benachrichtigungen zugeordnet. Medizinische Daten dürfen nicht erfasst werden.

Ganztägig schließt beide ausgewählten Kalendertage vollständig ein. Intern wird das Ende als Beginn des Folgetages gespeichert; iCal verwendet dieselbe exklusive Endkonvention. Ganztägige Anfragen für heute sind zulässig, vergangene Tage nicht. Zeitgebundene Anfragen dürfen nicht in der Vergangenheit beginnen. Nicht existente oder doppeldeutige Uhrzeiten beim Sommer-/Winterzeitwechsel werden mit deutscher Fehlermeldung abgelehnt.

Es gibt keine Serienbuchungen und keine Zahlungsabwicklung in diesem Modul.

## Rechte und Workflow

- Alle aktiven Leitenden können sämtliche Buchungsdetails einschließlich der Kontaktangaben lesen und eigene Buchungsanfragen erstellen. Leitendenstatus ohne eigene Stufenzuordnung reicht aus; automatisch über Entra zugeordnete aktive Stufen werden ebenfalls berücksichtigt.
- Die manuell vergebene Rolle **Vorstand** und MAP-Admins können alle Buchungen bearbeiten, genehmigen, ablehnen und stornieren. Zusätzliche Einzelrechte für Lesen, Anfragen, Vorstandsverwaltung und Raumkonfiguration sind im vorhandenen Berechtigungseditor verfügbar. Ein reines Leserecht erlaubt keine Anfragen.
- Neue Anfragen sind **Schwebend**. Der Vorstand entscheidet zwischen **Genehmigt** und **Abgelehnt**; bei Ablehnung ist eine Begründung optional. Bereits genehmigte Buchungen werden auch bei einer Änderung durch ein Vorstandsmitglied nicht stillschweigend neu genehmigt.
- Leitende können eigene Buchungen jederzeit stornieren; auch vergangene eigene Buchungen können storniert werden. Andere Anfragen können sie nicht bearbeiten oder stornieren. Stornierte Buchungen werden nicht wieder geöffnet; dafür eine neue Anfrage anlegen.
- Abgelehnte Buchungen können durch Überarbeitung erneut eingereicht werden und sind dann wieder schwebend. Die frühere Entscheidung bleibt im Verlauf.

## Konflikte

Überschneidungen entstehen nur bei mindestens einem gemeinsamen Raum und tatsächlich überlappenden Zeiten. Direkt aneinander anschließende Belegungen sind konfliktfrei. Schwebende Buchungen und vorgeschlagene Änderungen werden berücksichtigt; abgelehnte oder stornierte Einträge blockieren keine Räume.

Konflikte verhindern das Einreichen nicht. Bei bereits genehmigten Überschneidungen muss der Vorstand bei der Genehmigung die **zusätzliche Bestätigung** setzen. Die Bestätigung bezieht sich auf die aktuell angezeigten genehmigten Konflikte; nach zwischenzeitlichen Änderungen muss erneut geprüft werden. Alle Schreibvorgänge sperren dieselben Raumzeilen in stabiler Reihenfolge, damit zwei gleichzeitige Genehmigungen die zusätzliche Prüfung nicht umgehen.

## Änderungen

Bei einer genehmigten Buchung benötigen Änderungen an Räumen, Zeitraum, Ganztagsstatus, Gruppierung oder Zweck erneut eine Freigabe. Die ursprüngliche Buchung bleibt bis dahin unverändert gültig und sichtbar. Ein offener Antrag wird separat gekennzeichnet. Eine Ablehnung oder das Zurückziehen der Änderung lässt die ursprüngliche Genehmigung bestehen. Die Stornierung der gesamten Buchung storniert auch offene Änderungen.

Ansprechperson und Kontakt werden ohne erneute Freigabe aktualisiert. Solche Aktualisierungen werden beim späteren Genehmigen eines älteren Änderungsantrags nicht zurückgesetzt. Bearbeitungsfassungen verhindern unbemerkte Überschreibungen durch parallel geöffnete Formulare. Änderungen, Akteure, Entscheidungen und Begründungen bleiben als Verlauf gespeichert; in den Details werden die neuesten 100 Einträge angezeigt.

## Ansichten und Exporte

- Tabellarische Übersicht mit Zeitraum, Räumen, Gruppierung, Veranstaltung, Ansprechperson, Status, Konflikten und Aktionen.
- Filter nach Datumsspanne, Räumen, Gruppierung, Status und eigenen Buchungen. Schwebende Änderungsanträge werden auch dann gefunden, wenn nur deren vorgeschlagene Räume oder Termine zum Filter passen.
- Monats- und Wochenkalender mit mehrtägigen Belegungen; nicht genehmigte Änderungen sind ausdrücklich als Vorschlag gekennzeichnet. Auf kleinen Bildschirmen scrollt der Kalender innerhalb seiner Ansicht horizontal.
- Eigene Liste offener Buchungs- und Änderungsanträge für den Vorstand.
- Echter Excel-Export (`.xlsx`) mit Inline-Textzellen gegen Formelinjektion. Passende offene Änderungen sind eigene Zeilen. Das Tabellenblatt heißt „Raumbuchungen“.
- iCal-Download (`.ics`) mit stabilen Buchungs-IDs, Status, Zeitzonenwerten und Versionsnummern. Er exportiert die **aktuellen Buchungen**, nicht die noch ungeprüften Änderungsanträge. Schwebende Anfragen sind vorläufig, stornierte/abgelehnte Einträge als abgesagt markiert. Es ist ein geschützter Download nach Anmeldung, kein öffentlich abonnierbarer Feed. Kontakte sind enthalten; Exporte vertraulich behandeln.

## Benachrichtigungen und Moduleinstellungen

Neue und geänderte Anfragen, Entscheidungen, Kontaktänderungen, zurückgezogene Änderungen und Stornierungen erzeugen Mail-Aufträge. E-Mails gehen an die konfigurierten Empfänger und – sofern eine E-Mail-Adresse im MAP-Konto vorhanden ist – die buchende Person. Der freie externe Kontakttext wird **nicht** automatisch als Mail-Empfänger interpretiert. Bitte externe Personen gegebenenfalls selbst informieren.

Der Versand verwendet die vorhandene MAP-Mail-Warteschlange und SMTP-/Exchange-Konfiguration. In Dev mit Mailpit bleiben Nachrichten im Testpostfach. Überholte Nachrichten, etwa eine ausstehende Genehmigungsmail nach einer Stornierung, werden vor dem Versand verworfen. Die gemeinsame Warteschlange lässt sich nach Veranstaltungsanmeldungen, Raumbuchung und Konten/System filtern.

Unter **Profil → Einstellungen** sind Veranstaltungen, Raumbuchung und Konto & System getrennt erreichbar. Die Raumbuchung besitzt eigene Mailvorlagen und Platzhalter. Ihre Anpassung verändert keine Veranstaltungs- oder Passwortvorlagen. HTML-Maildarstellung, Absender und automatischer Nicht-antworten-Hinweis werden gemeinsam verwendet.

## Darkmode

Ohne eigene Auswahl folgt MAP der Systemeinstellung und reagiert auf deren Änderungen. Der dezente Button unter **Profil → Darstellung** wechselt zwischen System, Hell und Dunkel. Die manuelle Auswahl wird nur im jeweiligen Browser gespeichert. Veranstaltungen, Benutzerverwaltung und Raumansichten verwenden denselben Modus. Excel-Dateien und heruntergeladene QR-Codes behalten ihr Exportdesign; Mailprogramme bestimmen ihre eigene Darstellung.

## Datenschutz und Betriebsgrenzen

Die Raumdaten sind von Veranstaltungen unabhängig. Das Löschen einer Veranstaltung löscht keine Raumbuchungen. Eine Stornierung ist keine Datenlöschung. Für Löschfristen und gegebenenfalls tatsächliche Löschung müssen die Verantwortlichen einen eigenen Ablauf festlegen; dieses Update enthält keine automatische Löschfrist oder UI für endgültige Datenlöschung. Raumbuchungen werden durch die berechtigten Leitenden vollständig einschließlich Kontaktdaten und Verlauf eingesehen.

Dies ist ein Dev-Update. Ein echter Docker-/PostgreSQL-Lauf und ein Versand über euren Microsoft-Mandanten wurden lokal nicht durchgeführt. Der Server-Testdienst führt die PostgreSQL- und Migrationstests vor der Umstellung aus. Die lokale Prüfung und ihre Einschränkungen stehen im beigefügten Testbericht.
