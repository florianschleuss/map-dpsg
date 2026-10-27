# Abhängigkeiten und Gestaltung

Die Python-Pakete werden beim Image-Build aus dem Paketindex bezogen, nicht als fremder Quellcode in diesem Repository mitgeliefert. Die Versionen sind über requirements.txt und constraints.txt festgelegt. Maßgeblich sind die Lizenzdateien der jeweiligen konkreten Paketversionen, einschließlich ihrer transitiven Abhängigkeiten. Beispiele: Django (BSD), Gunicorn (MIT), PostgreSQL (PostgreSQL License), WhiteNoise (MIT), qrcode (BSD), cryptography (Apache-2.0/BSD), psycopg (LGPL), psycopg-binary mit seinen gebündelten Bibliotheken.

Docker-Basisimages und deren Systempakete besitzen eigene Bedingungen. Vor Weiterverteilung fertiger Images sind deren vollständige Lizenzhinweise zu berücksichtigen. Dieses Dokument behauptet keine abschließende Lizenzprüfung aller Binärbestandteile.

Es werden keine DPSG-, Kirchen- oder Stammeslogos mitgeliefert. Das neutrale Kompasssymbol ist eine einfache eigens erstellte SVG-Grafik. Wer ein eigenes Verbandslogo hinterlegt, muss die dafür geltenden Nutzungsbedingungen selbst beachten.

Die README-Screenshots wurden aus MAP mit fiktiven Beispieldaten erstellt.
