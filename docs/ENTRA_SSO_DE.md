# Microsoft-Anmeldung für MAP (Dev)

Dieses Update ergänzt Microsoft Entra ID für Verwaltungsbenutzer. Eltern benötigen weiterhin kein Konto. Der Versand über Exchange Online bleibt unabhängig davon konfiguriert.

## Dev aktualisieren

Den gesamten Inhalt der mitgelieferten Datei `MAP-SSO-Dev-Update-Befehl.txt` als root auf dem Server ausführen. Er erwartet **/opt/dev/map**, lehnt andere Pfade sowie als Produktion konfigurierte Container ab und verändert weder `/opt/map` noch Caddy oder `.env`. Er sichert Quellen und laufende Images, baut und prüft vor dem Wechsel und erstellt vor der additiven Migration eine PostgreSQL-Sicherung. Neue SSO-Tabellen verändern keine vorhandenen Anmeldungen. Bei einem Fehler werden Quellen und gegebenenfalls Images zurückgesetzt; bereits angelegte neue Tabellen bleiben erhalten. Eine Datenbankwiederherstellung erfolgt niemals automatisch.

Der Versionsschutz stoppt bei abweichenden Dateien, bevor etwas überschrieben wird. Dann die Meldung weitergeben. Der Befehl startet keine App auf dem eigenen Windows-Rechner und macht keinen Git-Commit oder Push.

## Einrichtung in MAP

1. Lokal als MAP-Admin anmelden. Im Profil **Microsoft-Anmeldung** öffnen. Einen funktionierenden lokalen technischen Adminzugang für Störungen beibehalten.
2. Zunächst die App nach den folgenden Schritten in Entra anlegen. Für Dev eine eigene App verwenden; keine Zugangsdaten der Mail-App übernehmen.
3. In MAP Tenant-ID, Client-ID, Wert des Geheimnisses, dessen Ablaufdatum und die Benachrichtigungsadresse eintragen.
4. Gruppen-IDs Stufen zuordnen oder für rein manuelle Freigabe leer lassen. Microsoft-Anmeldung aktivieren und speichern.
5. **Microsoft-Anmeldung testen** ausführen. Der Test prüft den vollständigen Anmeldeweg und zeigt Gruppen-IDs; er wechselt das aktuelle MAP-Konto nicht. Erst ein erfolgreicher echter Test bestätigt die Tenant-Konfiguration. Das Speichern allein prüft die Zugangsdaten nicht.
6. In einem privaten Browserfenster als normales Microsoft-Mitglied anmelden. Passende Stufen prüfen; ohne passende Gruppen muss die Freigabeseite erscheinen. Manuell freigeben, erneut anmelden und die effektiven Rechte kontrollieren.

Die Anmeldeseite zeigt bei aktivierter SSO-Verbindung den großen Button **Mit Microsoft anmelden** und darunter die aufklappbare **Lokale Anmeldung**. Ohne aktivierte SSO-Verbindung bleibt das lokale Anmeldeformular direkt sichtbar.

## Vorhandene Gruppen finden

1. [Microsoft Entra Admin Center](https://entra.microsoft.com/) öffnen.
2. **Entra ID → Gruppen → Alle Gruppen** wählen.
3. Nach Stufenbezeichnungen oder euren Teams suchen. Microsoft-365-Gruppen hinter Teams sind ebenfalls nutzbar.
4. Gruppe öffnen, die **Mitglieder** prüfen und die **Objekt-ID** kopieren. Nicht die Gruppen-E-Mail-Adresse oder den Anzeigenamen verwenden.
5. Die ID in MAP zusammen mit der passenden Stufe eintragen. Eine Microsoft-Gruppe kann mehreren Stufen zugeordnet werden; mehrere Gruppen können auf dieselbe Stufe zeigen.

Fehlt der Gruppenbereich, benötigt das Microsoft-Konto entsprechende Verzeichnis-Leserechte durch eure Microsoft-Administration. MAP selbst fordert für diesen Ablauf keine Verzeichnis-Leseberechtigung an.

Offizielle Anleitung: [Gruppen verwalten](https://learn.microsoft.com/en-us/entra/fundamentals/how-to-manage-groups).

## SSO-App in Entra registrieren

1. **Entra ID → App-Registrierungen → Neue Registrierung**. Name beispielsweise „MAP Dev Anmeldung“.
2. Unterstützte Kontotypen: **Nur Konten in diesem Organisationsverzeichnis**.
3. Umleitungs-URI, Plattform **Web**: `https://dev.map.example.org/accounts/microsoft/callback/`. Maßgeblich ist die in MAP angezeigte Adresse aus `PUBLIC_URL`.
4. Übersichtsseite: **Anwendungs-ID (Client-ID)** und **Verzeichnis-ID (Tenant-ID)** nach MAP kopieren.
5. **Zertifikate und Geheimnisse → Neuer geheimer Clientschlüssel**. Dessen einmal sichtbaren **Wert**, nicht die Geheimnis-ID, sowie das Ablaufdatum in MAP eintragen. Geheimnis niemals in Chat, Git oder Screenshots teilen.
6. **Tokenkonfiguration → Gruppenanspruch hinzufügen → Alle Gruppen**. Im ID-Token Gruppen als **Gruppen-ID/Objekt-ID** ausgeben. Keine Umstellung auf Anzeigenamen oder Rollen. Bei der Wahl nur zugewiesener Gruppen hängen Möglichkeiten von Lizenz und Zuweisung ab; die hier geprüfte Konfiguration verwendet „Alle Gruppen“.
7. Die Anmeldung nutzt OpenID Connect (`openid`, `profile` und von MSAL ergänzte Identitäts-Scopes). Keine `Mail.Send`-, `Directory.Read.All`- oder zusätzlichen Microsoft-Graph-Gruppenrechte hinzufügen. `offline_access` wird ausdrücklich ausgeschlossen. Eine vom Tenant geforderte Administratorzustimmung muss eure Microsoft-Administration erteilen.
8. Microsoft-Zugriffsregeln wie MFA und Benutzerzuweisung werden in Entra verwaltet. Die MAP-Konfiguration allein umgeht diese Regeln nicht. In Entra existierende Gastkonten gehören zum eingetragenen Verzeichnis; sie erhalten ebenfalls nur über eine konfigurierte Stufe oder manuelle Freigabe Zugriff.

Offizielle Grundlagen: [MSAL Python – Authorization Code Flow](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens), [Claims prüfen](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation).

## Rechte und Freigabe

- Identitäten werden ausschließlich über **Tenant-ID + Objekt-ID** verbunden. Eine gleiche E-Mail-Adresse führt nie zur Kontoübernahme.
- Gruppen vergeben nur automatische **Leitendenrechte für Stufen**, entsprechend den bestehenden MAP-Stufenrechten (Lesen, Anlegen, Bearbeiten und Löschen). Keine automatischen Rollen, Admin- oder technischen Rechte.
- Unbekannte Konten werden ohne lokales Passwort angelegt. Ohne passende Stufe oder manuelle Freigabe bleiben sie auf der Warteseite und können keine Verwaltungsdaten öffnen.
- Die konfigurierte Adresse erhält einmal je wartendem Konto eine Freigabeanfrage über die bestehende Mail-Warteschlange. Mailversand und Worker müssen dafür funktionieren. Eine nachträglich entfernte automatische Zuordnung wird nicht bei jeder Anmeldung erneut per Mail gemeldet.
- Manuelle Stufen werden im vorhandenen Leitendenprofil gespeichert; automatische Stufen separat. Synchronisieren entfernt ausschließlich abgeleitete automatische Stufen, keine manuellen Rollen, Einzelrechte oder ausdrücklich vorhandenen Veranstaltungsrechte.
- Microsoft-Sitzungen sind auf **15 Minuten** begrenzt. Danach erneut mit Microsoft anmelden; ein bestehender Microsoft-Browserlogin kann dabei den Ablauf verkürzen. Es gibt keinen Hintergrundabgleich mit Graph. Änderungen an Entra-Mitgliedschaften werden spätestens bei der nächsten erfolgreichen Anmeldung nach Ablauf dieses Zeitfensters übernommen.
- Die MAP-Sperre eines Microsoft-Zugangs und Änderungen an der SSO-Konfiguration greifen beim nächsten Request. Änderungen der Konfiguration verlangen eine neue Microsoft-Anmeldung. Die komplette Kontosperre erfolgt weiterhin unter Benutzer.
- Liefern Microsoft-Gruppenansprüche keine vollständige Liste (beispielsweise Gruppen-Overage), erhält das Konto keine automatischen Stufen. Manuelle Freigaben bleiben möglich. MAP folgt keinen Gruppen-URLs aus einem Token.
- Die Freigabeliste zeigt die neuesten **200** verknüpften Konten. Die normale Benutzerverwaltung bleibt für die vollständige Kontenliste verfügbar.

## Eindeutige Microsoft-Konten

Neu angelegte Konten erhalten den E-Mail-Namen vor dem @ mit dem Suffix `#SSO`, bei Kollisionen mit einer zusätzlichen Nummer. Die Zuordnung bleibt auf Tenant-ID und Objekt-ID aufgebaut. Bestehende automatische `entra_…`-Namen ohne lokales Passwort werden durch die Migration umbenannt. Benutzer-ID und Rechte bleiben gleich. Die Funktion zum nachträglichen Verbinden lokaler Konten ist entfernt. Bereits bestehende Identitätszuordnungen bleiben erhalten. Gleiche E-Mail-Adressen führen nie zur automatischen Kontoübernahme.

## Sicherheit und Betriebsgrenzen

MSAL führt den Authorization Code Flow mit PKCE, State und Nonce durch. MAP prüft zusätzlich die JWT-Signatur (RS256), den fest eingestellten Aussteller, Ziel-App, Tenant und Ablaufzeit. Anmeldevorgänge laufen nach zehn Minuten ab und werden beim Callback verbraucht. Fehlerseiten zeigen weder Microsoft-Geheimnisse noch Tokeninhalte. Das App-Geheimnis ist in der Datenbank verschlüsselt; der dauerhafte Django-`SECRET_KEY` muss geschützt und gesichert bleiben. Access-, Refresh- und ID-Tokens werden nicht dauerhaft gespeichert. Gruppen-IDs und die letzte erfolgreiche Anmeldung werden für die Zuordnung gespeichert; dies ist in den Datenschutzhinweisen ergänzt.

Der Rücksprung enthält kurzzeitig einen einmaligen Autorisierungscode in der URL. Caddy-Zugriffsprotokolle dürfen solche Query-Parameter nicht dauerhaft ungekürzt protokollieren. Die MAP-Webkonfiguration protokolliert keinen Access-Log; die Callback-Antwort setzt `Referrer-Policy: no-referrer` und `Cache-Control: no-store`.

Dieses Paket ist für Dev vorgesehen. Automatisierte Tests ersetzen keinen erfolgreichen echten Login mit eurer App und mindestens einem normalen Konto. Ein Live-Tenant-Test konnte bei der Erstellung ohne eure App-Konfiguration nicht durchgeführt werden. Für einen späteren Prod-Rollout separate App/Umleitungsadresse, Tenant-Freigaben und Datenschutzangaben prüfen.

## Prüfbericht dieses Dev-Pakets

- Vollständiger lokaler Django-Lauf: 468 Tests, 464 bestanden, vier PostgreSQL-spezifische Tests übersprungen.
- Anschließend 27 gezielte SSO-Tests bestanden; ein zusätzlicher Test für ungültige Konto-IDs ebenfalls bestanden.
- Darunter echte lokal signierte RSA-JWTs mit Ablehnung falscher Signatur, Ziel-App, Aussteller, Ablaufzeit, Tenant und Nonce; MSAL erzeugt PKCE und Nonce im Test. Microsoft-Netzwerkantworten wurden simuliert.
- Anmeldeseite und Admin-Einstellungen bei 1440 und 390 Pixeln geprüft, ohne horizontalen Seitenüberlauf; lokale Anmeldung aufklappbar.
- Migrationsstand konsistent. Linux/Python-3.12-Abhängigkeiten per pip-Dry-Run auflösbar. Sieben neue Paketversionen über OSV geprüft, keine dort gemeldeten Treffer zum Prüfzeitpunkt.
- Dev-Updater mit sieben simulierten Abläufen geprüft: Erfolg, Testfehler, Migrationsfehler, Startfehler, abweichende Quellen, Produktionskonfiguration und laufender Produktionscontainer.
- Kein lokaler Docker-/PostgreSQL-Lauf und kein echter Microsoft-Tenant-Login. Die vollständigen Containerchecks laufen im Dev-Update vor der Umstellung; der echte Tenant-Test ist in der Admin-Seite vorgesehen.
