"""Readable identifiers; Microsoft identity keys remain tenant plus object ID."""
import re
import unicodedata
from django.core.exceptions import ValidationError
from django.contrib.auth.validators import UnicodeUsernameValidator

def username_stem(email):
    stem=str(email).split('@',1)[0] if '@' in str(email) else 'Entra'
    return re.sub(r'[^\w.@+-]+','-',unicodedata.normalize('NFKC',stem)).strip('-') or 'Entra'

def available_username(User,email,exclude_pk=None):
    stem=username_stem(email);limit=User._meta.get_field('username').max_length
    for number in range(1,10001):
        suffix='#SSO' if number==1 else '-'+str(number)+'#SSO'
        candidate=stem[:limit-len(suffix)]+suffix
        if not User.objects.filter(username__iexact=candidate).exclude(pk=exclude_pk).exists():return candidate
    raise ValidationError('Für diese E-Mail-Adresse konnte kein freier SSO-Benutzername vergeben werden. Bitte die Administration informieren.')

def validate_portal_username(value):
    base=value[:-4] if value.endswith('#SSO') else value
    if not base:raise ValidationError('Bitte einen Benutzernamen vor #SSO angeben.')
    UnicodeUsernameValidator()(base)
