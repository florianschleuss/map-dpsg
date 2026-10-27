"""Operator isolation and publication readiness regression tests."""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.exceptions import ImproperlyConfigured
from email.header import decode_header, make_header
from email.utils import parseaddr
from map.site_config import local_asset, validate_operator
from map.mail_presentation import sender_address, html_message

@override_settings(SECURE_SSL_REDIRECT=False)
class SiteConfigurationTests(TestCase):
    def test_different_organizations_do_not_leak_between_requests(self):
        for name in ['Stamm Nord', 'Stamm Süd']:
            with override_settings(MAP_ORGANIZATION=name):
                response=self.client.get(reverse('login'))
                self.assertContains(response,name)
                self.assertNotContains(response,'https://dpsg.de')
                self.assertContains(response,'/static/map/logo.svg')
    def test_operator_text_is_escaped_in_templates_and_error_pages(self):
        with override_settings(MAP_ORGANIZATION='<script>alert(1)</script>'):
            for url in [reverse('login'),'/nonexistent-page/']:
                response=self.client.get(url)
                self.assertNotIn(b'<script>alert(1)</script>',response.content)
                self.assertIn(b'&lt;script&gt;',response.content)
    def test_local_assets_reject_remote_and_traversal_paths(self):
        for value in ['https://example.org/logo.svg','//example.org/logo','../secret','/absolute','a/../b']:
            with self.assertRaises(ImproperlyConfigured):local_asset(value)
        self.assertEqual(local_asset('operator/logo.svg'),'operator/logo.svg')
    def test_imprint_and_privacy_use_configured_operator(self):
        with override_settings(MAP_RESPONSIBLE_NAME='Vorstand Nord',MAP_RESPONSIBLE_ADDRESS='Musterweg 1',MAP_CONTACT_EMAIL='kontakt@example.org',MAP_IMPRINT_TEXT='Verantwortlich: Vorstand',MAP_HOSTING_DESCRIPTION='Hosting in der EU',MAP_PRIVACY_AUTHORITY='Zuständige Aufsicht Nord'):
            self.assertContains(self.client.get('/impressum/'),'Vorstand Nord')
            response=self.client.get('/datenschutz/')
            for text in ['Musterweg 1','kontakt@example.org','Hosting in der EU','Aufsicht Nord']:self.assertContains(response,text)
    def test_sender_identity_is_dynamic_and_rejects_injection(self):
        with override_settings(MAP_MAIL_SENDER_NAME='Anmeldungen Nord'):
            name,address=parseaddr(sender_address('no-reply@example.org'))
            self.assertEqual(str(make_header(decode_header(name))),'Anmeldungen Nord')
            self.assertIn('Anmeldungen Nord',html_message('Hallo'))
        with override_settings(MAP_MAIL_SENDER_NAME='Nord\nBcc: a@example.org'):
            with self.assertRaises(ValueError):sender_address('a@example.org')
    def test_missing_operator_and_https_block_production_check(self):
        with override_settings(MAP_RESPONSIBLE_NAME=""):
            errors=validate_operator()
        self.assertTrue(any('HTTPS' in e for e in errors))
        self.assertTrue(any('MAP_RESPONSIBLE_NAME' in e for e in errors))
    def test_complete_tls_configuration_passes_readiness(self):
        with override_settings(MAP_ORGANIZATION='Stamm Nord',MAP_RESPONSIBLE_NAME='Vorstand',MAP_RESPONSIBLE_ADDRESS='Musterweg 1',MAP_CONTACT_EMAIL='kontakt@example.org',MAP_IMPRINT_TEXT='Betreiberangaben',MAP_HOSTING_DESCRIPTION='EU',MAP_MAIL_DESCRIPTION='SMTP in EU',MAP_PRIVACY_LEGAL_TEXT='Anmeldungen: Art. 6 Abs. 1 b DSGVO',MAP_PRIVACY_AUTHORITY='Aufsicht',SECURE_SSL_REDIRECT=True,PUBLIC_URL='https://map.example.org',ALLOWED_HOSTS=['map.example.org'],CSRF_TRUSTED_ORIGINS=['https://map.example.org'],MAP_TRUSTED_PROXY_HOSTS=['caddy'],EMAIL_USE_TLS=True):
            self.assertEqual(validate_operator(),[])
    def test_public_health_is_minimal_and_requires_database(self):
        response=self.client.get('/healthz/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'ok')
        from unittest.mock import patch
        with patch('map.health.connection.cursor',side_effect=RuntimeError('secret database failure')):
            response=self.client.get('/healthz/')
        self.assertEqual(response.status_code,503)
        self.assertNotIn(b'secret',response.content)
