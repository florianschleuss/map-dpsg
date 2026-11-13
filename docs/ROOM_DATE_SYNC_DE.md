# Enddatum der Raumbuchung automatisch übernehmen

Bei Einmalbuchungen wird das Enddatum beim Auswählen des Startdatums auf denselben Tag gesetzt. Der gemeinsame Kalender aktualisiert dabei den gespeicherten Wert, die Datumsanzeige und den geöffneten Monat. Anschließend kann ein späteres Enddatum für mehrtägige Buchungen ausgewählt werden. Uhrzeiten werden nicht geändert; die Konfliktprüfung erhält die aktualisierten Daten.

Bei wöchentlichen Serien bleibt ein bereits gewähltes späteres Serienende erhalten. Liegt das bisherige Ende vor dem neuen Beginn, wird es ebenfalls auf das neue Startdatum gesetzt. Bereits gespeicherte Zeiträume werden beim bloßen Öffnen der Seite nicht verändert. Keine neue Datenbankmigration erforderlich.

Browserprüfung: tatsächliche Kalenderauswahl über mehrere Monate, sichtbares Enddatum, Kalendermonat und Markierung, mehrtägige Auswahl, unveränderte Uhrzeiten, Wiederholungen und aktuelle Konfliktanfrage; jeweils Desktop/Mobil und Hell/Dunkel.

Vergangene Raumbuchungen werden standardmäßig ausgeblendet, wenn ihr Ende bereits erreicht ist. Laufende Buchungen und wöchentliche Serien mit künftigem Ende bleiben sichtbar. Die Auswahl Vergangene anzeigen oder eine gezielte Von-/Bis-Auswahl gibt ältere Buchungen wieder frei. Kalendernavigation mit ausgewähltem Datum kann ebenfalls historische Belegungen anzeigen. Der Filter gilt auch für Exporte; stornierte Buchungen bleiben zusätzlich durch den separaten Statusfilter ausgeblendet. Alle Datensätze und Verläufe bleiben gespeichert.
