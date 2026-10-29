# Kalender, Platzlimits und Raumbuchungen

Alle Datumsfelder verwenden den deutschen Kalender der Veranstaltungserstellung. Datumsfelder ohne Uhrzeit verwenden denselben Kalender ohne Uhrzeitauswahl, optional mit Löschen-Funktion. Das gilt auch für dynamisch erzeugte Formularvorschauen. Der Kalender bleibt beim Monatswechsel geöffnet und unterstützt den grauen Darkmode.

Veranstaltungen haben standardmäßig weiterhin begrenzte Plätze je Stufe. Unter Platzverteilung steht zusätzlich Ohne Limit zur Verfügung. In diesem Modus gelten weder Gesamt- noch Stufenkontingente; die Stufenauswahl bleibt erforderlich. Die Warteliste entfällt. Beim Umstellen rücken bestehende gültige Wartelisteneinträge nach. Abgelaufene Bestätigungsfristen gelten weiterhin. Die Rückkehr zu einem begrenzten Modus ist nur mit ausreichenden Kontingenten möglich. Anzeige und Assistent zeigen keine fiktiven freien Plätze an. In der Datenbank bleiben die bisherigen Zahlenfelder zur Kompatibilität erhalten; sie werden im Modus Ohne Limit nicht als Begrenzung verwendet.

Die Raumbuchungsliste öffnet das Entscheidungsmenü als natives Popover in der obersten Darstellungsebene. Es enthält zwei Buttons (Genehmigen, Ablehnen), verschiebt keine Tabellenzeile und schließt per Escape oder Außenklick. Vorstandsrechte und Konfliktbestätigung werden weiterhin serverseitig geprüft. Die optionale Ablehnungsbegründung bleibt auf der Detailseite verfügbar.

Kontakt/zusätzliche Angaben ist kein Pflichtfeld mehr. Raumbuchungen und wöchentliche Serien dürfen auch in der Vergangenheit liegen und regulär genehmigt werden. Das Ende muss weiterhin nach dem Beginn liegen, mehrdeutige oder nicht existierende lokale Uhrzeiten bleiben unzulässig. Alle übrigen Genehmigungs-, Änderungs- und Konfliktregeln bleiben erhalten.

Migrationen: map.0016 erweitert die Modusauswahl; rooms.0005 macht Kontakt optional. Bestehende Datensätze und Standardlimits bleiben erhalten.
