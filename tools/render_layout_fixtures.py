"""Render isolated synthetic layout fixtures; always SQLite in memory, never production data."""
import os,sys
from pathlib import Path
repo=Path.cwd()
sys.path.insert(0,str(repo))
sys.dont_write_bytecode=True
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',SECRET_KEY='MVP-AUDIT-ONLY-NOT-A-PRODUCTION-SECRET-KEY-12345678901234567890',SQLITE_TEST='1',DEBUG='0',HTTPS='0',MAP_TRUSTED_PROXY_HOSTS='')
import django
django.setup()
from django.conf import settings
settings.DATABASES['default']['NAME']=':memory:'
settings.DATABASES['default'].setdefault('TEST',{})['NAME']=':memory:'
settings.EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
from django.core.management import call_command

import json
from django.test import Client
from django.urls import reverse
from datetime import date,time,timedelta
from rooms.forms import local_datetime
from rooms.models import GroupSession
from rooms.services import save_booking
from rooms.tests.test_bookings import RoomBookingTests
from map.tests.test_pools_delete_smtp import EventFixture
from map.form_schema import persist_schema,STANDARD_SCHEMA
from map.models import MailConfiguration
from map.email_content import TEMPLATES
from rooms.notifications import EVENTS
from map.event_wizard import SESSION_KEY
call_command('migrate',verbosity=0)
settings.ALLOWED_HOSTS=['testserver'];settings.MAP_ORGANIZATION='Beispielstamm'
RoomBookingTests.setUpTestData();case=RoomBookingTests();case.day=date(2027,8,2)
for i in range(4):
 row=GroupSession.objects.create(weekday=i,start_time=time(17),end_time=time(19),group_name=['Wölflinge Gruppe 2','Jungpfadfinderinnen und Jungpfadfinder','Pfadfinder','Rover'][i]);row.rooms.add(case.room,case.garden)
bookings=[]
for i in range(3):bookings.append(save_booking(case.leader,case.payload(starts_at=local_datetime(case.day,time(18)),ends_at=local_datetime(case.day,time(20)),purpose='Sommerplanung und Gruppenabend '+str(i),grouping='Wölflinge Gruppe 2')))
fixture=EventFixture();fixture.setUp()
persist_schema(STANDARD_SCHEMA,'Sommerlagerformular',fixture.template)
fixture.event.capacity_mode='unlimited';fixture.event.save()
reg=fixture.reg('Alex Beispiel',fixture.a);fixture.reg('Robin Beispiel',fixture.b)
MailConfiguration.objects.update_or_create(pk=1,defaults={'feedback_email':'feedback@example.org'})
c=Client();c.force_login(fixture.admin)
folder=Path('docs/.rendered/layout');folder.mkdir(parents=True,exist_ok=True);pages=[]
def capture(name,url,follow=False,role='admin'):
 response=c.get(url,follow=follow)
 if response.status_code!=200:raise RuntimeError((name,url,response.status_code))
 filename=name+'.html';(folder/filename).write_bytes(response.content)
 pages.append({'name':name,'url':url,'file':filename,'role':role})
for name,url in [
 ('events','/dashboard/'),('event-detail',f'/dashboard/events/{fixture.event.pk}/'),('event-settings',f'/dashboard/events/{fixture.event.pk}/settings/'),('event-statistics',f'/dashboard/events/{fixture.event.pk}/statistik/'),
 ('bookings','/raeume/'),('calendar','/raeume/kalender/?date=2027-08-02'),('calendar-week','/raeume/kalender/?date=2027-08-02&view=week'),('pending','/raeume/genehmigungen/'),('groups','/raeume/gruppenstunden/'),('group-edit','/raeume/gruppenstunden/1/'),('booking-new','/raeume/neu/'),('booking-detail',f'/raeume/{bookings[0].pk}/'),('booking-edit',f'/raeume/{bookings[0].pk}/bearbeiten/'),
 ('room-settings','/raeume/einstellungen/'),('room-catalogue','/raeume/raumverwaltung/'),('room-mail','/raeume/mailvorlagen/'),('room-mail-edit','/raeume/mailvorlagen/'+next(iter(EVENTS))+'/'),
 ('event-module-settings','/verwaltung/einstellungen/veranstaltungen/'),('event-mail','/verwaltung/email-vorlagen/?section=events'),('event-mail-edit','/verwaltung/email-vorlagen/'+next(iter(TEMPLATES))+'/'),('system-mail','/verwaltung/email-vorlagen/?section=system'),
 ('settings','/verwaltung/einstellungen/'),('mail-settings','/verwaltung/smtp/'),('mail-queue','/verwaltung/email/'),('sso','/verwaltung/microsoft/'),('people','/verwaltung/benutzer/'),('person-edit',f'/verwaltung/benutzer/{case.leader.pk}/'),('roles','/verwaltung/rollen/'),('role-new','/verwaltung/rollen/neu/'),
 ('admin-stages','/admin/map/scoutgroup/'),('admin-stage-new','/admin/map/scoutgroup/add/'),('builder',f'/admin/formularbaukasten/{fixture.template.pk}/?event={fixture.event.pk}'),('public-event','/events/'+fixture.event.slug+'/'),('privacy','/datenschutz/')]:capture(name,url)
# Inspect independent wizard steps using isolated session drafts, without submitting anything.
for step in [0,1,2,3,4,5]:
 draft='audit-step-'+str(step);session=c.session;session[SESSION_KEY]={draft:{'step':step,'data':{}}};session.save()
 capture('wizard-'+str(step+1),'/admin/veranstaltung-anlegen/?entwurf='+draft)
c.logout();capture('login','/accounts/login/',role='anonymous')
from django.views.i18n import JavaScriptCatalog
from django.test import RequestFactory
(folder/'django-admin-static-path.txt').write_text(str(Path(django.__file__).parent/'contrib/admin/static'),encoding='utf-8')
(folder/'admin-i18n.js').write_bytes(JavaScriptCatalog.as_view()(RequestFactory().get('/admin/jsi18n/')).content)
(folder/'pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
print('Rendered',len(pages),'isolated pages; no application source or real database changed.')
