# Konfiguration

Die technische Identität liegt in `.env` auf dem Server. Sie wird weder ins Repository noch in Screenshots übernommen. Nach Änderungen an `.env` müssen **web und worker neu erzeugt** werden:

```sh
docker compose up -d --no-build --force-recreate --wait web worker
```

Keine Änderung des SECRET_KEY bei einem normalen Update: Er schützt Links und verschlüsselte Mailzugangsdaten. Ein neuer Schlüssel macht bestehende Links ungültig und vorhandene verschlüsselte Inhalte unlesbar.

## Betreiberangaben außerhalb des Codes

| Variable | Verwendung |
|---|---|
| MAP_ORGANIZATION | Name im Kopfbereich, Footer und Seitentiteln |
| MAP_SITE_TITLE | Standardtitel des Browser-Tabs |
| MAP_MAIL_SENDER_NAME | Sichtbarer Name im SMTP-/Microsoft-Absender und Mailkopf |
| MAP_RESPONSIBLE_NAME / MAP_RESPONSIBLE_ADDRESS | Verantwortlicher Rechtsträger bzw. Vertretung und Anschrift |
| MAP_CONTACT_EMAIL | Kontakt für Datenschutz und Betreiberfragen |
| MAP_IMPRINT_URL | Vorhandenes HTTPS-Impressum; alternativ MAP_IMPRINT_TEXT für die interne Impressumsseite |
| MAP_HOSTING_DESCRIPTION | Tatsächlicher Hostinganbieter und Standort; keine erfundenen Rechenzentren |
| MAP_MAIL_DESCRIPTION | Tatsächlicher Versanddienst und wichtige Verarbeitungshinweise |
| MAP_PRIVACY_LEGAL_TEXT | Vom Betreiber geprüfte Rechtsgrundlagen; z. B. DSGVO oder gegebenenfalls kirchliches Recht |
| MAP_PRIVACY_AUTHORITY | Konkret zuständige Datenschutzaufsicht und Kontaktmöglichkeit |
| MAP_PHOTO_DISPLAY_LABEL | Letzte Frage des Foto-/Datenschutzbausteins |
| MAP_LOGO_PATH / MAP_FAVICON_PATH | Lokale Static-Pfade; Standard map/logo.svg |

Texte sind Klartext, kein HTML. Django maskiert HTML-Zeichen. Für mehrzeilige Werte kann Compose in doppelt gequoteten `.env`-Werten `\n` verwenden. Bei Dollarzeichen und anderen Sonderzeichen die Compose-Quotingregeln beachten. Die erzeugten Schlüssel verwenden ausschließlich Hexzeichen und brauchen keine besondere Behandlung.

Eigene Logos unter `operator-assets/operator/logo.svg` und z. B. `operator-assets/operator/favicon.png` hinterlegen, anschließend MAP_LOGO_PATH=operator/logo.svg und MAP_FAVICON_PATH=operator/favicon.png setzen. Nur selbst kontrollierte Dateien verwenden, Nutzungsrechte prüfen. Das Verzeichnis wird im Produktionsbetrieb nur lesbar eingebunden und vom öffentlichen Paket ausgeschlossen. Beim Start sammelt web die Static-Dateien in sein temporäres Verzeichnis. Andere MIME-Typen für das Favicon funktionieren ohne SVG-Zwang.

Die Foto-Beschriftung beeinflusst **neu eingefügte** Bibliotheksbausteine. Bereits gespeicherte Formulare und Anmeldungs-Snapshots bleiben erhalten und müssen bei Bedarf bewusst im Editor geändert werden.

## Technischer Betrieb

| Variable | Produktion |
|---|---|
| COMPOSE_PROJECT_NAME | Eindeutig, z. B. map-prod; trennt Container, Netz und Datenvolume |
| COMPOSE_FILE | compose.yaml:compose.production.yaml auf Linux |
| MAP_IMAGE | Eigener, versionierter Image-Tag je Release |
| PUBLIC_URL | Vollständige HTTPS-Herkunft, ohne abschließenden Slash |
| ALLOWED_HOSTS | Nur echte Hostnamen, kommasepariert; keine Sternfreigabe |
| CSRF_TRUSTED_ORIGINS | Dieselbe HTTPS-Herkunft wie PUBLIC_URL |
| HTTPS / DEBUG / MAP_PRODUCTION | 1 / 0 / 1 |
| PROXY_NETWORK | Bereits vorhandenes externes Docker-Netz des Reverse Proxys |
| MAP_PROXY_ALIAS | Eindeutiger Name für diese Installation im Proxy-Netz |
| MAP_TRUSTED_PROXY_HOSTS | DNS-Name des tatsächlichen Proxy-Containers |
| MAP_TRUSTED_PROXY_NETWORKS | Nur bei Bedarf präzise zusätzliche vertrauenswürdige Netze; nie 0.0.0.0/0 |
| POSTGRES_* | Eigene Datenbank, eigenes Passwort; nicht aus der Entwicklungsumgebung übernehmen |

Die gemeinsame Compose-Datei bietet keinen öffentlichen Datenbankport. Nur web hängt zusätzlich im Proxy-Netz. Die Hostvertrauensprüfung für Client-IP-Begrenzungen ersetzt keine Netztrennung: unkontrollierte Container dürfen nicht in dieses Netz aufgenommen werden.

## Konfiguration in der Oberfläche

Über das Profilmenü: Benutzer, technische Admins, Leitendenstatus, Stufen, Rollen, E-Mail-Einstellungen, Warteschlange und Systemmail-Vorlagen. Neue Installationen enthalten Admin, Manager und Read-Only, aber keine vorgegebenen Benutzer oder Passwörter. Stufenrechte entstehen beim Anlegen der Stufen.

SMTP oder Microsoft 365 kann in der UI gespeichert und getestet werden. Die Produktionsdatenbank übernimmt keine Geheimnisse aus der Entwicklung. Bei Microsoft 365 zuerst die Anwendung und Postfachbegrenzung im eigenen Mandanten einrichten; der Zugangstest allein belegt keine Zustellung. Anschließend eine echte Testnachricht an eine kontrollierte Adresse senden und SPF/DKIM/DMARC im eigenen Mailbetrieb prüfen. Keine DNS-Zugangsdaten in MAP hinterlegen.

`python manage.py check_production` prüft Pflichtangaben und wesentliche HTTPS-/Versandeinstellungen. Es versendet keine E-Mail und kann weder Rechtmäßigkeit noch tatsächliche Zustellung bestätigen.

## Neue Modulkonfiguration

Microsoft-Anmeldung und Gruppenmapping werden getrennt vom Mailversand in der UI eingerichtet. Räume, Raum-Mailvorlagen und die opt-in Belegungs-API liegen unter Raumeinstellungen. Optionale Mailtypen werden über ihre Statusfelder geschaltet; wesentliche Konto-/Bestätigungsabläufe bleiben geschützt. Die Einstellungen werden in der jeweiligen Installationsdatenbank gespeichert und nicht automatisch zwischen Dev und Prod synchronisiert.
