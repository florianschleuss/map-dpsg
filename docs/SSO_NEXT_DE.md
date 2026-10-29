# SSO: ursprüngliche Zielseite erhalten

Der Microsoft-Button übergibt das next-Feld aus der Anmeldeseite. Der Anmeldestart validiert den lokalen absoluten Pfad und speichert ihn zusammen mit dem bestehenden, kurzlebigen MSAL-Vorgang in der serverseitigen Sitzung. Die Microsoft-Callback-Adresse bleibt unverändert. Nach erfolgreicher Token- und Kontofreigabeprüfung erfolgt die Weiterleitung an das gespeicherte Ziel, beispielsweise /raeume/neu/. Query-Parameter am internen Ziel bleiben erhalten.

Externe, protokollrelative und ungültige Ziele werden verworfen. Der Callback validiert den gespeicherten Pfad erneut und ignoriert ein dort zusätzlich übermitteltes next-Feld. Ohne gültiges Ziel bleibt das Dashboard der Standard. Ein noch nicht freigegebenes Konto landet weiterhin auf der Warteseite; die Rechte der Zielseite bleiben unverändert geprüft. Der Konfigurationstest führt unverändert zurück zu den SSO-Einstellungen. Keine Änderungen an Entra oder Datenbankmigrationen erforderlich.

Regressionen: Microsoft-Formular, gespeicherter Vorgang, erfolgreiche Weiterleitung mit Query-Parametern, fehlende Freigabe, externe Ziele, fehlerhafte Pfade und bereits angemeldete Konten.
