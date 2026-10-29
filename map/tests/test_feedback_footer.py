from django.test import TestCase,override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from .test_pools_delete_smtp import EventFixture
from map.models import MailConfiguration
from map.mail_admin import MailConfigurationForm
from map.site_config import site_context,validate_operator

@override_settings(ALLOWED_HOSTS=['testserver'])
class FeedbackTests(EventFixture,TestCase):
    def test_feedback_can_be_saved_independently_of_mail_transport(self):
        config=MailConfiguration.objects.create(pk=1,enabled=False,from_email='sender@example.org',password_encrypted='kept-encrypted-value')
        form=MailConfigurationForm({'feedback_email':'feedback@example.org','provider':'smtp','from_email':'sender@example.org'},instance=config)
        self.assertTrue(form.is_valid(),form.errors);form.save();config.refresh_from_db()
        self.assertEqual(config.feedback_email,'feedback@example.org');self.assertFalse(config.enabled)
        self.assertEqual(config.password_encrypted,'kept-encrypted-value')
        self.assertEqual(config.from_email,'sender@example.org')
        self.assertContains(self.client.get(reverse('login')),'href="mailto:feedback@example.org"')
        self.assertContains(self.client.get(reverse('login')),'Probleme gefunden / Feedback zur Website')
        self.assertEqual(site_context()['map_site']['feedback_mailto'],'mailto:feedback@example.org')

    def test_unconfigured_or_cleared_feedback_link_is_hidden(self):
        self.assertNotContains(self.client.get(reverse('login')),'Feedback zur Website')
        MailConfiguration.objects.create(pk=1,feedback_email='')
        self.assertNotContains(self.client.get(reverse('login')),'Feedback zur Website')
        self.assertFalse(MailConfigurationForm({'feedback_email':'bad@example.org?bcc=other@example.org'}).is_valid())

    def test_only_authorized_accounts_can_change_feedback(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(reverse('mail_settings'),{'feedback_email':'feedback@example.org'}).status_code,403)
        self.client.force_login(self.admin)
        response=self.client.post(reverse('mail_settings'),{'feedback_email':'feedback@example.org','action':'save'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(MailConfiguration.objects.get(pk=1).feedback_email,'feedback@example.org')

    def test_unlimited_dashboard_uses_count_without_denominator(self):
        self.event.capacity_mode='unlimited';self.event.save();self.reg('Erstes Kind',self.a)
        self.client.force_login(self.admin);response=self.client.get(reverse('dashboard'))
        self.assertContains(response,'<strong>1</strong>',html=True)
        self.assertNotContains(response,'1 / Ohne Limit')

    @override_settings(EMAIL_USE_TLS=False,EMAIL_USE_SSL=False)
    def test_pre_migration_readiness_does_not_select_new_feedback_column(self):
        MailConfiguration.objects.create(pk=1)
        with CaptureQueriesContext(connection) as queries:validate_operator()
        self.assertTrue(queries.captured_queries)
        self.assertTrue(all('feedback_email' not in row['sql'] for row in queries.captured_queries))
