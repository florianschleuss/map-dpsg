"""Rename automatically provisioned SSO accounts without changing their identity keys."""
import re
import unicodedata
from django.db import migrations
from django.contrib.auth.hashers import is_password_usable

def rename(apps,schema_editor):
    Identity=apps.get_model('map','EntraIdentity');alias=schema_editor.connection.alias
    User=Identity._meta.get_field('user').remote_field.model
    for identity in Identity.objects.using(alias).select_related('user').order_by('pk'):
        user=identity.user
        if not re.fullmatch(r'entra_[a-f0-9]{32}',user.username) or is_password_usable(user.password):continue
        stem=user.email.split('@',1)[0] if '@' in user.email else 'Entra'
        stem=re.sub(r'[^\w.@+-]+','-',unicodedata.normalize('NFKC',stem)).strip('-') or 'Entra'
        limit=User._meta.get_field('username').max_length
        for number in range(1,10001):
            suffix='#SSO' if number==1 else '-'+str(number)+'#SSO';candidate=stem[:limit-len(suffix)]+suffix
            if not User.objects.using(alias).filter(username__iexact=candidate).exclude(pk=user.pk).exists():
                User.objects.using(alias).filter(pk=user.pk).update(username=candidate);break

class Migration(migrations.Migration):
    dependencies=[('map','0013_emailjob_room_booking_emailjob_room_change_and_more')]
    operations=[migrations.RunPython(rename,migrations.RunPython.noop)]
