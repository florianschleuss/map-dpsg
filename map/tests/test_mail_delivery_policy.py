from datetime import timedelta,time
from unittest.mock import patch
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from map.models import MailTemplatePolicy,EmailJob,ScoutGroup,Event,EventGroup,LeaderProfile
from map.form_schema import persist_schema,STANDARD_SCHEMA
from map.services import register,queue_message
from map.mail_policy import enabled,PROTECTED
from rooms.models import Room,RoomBooking,RoomSettings
from rooms.notifications import notify
from rooms.forms import local_datetime

@override_settings(ALLOWED_HOSTS=['testserver'],PUBLIC_URL='https://dev.example.invalid')
class MailDeliveryPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=get_user_model().objects.create_superuser('policy-admin','admin@example.invalid','test-policy-password-123')
        cls.board=get_user_model().objects.create_user('policy-board','board@example.invalid');cls.board.groups.add(Group.objects.get(name='Vorstand'))
        cls.outsider=get_user_model().objects.create_user('policy-outsider')
        cls.stage=ScoutGroup.objects.create(name='Policy-Stufe');template=persist_schema(STANDARD_SCHEMA,'Policy-Formular');now=timezone.now()
        cls.event=Event.objects.create(title='Policy-Veranstaltung',slug='policy-event',group=cls.stage,form_template=template,published=True,capacity=10,confirmation_required=False,
            starts_at=now+timedelta(days=30),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=10))
        EventGroup.objects.create(event=cls.event,group=cls.stage,capacity=10)

    def url(self,scope,key):return reverse('set_mail_template_state',args=[scope,key])
    def disable(self,scope,key):MailTemplatePolicy.objects.update_or_create(scope=scope,key=key,defaults={'enabled':False})

    def test_protected_templates_remain_enabled_and_cannot_be_switched_off(self):
        self.client.force_login(self.admin)
        for key in PROTECTED:
            self.disable('map',key);self.assertTrue(enabled('map',key))
            self.assertEqual(self.client.post(self.url('map',key),{'enabled':'0'}).status_code,403)

    def test_optional_switch_is_post_only_csrf_protected_and_idempotent(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('map','changed')).status_code,405)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.admin)
        self.assertEqual(strict.post(self.url('map','changed'),{'enabled':'0'}).status_code,403)
        for _ in range(2):self.assertEqual(self.client.post(self.url('map','changed'),{'enabled':'0'}).status_code,302)
        self.assertFalse(enabled('map','changed'))
        self.client.post(self.url('map','changed'),{'enabled':'1'});self.assertTrue(enabled('map','changed'))

    def test_module_rights_do_not_allow_disabling_other_modules(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.url('rooms','approved'),{'enabled':'0'}).status_code,403)
        self.client.force_login(self.board)
        self.assertEqual(self.client.post(self.url('rooms','approved'),{'enabled':'0'}).status_code,302)
        self.assertEqual(self.client.post(self.url('map','changed'),{'enabled':'0'}).status_code,403)

    def test_disabled_registration_change_does_not_create_mail_but_essential_registration_does(self):
        self.disable('map','registration');row=register(self.event.pk,'Test Kind','test@example.invalid',{'phone':'0000','food':'Vegan'})
        self.assertTrue(EmailJob.objects.filter(registration=row,template_key='registration').exists())
        before=EmailJob.objects.count();self.disable('map','changed');queue_message(row,'Anmeldung geändert')
        self.assertEqual(EmailJob.objects.count(),before)

    def test_room_decision_and_booking_data_are_retained_when_mail_disabled(self):
        day=timezone.localdate()+timedelta(days=2)
        row=RoomBooking.objects.create(creator=self.board,starts_at=local_datetime(day,time(9)),ends_at=local_datetime(day,time(17)),grouping='Test',purpose='Test',contact_person='Test',contact='Test',status='approved')
        row.rooms.add(Room.objects.first());self.disable('rooms','approved');notify(row,'approved')
        self.assertFalse(EmailJob.objects.filter(room_booking=row).exists());self.assertTrue(RoomBooking.objects.filter(pk=row.pk,status='approved').exists())

    def test_disabling_also_stops_already_tagged_queue_jobs_and_reenable_needs_retry(self):
        job=EmailJob.objects.create(template_scope='map',template_key='changed',recipient='test@example.invalid',subject='Test',body='Test',next_attempt=timezone.now())
        self.disable('map','changed')
        with patch('map.management.commands.process_queue.send_mail',return_value=1) as send:
            call_command('process_queue',verbosity=0);send.assert_not_called()
        job.refresh_from_db();self.assertEqual(job.last_error,'TemplateDisabled');self.assertIsNone(job.sent_at)
        MailTemplatePolicy.objects.filter(scope='map',key='changed').update(enabled=True)
        with patch('map.management.commands.process_queue.send_mail',return_value=1) as send:
            call_command('process_queue',verbosity=0);send.assert_not_called()
            job.attempts=0;job.last_error='';job.save();call_command('process_queue',verbosity=0);send.assert_called_once()

    def test_legacy_unclassified_job_is_not_incorrectly_suppressed(self):
        job=EmailJob.objects.create(recipient='legacy@example.invalid',subject='Alte Nachricht',body='Test',next_attempt=timezone.now());self.disable('map','changed')
        with patch('map.management.commands.process_queue.send_mail',return_value=1) as send:
            call_command('process_queue',verbosity=0);send.assert_called_once()
        job.refresh_from_db();self.assertIsNotNone(job.sent_at)

    def test_template_overview_exposes_state_and_essential_lock(self):
        self.client.force_login(self.admin);self.disable('map','changed')
        response=self.client.get(reverse('email_templates'),{'section':'events'})
        self.assertContains(response,'Deaktiviert');self.assertContains(response,'Erforderlich · aktiv')
        self.assertContains(response,self.url('map','changed'));self.assertNotContains(response,self.url('map','registration'))

    def test_resetting_content_does_not_reenable_delivery(self):
        self.client.force_login(self.admin);self.disable('map','changed')
        self.client.post(reverse('email_template_edit',args=['changed']),{'action':'reset','confirm_reset':'yes'})
        self.assertFalse(enabled('map','changed'))
