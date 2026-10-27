from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import EmailJob,EmailTemplate,ScoutGroup,FormTemplate,Event,EventGroup
from map.services import register
from map.mail_templates import system_content
from map.email_content import default_content,TEMPLATES,example_context
from unittest.mock import patch

@override_settings(SECURE_SSL_REDIRECT=False)
class QueueActionsTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='queueadmin9',email='admin@example.org',password='Strong-admin-pass-593!')
        self.reader=get_user_model().objects.create_user(username='queuereader9')
        self.reader.user_permissions.add(Permission.objects.get(content_type__app_label='map',codename='view_emailjob'))
        self.pending=EmailJob.objects.create(recipient='parent@example.org',subject='Ausstehend',body='Text',next_attempt=timezone.now(),attempts=2,last_error='OSError')
        self.failed=EmailJob.objects.create(recipient='parent@example.org',subject='Fehler',body='Text',next_attempt=timezone.now(),attempts=8,last_error='OSError')
        self.sent=EmailJob.objects.create(recipient='parent@example.org',subject='Gesendet',body='Text',next_attempt=timezone.now(),sent_at=timezone.now(),attempts=1)
        self.url=reverse('mail_queue');self.client.force_login(self.admin)
    def test_retry_resets_pending_and_failed_but_never_resends_sent(self):
        response=self.client.post(self.url,{'action':'retry','job_ids':[self.pending.pk,self.failed.pk,self.sent.pk]})
        self.assertEqual(response.status_code,302)
        for row in [self.pending,self.failed]:row.refresh_from_db();self.assertEqual(row.attempts,0);self.assertEqual(row.last_error,'')
        self.sent.refresh_from_db();self.assertEqual(self.sent.attempts,1);self.assertIsNotNone(self.sent.sent_at)
    def test_delete_requires_confirmation(self):
        self.assertEqual(self.client.post(self.url,{'action':'delete','job_ids':[self.pending.pk]}).status_code,400);self.assertTrue(EmailJob.objects.filter(pk=self.pending.pk).exists())
    def test_selected_delete_only_removes_selected_rows(self):
        response=self.client.post(self.url,{'action':'delete','job_ids':[self.pending.pk],'confirm_delete':'yes'})
        self.assertEqual(response.status_code,302);self.assertFalse(EmailJob.objects.filter(pk=self.pending.pk).exists());self.assertEqual(EmailJob.objects.count(),2)
    def test_filtered_delete_leaves_other_statuses_untouched(self):
        response=self.client.post(self.url+'?status=failed',{'action':'delete_filtered','confirm_delete':'yes'})
        self.assertEqual(response.status_code,302);self.assertFalse(EmailJob.objects.filter(pk=self.failed.pk).exists());self.assertTrue(EmailJob.objects.filter(pk=self.sent.pk).exists());self.assertTrue(EmailJob.objects.filter(pk=self.pending.pk).exists())
    def test_malformed_selection_is_rejected(self):
        self.assertEqual(self.client.post(self.url,{'action':'retry','job_ids':['not-an-id']}).status_code,400)
    def test_reader_cannot_retry_or_delete_even_with_forged_post(self):
        self.client.force_login(self.reader);self.assertEqual(self.client.get(self.url).status_code,200)
        for action in ['retry','delete','delete_filtered']:self.assertEqual(self.client.post(self.url,{'action':action,'job_ids':[self.pending.pk],'confirm_delete':'yes'}).status_code,403)
        self.assertEqual(EmailJob.objects.count(),3)
    def test_retry_permission_does_not_grant_delete(self):
        self.reader.user_permissions.add(Permission.objects.get(content_type__app_label='map',codename='change_emailjob'));self.client.force_login(self.reader)
        self.assertEqual(self.client.post(self.url,{'action':'retry','job_ids':[self.failed.pk]}).status_code,302)
        self.assertEqual(self.client.post(self.url,{'action':'delete','job_ids':[self.pending.pk],'confirm_delete':'yes'}).status_code,403)
    def test_delete_permission_does_not_grant_retry(self):
        self.reader.user_permissions.add(Permission.objects.get(content_type__app_label='map',codename='delete_emailjob'));self.client.force_login(self.reader)
        self.assertEqual(self.client.post(self.url,{'action':'retry','job_ids':[self.failed.pk]}).status_code,403)
        self.assertEqual(self.client.post(self.url,{'action':'delete','job_ids':[self.pending.pk],'confirm_delete':'yes'}).status_code,302)
    def test_queue_mutations_are_csrf_protected(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        for action in ['retry','delete','delete_filtered']:self.assertEqual(client.post(self.url,{'action':action,'job_ids':[self.pending.pk],'confirm_delete':'yes'}).status_code,403)
    def test_filter_and_actions_are_visible_in_german(self):
        response=self.client.get(self.url+'?status=failed');self.assertContains(response,'Ausgewählte erneut versuchen');self.assertContains(response,'Aufträge endgültig löschen');self.assertNotContains(response,'<strong>Gesendet</strong>')

@override_settings(SECURE_SSL_REDIRECT=False)
class MailTemplateEditorTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='templateadmin9',email='admin@example.org',password='Strong-admin-pass-593!')
        self.user=get_user_model().objects.create_user(username='templateuser9')
        self.client.force_login(self.admin);self.url=reverse('email_template_edit',args=['registration'])
        self.subject,self.body=default_content('registration')
    def test_all_eight_live_templates_are_listed(self):
        response=self.client.get(reverse('email_templates'))
        for key,(title,description) in TEMPLATES.items():self.assertContains(response,reverse('email_template_edit',args=[key]))
    def test_preview_does_not_save_or_send(self):
        with patch('map.mailer.send_mail') as send:
            response=self.client.post(self.url,{'action':'preview','subject':'Hallo {child_name}','body':self.body})
        self.assertEqual(response.status_code,200);self.assertContains(response,'Hallo Alex Beispiel');self.assertFalse(EmailTemplate.objects.exists());self.assertFalse(EmailJob.objects.exists());send.assert_not_called()
    def test_saved_override_is_used_by_real_registration_queue(self):
        self.assertEqual(self.client.post(self.url,{'action':'save','subject':'Willkommen: {event_title}','body':'Hallo {child_name}!\n'+self.body}).status_code,302)
        stage=ScoutGroup.objects.create(name='WösMail9');template=FormTemplate.objects.create(name='Leer9');now=timezone.now()
        event=Event.objects.create(group=stage,form_template=template,title='Echtes Testlager9',slug='mail9',published=True,confirmation_required=False,starts_at=now+timedelta(days=5),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=4))
        EventGroup.objects.create(event=event,group=stage,capacity=20)
        row=register(event.pk,'Testkind9','parent@example.org',{})
        job=EmailJob.objects.get(event=event);self.assertEqual(job.subject,'Willkommen: Echtes Testlager9');self.assertIn('Hallo Testkind9!',job.body);self.assertIn('/manage/',job.body)
    def test_unknown_placeholder_and_missing_secure_links_are_form_errors(self):
        for body in ['Hallo {secret_key}', 'Keine Links']:
            response=self.client.post(self.url,{'action':'save','subject':self.subject,'body':body});self.assertEqual(response.status_code,200);self.assertFalse(EmailTemplate.objects.exists())
    def test_reset_requires_explicit_confirmation(self):
        EmailTemplate.objects.create(key='registration',subject='Angepasst',body=self.body)
        self.client.post(self.url,{'action':'reset'});self.assertTrue(EmailTemplate.objects.exists())
        self.assertEqual(self.client.post(self.url,{'action':'reset','confirm_reset':'yes'}).status_code,302);self.assertFalse(EmailTemplate.objects.exists())
    def test_existing_queued_messages_remain_unchanged(self):
        job=EmailJob.objects.create(recipient='old@example.org',subject='Bisheriger Betreff',body='Bisheriger Text',next_attempt=timezone.now())
        self.client.post(self.url,{'action':'save','subject':'Neu','body':self.body});job.refresh_from_db();self.assertEqual(job.subject,'Bisheriger Betreff');self.assertEqual(job.body,'Bisheriger Text')
    def test_unknown_template_returns_404(self):self.assertEqual(self.client.get(reverse('email_template_edit',args=['unknown'])).status_code,404)
    def test_template_permission_is_enforced_for_get_post_and_reset(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.assertEqual(self.client.post(self.url,{'action':'save','subject':'Neu','body':self.body}).status_code,403)
        self.assertEqual(self.client.post(self.url,{'action':'reset','confirm_reset':'yes'}).status_code,403)
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='map',codename='change_emailtemplate'))
        self.assertEqual(self.client.get(self.url).status_code,200)
    def test_template_post_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(self.url,{'action':'save','subject':self.subject,'body':self.body}).status_code,403)
    def test_preview_escapes_markup(self):
        response=self.client.post(self.url,{'action':'preview','subject':'<script>alert(1)</script>','body':self.body})
        self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>alert(1)</script>')
    def test_required_confirmation_section_still_appears_when_pending(self):
        subject,body=system_content('registration',example_context());self.assertIn('/confirm/BEISPIEL/',body);self.assertIn('/manage/BEISPIEL/',body)
