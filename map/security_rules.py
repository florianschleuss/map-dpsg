"""Pure rules for proxy boundaries, bounded values and security validation."""
from ipaddress import ip_address,ip_network

def client_ip(peer,forwarded='',trusted_networks=()):
    try:remote=ip_address(peer)
    except (TypeError,ValueError):return 'unknown'
    networks=[]
    for value in trusted_networks:
        try:networks.append(ip_network(value,strict=False))
        except ValueError:continue
    trusted=lambda address:any(address in network for network in networks)
    if not trusted(remote) or not forwarded:return str(remote)
    if len(forwarded)>1024:return str(remote)
    values=forwarded.split(',')
    if len(values)>10:return str(remote)
    try:chain=[ip_address(value.strip()) for value in values]
    except ValueError:return str(remote)
    for address in reversed(chain):
        if not trusted(address):return str(address)
    return str(chain[0]) if chain else str(remote)

def bounded_confirmation_hours(value):
    try:return min(8760,max(1,int(value)))
    except (TypeError,ValueError,OverflowError):return 48

def numeric_pk(value):
    text=str(value)
    if not text.isascii() or not text.isdigit() or len(text)>19:return None
    number=int(text)
    return number if 0<number<=9223372036854775807 else None

def normalized_login(value):
    import unicodedata
    return unicodedata.normalize('NFKC',str(value)[:1024]).strip().casefold()[:150]
