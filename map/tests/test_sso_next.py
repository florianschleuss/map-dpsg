from unittest.mock import patch
from urllib.parse import urlencode
from django.test import TestCase,override_settings
from django.urls import reverse
from .test_sso import EntraSSOTests
from map.sso_views import safe_next

@override_settings(PUBLIC_URL='https://dev.map.example.org',ALLOWED_HOSTS=['testserver'])
class SSONextTests(TestCase):
    setUp=EntraSSOTests.setUp
    identity=EntraSSOTests.identity
    save_flow=EntraSSOTests.save_flow
    callback=EntraSSOTests.callback
    def test_login_form_forwards_next_to_microsoft(self):
        response=self.client.get(reverse('login'),{'next':'/raeume/neu/'})
        # Inspect the Microsoft form separately from the local login form.
        html=response.content.decode();form=html.split('action="'+reverse('sso_start')+'"',1)[1].split('</form>',1)[0]
        self.assertIn('name="next" value="/raeume/neu/"',form)

    def test_start_saves_next_in_server_flow_and_not_provider_callback(self):
        with patch('map.sso_views.client') as app:
            app.return_value.initiate_auth_code_flow.return_value={'state':'state','nonce':'nonce','auth_uri':'https://login.microsoftonline.com/test'}
            response=self.client.post(reverse('sso_start'),{'next':'/raeume/neu/'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.session['entra_flow']['next'],'/raeume/neu/')
        self.assertNotIn('next=',app.return_value.initiate_auth_code_flow.call_args.kwargs['redirect_uri'])

    def complete(self,target,approved=True,callback_next=None):
        identity=self.identity();identity.approved=approved;identity.save()
        self.save_flow();session=self.client.session;session['entra_flow']['next']=target;session.save()
        with patch('map.sso_views.client') as app,patch('map.sso_views.validate_token',return_value=self.claims):
            app.return_value.acquire_token_by_auth_code_flow.return_value={'id_token':'test-token'}
            return self.client.get(reverse('sso_callback'),{'state':'expected-state','code':'code','next':callback_next or 'https://evil.example/'})

    def test_approved_login_returns_to_original_target_with_query(self):
        response=self.complete('/raeume/neu/?from=calendar')
        self.assertEqual(response.status_code,302);self.assertEqual(response['Location'],'/raeume/neu/?from=calendar')
        self.assertNotIn('entra_flow',self.client.session)

    def test_pending_user_still_waits_for_approval(self):
        response=self.complete('/raeume/neu/',approved=False)
        self.assertEqual(response['Location'],reverse('sso_waiting'))

    def test_unsafe_targets_fall_back_to_dashboard(self):
        response=self.complete('//evil.example/')
        self.assertEqual(response['Location'],reverse('dashboard'))

    def test_local_path_validator_rejects_external_or_malformed_targets(self):
        for target in ['https://evil.example/','//evil.example/','/\\evil.example/','javascript:alert(1)','relative/path','/https://'+'x'*2050,None]:
            self.assertEqual(safe_next(target),'',repr(target))
        self.assertEqual(safe_next('/raeume/neu/'),'/raeume/neu/')

    def test_already_authenticated_start_honors_local_target(self):
        self.client.force_login(self.local)
        response=self.client.post(reverse('sso_start'),{'next':'/raeume/neu/'})
        self.assertEqual(response['Location'],'/raeume/neu/')
