"""Protected consistent dump plus the matching local configuration."""
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import shutil
import subprocess

def backup(root):
    root=Path(root);folder=root/'backups';folder.mkdir(mode=0o700,exist_ok=True)
    env=dict(os.environ,COMPOSE_FILE='compose.yaml:compose.production.yaml')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3)
    dump=folder/('map-'+stamp+'.dump');partial=dump.with_suffix('.partial');config=dump.with_suffix('.env')
    fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        subprocess.run(['docker','compose','exec','-T','db','sh','-c','exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'],cwd=root,env=env,check=True,stdout=stream)
    if partial.stat().st_size==0:raise RuntimeError('Leere Sicherung.')
    with partial.open('rb') as stream:
        subprocess.run(['docker','compose','exec','-T','db','pg_restore','--list'],cwd=root,env=env,check=True,stdin=stream,stdout=subprocess.DEVNULL)
    fd=os.open(config,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as target,(root/'.env').open('rb') as source:shutil.copyfileobj(source,target)
    partial.rename(dump)
    print('Sicherung erstellt: '+str(dump)+' (enthält persönliche Daten; extern geschützt sichern).')
    return dump

if __name__=='__main__':backup(Path(__file__).resolve().parent.parent)
