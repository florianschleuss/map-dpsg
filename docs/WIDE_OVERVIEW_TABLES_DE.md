# Breitere und lesbarere Übersichten

Datenreiche Übersichten verwenden einen eigenen Layoutmodus bis 1.800 Pixel statt der bisherigen gemeinsamen Begrenzung auf 1.180 Pixel. Betroffen sind Buchungsübersicht, offene Raumanfragen, Raumkalender, Veranstaltungs-Anmeldungsübersicht, Benutzerliste und Mail-Warteschlange. Kopfzeile, Navigationspfad und Fußbereich passen sich an. Andere Seiten behalten ihr bisheriges Layout.

Die Buchungstabelle verwendet größere Schrift und ausgewogene Spaltenbreiten. Veranstaltungstitel erhalten den größten Anteil. Lange Inhalte können umbrechen; Status und Aktionen bleiben erreichbar. Abwechselnde Zeilenhintergründe und eine Hover-Markierung unterstützen die Zuordnung innerhalb einer Zeile. Die Tabellen bleiben auf Mobilgeräten innerhalb ihres eigenen Containers seitlich verschiebbar. Die Buchungstabelle ist für Tastaturbedienung fokussierbar. Die bestehenden Entscheidungs-Overlays bleiben in der obersten Darstellungsebene.

Keine Datenbankmigration, keine Änderungen an Buchungen, Filtern oder Berechtigungen. Browserprüfung mit echten Django-Seiten und erfundenen Beispieldaten bei 390, 1280, 1440, 1920 und 2560 Pixeln in Hell/Dunkel. Geprüft werden Seitenbreite, abgeschnittene Zellen, lange Namen/Texte, horizontales Scrollen und Entscheidungsmenüs.
