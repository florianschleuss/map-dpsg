# Einheitliche MAP-Seitenhülle

Die Kopfzeile, das Profil, die Modulnavigation, Breadcrumbs und der Footer verwenden ein gemeinsames Inhaltsraster. Der Inhalt ist bis 1132 Pixel breit; Seitenabstände sind am Handy 16 und sonst 24 Pixel. Formulare bleiben innerhalb dieses Rasters. Die Seitenhülle verändert sich nicht mehr durch die bisherige map-layout-wide-Klasse.

Ausschließlich die Buchungstabelle (auch offene Genehmigungen) und der Monats-/Wochenkalender der Raumbuchung spannen als room-data-wide über die volle verfügbare Inhaltsfläche abzüglich der Seitenabstände. Filter, Überschriften, Raumreiter, Exportaktionen und Formulare bleiben im normalen Raster. Auf kleinen Bildschirmen scrollen die breiten Datenflächen innerhalb ihres Containers, nicht die ganze Seite.

## Gemeinsame Gestaltung

Die verantwortlichen Regeln stehen in static/map/layout.css und werden in MAP sowie in der nativen Django-Verwaltung nach den Farben geladen. Alte Regeln für dieselbe Seitenhülle wurden aus den bisherigen Stylesheets entfernt. Die aktive Tabfarbe ist das Grün #47795C aus dem Regenbogenbanner; die Schrift ist weiß, auch im Dunkelmodus und in der Stufenverwaltung. Alle Kalender-Navigationsbuttons sind gleich hoch.

Raumreiter beginnen bei Übersicht, Kalender, Genehmigungen, Gruppenstunden und neuer Anfrage auf derselben Höhe. Der Kalender bleibt innerhalb seiner Datenfläche kompakt. Die neue Anfrage besitzt eine gleich hohe Rücksprungaktion statt einer verschwindenden Kopfaktion. Einstellungsreiter erhalten dieselbe Darstellung und einen aktiven Zustand. Ein aktiver Reiter außerhalb des sichtbaren mobilen Ausschnitts wird ohne Verschieben der gesamten Seite in die Leiste gescrollt.

Der Footer ist durchgehend breit; seine Texte bleiben im Inhaltsraster. Breadcrumbs verwenden dieselben Containerkanten, keine abweichende 100vw-Berechnung. Lange Überschriften können innerhalb schmaler Geräte umbrechen. Zugehörige Kopfaktionen schrumpfen nicht mehr auf mehrzeilige Schaltflächen.

## Ruhige Initialisierung und Datumsauswahl

Die richtige Anfangsdarstellung für Filter, Wiederholungsfelder, Kostenfelder und Datumsbedienelemente ist bereits vor der sichtbaren JavaScript-Initialisierung berücksichtigt. Ohne JavaScript bleiben die nativen Formularfelder verwendbar. Falls das Kalender-Skript nicht geladen wird, wird die frühzeitige Erweiterungsklasse wieder entfernt.

Die Datumsauswahl wird innerhalb des sichtbaren Browserbereichs positioniert. Sie öffnet bei fehlendem Platz oberhalb oder begrenzt ihre Höhe. Fensteränderungen und Scrollen aktualisieren die Position. Monatswechsel halten das Popup offen und erhalten den Tastaturfokus; Escape schließt es.

## Regressionstests

Die normale Django-/PostgreSQL-Suite prüft weiterhin die Anwendungsfunktionen. Zusätzlich können isolierte Browserfixtures und Geometrieprüfungen ausgeführt werden. Voraussetzungen sind die Projekt-Pythonabhängigkeiten, Node.js und Playwright mit einem installierten Testbrowser.

Vom Projektverzeichnis aus:

    python tools/render_layout_fixtures.py
    node tools/check_ui_layout.cjs

Der Fixture-Generator erzwingt SQLite im Arbeitsspeicher und verwendet ausschließlich erfundene Testdaten. Er schreibt nur nach docs/.rendered/layout. Er liest keine Produktionsdatenbank und sendet keine E-Mails. Im normalen Docker-Compose-Test wird dieser optionale Browserlauf nicht automatisch gestartet.

Optionale Umgebungsvariablen: MAP_BROWSER_TYPE (chromium oder webkit), MAP_BROWSER_EXECUTABLE, MAP_PLAYWRIGHT_MODULE, MAP_LAYOUT_SOURCE, MAP_LAYOUT_FIXTURES, MAP_DJANGO_ADMIN_STATIC, MAP_LAYOUT_PAGES und MAP_LAYOUT_WIDTHS. Die letzten beiden sind kommagetrennte Teilmengen. Standardmäßig werden 41 Ansichten in Hell und Dunkel bei 360, 390, 768, 1280, 1440 und 1920 Pixeln geprüft. Die Prüfungen kontrollieren tatsächliche Geometrie, aktive Tabs, volle Breite nur für Raumdaten, Ladeverschiebungen, Filterzustände, Navigation und Datumspopups. Ergebnisdateien liegen neben den Fixtures und gehören nicht ins öffentliche Repository.

## Deployment

Keine Datenbankmigration und keine neue Betreiberkonfiguration nötig. Das bekannte Produktionsupdate erhält Zugangsdaten und vorhandene Buchungen. Nach erfolgreichem Update die Seite neu laden, damit die neuen Styles geladen werden.
