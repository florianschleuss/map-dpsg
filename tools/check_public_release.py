"""Catch accidentally included private artifacts without printing their contents."""
from pathlib import Path
import ast, re, subprocess
root=Path(__file__).resolve().parent.parent
errors=[]
try:
    result=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,check=True)
    tracked=[p for p in result.stdout.decode().split('\0') if p]
except (OSError,subprocess.CalledProcessError): tracked=[]
for name in tracked:
    p=Path(name)
    if p.name=='.env' or (p.name.startswith('.env.') and p.name!='.env.example') or p.suffix in ['.dump','.sqlite3','.sql'] or 'operator-assets' in p.parts and p.name!='.gitkeep': errors.append('Private Datei versioniert: '+name)
for p in root.rglob('*'):
    if not p.is_file() or any(x in p.parts for x in ['.git','__pycache__','node_modules','.venv','venv','backups','.rendered','staticfiles','operator-assets','instance']):continue
    if p.name.startswith('.env') and p.name!='.env.example':continue
    relative=p.relative_to(root).as_posix()
    if p.suffix in ['.dump','.sqlite3','.sql','.zip']:errors.append('Nicht für öffentliche Quellen bestimmt: '+relative)
    if p.suffix not in ['.py','.html','.js','.cjs','.md','.yaml','.yml','.txt','.svg']:continue
    text=p.read_text(encoding='utf-8')
    if p.suffix=='.py':ast.parse(text,filename=relative)
    if p.name!=Path(__file__).name and re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):errors.append('Privater Schlüssel gefunden: '+relative)
if errors:raise SystemExit('\n'.join(errors))
print('Quellenprüfung bestanden. Zusätzlich Diff und Git-Historie vor Veröffentlichung prüfen.')
