"""Escaped HTML alternative and consistent transactional-mail identity."""
from email.utils import parseaddr,formataddr
from html import escape
import re

SENDER_NAME='Anmeldungsverwaltung'

def sender_name():
    from django.conf import settings
    value = settings.MAP_MAIL_SENDER_NAME
    if '\r' in value or '\n' in value: raise ValueError('Ungültiger Absendername.')
    return value
FOOTER='Diese E-Mail wurde automatisch erstellt. Bitte antworte nicht auf diese Nachricht: Dieses Postfach wird nicht gelesen. Bei Fragen wende dich an die Leitenden der Veranstaltung; bei Kontofragen an die Administration.'

def sender_address(value):
    address=parseaddr(value)[1]
    if not address or '\r' in value or '\n' in value:raise ValueError('Ungültige Absenderadresse.')
    return formataddr((sender_name(),address))

def with_footer(message):
    return message.rstrip() if message.rstrip().endswith(FOOTER) else message.rstrip()+'\n\n'+FOOTER

def html_message(message):
    text=with_footer(message)
    content=text[:-len(FOOTER)].rstrip()
    # No user HTML is trusted. Link only explicit HTTP(S) URLs after escaping.
    content=escape(content)
    content=re.sub(r'https?://[^\s<>]+',lambda m:'<a href="'+m.group(0)+'" style="color:#174d68;overflow-wrap:anywhere">'+m.group(0)+'</a>',content)
    return '<!doctype html><html lang="de"><body style="font-family:Arial,sans-serif;color:#213d4b;background:#f2f5f7;padding:24px"><main style="max-width:640px;margin:auto;background:white;padding:28px;border-radius:12px"><p style="font-size:14px;color:#4c6572">'+escape(sender_name())+'</p><div style="white-space:pre-wrap;font-size:16px;line-height:1.65">'+content+'</div><hr style="border:0;border-top:1px solid #d4dfe4;margin:28px 0"><p style="font-size:12px;line-height:1.5;color:#526570">'+escape(FOOTER)+'</p></main></body></html>'
