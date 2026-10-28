"""Apply an immutable, reviewed release to an existing production stack.

Run this script from a verified release archive, never from the target directory.
It does not edit .env, proxy configuration, operator assets or application records.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime,timezone

SOURCE=Path(__file__).resolve().parent.parent


def command(args,cwd,**kwargs):
    return subprocess.run(args,cwd=cwd,check=True,**kwargs)


def docker_json(args,cwd):
    return json.loads(command(['docker',*args],cwd,text=True,stdout=subprocess.PIPE).stdout)


def compose(root,files,project,args,**kwargs):
    return command(['docker','compose','--project-name',project,*[part for f in files for part in ['-f',f]],*args],root,**kwargs)


def discover(root):
    ids=command(['docker','ps','-aq'],root,text=True,stdout=subprocess.PIPE).stdout.split()
    records=docker_json(['inspect',*ids],root) if ids else []
    stack=[r for r in records if (r.get('Config',{}).get('Labels') or {}).get('com.docker.compose.project.working_dir')==str(root) and r.get('State',{}).get('Running',True)]
    services={}
    for record in stack:
        labels=record['Config']['Labels'];name=labels.get('com.docker.compose.service')
        if name in ['web','worker','db']:
            if name in services:raise RuntimeError('Mehrere Instanzen eines Dienstes gefunden; zuerst die Deployment-Auswahl klären.')
            services[name]=record
    if set(services)!=set(['web','worker','db']):raise RuntimeError('Laufende Prod-Dienste web, worker und db konnten nicht eindeutig zugeordnet werden.')
    projects={r['Config']['Labels']['com.docker.compose.project'] for r in services.values()}
    if len(projects)!=1:raise RuntimeError('Uneindeutiges Compose-Projekt. Nichts geändert.')
    project=projects.pop();raw=services['web']['Config']['Labels'].get('com.docker.compose.project.config_files','')
    files=[]
    for name in raw.split(','):
        path=Path(name)
        if not path.is_absolute():path=root/path
        if path.resolve().parent!=root or not path.is_file():raise RuntimeError('Compose-Konfigurationspfad ist nicht eindeutig innerhalb der Prod-Installation.')
        files.append(path.name)
    if not files:raise RuntimeError('Die laufende Compose-Auswahl fehlt.')
    config=json.loads(compose(root,files,project,['config','--format','json'],text=True,stdout=subprocess.PIPE).stdout)
    env=config['services']['web'].get('environment',{})
    if str(env.get('MAP_PRODUCTION','0')).lower() not in ['1','true'] or str(env.get('DEBUG','1')).lower() not in ['0','false']:
        raise RuntimeError('Keine abgesicherte Produktionskonfiguration erkannt. Nichts geändert.')
    images={config['services'][service].get('image') for service in ['web','worker','init']}
    if len(images)!=1 or None in images:raise RuntimeError('Prod benötigt einen gemeinsamen expliziten Image-Tag für web, worker und init.')
    image=images.pop()
    if any(services[service]['Config']['Image']!=image for service in ['web','worker']):raise RuntimeError('Die konfigurierte Image-Auswahl weicht vom laufenden Stack ab. Nichts geändert.')
    for record in records:
        if (record.get('Config',{}).get('Labels') or {}).get('com.docker.compose.project.working_dir')!=str(root) and record.get('Config',{}).get('Image')==image:
            raise RuntimeError('Der Prod-Image-Tag wird von einem anderen Stack verwendet. Nichts geändert.')
    return project,files,config,services,image


def read_sources(source,manifest):
    values={}
    for name in manifest['paths']:
        path=source/name
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):raise RuntimeError('Ungültige Release-Datei: '+name)
        if name in manifest.get('remove',[]):values[name]=None;continue
        if not path.is_file():raise RuntimeError('Release-Datei fehlt: '+name)
        values[name]=path.read_bytes()
    return values


def preflight(root,values,manifest):
    old={};mismatches=[]
    for name,new in values.items():
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise RuntimeError('Unsicherer Zielpfad: '+name)
        data=path.read_bytes() if path.is_file() else None
        old[name]=data
        if data==new:continue
        # Text snapshots normalize line endings just as Python read_text on the server.
        digest=hashlib.sha256(data).hexdigest() if data is not None else None
        allowed=manifest['paths'][name]
        if digest not in allowed:
            try:normalized=data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode() if data is not None else None
            except UnicodeDecodeError:normalized=data
            if (hashlib.sha256(normalized).hexdigest() if normalized is not None else None) not in allowed:mismatches.append(name)
    if mismatches:raise RuntimeError('Abweichender Prod-Quellstand. Nichts geändert:\n- '+'\n- '.join(mismatches)+'\nBitte die gesamte Liste weitergeben; keine Prüfungen umgehen.')
    return old


def write_files(root,values):
    for name,data in values.items():
        path=root/name
        if data is None:
            if path.exists():path.unlink()
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            mode=(path.stat().st_mode & 0o777) if path.exists() else (0o755 if path.suffix=='.sh' else 0o644)
            fd,name=tempfile.mkstemp(prefix='.map-release-',dir=path.parent)
            temporary=Path(name)
            try:
                with os.fdopen(fd,'wb') as stream:stream.write(data)
                temporary.chmod(mode);os.replace(temporary,path)
            finally:
                if temporary.exists():temporary.unlink()


def apply(root,source):
    if not hasattr(os,'geteuid') or os.geteuid()!=0:raise RuntimeError('Auf dem Linux-Server als root ausführen.')
    root=Path(root).absolute()
    if root.resolve()!=root or 'dev' in root.parts or root==source.resolve():raise RuntimeError('Ungültiger oder nicht produktiver Zielpfad.')
    if not (root/'.env').is_file():raise RuntimeError('Prod-.env fehlt.')
    if (source/'.env').exists() or (source/'.env').is_symlink():raise RuntimeError('Das separate Release-Verzeichnis darf noch keine .env enthalten.')
    manifest=json.loads((source/'deploy/release-baselines.json').read_text(encoding='utf-8'))
    values=read_sources(source,manifest)
    old=preflight(root,values,manifest)
    project,files,config,services,image=discover(root)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    check_project='map-release-check-'+stamp.lower()
    old_images={r['Config']['Image']:r['Image'] for s,r in services.items() if s in ['web','worker']}
    for index,image_id in enumerate(set(old_images.values())):
        command(['docker','image','tag',image_id,'map-production-rollback:'+stamp.lower()+'-'+str(index)],root)
    stopped=False;written=False;migrating=False;backup=None;env_created=False;production_files=files;override_file=None
    try:
        # Build and test the downloaded source without replacing live source or stopping Prod.
        fd=os.open(source/'.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);env_created=True
        with os.fdopen(fd,'wb') as stream:stream.write((root/'.env').read_bytes())
        candidate=json.loads(compose(source,['compose.yaml'],check_project,['config','--format','json'],text=True,stdout=subprocess.PIPE).stdout)
        test=candidate['services']['test'].get('environment',{})
        if test.get('POSTGRES_HOST')!='test-db' or test.get('EMAIL_BACKEND')!='django.core.mail.backends.locmem.EmailBackend':raise RuntimeError('Testdatenbank oder Mail-Isolierung ist nicht gewährleistet.')
        if set(candidate['services']['test'].get('depends_on',{}))!={'test-db'} or candidate['services']['test-db'].get('volumes') or candidate['services']['test-db'].get('ports'):
            raise RuntimeError('Der Testdienst ist nicht auf eine eigene kurzlebige Datenbank begrenzt.')
        if candidate.get('networks',{}).get('default',{}).get('name')!=check_project+'_default':raise RuntimeError('Das Testnetzwerk ist nicht eindeutig isoliert.')
        if candidate['services']['web'].get('image')!=image:raise RuntimeError('Image-Auswahl des Releases passt nicht zum laufenden Prod-Stack.')
        compose(source,['compose.yaml'],check_project,['build','web','worker','init','test'])
        compose(source,['compose.yaml'],check_project,['--profile','tools','run','--rm','-T','-e','MAP_PRODUCTION=0','test'])
        if (root/'operator-assets').is_dir():
            override_file=source/('.map-production-check-'+stamp+'.json')
            override={'services':{'init':{'volumes':[{'type':'bind','source':str(root/'operator-assets'),'target':'/app/operator-assets','read_only':True}]}}}
            with override_file.open('x',encoding='utf-8') as stream:json.dump(override,stream)
            production_files=files+[str(override_file)]
        compose(root,production_files,project,['--profile','tools','run','--rm','-T','init','python','manage.py','check_production'])
        # Abort rather than overwrite an operator edit made during the build.
        if preflight(root,values,manifest)!=old:raise RuntimeError('Prod-Dateien wurden während der Prüfung geändert. Nichts überschrieben.')
        backup_root=root/'backups'
        if backup_root.is_symlink() or not backup_root.resolve().is_relative_to(root):raise RuntimeError('Unsicherer Sicherungspfad.')
        backup=backup_root/('release-'+stamp);backup.mkdir(parents=True,mode=0o700)
        (backup/'.env').write_bytes((root/'.env').read_bytes());(backup/'.env').chmod(0o600)
        for name,data in old.items():
            if data is not None:
                path=backup/'sources'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(0o600)
        (backup/'images.json').write_text(json.dumps(old_images),encoding='utf-8');(backup/'images.json').chmod(0o600)
        stopped=True
        print('Prüfungen bestanden. Prod-Web und Worker werden für Sicherung und Migration angehalten.',flush=True)
        compose(root,files,project,['stop','web','worker'])
        dump=backup/'database.dump'
        with dump.open('wb') as output:
            dump.chmod(0o600)
            compose(root,files,project,['exec','-T','db','sh','-c','exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom'],stdout=output)
        if dump.stat().st_size<10:raise RuntimeError('Datenbanksicherung ist leer.')
        with dump.open('rb') as stream:compose(root,files,project,['exec','-T','db','pg_restore','--list'],stdin=stream,stdout=subprocess.DEVNULL)
        written=True;write_files(root,values)
        migrating=True
        compose(root,production_files,project,['--profile','tools','run','--rm','-T','init','python','manage.py','migrate','--noinput'])
        compose(root,production_files,project,['--profile','tools','run','--rm','-T','init','python','manage.py','check_production'])
        compose(root,production_files,project,['--profile','tools','run','--rm','-T','init','python','manage.py','check','--deploy'])
        compose(root,files,project,['up','-d','--no-build','--force-recreate','--wait','web','worker'])
        compose(root,files,project,['ps'])
    except Exception:
        # Never restore a database automatically after a failed rollout.
        if stopped:
            try:compose(root,files,project,['stop','web','worker'])
            except Exception:pass
        if written:write_files(root,old)
        for tag,image_id in old_images.items():command(['docker','image','tag',image_id,tag],root)
        if stopped:compose(root,files,project,['up','-d','--no-build','--force-recreate','--wait','web','worker'])
        print('Release abgebrochen. Bisherige Quellen/Images wiederhergestellt; vorhandene Daten nicht zurückgesetzt.',file=sys.stderr)
        if migrating:print('Bereits erfolgreiche Datenbankmigrationen bleiben bestehen. Sicherung: '+str(backup),file=sys.stderr)
        raise
    finally:
        try:compose(source,['compose.yaml'],check_project,['--profile','tools','down','-v'])
        except Exception:print('Isolierten Test-Stack bei Bedarf bereinigen: '+check_project,file=sys.stderr)
        env_file=source/'.env'
        if env_created and env_file.exists():env_file.unlink()
        if override_file is not None and override_file.exists():override_file.unlink()
    print('Prod-Release abgeschlossen. Sicherung: '+str(backup))
    print('Keine Dev-Daten übernommen. Microsoft-Anmeldung, Vorstand-Zuordnung und API-Aktivierung in Prod prüfen.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args()
    import fcntl
    root=Path(args.root).absolute()
    if root.resolve()!=root or 'dev' in root.parts or not (root/'.env').is_file():raise RuntimeError('Ungültiger Prod-Pfad.')
    fd=os.open(root/'.release-update.lock',os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Für diese Installation läuft bereits ein Release-Update.') from None
        apply(root,SOURCE)

if __name__=='__main__':
    try:main()
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
