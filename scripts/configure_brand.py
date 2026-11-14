"""Configure a public header short name without changing the legal operator name."""
import argparse,json,os,re,tempfile,uuid
from pathlib import Path
from apply_release import discover,compose


def replace_env(path,data):
    mode=path.stat().st_mode & 0o777
    fd,name=tempfile.mkstemp(prefix='.env.brand-',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data)
        temporary.chmod(mode);os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def configure(root,name):
    root=Path(root).absolute();env=root/'.env';name=name.strip()
    if not name or len(name)>160 or any(ord(c)<32 or c=='$' for c in name):
        raise RuntimeError('Bitte einen gültigen Kurznamen ohne Steuerzeichen oder Dollarzeichen angeben.')
    if root.resolve()!=root or 'dev' in root.parts or env.is_symlink() or not env.is_file():
        raise RuntimeError('Ungültiger Produktionspfad oder unsichere .env-Datei.')
    previous=env.read_bytes()
    pattern=rb'(?m)^[ \t]*(?:export[ \t]+)?MAP_BRAND_ORGANIZATION[ \t]*=[^\r\n]*(?:\r?\n|$)'
    updated=re.sub(pattern,b'',previous).rstrip(b'\r\n')+b'\nMAP_BRAND_ORGANIZATION='+json.dumps(name,ensure_ascii=False).encode()+b'\n'
    if updated==previous:return
    project,files,*_=discover(root)
    backups=root/'backups'
    if backups.is_symlink() or not backups.resolve().is_relative_to(root):raise RuntimeError('Unsicherer Sicherungspfad.')
    backups.mkdir(mode=0o700,exist_ok=True)
    backup=backups/('brand-env-'+uuid.uuid4().hex+'.env')
    fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(previous)
    args=['up','-d','--no-build','--no-deps','--force-recreate','--wait','web']
    replace_env(env,updated)
    try:compose(root,files,project,args)
    except Exception:
        replace_env(env,previous);compose(root,files,project,args);raise
    print('Anzeigename im Kopfbereich gespeichert. Sicherung: '+str(backup))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--name',required=True);args=parser.parse_args()
    if not hasattr(os,'geteuid') or os.geteuid()!=0:raise RuntimeError('Auf dem Linux-Server als root ausführen.')
    root=Path(args.root).absolute()
    if root.resolve()!=root or 'dev' in root.parts or not (root/'.env').is_file():raise RuntimeError('Ungültiger Prod-Pfad.')
    import fcntl
    fd=os.open(root/'.release-update.lock',os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    with os.fdopen(fd,'w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Für diese Installation läuft bereits ein Update.') from None
        configure(root,args.name)

if __name__=='__main__':main()
