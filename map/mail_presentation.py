"""Escaped HTML alternative and consistent transactional-mail identity."""
from email.utils import parseaddr,formataddr
from html import escape
import re
from urllib.parse import urlsplit

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
    """Use structural HTML breaks; mail clients may discard white-space CSS."""
    text=with_footer(message).replace('\r\n','\n').replace('\r','\n')
    content=text[:-len(FOOTER)].rstrip()
    def linked_line(line):
        parts=[];position=0
        for match in re.finditer(r"https?://[^\s<>\"']+",line):
            if match.end()<len(line) and line[match.end()] in "\"'":
                continue
            url=match.group(0)
            parts.append(escape(line[position:match.start()]))
            safe=escape(url,quote=True)
            try:path=urlsplit(url).path
            except ValueError:path=''
            label=('E-Mail-Adresse bestätigen' if path.startswith('/confirm/') else 'Anmeldung öffnen und verwalten' if path.startswith('/manage/') else 'Neues Passwort festlegen' if '/passwort/' in path or '/reset/' in path else 'Link öffnen')
            parts.append('<a href="'+safe+'" style="color:#174d68;text-decoration:underline;word-break:break-all;overflow-wrap:anywhere">'+label+'</a>')
            position=match.end()
        parts.append(escape(line[position:]))
        return ''.join(parts)
    paragraphs=[]
    for paragraph in re.split(r'\n{2,}',content):
        if paragraph:
            paragraphs.append('<p style="margin:0 0 18px;font-size:16px;line-height:26px;mso-line-height-rule:at-least;color:#213d4b">'+'<br>'.join(linked_line(line) for line in paragraph.split('\n'))+'</p>')
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background-color:#f2f5f7;font-family:Arial,sans-serif">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#f2f5f7"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#ffffff" style="max-width:640px;background-color:#ffffff"><tr><td style="padding:28px;font-family:Arial,sans-serif;color:#213d4b">'
        '<p style="margin:0 0 24px;font-size:14px;line-height:21px;color:#4c6572">'+escape(sender_name())+'</p>'
        +''.join(paragraphs)+
        '<hr style="border:0;border-top:1px solid #d4dfe4;margin:28px 0">'
        '<p style="margin:0;font-size:12px;line-height:18px;color:#526570">'+escape(FOOTER)+'</p>'
        '</td></tr></table></td></tr></table></body></html>')
