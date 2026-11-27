# Gruppenstunden und kompakte Raumnavigation

Unter Raumbuchung gibt es den vierten Reiter Gruppenstunden. Sichtbarkeit und serverseitige Verwaltung verwenden genau die vorhandene Genehmigungsprüfung: aktive Admins, Vorstand oder die Einzel-/Rollenberechtigung rooms.manage_bookings. Normale Anfragende können die Verwaltung weder aufrufen noch über POST verändern. Es werden keine zusätzlichen Rollen oder Rechte vergeben.

## Wochenregeln

Eine Gruppenstunde besteht aus einem Wochentag, Start- und Enduhrzeit am selben Tag, einem oder mehreren Räumen und einer freien Gruppenbezeichnung. Die Regel gilt wöchentlich ohne Datumsbegrenzung, bis sie bearbeitet oder gelöscht wird. Eine Datumsbegrenzung oder Ferienausnahmen sind nicht Teil dieser Version. Eingaben werden validiert, Räume mit Referenzen archiviert und konkurrierende Bearbeitungen über eine Versionsprüfung abgefangen. Das Löschen erfordert eine ausdrückliche Bestätigung. Letzte Änderung und bearbeitende Person werden angezeigt; ein vollständiger Änderungsverlauf ist nicht implementiert.

## Ausschließlich Hinweise

Gruppenstunden sind eigene Datensätze, keine RoomBooking-Einträge. Sie erscheinen weder in Buchungsübersicht, Monats-/Wochenkalender, offenen Genehmigungen noch in Excel/iCal oder der öffentlichen Belegungs-API. Die Anfragenden sehen nur bei einer echten zeitlichen Überschneidung im gleichen Raum einen Hinweis mit Gruppenname, Wochentag, Uhrzeit und betroffenen Räumen. Auch Mehrtages-, ganztägige und wöchentlich wiederkehrende Buchungen werden geprüft. Es gelten lokale Wochenzeiten; direkt anschließende Zeiten überschneiden sich nicht. Jede betroffene Gruppenstunde wird nur einmal genannt.

Hinweise erscheinen bei der Live-Prüfung, Vorschau, den Buchungsdetails und der Konfliktanzahl bestehender Anfragen. Sie verhindern weder das Einreichen noch das Genehmigen und verlangen keine zusätzliche Bestätigung. Echte Konflikte mit bereits genehmigten Buchungen behalten unverändert ihre zusätzliche Bestätigungspflicht. Änderungen der Wochenregeln lösen keine Buchungs- oder E-Mail-Aufträge aus.

## Oberfläche

Modul- und Raumreiter haben einen eigenen Tab-Hintergrund, deutlichen aktiven Zustand und Tastaturfokus. Mobile Raumreiter lassen sich bei Bedarf horizontal verschieben. Filter sind auf dem Handy zunächst zugeklappt; im Kalender gilt das auch am Desktop. Bei Eingabefehlern werden sie geöffnet. Die Buchungsübersicht am Desktop zeigt die Filter weiterhin direkt. Manuell geöffnete/geschlossene Filter bleiben beim Ändern der Fensterbreite in ihrem gewählten Zustand.

Der Kalender verwendet kleinere Tagesfelder, Abstände und eine kompaktere Überschrift. Im Monat wird zunächst ein Eintrag je Tag gezeigt, zusätzliche Einträge bleiben unter + weitere vollständig aufklappbar. In der Wochenansicht werden alle Einträge angezeigt. Der Eintragstitel lautet Zweck - Gruppierung; lange Texte sind im Tooltip und in den Buchungsdetails vollständig erreichbar. Kürzere Zeitangaben ersetzen den wiederholten Datumsbereich, die Details bleiben unverändert.

## Installation und Prüfung

Die additive Migration rooms.0006_groupsession erstellt ausschließlich die neue Wochenregel-Tabelle und ihre Raumzuordnung. Der normale Produktions-Release-Installer führt Tests, Sicherung und Migration aus. Vorhandene Buchungen und Nutzerrechte werden nicht umgeschrieben. Kein neuer Umgebungsparameter erforderlich. Ziel des bereitgestellten Befehls ist /opt/map; Entwicklung bleibt unverändert.

Geprüft sind Rechte, CRUD, CSRF, Versionierung, Zeit-/Raumgrenzen, lokale Wochenzeiten, wiederkehrende und mehrtägige Anfragen, echte genehmigte Konflikte, API-/Export-Abgrenzung sowie Mobil/Desktop und Hell/Dunkel. Reale Nutzerzugänge wurden nicht auf dem Produktionsserver verändert oder getestet.
