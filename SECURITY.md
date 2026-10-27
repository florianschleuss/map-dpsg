# Sicherheit

Bitte keine personenbezogenen Daten, persönlichen Anmeldelinks, Zugangsdaten, Datenbank-Dumps oder vollständigen E-Mail-Aufträge in öffentlichen Issues veröffentlichen. Sicherheitslücken über den privaten Meldeweg des jeweiligen Repository-Betreibers melden; falls verfügbar, GitHubs private Sicherheitsmeldungen verwenden. Ein öffentlicher Issue-Tracker ist kein geeigneter erster Meldeweg für ausnutzbare Lücken.

Vor dem tatsächlichen Veröffentlichen muss der Repository-Betreiber einen erreichbaren privaten Kontakt oder private Sicherheitsmeldungen einrichten. Dieses vorbereitete Paket nennt bewusst keinen erfundenen Maintainer-Kontakt und verspricht keine Reaktionsfrist.

Produktionsbetrieb benötigt HTTPS, getrennte Datenbanken für Test und Produktion, geschützte Sicherungen und regelmäßige Updates. SECRET_KEY schützt signierte Links und verschlüsselte Mailzugangsdaten: nicht veröffentlichen und nicht ohne Migrations-/Wiederherstellungsplan ändern.
