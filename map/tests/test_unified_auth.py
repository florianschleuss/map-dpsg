from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings

@override_settings(SECURE_SSL_REDIRECT=False)
class UnifiedLoginTests(TestCase):
    def setUp(self):
        self.team = get_user_model().objects.create_user(username='map-team', password='Strong-test-pass-593!')
        self.admin = get_user_model().objects.create_superuser(username='map-admin', email='admin@example.org', password='Strong-admin-pass-294!')
    def test_team_and_admin_use_one_template(self):
        for area in ['team','admin']:
            response=self.client.get('/accounts/login/',{'area':area})
            self.assertEqual(response.status_code,200)
            self.assertTemplateUsed(response,'registration/login.html')
            self.assertContains(response,'csrfmiddlewaretoken')
    def test_native_admin_login_redirects_to_shared_form(self):
        response=self.client.get('/admin/login/',{'next':'/admin/'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.startswith('/accounts/login/?'))
    def test_team_login_targets_dashboard(self):
        response=self.client.post('/accounts/login/',{'username':'map-team','password':'Strong-test-pass-593!','area':'team'})
        self.assertRedirects(response,'/dashboard/')
    def test_admin_login_targets_admin(self):
        response=self.client.post('/accounts/login/',{'username':'map-admin','password':'Strong-admin-pass-294!','area':'admin'})
        self.assertRedirects(response,'/dashboard/')
    def test_area_parameter_does_not_change_identity_or_privileges(self):
        response=self.client.post('/accounts/login/',{'username':'map-team','password':'Strong-test-pass-593!','area':'admin'})
        self.assertRedirects(response,'/dashboard/')
        self.assertEqual(self.client.get('/admin/auth/user/').status_code,302)
    def test_external_next_cannot_redirect_outside_map(self):
        response=self.client.post('/accounts/login/',{'username':'map-team','password':'Strong-test-pass-593!','area':'team','next':'https://evil.example/'})
        self.assertEqual(response.url,'/dashboard/')
    def test_shared_login_requires_csrf(self):
        response=Client(enforce_csrf_checks=True).post('/accounts/login/',{'username':'map-team','password':'Strong-test-pass-593!'})
        self.assertEqual(response.status_code,403)
    def test_admin_home_is_same_dashboard(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get('/admin/'),'/dashboard/')
