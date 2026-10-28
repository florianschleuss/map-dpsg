# MAP: Raumverwaltung, öffentliche Tagesbelegung und vollständige Testveranstaltung

## Dev-Update ausführen

1. `MAP-Raumverwaltung-API-Dev-Update-Befehl.txt` öffnen und den gesamten Inhalt in die Remote-Konsole des Servers kopieren, als root ausführen. Das aktuelle Arbeitsverzeichnis spielt keine Rolle.
2. Das Skript arbeitet ausschließlich in `/opt/dev/map`. Produktion, `.env`, Zugangsdaten und Caddy werden nicht verändert. Kein Git-Commit und kein Push; keine Installation auf deinem PC.
3. Der bekannte Quellstand, die Compose-Auswahl und getrennte Dev-/Prod-Images werden geprüft. Bei Abweichungen erfolgt vor dem Austausch ein Abbruch mit vollständiger Dateiliste. Bitte diese Meldung weitergeben, keine Prüfungen umgehen.
4. Dev-Web und Dev-Worker werden für das Update angehalten. Betroffene Quellen und bisherige Images werden gesichert. Dann werden Dev-Images gebaut und die vollständigen Tests im isolierten Testdienst ausgeführt. Erst bei Erfolg folgen PostgreSQL-Sicherung, Migration und Neustart von Dev.
5. Bei einem Fehler werden vorherige Quellen und Image-Tags wiederhergestellt. Bereits ausgeführte Datenbankmigrationen werden nicht automatisch rückgängig gemacht. Die PostgreSQL-Sicherung liegt im am Ende genannten Dev-Sicherungsverzeichnis.
6. Browser nach Erfolg mit Strg+F5 neu laden.

Wie zuvor erlaubt, werden nur ältere Sicherungen der eigenen Dev-Updater (`sso-dev-*`, `rooms-dev-*`, `ui-sso-dev-*`, `rooms-api-dev-*`) innerhalb des geprüften Dev-Sicherungsordners entfernt. Andere Sicherungen bleiben erhalten.

## Räume anlegen, bearbeiten und entfernen

**Profil → Raumeinstellungen → Räume verwalten**, ausschließlich für Admins. Namen und Reihenfolge sind bearbeitbar, weitere Räume können angelegt werden. Unbenutzte Räume werden nach ausdrücklicher Bestätigung endgültig gelöscht. Hat ein Raum bereits Buchungen oder Änderungsanträge, archiviert ihn derselbe Vorgang; seine Historie bleibt erhalten. Archivierte Räume stehen für neue Buchungen nicht zur Auswahl. Bestehende Buchungen bleiben sichtbar. Archivierte Räume werden nur noch als historische Einträge angezeigt; die eigene Aktivieren-/Archivieren-Aktion entfällt.

Die bisherigen sechs Standardräume sind bei der ersten Einrichtung weiterhin vorhanden. Bewusst gelöschte Räume werden bei künftigen Migrationen nicht automatisch neu angelegt. Die öffentliche Tagesaggregation verwendet ausschließlich aktive Räume.

## Navigation und Einstellungen

Oben stehen nur **Veranstaltungen** und **Raumbuchung**. Offene Raumgenehmigungen bleiben als Reiter innerhalb der Raumbuchung erreichbar.

Das Profilmenü trennt **Veranstaltungen**, **Raumbuchung** und **Konto & System**. Veranstaltungseinstellungen enthalten die Veranstaltungs-Mailvorlagen; Raumeinstellungen enthalten Raumverwaltung, Raum-Mailvorlagen, Empfänger und die öffentliche API. Mailversand, Mail-Warteschlange, System-Mailvorlagen, Microsoft-Anmeldung und Benutzer-/Rollen-/Stufenverwaltung sind gemeinsame Dienste und erscheinen abhängig von den eigenen Rechten.

Auf Einstellungsseiten gibt es keine Buchungs-/Kalendernavigation mehr. Die kleinen Untermenüs bleiben innerhalb des jeweiligen Moduls; das frühere modulübergreifende Querlink-Menü entfällt. Systemvorlagen und Veranstaltungsvorlagen sind getrennte Listen. Kalendernavigation und die oberen Kacheln sind ausgerichtet. Der Profilbereich ist bei kleiner Fensterhöhe scrollbar.

## Darkmode

Neutrale Grautöne und die bestehende System-/Browserauswahl bleiben erhalten. Überarbeitet wurden unter anderem Kennzahlen, Datenschutzhinweise, Stufen- und Rechteauswahl, Platzkontingente, Formularbaukasten und Bibliothek, Wizard, Einstellungs- und Mailseiten sowie Eltern- und Fehleransichten. Fehlermeldungsseiten verwenden die Darstellung auch ohne Datenbankzugriff; bei ausbleibendem JavaScript folgt ihre Farbwahl der Systemeinstellung.

## Vollständige Dummy-Veranstaltung

**Profil → Entwicklung → Dummy-Veranstaltung erstellen** ist weiterhin nur in Dev und mit Veranstaltungs-Anlegerecht verfügbar. Die neu erzeugte Veranstaltung enthält:

- unveröffentlichten Testentwurf mit Termin in 30 Tagen und 20 Plätzen;
- 29 ausdrücklich erfundene Kinder-/Elternangaben unter reservierten `example.invalid`-Adressen;
- 12 bestätigte, 8 auf Bestätigung wartende, 4 Wartelisten-, 3 stornierte und 2 abgelaufene Anmeldungen;
- sechs manuell als bezahlt markierte bestätigte Anmeldungen und weitere offene Zahlungen;
- 25 Euro Beispielbeitrag mit Bargeldzahlung und ausdrücklichem Testhinweis;
- vollständig ausgefüllte Formularantworten, Verpflegungsoptionen, zusätzliche Kontakte einschließlich Verhältnis, Anreise, Zahlen-/Checkboxfelder und Ja-/Nein-Entscheidungen zum Datenschutz.

Die 20 regulären Plätze sind mit bestätigten und vorläufigen Anmeldungen belegt; Wartelisteneinträge rücken daher nicht sofort nach. Offene Bestätigungen haben eine Frist von 48 Stunden und können später regulär ablaufen. Testdaten werden durch das aktuelle echte Anmeldeformular und die Modellvalidierung geprüft. Der normale Wizard-Erstellungsdienst bleibt die Grundlage. Es werden **keine Mails oder Versandaufträge** erzeugt. Bereits vorhandene Dummy-Veranstaltungen werden nicht nachträglich verändert; bitte eine neue anlegen. Die Testveranstaltung lässt sich normal bearbeiten, auswerten, exportieren und löschen.

## Öffentliche API und WordPress

In **Raumeinstellungen** die öffentliche Belegungs-API aktivieren und speichern. Erst danach ist `https://dev.map.example.org/api/v1/rooms/occupancy/` erreichbar. Ohne Aktivierung: HTTP 404.

Die API liefert nur Belegungstage sowie schwebend/genehmigt und teilweise/alle Räume betroffen. Keine Personen, Veranstaltungszwecke, Kontakte oder Uhrzeiten; ausschließlich die Raumnamen werden zusätzlich ausgegeben. „Voll“ bedeutet, dass alle aktiven Räume den gesamten lokalen Kalendertag lückenlos belegt sind. Teilzeitbelegungen bleiben teilweise. Die API liefert zusätzlich die Namen der betroffenen Räume.

Die vollständige Beschreibung, Beispielantwort und ein kopierbarer Auftrag für eine spätere WordPress-Umsetzung stehen in `MAP-Raumbelegung-API-DE.md`. Das Beispielplugin `wordpress-map-raumbelegung.php` liefert den Shortcode `[map_raumbelegung]`. Es wird durch den MAP-Update-Befehl **nicht** in WordPress installiert. Dafür die Anleitung in der API-Beschreibung verwenden. Das Beispiel ist noch nicht in eurer echten WordPress-Installation getestet.

Dieses Paket installiert die API ausschließlich in Dev. Die Prod-Domain kann erst nach einem separaten Prod-Deployment verwendet werden.

## Nach dem Einspielen prüfen

Als Admin einen Raum anlegen und einen unbenutzten Raum löschen. Einen gebuchten Raum archivieren und die erhaltene Buchung ansehen. Profilmenü und Raum-/Veranstaltungseinstellungen mobil prüfen. Eine neue Dummy-Veranstaltung erstellen, Details aufklappen, Statistik und Excel öffnen. API aktivieren und einen begrenzten Zeitraum mit `?start=YYYY-MM-DD&end=YYYY-MM-DD` abfragen. Anschließend bei Bedarf das WordPress-Beispiel separat testen.
