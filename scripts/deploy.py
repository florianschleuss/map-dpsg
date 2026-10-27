"""Deploy a reviewed source tree; never modify proxy, env, or another stack."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parent.parent

def run(args, capture=False):
    env=dict(os.environ,COMPOSE_FILE='compose.yaml:compose.production.yaml')
    return subprocess.run(['docker','compose']+args,cwd=ROOT,env=env,check=True,text=True,stdout=subprocess.PIPE if capture else None)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    if not (ROOT/'.env').is_file():raise RuntimeError('.env fehlt.')
    run(['config','-q'])
    run(['build','--pull','web','worker','test'])
    run(['--profile','tools','run','--rm','-T','test'])
    run(['up','-d','--wait','db'])
    if args.bootstrap:
        query='exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = current_schema()"'
        if run(['exec','-T','db','sh','-c',query],capture=True).stdout.strip()!='0':raise RuntimeError('Bootstrap verweigert: Datenbank enthält bereits Tabellen.')
    else:
        run(['--profile','tools','run','--rm','-T','init','python','manage.py','check_production'])
        run(['stop','web','worker'])
        from backup import backup
        try:backup(ROOT)
        except Exception:
            run(['start','web','worker'])
            raise RuntimeError('Keine Migration: Sicherung fehlgeschlagen. Bisherige Container wieder gestartet.') from None
    try:
        run(['--profile','tools','run','--rm','-T','init'])
        run(['up','-d','--no-build','--force-recreate','--wait','web','worker'])
    except Exception:
        run(['stop','web','worker'])
        raise RuntimeError('Migration oder Start fehlgeschlagen. App bleibt gestoppt; keine automatische Datenbank-Rücksetzung. Siehe docs/BETRIEB.md.') from None
    run(['ps'])
    if args.bootstrap:print('Installation gestartet; noch keine Produktivfreigabe. Admin anlegen, Versand und Betreiberangaben konfigurieren, check_production und Probeanmeldung durchführen.')
    else:run(['--profile','tools','run','--rm','-T','init','python','manage.py','check','--deploy'])

if __name__=='__main__':
    try:main()
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
