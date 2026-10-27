# Betrieb, Updates und Wiederherstellung

## Getrennte Umgebungen

Entwicklung, Produktion, CI und Wiederherstellung dürfen weder denselben Compose-Projektnamen noch dasselbe PostgreSQL-Volume verwenden. Der Compose-Projektname ist Teil der Volume-Zuordnung. Beim Verschieben einer bestehenden Installation nicht beiläufig ändern; das würde scheinbar eine leere Datenbank erzeugen. Die Produktion wird als neue Installation gestartet, ohne eine automatische Übernahme von Entwicklungsdaten.

## Backups

```sh
cd /opt/map
sh scripts/backup.sh
```

Das Skript erzeugt einen PostgreSQL-Custom-Dump, prüft dessen Lesbarkeit und sichert die passende `.env` mit restriktiven Dateirechten. Ein konsistenter DB-Dump ist online möglich. Für einen zusammenhängenden Wiederherstellungspunkt bei Releases stoppt deploy.sh zunächst web und worker. Eine Prüfung von pg_restore --list ersetzt **keinen** tatsächlich ausgeführten Restore.

Zusätzlich sichern: verwendete Quellversion/Release-Archiv, eigene operator-assets, angepasste Proxy-Konfiguration und Zugriff auf den passenden SECRET_KEY. Mailgeheimnisse können ohne diesen Schlüssel nicht entschlüsselt werden. Backups enthalten persönliche Daten und Geheimnisse und gehören niemals ins Repository oder in einen öffentlichen Download.

Empfehlung: tägliche Ausführung über systemd, verschlüsselte Übertragung zu einem getrennten Backupziel, eingeschränkte Zugriffsrechte und dokumentierte Aufbewahrung. Die Dateien unter deploy/systemd sind Vorlagen, nicht automatisch aktiviert. Das lokale Skript setzt weder eine automatische Löschung noch eine externe Sicherung um. Fristen für Sicherungen und exportierte Dateien muss der Betreiber festlegen und in seine Datenschutzangaben übernehmen.

## Wiederherstellung üben

1. Passendes Release nach `/opt/map-restore` kopieren; niemals die laufende Installation als Testziel verwenden.
2. Die **zur Sicherung passende** `.env` dort mit Modus 600 bereitstellen. SECRET_KEY und Datenbankkennung erhalten. Für den Test einen anderen Projekt-/Aliasnamen wählen und ausgehende E-Mails deaktivieren. Persönliche Daten aus dem Restore nicht öffentlich anbieten.
3. Nur die frische Datenbank des getrennten Stacks starten und den Dump importieren. Die Ziel-Datenbank muss leer sein:

```sh
cd /opt/map-restore
docker compose -f compose.yaml -p map-restore up -d --wait db
docker compose -f compose.yaml -p map-restore exec -T db sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --single-transaction' < /GESCHUETZTER/PFAD/map-ZEITPUNKT.dump
docker compose -f compose.yaml -p map-restore --profile tools run --rm -T init python manage.py migrate --check
```

4. Konten, Datensatzzahlen und Entschlüsselbarkeit der Mailkonfiguration gezielt im abgeschotteten Test prüfen. Keinen Worker mit echten Empfängern starten. Zwischenzeitliche Löschungen müssen bei einer echten Wiederinbetriebnahme berücksichtigt werden.
5. Zeitpunkt, verwendete Sicherung und Ergebnis dokumentieren. Produktionswiederherstellung erst nach bewusster Entscheidung und Sicherung des aktuellen Zustands durchführen.

`scripts/restore.sh` verweist absichtlich auf diesen kontrollierten Ablauf und überschreibt keine laufende Datenbank.

## Releases aktualisieren

Nicht bei jedem Besuch und nicht automatisch beim Containerstart aus Git aktualisieren. Eine geprüfte Quellversion mit dokumentiertem Tag bzw. Commit übernehmen. Vorher die aktuelle Quellversion außerhalb des Arbeitsverzeichnisses sichern, beispielsweise in einem geschützten Release-Archiv. `.env`, operator-assets und Datenvolume erhalten. Bei Git-Nutzung nicht von laufenden Produktionsservern ins öffentliche Repository committen.

Dann:

```sh
cd /opt/map
sh scripts/deploy.sh
```

Das Skript baut Images, prüft Paketkonsistenz und OSV, führt die gesamte PostgreSQL-Suite im Testdienst aus und prüft die Produktivkonfiguration. Erst anschließend stoppt es die App, sichert die Datenbank und führt Migrationen aus. Bei einem Fehler vor der Wartungsphase laufen die vorhandenen Container weiter. Bei fehlgeschlagener Sicherung startet es die bisherigen Container wieder. Bei fehlgeschlagener Migration bleibt die App gestoppt; ein Datenbank-Rollback wird nicht geraten oder automatisch ausgeführt. Ein Fehler beim abschließenden Gesundheitscheck erfordert ebenfalls Prüfung der Logs und eine bewusste Wiederherstellungsentscheidung.

Das Skript lädt selbst keine neue Quellversion herunter, rotiert keine Geheimnisse und ändert Caddy nicht. Nach Schemaänderungen darf nicht blind nur ein altes Image gestartet werden. DB und Code müssen zueinander passen.

## Überwachen

```sh
docker compose ps
docker compose logs --tail=100 web worker
docker compose --profile tools run --rm -T init python manage.py check_production
```

Der Web-Healthcheck prüft HTTP und die Datenbank. Der Worker hat **keinen vollständigen Versand-Healthcheck**: Zusätzlich Warteschlange, wiederkehrende Fehler und ausstehende Nachrichten prüfen. Ein laufender Container belegt keine Zustellung. Einen externen HTTPS-Erreichbarkeitsalarm und Backupüberwachung separat einrichten.

Logausgaben nicht ungeprüft veröffentlichen. Anwendungszugriffslogs mit persönlichen Linkpfaden sind im mitgelieferten Gunicorn-Aufruf deaktiviert. Proxy-/Providerlogs bleiben Betreiberverantwortung. Docker-Logs der App werden in ihrer Größe begrenzt.

## Öffentliches Repository veröffentlichen

Nur den Inhalt des vorbereiteten Repository-Verzeichnisses verwenden, nicht den übergeordneten Arbeitsordner und nicht das private Deploymentprofil. Vor dem ersten Commit die Dateiliste durchsehen, `python3 tools/check_public_release.py` ausführen und einen geeigneten Secret-Scanner nutzen. Ohne vorhandene Git-Historie beginnen. Falls eine bestehende Historie übernommen wird, muss auch sie vollständig geprüft werden; spätere .gitignore-Einträge entfernen keine früheren Geheimnisse.

Vor Veröffentlichung privaten Sicherheitsmeldeweg einrichten, Lizenzstatus klar kennzeichnen und die README-Screenshots prüfen. Die Entscheidung zur Lizenz steht noch aus. Es wurde weder ein Remote-Repository angelegt noch Code veröffentlicht.
