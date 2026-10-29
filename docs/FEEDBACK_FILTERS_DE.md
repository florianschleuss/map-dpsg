# Filter und Feedback

Stornierte Raumbuchungen werden standardmäßig ausgeblendet, bleiben aber mit Details und Verlauf gespeichert. Der Statusfilter bietet Nicht storniert, Alle Status und die einzelnen Zustände. Die Auswahl gilt auch für Kalender und Exporte. Die eigene Buchungsansicht bleibt beim Filtern erhalten. Die Filterleiste ist in einheitliche Felder aufgeteilt und passt sich an schmale Bildschirme an.

Veranstaltungen ohne Limit zeigen auf dem Dashboard ausschließlich die Anmeldezahl, ohne Nenner. Begrenzte Veranstaltungen behalten die Anzeige belegt / Plätze.

Unter E-Mail-Einstellungen ist Feedback-Adresse für die Website separat vom Versandpostfach einstellbar. Die Adresse wird öffentlich als Mailto-Link Probleme gefunden / Feedback zur Website im Footer angezeigt. Leer lassen blendet den Link aus. Der Link öffnet das Mailprogramm; MAP verschickt dadurch keine Nachricht und ergänzt keine persönlichen Anmelde-URLs oder Zugangstoken. Die Adresse ist unabhängig von SMTP/Graph und kann bei deaktivierten eigenen Versanddaten gespeichert werden. Bestehende Geheimnisse bleiben unverändert.

Migration map.0017 ergänzt ein optionales E-Mail-Feld. Die Produktionsbereitschaftsprüfung liest vor der Migration nur die vorhandenen Versandfelder; dadurch funktioniert sie auch mit dem bisherigen Datenbankschema.
