"""Create local secrets without installing anything; never overwrite existing .env."""
import os
from pathlib import Path
import secrets
root = Path(__file__).resolve().parent.parent
target = root / '.env'
text = (root / '.env.example').read_text(encoding='utf-8')
text = text.replace('SECRET_KEY=\n', 'SECRET_KEY=' + secrets.token_hex(48) + '\n')
text = text.replace('POSTGRES_PASSWORD=\n', 'POSTGRES_PASSWORD=' + secrets.token_hex(32) + '\n')
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream: stream.write(text)
print('Neue .env angelegt. Betreiberangaben und Domain vor dem Produktivstart konfigurieren.')
