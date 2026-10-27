# Prüfumfang – MAP 1.0.0-rc1

Stand: 27. Oktober 2026. Grundlage ist der auf dem Entwicklungsserver erfolgreich angewendete MVP-Stand 12.1; dieser Releasekandidat lagert Betreiberangaben aus und ergänzt den getrennten Produktionsbetrieb.

## Tatsächlich ausgeführt

| Prüfung | Ergebnis |
|---|---|
| Vollständige Django-Suite, isoliertes SQLite | 425 Tests: 421 bestanden, vier PostgreSQL-spezifische Tests übersprungen |
| Gezielte Nachprüfung nach letzten Templateänderungen | 43 Tests bestanden; nach zusätzlicher Betreiber-Testisolation nochmals acht Tests bestanden (Betreiberkonfiguration, Rollen, Datenschutz, SMTP und Lösch-/Platzpool-Abläufe) |
| Reine Quell-/Funktionstests | 17 statische, 16 Rechte- und elf Sicherheitsprüfungen bestanden |
| Deployment- und Sicherungsabläufe mit simulierten Docker-Aufrufen | Acht Tests bestanden; prüft Reihenfolge und Fehlerbehandlung, keine echte Datenbankwiederherstellung |
| Docker-Compose-Konfigurationen | Entwicklung und Produktion syntaktisch validiert; getrennte Projektnamen/Volumes, keine öffentlichen Produktionsports, nur web im Proxy-Netz, kein Mailpit in Produktion |
| Django-Systemprüfung / Migrationen | Ohne Fehler; keine fehlenden Migrationen erkannt |
| Static-Dateien | Anwendung, Logo und Admin-Dateien erfolgreich eingesammelt |
| Linux-x86_64-/Python-3.12-Abhängigkeiten | Alle aufgelösten Wheels heruntergeladen, finaler requirements-/constraints-Stand daraus erfolgreich aufgelöst |
| OSV für die heruntergeladenen Versionen | Keine bekannten Treffer bei der Prüfung; kein Beleg für generelle Fehlerfreiheit |
| Fünf echte Ansichten mit künstlichen Daten | Browser-Rendering in 1440 und 390 Pixeln, keine Seitenüberläufe und keine JavaScript-Ausnahmen; Bibliotheksbaustein Datenschutz wurde interaktiv eingefügt |
| Öffentlicher Quellumfang | Python-Syntax, private Dateitypen, relative README-Bildverweise und Paketinhalt geprüft; keine .env, Dumps, Anmeldedaten, privaten Betreiberprofile oder fremden Logos im Release-Archiv |

Die Screenshots entstehen ohne Webserver aus echten Django-Antworten und ausschließlich erfundenen Daten. Die Anmeldung für das Rendern wird nur im temporären Testclient erzeugt. Es wurden keine echten Produktionskonten, Live-Anmeldungen oder Mailzugangsdaten in den Release übernommen.

## Noch vor echter Freigabe auszuführen

- Echter Linux-Image-Build, Gunicorn-Start und vollständiger PostgreSQL-Testlauf einschließlich der vier Parallelitätstests. Docker Engine stand lokal nicht zur Verfügung. Der Serverstart und die mitgelieferte CI führen diese Tests aus; hier wird kein erfolgreicher CI-Lauf behauptet.
- Reale HTTPS-Routing-/Zertifikatsprüfung mit der tatsächlichen Domain.
- Betreiberangaben und Rechtsgrundlagen fachlich prüfen und vollständig eintragen.
- SMTP-/Microsoft-Zugang und reale Zustellung, persönliche Links sowie Rollen mit kontrollierten Testdaten prüfen.
- PostgreSQL-Dump in einem getrennten Restore-Stack tatsächlich wiederherstellen, externe Backups und Monitoring aktivieren.

Kein unabhängiges Penetrationstest-Zertifikat, keine vollständige rechtliche oder Lizenzprüfung aller Binärabhängigkeiten, keine Hochverfügbarkeitszusage. Die Projektlizenz ist noch offen. Das Repository wurde vorbereitet, aber nicht auf einer externen Plattform veröffentlicht und die Produktion wurde von hier nicht auf dem Server gestartet.
