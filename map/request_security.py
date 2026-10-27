"""Only explicitly trusted reverse proxies can supply a client address."""
from functools import lru_cache
import socket
from django.conf import settings
from .security_rules import client_ip,normalized_login

@lru_cache(maxsize=16)
def proxy_addresses(host):
    try:return tuple(sorted({entry[4][0] for entry in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)}))
    except OSError:return ()

def client_address(request):
    networks=list(getattr(settings,'MAP_TRUSTED_PROXY_NETWORKS',[]))
    for host in getattr(settings,'MAP_TRUSTED_PROXY_HOSTS',[]):networks.extend(proxy_addresses(host))
    return client_ip(request.META.get('REMOTE_ADDR',''),request.META.get('HTTP_X_FORWARDED_FOR',''),networks)

def login_allowed(request):
    from .services import throttle
    address=client_address(request)
    username=normalized_login(request.POST.get('username',''))
    # Each dimension is checked even when a previous dimension is blocked.
    allowed=[throttle('login-ip:'+address,limit=60,seconds=900),
             throttle('login-account:'+username,limit=30,seconds=900),
             throttle('login:'+username+':'+address,limit=20,seconds=900)]
    return all(allowed)
