# Prüfbericht – Raumbuchung und Darkmode (Dev)

Stand: 27.10.2026. Kein Commit, Push oder Produktionsrollout.

## Automatisierte Prüfungen

- Vollständiger Django-Lauf für `map` und `rooms`: **508 Tests**, davon **503 bestanden** und **5 PostgreSQL-spezifische Tests lokal übersprungen** (182,568 Sekunden).
- Nach den abschließenden Anpassungen am iCal-UID-Format: alle **38 Raumbuchungstests** erneut ausgeführt, **37 bestanden**, ein PostgreSQL-Test übersprungen.
- Zusätzlich gezielte historische Migrations- und Modultests: **43 Tests**, 42 bestanden, ein PostgreSQL-Test übersprungen.
- Django-Systemprüfung ohne Befunde. `makemigrations --check --dry-run`: keine ausstehenden Modelländerungen. Python-Quellen kompilierbar.

Die Raumtests prüfen unter anderem Rollen/Einzelrechte, fremde Buchungen, alle Räume und externe Kontakte, Vergangenheit, negative Zeiträume, mehrtägige Ganztagsbuchungen, Zeitumstellungen, Konflikte mit offenen und genehmigten Buchungen, veraltete Konfliktbestätigungen, beantragte Änderungen ohne Verlust der alten Genehmigung, Ablehnung, Kontaktdatenänderungen, Zurückziehen/Stornieren, konkurrierende Formularfassungen, CSRF, Benachrichtigungseigentum, Mail-Aufträge und das Verwerfen überholter Nachrichten, Filter einschließlich Änderungsanträgen, echte Excel-Struktur ohne Formeln, iCal-Escaping/Zeilenfaltung, HTML-Escaping sowie die Trennung der Vorlagen und Einstellungen.

Ein zusätzlicher PostgreSQL-Paralleltest startet zwei gleichzeitig überlappende Genehmigungen: Nur eine darf ohne zusätzliche Konfliktbestätigung durchgehen. Dieser Test ist lokal unter SQLite übersprungen und wird im Server-Testdienst mit PostgreSQL ausgeführt.

Historische Migrationstests stellen jetzt den vollständigen jeweils aktuellen Migrationsstand wieder her. Ihre Prüfungen zum Erhalt vorhandener Anmeldungen, privater Links, Mail-Aufträge, Kosten- und Leitendendaten bleiben bestehen.

## Browser und Bedienung

**72 Kombinationen** aus 18 echten gerenderten Ansichten, 1440/390 Pixel Breite und heller/dunkler Systemvorgabe geprüft. Darunter Raumübersicht, Details, Formular, beide Kalender, Einstellungen, Mailvorlagen, Benachrichtigungen, Benutzerbearbeitung, native Stufenverwaltung und vorhandene Dashboard-, Anmeldungs-, Statistik-, Formularbaukasten-, Elternformular- und Datenschutzansichten. Kein horizontaler Seitenüberlauf (Tabellen/Kalender scrollen innerhalb ihrer vorgesehenen Container), keine JavaScript-Fehler.

Systemvorgabe, Wechsel der Systemeinstellung und manuelle Darstellungswahl geprüft. Der Darstellungsbutton erreicht im Ruhe- und Hoverzustand in beiden Modi mindestens 4,5:1 Textkontrast. Dies ist keine vollständige WCAG-Zertifizierung sämtlicher alter Komponenten. Die native Admin-Kopfzeile und schmale native Formulare wurden beim Test korrigiert. „Alle Räume auswählen“ markiert sechs Räume; „Ganztägig“ blendet Uhrzeiten aus und deaktiviert sie.

Alle Browserdaten wurden mit erfundenen Personen, Kontakten und Terminen in einer isolierten In-Memory-Datenbank erstellt. Es wurden weder echte Anmeldungen angelegt noch externe Nachrichten versendet.

## Dev-Updater

13 simulierte Abläufe bestanden: Erfolg, Testfehler, Migrationsfehler, Startfehler, unbekannte Quellen, Produktionskonfiguration, laufender Produktionscontainer, bekannte zusätzliche Bildfreigabe, vollständige Abweichungsliste, geklonte Compose-Auswahl, Quellstand vor SSO, gemeinsamer Prod-Image-Tag und gezieltes Entfernen alter eigener Dev-Sicherungen unter Erhalt einer anders benannten Sicherung.

Dev-Web/Worker werden für konsistente Quellen und Templates vorübergehend gestoppt. Bei Fehlern werden Quellen und Image-Tags wiederhergestellt und die vorherige Dev-Anwendung gestartet. Vor der Migration wird die Dev-Datenbank gesichert. Ergänzte Tabellen werden bei einem späteren Fehler nicht automatisch gelöscht. Alte fremde Sicherungen, Prod-Dateien, Docker-Volumes und Caddy bleiben unberührt.

## Noch auf Dev zu bestätigen

Ein echter Docker-/PostgreSQL-Lauf und der echte SMTP-/Exchange-Versand wurden lokal nicht durchgeführt. Das Installationsskript führt die vollständigen Containerchecks einschließlich PostgreSQL vor der Umstellung aus. Anschließend mit tatsächlichem Leitenden-/Vorstandskonto eine Anfrage, eine überlappende Genehmigung und einen Änderungsantrag sowie Mailpit bzw. den beabsichtigten Versandweg prüfen.

Die Raum-Freigabe ist unabhängig vom echten Microsoft-SSO-Tenanttest. Vorhandene SSO-Einstellungen werden nicht geändert; der bisherige SSO-Quellstand ist als Voraussetzung im Dev-Paket enthalten.
