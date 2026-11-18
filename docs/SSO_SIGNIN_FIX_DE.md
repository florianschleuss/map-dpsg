# Microsoft-Anmeldung: gemeinsame Netze und iPhones

Das bisherige Limit von 60 Starts pro IP in 15 Minuten konnte gemeinsame WLANs oder einen als Client erkannten Proxy sperren. Neue Zähler: 20 Starts pro Browsersitzung in 5 Minuten, zusätzlich 600 Starts pro IP in 15 Minuten. Gesperrte Browser erhöhen den Netzwerkwert nicht weiter. Die alten SSO-Zähler werden nicht mehr ausgewertet; andere Anmeldeschutzfunktionen bleiben unverändert. Die Antwort enthält eine deutsche Wartezeit und Retry-After. Das sind konservative volle Zeitfenster, keine sekundengenaue Restzeit.

Die Content-Security-Policy erlaubt auf den lokalen Anmeldeseiten und SSO-Einstiegsseiten zusätzlich ausschließlich https://login.microsoftonline.com als Formularziel. Manche Browser prüfen auch Weiterleitungen nach Formularen gegen diese Regel. Andere Seiten behalten form-action self. CSRF, Tenantbindung, PKCE, Nonce, State und sichere next-Weiterleitungen bleiben bestehen.

Der Ablauf bleibt eine Navigation im selben Fenster mit GET-Callback. Er benötigt weder Popup noch Drittanbieter-Cookies. SameSite=Lax bleibt erhalten; insbesondere nicht ohne Abstimmung auf Strict umstellen. Eingebettete Browser in Teams oder Outlook können sich von Safari unterscheiden. Bei Problemen den Link in Safari öffnen.

## Proxy-Konfiguration

MAP_TRUSTED_PROXY_HOSTS muss den tatsächlichen DNS-Namen/Alias des Caddy-Containers enthalten, z.B. caddy oder dpsg-caddy. Bestehende Einstellungen werden nicht ungeprüft überschrieben. Niemals pauschal alle IP-Netze vertrauen. Nur wenn der direkte Peer explizit vertraut wird, wird X-Forwarded-For ausgewertet. Die bisherigen Proxy-Vertrauensgrenzen bleiben erhalten. Auch bei einer fehlenden Zuordnung gilt nun das großzügigere Netzwerklimit.

## Prüfung nach Installation

Mit zwei bislang nicht angemeldeten Personen im selben WLAN testen. Auf einem iPhone die Seite in Safari öffnen, Microsoft-Anmeldung starten, Konto wählen und nach Rückkehr den freigegebenen MAP-Zugang bzw. die Freigabeseite prüfen. Danach einen Veranstaltungs-/Raumbuchungslink mit next testen. Tenant- und Gerätesicherheitsrichtlinien bei Microsoft können weiterhin Einfluss haben.

Die automatisierten Tests simulieren Microsoft. Sie prüfen keine realen Tenant-Richtlinien oder tatsächlichen iPhone-Geräte.
