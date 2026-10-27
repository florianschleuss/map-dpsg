"""Local readiness probe, preserving the configured public Host header."""
import os
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
host = urlsplit(os.environ.get('PUBLIC_URL', 'http://localhost:8000')).netloc
request = Request('http://127.0.0.1:8000/healthz/', headers={'Host': host, 'X-Forwarded-Proto': 'https' if os.environ.get('HTTPS') == '1' else 'http'})
with urlopen(request, timeout=4) as response:
    if response.status != 200 or response.read(16) != b'ok': raise SystemExit(1)
