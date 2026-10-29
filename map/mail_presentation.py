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

MAIL_SCHEMES={
    'blue':dict(background='#f2f5f7',text='#213d4b',link='#174d68',muted='#4c6572',footer='#526570',border='#d4dfe4'),
    'mono':dict(background='#eeeeee',text='#202020',link='#111111',muted='#444444',footer='#555555',border='#cccccc'),
    'rainbow':dict(background='#faf8f3',text='#262626',link='#215570',muted='#4a4a4a',footer='#555555',border='#ddd5c7'),
}

def configured_color_scheme():
    from .models import MailConfiguration
    return MailConfiguration.objects.filter(pk=1).values_list('mail_color_scheme',flat=True).first() or 'blue'

def html_message(message,scheme='blue'):
    """Use structural HTML breaks; mail clients may discard white-space CSS."""
    scheme=scheme if scheme in MAIL_SCHEMES else 'blue'
    palette=MAIL_SCHEMES[scheme]
    stripe=''
    if scheme=='rainbow':
        colors=['#c94a42','#e78d2b','#e6be47','#477c5b','#256d94','#8a5884']
        stripe='<tr aria-hidden="true"><td style="padding:0"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'+''.join('<td width="16.66%" height="10" bgcolor="'+color+'" style="background-color:'+color+';font-size:0;line-height:0">&#160;</td>' for color in colors)+'</tr></table></td></tr>'
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
            parts.append('<a href="'+safe+'" style="color:'+palette['link']+';text-decoration:underline;word-break:break-all;overflow-wrap:anywhere">'+label+'</a>')
            position=match.end()
        parts.append(escape(line[position:]))
        return ''.join(parts)
    paragraphs=[]
    for paragraph in re.split(r'\n{2,}',content):
        if paragraph:
            paragraphs.append('<p style="margin:0 0 18px;font-size:16px;line-height:26px;mso-line-height-rule:at-least;color:'+palette['text']+'">'+'<br>'.join(linked_line(line) for line in paragraph.split('\n'))+'</p>')
    result=('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body data-mail-scheme="'+scheme+'" style="margin:0;padding:0;background-color:'+palette['background']+';font-family:Arial,sans-serif">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="'+palette['background']+'"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#ffffff" style="max-width:640px;background-color:#ffffff">'+stripe+'<tr><td style="padding:28px;font-family:Arial,sans-serif;color:'+palette['text']+'">'
        '<p style="margin:0 0 24px;font-size:14px;line-height:21px;color:'+palette['muted']+'">'+escape(sender_name())+'</p>'
        +''.join(paragraphs)+
        '<hr style="border:0;border-top:1px solid '+palette['border']+';margin:28px 0">'
        '<p style="margin:0;font-size:12px;line-height:18px;color:'+palette['footer']+'">'+escape(FOOTER)+'</p>'
        '</td></tr></table></td></tr></table></body></html>')
    return result
