# Entwicklung

Quellcode und technische Bezeichner sind Englisch, Oberfläche und Anwenderdokumentation Deutsch. Vor einer Beitragsannahme muss die noch offene Projektlizenz geklärt werden.

Tests mit realem PostgreSQL, ohne Zugriff auf die Produktivdatenbank:

```sh
python3 scripts/init-env.py  # nur wenn .env noch nicht existiert
sh scripts/test.sh
```

Der Testdienst verwendet ausschließlich den eigenen temporären PostgreSQL-Dienst test-db und feste Testzugangsdaten. Diese sind keine Produktivzugangsdaten. Zusätzlich können die unabhängigen Prüfungen über python3 checks/static_checks.py, checks/permission_checks.py und checks/security_checks.py ausgeführt werden.

Screenshots reproduzieren: Python-Anwendungsabhängigkeiten in einer isolierten Entwicklerumgebung bereitstellen, `python tools/render_screenshot_pages.py` ausführen und anschließend mit Node.js ab Version 20 und Playwright `node tools/screenshot.cjs` ausführen. Optional `CHROME_PATH` auf einen vorhandenen Chrome-Browser setzen. Das Python-Werkzeug erzwingt eine In-Memory-Datenbank und künstliche Daten, versendet keine Mails und startet keinen Webserver.

Vor dem Commit `python3 tools/check_public_release.py` ausführen. Dieses Werkzeug ist eine zusätzliche Prüfung, kein Ersatz für die Durchsicht des Git-Diffs und gegebenenfalls der gesamten Git-Historie. Niemals Produktionskopien, alte Update-Befehle, private Betreiberprofile oder Backups ins Repository kopieren.
