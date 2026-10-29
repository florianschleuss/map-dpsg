# Wöchentliche Raumbuchungen

Der Schalter steht standardmäßig auf Einmalig. Wiederkehrend bucht einen Wochentag mit Beginn und Ende am selben Tag. Start- und Enddatum begrenzen die Serie einschließlich; gespeichert werden der erste und letzte tatsächlich passende Termin. Die maximale Serienlänge beträgt 520 Wochen. Ganztägig bleibt bei Einmalbuchungen verfügbar.

Eine Anfrage und eine Genehmigung gelten für die ganze Serie. Bearbeiten und Stornieren betreffen die gesamte Serie; einzelne Ausnahmen werden derzeit nicht unterstützt. Genehmigte Serien bleiben bis zur Genehmigung einer geänderten Fassung unverändert gültig. Kontaktänderungen werden wie bisher sofort übernommen.

Konflikte, Kalender, Zeitraumfilter und öffentliche API berücksichtigen nur tatsächliche Wochentermine. Die lokale Uhrzeit bleibt bei Sommer-/Winterzeit konstant. Nicht existierende oder doppeldeutige Uhrzeiten werden mit einer deutschen Fehlermeldung abgelehnt.

Excel zeigt die Serie als lesbaren Zeitraum. iCal enthält einzelne Termine mit stabilen Kennungen und korrekten UTC-Zeiten, damit alle Kalenderprogramme die Zeitumstellung korrekt abbilden.

Die Tabellenzeile öffnet Details. Der Stift öffnet die Bearbeitung. Das Entscheidungsmenü ist ausschließlich für den Vorstand bei offenen Buchungen/Änderungen verfügbar und sendet geschützte POST-Anfragen. Bei bestehenden genehmigten Konflikten ist die zusätzliche Bestätigung auf der Detailseite erforderlich. Alle bisherigen Rollen- und Versionsprüfungen bleiben aktiv.

Datenmigration 0004 ergänzt ausschließlich recurring=False an bestehenden Buchungen und Änderungsanträgen. Bestehende Buchungen bleiben Einmaltermine.
