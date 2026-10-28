# Geprüften MAP-Release in eine bestehende Produktion übernehmen

## Voraussetzungen

Ein grüner GitHub-Testlauf für den ausgewählten Commit, laufende Prod-Dienste web/worker/db, Docker Compose, Python 3 und ausreichender freier Speicher für Image-Build und eine zusätzliche Datenbanksicherung. Das Release muss in einem separaten Verzeichnis liegen und darf dort noch keine `.env` besitzen. Der ausgelieferte konkrete Update-Befehl lädt einen festen Commit und prüft zusätzlich den SHA-256-Wert des Archivs.

Produktion und Entwicklung müssen unterschiedliche Compose-Projekte, Datenbanken und App-Image-Tags verwenden. Der Installer ermittelt die tatsächlich laufende Compose-Auswahl über Container-Labels; er rät keine Proxy-/Netzwerkkonfiguration. Standardziel ist in den Betreiberbefehlen `/opt/map`; andere ausdrücklich gewählte Prod-Pfade können mit `--root` verwendet werden. Dev-Verzeichnisse werden abgewiesen. Eine Dateisperre verhindert parallele Release-Läufe derselben Installation.

## Ablauf

1. Alle vorgesehenen Quelldateien müssen einem bekannten Git-/Dev-Ausgangsstand oder bereits dem Zielrelease entsprechen. Unbekannte Änderungen führen zu einer vollständigen Abweichungsliste, bevor etwas überschrieben wird. `.env`, unversionierte Compose-Ergänzungen, Betreiberassets, Proxy und Anwendungsdaten werden nicht aus Dev kopiert.
2. Die Prod-`.env` wird ausschließlich als geschützte temporäre Datei für die separate Release-Prüfung verwendet und danach entfernt. Sie wird nicht ausgegeben oder im öffentlichen Archiv mitgeliefert.
3. Der neue Stand wird gebaut und gegen eine eigene kurzlebige PostgreSQL-Testdatenbank geprüft, mit lokalem Mail-Backend. Prod läuft dabei weiter. Fehlgeschlagene Builds/Tests verändern keine Prod-Quellen oder Datenbank.
4. Die bestehende Produktivkonfiguration wird mit dem neuen Image geprüft. Änderungen an Prod-Dateien während des Builds führen zum Abbruch.
5. Erst danach werden Web und Worker angehalten. Unter `backups/release-<UTC-Zeit>/` entstehen bisherige Quelldateien, Image-IDs, eine geschützte `.env`-Kopie und ein PostgreSQL-Dump. Dessen Inhaltsverzeichnis wird vor Migration geprüft.
6. Der Installer übernimmt die Release-Dateien, führt Migrationen sowie Produktions-/Django-Prüfungen aus und startet die App mit Gesundheitsprüfung. Es wird keine Beispieldaten-Erzeugung aufgerufen.
7. Nur der eindeutig benannte temporäre Test-Stack wird entfernt. Vorhandene Prod-Sicherungen und Rollback-Images werden nicht automatisch gelöscht.

## Nachkontrolle

Lokal als bestehender Admin anmelden. Bestehende Veranstaltungen, Anmeldung, Excel-Export und Mail-Warteschlange kontrollieren. Für Microsoft SSO unter dem Profil die Prod-App konfigurieren: eigener Tenant, Client-ID, Geheimnis und Gruppen-Objekt-IDs. Die für Prod erforderliche Web-Rücksprungadresse in Entra zusätzlich eintragen, zum Beispiel `https://map.example.org/accounts/microsoft/callback/`. Teams-Gruppen benötigen den Gruppenanspruch „Alle Gruppen“ als Objekt-IDs im ID-Token. Die Mailversand-App bleibt davon unabhängig. Ein getesteter lokaler technischer Adminzugang muss erhalten bleiben.

Die Dev-SSO-Konfiguration wird nicht automatisch übernommen; IDs der Stufen und Verschlüsselungsschlüssel können sich unterscheiden. Dasselbe gilt für manuelle Rollen und die Vorstand-Zuordnung. Die öffentliche Belegungs-API muss in Prod bewusst aktiviert werden; sie veröffentlicht auch konfigurierte Raumnamen. Dummy-Erzeugung bleibt bei `MAP_PRODUCTION=1` gesperrt.

## Fehler und Rückfall

Vor dem Umschalten bleibt Prod bei Build-/Testfehlern in Betrieb. Nach Beginn der Wartungsphase versucht das Skript, alte Quellen und Image-Tags wiederherzustellen und die vorherigen Dienste zu starten. Bereits erfolgreich ausgeführte Datenbankmigrationen werden **nicht automatisch** zurückgenommen: ein Zurückspielen könnte zwischenzeitlich angenommene echte Daten entfernen. Die bisherige Migration dieses Releases ist additiv; trotzdem nach einem Fehler keine weiteren manuellen Migrationen raten, sondern Meldung und Sicherungspfad prüfen.

Die Sicherung enthält vertrauliche Betriebsdaten und gehört nicht ins Git-Repository. Datenbank-Restore nur nach bewusstem Stoppen der schreibenden Dienste und fachlicher Entscheidung gemäß [Betrieb](BETRIEB.md). Alte App-Images bleiben unter `map-production-rollback:<Zeit>-<Nummer>` verfügbar. Für die manuelle Image-Auswahl liegen die bisherigen Tags und IDs in `images.json` der Sicherung.

Kein Installer kann einen defekten Datenträger, erschöpften Speicher oder ein außerhalb des Deployment-Prozesses verändertes System vollständig auffangen. Falls die automatische Wiederinbetriebnahme selbst scheitert, bleiben Sicherung und alte Image-IDs für eine gezielte Wiederherstellung erhalten.
