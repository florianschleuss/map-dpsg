"""Render real MAP views with invented fixtures in an in-memory database.
Never connects to the configured production database and never sends emails.
Run from repository root: python tools/render_screenshot_pages.py
"""
import os, sys, json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',SQLITE_TEST='1',SECRET_KEY='SCREENSHOT-ONLY-NOT-A-REAL-SECRET-123456789012345678901234567890',DEBUG='0',HTTPS='0',MAP_TRUSTED_PROXY_HOSTS='',MAP_ORGANIZATION='Stamm Waldlicht',MAP_CONTACT_EMAIL='kontakt@example.org',MAP_MAIL_SENDER_NAME='Anmeldungen Waldlicht')
import django
django.setup()
from django.conf import settings
settings.DATABASES['default']['NAME']=':memory:'
settings.ALLOWED_HOSTS=['testserver']
settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
from django.core.management import call_command
call_command('migrate',verbosity=0)
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from map.models import ScoutGroup,Event,EventGroup
from map.form_schema import persist_schema,STANDARD_SCHEMA
from map.services import register
user=get_user_model().objects.create_superuser(username='Leitung',email='leitung@example.org')
user.set_unusable_password();user.save()
groups=[ScoutGroup.objects.create(name=n) for n in ['Wölflinge','Jungpfadfinder','Pfadfinder']]
schema=[{'title':'Kontakt','fields':[{'key':'phone','label':'Telefon für Rückfragen','type':'text','required':True}]},{'title':'Verpflegung','fields':[{'key':'food','label':'Verpflegung','type':'select','required':True,'choices':['Vegetarisch','Vegan','Keine besondere Kost']},{'key':'notes','label':'Hinweise zur Verpflegung','type':'textarea','required':False}]}]
template=persist_schema(schema,'Lager & Abenteuer')
now=timezone.now()
event=Event.objects.create(title='Lager am See',slug='sommerlager',description='Eine Woche draußen. Gemeinsam kochen, Neues entdecken und abends am Lagerfeuer sitzen.',group=groups[0],form_template=template,capacity=36,published=True,costs_configured=True,confirmation_required=False,starts_at=now+timedelta(days=42),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=30))
for group in groups:EventGroup.objects.create(event=event,group=group,capacity=12)
for index in range(18):register(event.pk,'Beispielkind '+str(index+1),'eltern'+str(index)+'@example.org',{'phone':'0123 456789','food':['Vegetarisch','Vegan','Keine besondere Kost'][index%3]},group_id=groups[index%3].pk)
Event.objects.create(title='Abenteuerwochenende',slug='abenteuerwochenende',group=groups[1],form_template=template,capacity=24,published=False,starts_at=now+timedelta(days=65),registration_opens=now,registration_closes=now+timedelta(days=50))
client=Client();client.force_login(user)
pages={'dashboard':'/dashboard/','anmeldungen':f'/dashboard/events/{event.pk}/','statistik':f'/dashboard/events/{event.pk}/statistik/','formularbaukasten':f'/admin/formularbaukasten/{template.pk}/','elternformular':'/events/sommerlager/'}
out=root/'docs/.rendered';out.mkdir(parents=True,exist_ok=True)
for name,url in pages.items():
    if name=='elternformular':client.logout()
    response=client.get(url)
    if response.status_code!=200:raise RuntimeError(name+': '+str(response.status_code))
    html=response.content.decode().replace('/static/','https://map.example.org/static/')
    (out/(name+'.html')).write_text(html,encoding='utf-8')
print('Five real application pages rendered using invented data only.')
