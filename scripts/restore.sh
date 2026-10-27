#!/bin/sh
# Restore to a separately initialized empty test installation, never in-place.
set -eu
cd "$(dirname "$0")/.."
printf '%s\n' 'Wiederherstellung ist absichtlich kein Ein-Klick-Befehl. Siehe docs/BETRIEB.md: getrennten Restore-Stack anlegen und passendes SECRET_KEY übernehmen.' >&2
exit 1
