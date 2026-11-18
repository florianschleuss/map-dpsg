# Zugang nur zur Raumbuchung

Ein lokales Konto, z.B. Gemeindebüro, benötigt lediglich Raumbuchungen lesen und Raumbuchungen anfragen. In der Benutzerverwaltung entweder diese Einzelrechte setzen oder eine eigene Rolle mit diesen beiden Rechten anlegen und zuweisen. Kein technischer Admin, kein Admin/Manager/Read-Only und keine Veranstaltungs- oder Stufenrechte. Leitendenstatus ist für dieses Konto nicht nötig. Alle Raumbuchungsdetails einschließlich Kontaktdaten und Exporten sind mit dem Leserecht sichtbar.

Konten mit Raumzugang und ohne Veranstaltungsrechte landen standardmäßig direkt bei /raeume/. Der Veranstaltungsreiter ist ausgeblendet; das MAP-Logo und die Raum-Navigationspfade führen zu den Räumen. Auch /dashboard/ führt diese Konten zu den Räumen weiter. Gültige lokale next-Links bleiben wirksam. Veranstaltungsdaten werden weiterhin durch ihre bestehenden Berechtigungsprüfungen geschützt.

Die Erkennung berücksichtigt globale Veranstaltungsrollen, Stufenrechte auch ohne bestehende Veranstaltungen, lokale und automatische SSO-Stufenzuordnungen, persönliche Veranstaltungsrechte und Formularverwaltungsrechte. Es handelt sich um eine additive Rechteprüfung: Andere Rechte werden durch die Raumrolle nicht entzogen. Konten mit Veranstaltungsrechten behalten ihren bisherigen Einstieg. Auch manuell freigegebene SSO-Raumkonten können diesen Einstieg nutzen.

Keine Konten, Rollen oder Rechte werden automatisch angelegt oder verändert. Keine Datenbankmigration und keine zusätzliche Einstellung erforderlich. Korrigiert werden außerdem fehlerhafte Umlaute in Microsoft-Anmeldetexten.
