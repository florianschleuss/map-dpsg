# Installation auf einem Linux-Server

## Aufbau

Eine eigene Installation je Organisation und Umgebung: PostgreSQL, web und Mailworker, getrennt von anderen Anwendungen. Docker Compose verwaltet den Stack; ein bestehender Caddy, Traefik oder Nginx übernimmt HTTPS. Diese Anleitung verwendet Caddy im Docker-Netz `reverse-proxy` und den Beispielhost `map.example.org`. Die Werte sind vor dem Start anzupassen.

Voraussetzungen: Linux-Server, Docker Engine mit Compose V2, Python 3 für die Erzeugung der Konfiguration, öffentliche Domain mit korrektem DNS und erreichbaren Ports 80/443 am vorhandenen Reverse Proxy. Der Paketstand wurde für Linux x86_64/Python 3.12 auflösbar geprüft; andere Architekturen wurden nicht ausgeführt.

## 1. Quellen und getrennte Konfiguration

Release-ZIP direkt auf dem Server in ein neues Verzeichnis entpacken, z. B. `/opt/map`. Alternativ das freigegebene Repository nach Lizenzentscheidung klonen. Keine alte `.env`, keine Entwicklungsdatenbank und keine personenbezogenen Dateien ins öffentliche Repository übernehmen.

```sh
cd /opt/map
python3 scripts/init-env.py
chmod 600 .env
nano .env
```

Mindestens die Betreiberangaben aus [KONFIGURATION.md](KONFIGURATION.md), die Domain und folgenden Produktionswerte setzen:

```dotenv
COMPOSE_FILE=compose.yaml:compose.production.yaml
COMPOSE_PROJECT_NAME=map-prod
MAP_IMAGE=map-prod:1.0.0-rc1
MAP_PRODUCTION=1
DEBUG=0
HTTPS=1
PUBLIC_URL=https://map.example.org
ALLOWED_HOSTS=map.example.org
CSRF_TRUSTED_ORIGINS=https://map.example.org
PROXY_NETWORK=reverse-proxy
MAP_PROXY_ALIAS=map-production
MAP_TRUSTED_PROXY_HOSTS=caddy
```

Die erzeugten zufälligen Werte für SECRET_KEY und POSTGRES_PASSWORD beibehalten und sicher sichern. Das externe Proxy-Netz muss bereits existieren und der Reverse Proxy muss daran angeschlossen sein. Das Skript startet keine neue zweite Caddy-Instanz.

## 2. Build, Tests und erste Migration

```sh
sh scripts/deploy.sh --bootstrap
```

Der Erststart wird verweigert, wenn die Ziel-Datenbank bereits Tabellen enthält. Vorher läuft die gesamte Testsuite auf dem **eigenen temporären Test-PostgreSQL**, nicht auf der Produktivdatenbank. Ein Fehler stoppt den Vorgang. Die OSV-Prüfung braucht ausgehendes HTTPS; bei Störung oder bekanntem Fund wird nicht einfach weitergemacht.

Eine erfolgreiche Ersteinrichtung bedeutet noch keine fachliche Produktivfreigabe. Es gibt zunächst keine Benutzer und keine Veranstaltungen.

## 3. Persönliches Admin-Konto anlegen

```sh
docker compose --profile tools run --rm init python manage.py createsuperuser
```

Eigenen Benutzernamen und eigenes starkes Passwort eingeben. Es gibt keine mitgelieferten Zugangsdaten. Weitere normale Admin-/Manager-Konten werden später in der UI angelegt; technische Adminrechte nur gezielt vergeben.

## 4. Bestehenden Caddy ergänzen

Diesen zusätzlichen Block in die vorhandene Caddyfile aufnehmen, **bestehende Seiten erhalten**:

```caddyfile
map.example.org {
    encode zstd gzip
    reverse_proxy map-production:8000
}
```

Der Alias entspricht MAP_PROXY_ALIAS. Konfiguration im vorhandenen Caddy-Container validieren und anschließend neu laden. Beispiel, wenn der Container `caddy` heißt:

```sh
docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Nicht zum localhost-Port des Webservers im Caddy-Container weiterleiten. Caddy bezieht Zertifikate für die konfigurierte öffentliche Domain selbst, sofern DNS und Challenges erreichbar sind. Bei TLS-Problemen erst DNS und Caddy-Logs prüfen, keine Zertifikatsdateien blind löschen.

## 5. Versand, Betreiberangaben und Probelauf

Über HTTPS anmelden. Im Profilmenü E-Mail-Einstellungen öffnen, SMTP oder Microsoft 365 konfigurieren, Zugang prüfen und eine Testmail auslösen. Rechtliche Betreiberangaben in `.env` vervollständigen und web/worker neu erzeugen.

```sh
docker compose --profile tools run --rm -T init python manage.py check_production
docker compose --profile tools run --rm -T init python manage.py check --deploy
docker compose ps
```

Danach mit künstlichen Daten eine Veranstaltung und Anmeldung einschließlich Bestätigung, Warteliste, Änderungen, Stornierung, Export und gegebenenfalls Zahlungserinnerung durchspielen. Konten mit unterschiedlichen Rollen prüfen. Betreiberangaben, Freigaben und Versand fachlich bestätigen. Erst dann echte Veranstaltungen veröffentlichen. Technische Tests sind keine Rechtsberatung und keine Zustellgarantie.

## 6. Backups und spätere Releases

Vor echten Anmeldungen Backups **außerhalb desselben Servers** einrichten und die Wiederherstellung in einem getrennten Stack erproben. Siehe [BETRIEB.md](BETRIEB.md). Regelmäßige Sicherung allein ohne Wiederherstellungstest genügt nicht.

Grundlagen: [Compose für Produktion](https://docs.docker.com/compose/how-tos/production/), [getrennte Compose-Projekte](https://docs.docker.com/compose/intro/compose-application-model/), [Caddy Reverse Proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
