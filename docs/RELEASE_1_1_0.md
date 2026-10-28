# MAP 1.1.0

Entra-SSO mit tenantgebundener Identität und mehreren automatischen Stufen, unabhängige Raumbuchung mit Genehmigungen und Änderungsanträgen, verwaltbarer Raumkatalog, öffentliche Ganztagsaggregation, getrennte Einstellungen und systemabhängige graue Darstellung. Optionale Mailvorlagen erhalten eigene Versandrichtlinien; Pflichtnachrichten bleiben aktiv. Benutzerkonten können mit signierter Bestätigung und Schutz des letzten Adminzugangs gelöscht werden. Operative Datensätze bleiben erhalten; private Vorlagen werden kontrolliert übertragen.

Lokale Endprüfung: 555 Anwendungstests, 550 bestanden und fünf PostgreSQL-spezifisch übersprungen. Zwischenstufen wurden zusätzlich separat geprüft (31 SSO-Tests, 94 Modul-/SSO-Tests mit einem PostgreSQL-Skip und 26 Mail-/API-Tests). Die Produktionsbereitstellung besitzt 17 simulierte Standardbibliotheks-Tests für Reihenfolge, Sicherungen, Isolation und Rückfall. Bestehende Deploymenttests und öffentliche Quellenprüfung bleiben Teil der CI. Die verbindliche Linux-/PostgreSQL-Prüfung erfolgt zusätzlich in GitHub Actions und vor jeder Produktionsmigration.

Browserprüfungen der Entwicklung umfassten unter anderem 120 Kombinationen aus Ansicht, Bildschirmgröße und Darstellung sowie 16 Account-/Checkbox-Kombinationen. Keine echten Benutzer, Microsoft-Geheimnisse oder Produktionsdaten gehören zu den Testfixtures. Ein echter Login und eine Probeanmeldung müssen nach dem Prod-Update im realen System geprüft werden.

Die Open-Source-Lizenzentscheidung bleibt unverändert offen; siehe LICENSE-NOTICE.md. Dieses Release schreibt keine ungewählte Lizenz fest.

## Prod-Kompatibilitätskorrektur

Die Freigabeliste akzeptiert zusätzlich die exakt bekannten Inhalte von `.github/dependabot.yml` aus Commit `26b495e` und `map/tests/test_privacy_link_ui.py` aus Commit `9a669d4`. Diese Versionen wurden vor dem aktuellen Release ausgeliefert. Es werden keine unbekannten Dateien pauschal freigegeben; Regressionen prüfen alte LF-/CRLF-Dateien sowie weiterhin abgewiesene individuelle Änderungen. Die Anwendung und der eigentliche Deployment-Ablauf bleiben unverändert. Der Release-Installer besitzt nun 18 Tests.
