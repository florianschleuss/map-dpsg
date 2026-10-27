"""Verify dependency floors in the freshly built test image; no network calls."""
from importlib.metadata import version
import re

REQUIRED={'Django':((5,2,18),(5,3,0)),'gunicorn':((26,2,0),(27,0,0)),'cryptography':((50,0,0),(51,0,0))}
for package,(minimum,maximum) in REQUIRED.items():
    text=version(package)
    match=re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?',text)
    if not match:raise SystemExit('Nicht auswertbare Paketversion: '+package)
    current=tuple(int(value or 0) for value in match.groups())
    if not minimum<=current<maximum:raise SystemExit('Nicht unterstÃ¼tzte Paketversion: '+package+' '+text)
    print(package+': '+text+' â€“ Versionsgrenze erfÃ¼llt')
