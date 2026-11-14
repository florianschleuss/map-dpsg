# Aufbau des MAP-Kopfbereichs

Die gemeinsame Kopfzeile zeigt MAP als Produktnamen und darunter Modulare Anmelde-Plattform · Stammesname. Das konfigurierte Symbol bleibt erhalten. Die Wortmarke und die zweite Zeile sind für Desktop und Mobil sowie Hell/Dunkel angepasst; dies gilt auch für die native Administration.

MAP_BRAND_ORGANIZATION ist ein optionaler Kurzname ausschließlich für die Kopfzeile. Ist er leer, wird MAP_ORGANIZATION verwendet. Die vollständigen Betreiberangaben, der Mailabsender und die Datenschutzangaben verwenden weiterhin ihre eigenen Einstellungen. In der öffentlichen Konfiguration ist kein Stammesname fest eingebaut. Die isolierten Anwendungstests überschreiben auch den Kurznamen mit einem neutralen Wert.

Zur sicheren Konfiguration auf dem Produktionsserver dient python3 scripts/configure_brand.py --root /opt/map --name 'Stammes-Kurzname'. Das Werkzeug sichert die bisherige .env unter backups, setzt ausschließlich MAP_BRAND_ORGANIZATION und startet den Webdienst mit dem vorhandenen Image neu. Es verwendet dieselbe Update-Sperre wie das Release-Werkzeug. Bei Neustartfehlern wird die ursprüngliche Konfiguration wiederhergestellt. Gespeicherte Zugangsdaten werden nicht ausgegeben.

Keine Datenbankmigration erforderlich. Geprüft wurden Dashboard, Buchungsübersicht, Anmeldung und native Administration bei 360, 390, 768, 1440 und 1920 Pixeln in Hell/Dunkel. Die Konfigurationsprüfungen decken Erhalt bestehender Einstellungen, wiederholte Ausführung, ungültige Eingaben und Wiederherstellung bei Neustartfehlern ab.
