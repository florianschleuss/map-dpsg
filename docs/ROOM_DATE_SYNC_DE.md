# Enddatum der Raumbuchung automatisch übernehmen

Bei Einmalbuchungen wird das Enddatum beim Auswählen des Startdatums auf denselben Tag gesetzt. Der gemeinsame Kalender aktualisiert dabei den gespeicherten Wert, die Datumsanzeige und den geöffneten Monat. Anschließend kann ein späteres Enddatum für mehrtägige Buchungen ausgewählt werden. Uhrzeiten werden nicht geändert; die Konfliktprüfung erhält die aktualisierten Daten.

Bei wöchentlichen Serien bleibt ein bereits gewähltes späteres Serienende erhalten. Liegt das bisherige Ende vor dem neuen Beginn, wird es ebenfalls auf das neue Startdatum gesetzt. Bereits gespeicherte Zeiträume werden beim bloßen Öffnen der Seite nicht verändert. Keine neue Datenbankmigration erforderlich.

Browserprüfung: tatsächliche Kalenderauswahl über mehrere Monate, sichtbares Enddatum, Kalendermonat und Markierung, mehrtägige Auswahl, unveränderte Uhrzeiten, Wiederholungen und aktuelle Konfliktanfrage; jeweils Desktop/Mobil und Hell/Dunkel.
