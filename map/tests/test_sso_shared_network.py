"""Regression coverage for group sign-in behind NAT and browser CSP redirects."""
import hashlib
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.test import TestCase, Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import Throttle
from map.request_security import sso_retry_after, client_address

@override_settings(MAP_TRUSTED_PROXY_HOSTS=[], MAP_TRUSTED_PROXY_NETWORKS=[], SECURE_SSL_REDIRECT=False)
class SharedSSOSigninTests(TestCase):
    def request(self, session=None, address='198.51.100.2'):
        request=RequestFactory().post('/accounts/microsoft/start/', REMOTE_ADDR=address)
        request.session={} if session is None else session
        return request

    def test_eighty_browsers_can_start_from_same_network(self):
        for _ in range(80):
            self.assertEqual(sso_retry_after(self.request()), 0)

    def test_repeated_browser_is_limited_without_blocking_others(self):
        session={}
        for _ in range(20):self.assertEqual(sso_retry_after(self.request(session)),0)
        self.assertEqual(sso_retry_after(self.request(session)),300)
        self.assertEqual(sso_retry_after(self.request()),0)

    def test_rotating_browsers_still_hits_network_limit(self):
        for _ in range(600):self.assertEqual(sso_retry_after(self.request()),0)
        self.assertEqual(sso_retry_after(self.request()),900)
        self.assertEqual(sso_retry_after(self.request(address='198.51.100.3')),0)

    def test_expired_window_allows_retry(self):
        session={}
        for _ in range(21):sso_retry_after(self.request(session))
        Throttle.objects.update(window_start=timezone.now()-timedelta(minutes=16))
        self.assertEqual(sso_retry_after(self.request(session)),0)

    def test_old_ip_lock_does_not_survive_update(self):
        key=hashlib.sha256((settings.SECRET_KEY+'sso-start:198.51.100.2').encode()).hexdigest()
        Throttle.objects.create(key=key,count=999,window_start=timezone.now())
        self.assertEqual(sso_retry_after(self.request()),0)

    def test_forwarded_headers_only_trusted_from_configured_proxy(self):
        request=self.request(address='172.18.0.2');request.META['HTTP_X_FORWARDED_FOR']='198.51.100.8'
        self.assertEqual(client_address(request),'172.18.0.2')
        with override_settings(MAP_TRUSTED_PROXY_HOSTS=['caddy']), patch('map.request_security.proxy_addresses',return_value=('172.18.0.2',)):
            self.assertEqual(client_address(request),'198.51.100.8')

    def test_throttle_page_has_german_wait_and_retry_header(self):
        with patch('map.request_security.sso_retry_after',return_value=300):
            response=self.client.post(reverse('sso_start'))
        self.assertEqual(response.status_code,429)
        self.assertEqual(response['Retry-After'],'300')
        self.assertContains(response,'5 Minuten',status_code=429)

    def test_only_login_pages_allow_exact_microsoft_host(self):
        for path in ['/accounts/login/','/admin/login/','/accounts/microsoft/start/','/verwaltung/microsoft/']:
            response=self.client.get(path)
            self.assertIn("form-action 'self' https://login.microsoftonline.com;",response['Content-Security-Policy'])
        for path in ['/','/datenschutz/','/accounts/microsoft/callback/']:
            response=self.client.get(path)
            self.assertIn("form-action 'self';",response['Content-Security-Policy'])
            self.assertNotIn('login.microsoftonline.com',response['Content-Security-Policy'])

    def test_csrf_is_still_required(self):
        response=Client(enforce_csrf_checks=True).post(reverse('sso_start'))
        self.assertEqual(response.status_code,403)
