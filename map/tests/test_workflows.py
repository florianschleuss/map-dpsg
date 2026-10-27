from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import signing, mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import ScoutGroup, FormTemplate, FormModule, FormField, Event, EventPermission, Registration, EmailJob
from map.forms import RegistrationForm, template_schema
from map import services as svc

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SECURE_SSL_REDIRECT=False)
class WorkflowTests(TestCase):
    def setUp(self):
        self.group = ScoutGroup.objects.create(name='Stamm')
        self.template = FormTemplate.objects.create(name='Standard')
        self.module = FormModule.objects.create(template=self.template, title='Kontakt')
        FormField.objects.create(module=self.module, key='phone', label='Telefon', kind='text', required=True)
        now = timezone.now()
        self.event = Event.objects.create(group=self.group, form_template=self.template, title='Lager', slug='lager', starts_at=now+timedelta(days=20), registration_opens=now-timedelta(days=1), registration_closes=now+timedelta(days=10), capacity=1, published=True)
    def register(self, name='Anna Kind', email='parent@example.org'):
        return svc.register(self.event.pk, name, email, {'phone': '01234'})
    def user(self, name, role=None, event=None):
        user = get_user_model().objects.create_user(username=name, password='test-password-349!')
        if role: EventPermission.objects.create(user=user, event=event or self.event, role=role)
        return user
    def test_confirmation_and_purpose_bound_tokens(self):
        row = self.register()
        self.assertEqual(row.status, 'pending')
        token = svc.token_for(row, 'confirm')
        self.assertEqual(svc.resolve_token(token, 'confirm').pk, row.pk)
        with self.assertRaises(ValidationError): svc.resolve_token(token, 'manage')
        with self.assertRaises(ValidationError): svc.resolve_token(token+'x', 'confirm')
        response = self.client.get(reverse('confirm', args=[token]))
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertFalse(row.email_verified)
        self.client.post(reverse('confirm', args=[token]))
        row.refresh_from_db()
        self.assertEqual(row.status, 'confirmed')
        self.assertTrue(row.email_verified)
    def test_expired_token(self):
        token = svc.token_for(self.register(), 'manage')
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp()+40*86400):
            with self.assertRaises(ValidationError): svc.resolve_token(token, 'manage')
    def test_normalized_duplicate_and_database_constraint(self):
        row = self.register()
        with self.assertRaises(ValidationError): self.register('  ANNA   KIND ', 'PARENT@example.org')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Registration.objects.create(event=self.event, child_name='Other', email=row.email, identity=row.identity, status='waitlisted')
    def test_waitlist_and_cancellation_promote_oldest(self):
        first = self.register()
        second = self.register('Ben Kind')
        third = self.register('Clara Kind')
        self.assertEqual(second.status, 'waitlisted')
        svc.confirm(second.pk)
        svc.cancel(first.pk)
        second.refresh_from_db(); third.refresh_from_db()
        self.assertEqual(second.status, 'confirmed')
        self.assertEqual(third.status, 'waitlisted')
    def test_deadline_expiry_releases_capacity(self):
        first = self.register()
        second = self.register('Ben Kind')
        svc.confirm(second.pk)
        Registration.objects.filter(pk=first.pk).update(confirmation_deadline=timezone.now()-timedelta(seconds=1))
        svc.rebalance(self.event.pk)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(first.status, 'expired')
        self.assertEqual(second.status, 'confirmed')
    def test_full_without_waitlist(self):
        self.event.waitlist_enabled=False; self.event.save()
        self.register()
        with self.assertRaises(ValidationError): self.register('Ben Kind')
    def test_confirmation_can_be_disabled(self):
        self.event.confirmation_required=False; self.event.save()
        row=self.register()
        self.assertEqual(row.status, 'confirmed')
        self.assertTrue(row.email_verified)
    def test_closed_and_unpublished(self):
        self.event.published=False; self.event.save()
        with self.assertRaises(ValidationError): self.register()
        self.assertEqual(self.client.get(reverse('event', args=['lager'])).status_code,404)
    def test_form_validation_and_snapshot(self):
        form=RegistrationForm({'child_name':'Anna','email':'p@example.org','consent':'on'},modules=template_schema(self.template))
        self.assertFalse(form.is_valid())
        row=self.register()
        FormField.objects.filter(module=self.module).update(label='Changed')
        row.refresh_from_db()
        self.assertEqual(row.schema_snapshot[0]['fields'][0]['label'],'Telefon')
    def test_public_registration_and_csrf(self):
        url=reverse('event',args=['lager'])
        data={'child_name':'Anna Kind','email':'parent@example.org','consent':'on','answer_phone':'123'}
        self.assertEqual(Client(enforce_csrf_checks=True).post(url,data).status_code,403)
        self.assertEqual(self.client.post(url,data).status_code,200)
        self.assertEqual(Registration.objects.count(),1)
        self.assertEqual(EmailJob.objects.count(),1)
    def test_edit_and_explicit_cancel(self):
        row=self.register(); token=svc.token_for(row,'manage'); url=reverse('manage',args=[token])
        self.client.post(url,{'answer_phone':'567','action':'save'})
        row.refresh_from_db(); self.assertEqual(row.answers['phone'],'567')
        self.client.post(url,{'action':'cancel'})
        row.refresh_from_db(); self.assertEqual(row.status,'pending')
        self.client.post(url,{'action':'cancel','cancel_confirm':'yes'})
        row.refresh_from_db(); self.assertEqual(row.status,'cancelled')
        self.register()
    def test_permissions_deny_cross_event_and_viewer_writes(self):
        row=self.register()
        viewer=self.user('viewer','viewer')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('event_admin',args=[self.event.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('export_csv',args=[self.event.pk])).status_code,200)
        for url in [reverse('event_settings',args=[self.event.pk]),reverse('staff_registration',args=[row.pk])]:
            self.assertEqual(self.client.get(url).status_code,403)
            self.assertEqual(self.client.post(url,{}).status_code,403)
        stranger=self.user('stranger')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse('export_csv',args=[self.event.pk])).status_code,403)
    def test_editor_can_edit(self):
        row=self.register()
        self.client.force_login(self.user('editor','editor'))
        self.assertEqual(self.client.post(reverse('staff_registration',args=[row.pk]),{'answer_phone':'999','action':'save'}).status_code,302)
        row.refresh_from_db(); self.assertEqual(row.answers['phone'],'999')
    def test_csv_formula_injection(self):
        self.register('=HYPERLINK("evil")')
        self.client.force_login(self.user('viewer','viewer'))
        response=self.client.get(reverse('export_csv',args=[self.event.pk]))
        self.assertIn("'=HYPERLINK",response.content.decode())
        self.assertEqual(response['Cache-Control'],'no-store')
    def test_resend_is_generic_and_rate_limited(self):
        self.register()
        url=reverse('resend',args=['lager'])
        for _ in range(5):
            self.assertEqual(self.client.post(url,{'child_name':'Anna Kind','email':'parent@example.org'}).status_code,200)
        self.assertEqual(EmailJob.objects.count(),4)
        response=self.client.post(url,{'child_name':'Nobody','email':'no@example.org'})
        self.assertContains(response,'Falls eine aktive Anmeldung')
    def test_queue_success_and_failure_retry(self):
        self.register()
        call_command('process_queue')
        job=EmailJob.objects.first()
        self.assertIsNotNone(job.sent_at)
        self.assertEqual(len(mail.outbox),1)
        self.register('Ben Kind')
        with patch('map.management.commands.process_queue.send_mail',side_effect=OSError('private detail')):
            call_command('process_queue')
        job=EmailJob.objects.filter(sent_at__isnull=True).first()
        self.assertEqual(job.attempts,1)
        self.assertEqual(job.last_error,'OSError')
        self.assertGreater(job.next_attempt,timezone.now())
    def test_throttle_limit(self):
        self.assertTrue(svc.throttle('sample',limit=1))
        self.assertFalse(svc.throttle('sample',limit=1))
