# MAP – Benutzerkonten löschen und Passwort-Link-Checkbox ausrichten

## Dev-Update ausführen

1. Die Datei `MAP-Benutzerloeschung-Dev-Update-Befehl.txt` vollständig öffnen und in die Remote-Konsole des Servers kopieren, als root ausführen. Das aktuelle Arbeitsverzeichnis ist egal.
2. Ausschließlich `/opt/dev/map` wird verändert. Produktion, `.env`, Zugangsdaten und Caddy bleiben unverändert. Kein Commit oder Push; keine Installation auf deinem PC.
3. Vor Änderungen prüft das Skript den bekannten Quellstand sowie getrennte Dev-/Prod-Konfiguration und Images. Bei einer Abweichung bricht es ab und zeigt alle betroffenen Dateien. Bitte die vollständige Meldung weitergeben.
4. Dev-Web und Dev-Worker werden vorübergehend gestoppt. Quellen und bisherige Images werden gesichert; neue Images werden gebaut und die vollständigen Tests im Testdienst ausgeführt. Erst danach folgen PostgreSQL-Sicherung, Migration (für diese Änderung ohne zusätzliche Schemaänderung) und Dev-Neustart.
5. Bei Fehlern werden Quellen und Image-Tags wiederhergestellt. Bereits erfolgte Datenbankänderungen würden nicht automatisch zurückgenommen; die Datenbanksicherung liegt im ausgegebenen Sicherungsordner.
6. Nach Erfolg Strg+F5 im Browser.

Nur ältere Sicherungsordner eigener Dev-Updater (`sso-dev-*`, `rooms-dev-*`, `ui-sso-dev-*`, `rooms-api-dev-*`, `mail-ui-dev-*`, `users-dev-*`) werden wie zuvor erlaubt innerhalb des geprüften Dev-Sicherungsordners entfernt. Andere Sicherungen bleiben erhalten.

## Benutzer löschen

**Profil → Benutzer → Person bearbeiten → Benutzerkonto löschen**.

Ein Bestätigungsdialog beschreibt die Folgen. Abbrechen oder Escape schließt ohne Änderung. Ohne JavaScript führt der Link auf eine eigene Bestätigungsseite. Erst **Benutzer endgültig löschen** sendet einen geschützten POST-Auftrag. Die zusätzliche signierte Bestätigung ist 15 Minuten gültig und an ausführendes Konto, Zielkonto und dessen gespeicherten Benutzernamen gebunden. Nach einer zwischenzeitlichen Namensänderung oder bei abgelaufener Bestätigung muss der Dialog neu geöffnet werden.

Es gelten die bisherigen Rechte der Benutzerverwaltung. Technische Admin-Konten können nur technische Admins löschen. Das eigene Konto kann nicht gelöscht werden. Mindestens ein aktives Admin-Konto und der technische Adminzugang bleiben geschützt; die Prüfung läuft beim tatsächlichen Löschen unter Datenbanksperren nochmals gegen den aktuellen Stand.

## Was entfernt wird

Das Benutzerkonto einschließlich Passwort und direkter Rollen-/Rechtezuordnungen, Leitendenprofil und Stufenzuordnungen, persönliche Veranstaltungsberechtigungen, Microsoft-Identitätsverknüpfung und zugehörige Passwort-Reset-Aufträge werden entfernt. Die bisherigen Anmeldesitzungen erhalten bei weiteren Aufrufen keinen authentifizierten Zugriff mehr. Es werden dadurch keine Mails ausgelöst.

## Was erhalten bleibt

Veranstaltungen, Kinder-Anmeldungen, Formulare, Raumbuchungen, Entscheidungen und Protokolle bleiben bestehen. Personenverweise in diesen Datensätzen werden gemäß ihren bestehenden Beziehungen geleert. Kontaktpersonen/-texte in Raumbuchungen und bereits gespeicherte Nachrichtentexte bleiben erhalten. Kontolöschung ist deshalb keine pauschale Entfernung aller in Freitexten vorkommenden Angaben.

Eigene Formularvorlagen werden dem löschenden Konto zugeordnet. Das verhindert, dass eine bisher private Vorlage nach Entfernung ihres Eigentümers unbeabsichtigt als allgemeine Standardvorlage sichtbar wird. Bestehende veranstaltungsbezogene Formularzugriffe bleiben erhalten.

## Besonderheit Microsoft/Entra

Das Microsoft-Konto selbst wird nicht gelöscht. Ist die Microsoft-Anmeldung weiter erlaubt und bestehen passende Entra-Gruppenmitgliedschaften, kann beim nächsten Login ein neues MAP-Konto entstehen, gegebenenfalls mit automatischen Stufenrechten. Manuell vergebene Rollen und persönliche Rechte des gelöschten Kontos werden dadurch nicht wiederhergestellt. Soll der Zugang dauerhaft gesperrt bleiben, das MAP-Konto deaktivieren oder die Anmeldung/Freigabe in Entra entziehen. Der Löschdialog weist bei Microsoft-Konten darauf hin.

## Checkbox zum Passwort-Link

Checkbox und Erklärung stehen nun in zwei festen Spalten; der Text kann sauber umbrechen. Der Versandbutton steht mit Abstand darunter. Das wurde in heller/dunkler Darstellung auf Desktop und Mobilgerät geprüft. Der bestehende ausdrückliche Haken vor dem E-Mail-Versand bleibt notwendig.

## Nach dem Update prüfen

Ein ausschließlich dafür angelegtes Dev-Testkonto öffnen, die Checkbox-Ausrichtung ansehen und den Löschdialog zunächst abbrechen. Danach das Testkonto bewusst löschen. Bestehende Veranstaltungen und Raumbuchungen müssen erhalten bleiben. Beim eigenen Konto darf kein Löschbutton angeboten werden. Für Microsoft-Konten den Hinweis zur möglichen erneuten Kontoanlage beachten.
