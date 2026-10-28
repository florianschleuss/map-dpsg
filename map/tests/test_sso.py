import hashlib
import time
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from map.models import ScoutGroup, LeaderProfile, EmailJob
from map.sso_models import SSOConfiguration, EntraIdentity, EntraStageMapping, SSOAudit
from map.sso import resolve_identity, automatic_stage_ids, validate_token, groups_from, SSOError, can_enter
from map.sso_forms import SSOSettingsForm
from map.mailer import encrypt_password, decrypt_client_secret


@override_settings(PUBLIC_URL='https://dev.map.example.org', ALLOWED_HOSTS=['testserver'])
class EntraSSOTests(TestCase):
    def setUp(self):
        self.tenant=uuid.uuid4(); self.client_id=uuid.uuid4(); self.group=uuid.uuid4()
        self.config=SSOConfiguration.objects.create(pk=1, enabled=True, tenant_id=self.tenant, client_id=self.client_id,
            client_secret_encrypted=encrypt_password('sso-test-secret'), secret_expires_on=timezone.localdate()+timedelta(days=90), notification_email='admins@example.org')
        self.stage=ScoutGroup.objects.create(name='Wölflinge')
        self.other=ScoutGroup.objects.create(name='Juffis')
        self.admin=get_user_model().objects.create_superuser('technical','technical@example.org','Strong-Password-12345')
        self.local=get_user_model().objects.create_user('local','same@example.org','Strong-Password-12345')
        self.claims={'tid':str(self.tenant),'oid':str(uuid.uuid4()),'email':'same@example.org','given_name':'Alex','groups':[]}

    def identity(self, groups=None, user=None):
        claims=dict(self.claims)
        if groups is not None:claims['groups']=groups
        if user is not None:
            EntraIdentity.objects.get_or_create(tenant_id=self.tenant,object_id=self.claims['oid'],defaults={'user':user,'approved':True})
        return resolve_identity(claims,self.config)

    def save_flow(self, mode='login', at=None, user=None):
        session=self.client.session
        session['entra_flow']={'flow':{'state':'expected-state','nonce':'nonce'},'at':at or time.time(),
            'revision':str(self.config.revision),'mode':mode,'user':user.pk if user else None}
        session.save()

    def callback(self):return self.client.get(reverse('sso_callback'),{'state':'expected-state','code':'one-use-code'})

    def signin(self, identity):
        self.client.force_login(identity.user)
        session=self.client.session;session['map_sso']={'identity':identity.pk,'at':time.time(),'revision':str(self.config.revision)};session.save()

    def test_unknown_user_is_pending_and_email_is_sent_only_once(self):
        identity=self.identity()
        self.assertFalse(can_enter(identity)); self.assertFalse(identity.user.has_usable_password())
        self.assertFalse(identity.user.is_staff);self.assertFalse(identity.user.is_superuser)
        self.assertEqual(identity.user.groups.count(),0)
        self.identity();self.assertEqual(EmailJob.objects.filter(recipient='admins@example.org').count(),1)
        self.assertNotEqual(identity.user.pk,self.local.pk)

    def test_mapping_grants_only_assigned_stage_not_admin_or_roles(self):
        EntraStageMapping.objects.create(group_id=self.group,stage=self.stage)
        identity=self.identity([str(self.group)])
        from map.access import stage_ids
        self.assertTrue(can_enter(identity));self.assertEqual(stage_ids(identity.user,'change'),{self.stage.pk})
        self.assertEqual(identity.user.groups.count(),0);self.assertFalse(identity.user.is_staff)

    def test_sync_removes_automatic_but_preserves_manual_stage_and_roles(self):
        EntraStageMapping.objects.create(group_id=self.group,stage=self.stage)
        identity=self.identity([str(self.group)],self.local)
        profile=LeaderProfile.objects.create(user=self.local,is_leader=True);profile.stages.add(self.other)
        role=Group.objects.create(name='Manual role');self.local.groups.add(role)
        identity=self.identity([])
        from map.access import stage_ids
        self.assertEqual(stage_ids(self.local,'view'),{self.other.pk})
        self.assertTrue(self.local.groups.filter(pk=role.pk).exists());self.assertTrue(identity.approved)

    def test_overage_or_missing_claims_clear_automatic_grants(self):
        for claims in [{}, {'groups':['invalid']}, {'hasgroups':True}, {'groups':[str(self.group)],'_claim_names':{'groups':'src1'}}]:
            self.assertEqual(groups_from(claims),([],False))
        EntraStageMapping.objects.create(group_id=self.group,stage=self.stage)
        identity=self.identity([str(self.group)])
        claims=dict(self.claims,hasgroups=True);resolve_identity(claims,self.config)
        self.assertEqual(automatic_stage_ids(identity.user),set())

    def test_different_tenant_does_not_create_account(self):
        self.claims['tid']=str(uuid.uuid4())
        with self.assertRaises(SSOError):self.identity()
        self.assertEqual(EntraIdentity.objects.count(),0)

    def test_blocked_and_disabled_accounts_cannot_sign_in(self):
        identity=self.identity();identity.blocked=True;identity.save()
        with self.assertRaises(SSOError):self.identity()
        identity.blocked=False;identity.save();identity.user.is_active=False;identity.user.save()
        with self.assertRaises(SSOError):self.identity()

    def test_expired_automatic_rights_are_not_used(self):
        EntraStageMapping.objects.create(group_id=self.group,stage=self.stage)
        identity=self.identity([str(self.group)]);identity.last_login_at=timezone.now()-timedelta(minutes=16);identity.save()
        self.assertEqual(automatic_stage_ids(identity.user),set())

    def test_account_link_route_is_removed(self):
        self.client.force_login(self.local)
        self.assertEqual(self.client.get('/accounts/microsoft/link/').status_code,404)

    def test_legacy_link_flow_is_rejected(self):
        self.client.force_login(self.local);self.save_flow('link',user=self.local)
        self.assertEqual(self.callback().status_code,400)
        self.assertFalse(EntraIdentity.objects.exists())

    def test_existing_identity_remains_assigned_to_existing_user(self):
        self.identity(user=self.local)
        self.assertEqual(self.identity().user_id,self.local.pk)

    def test_callback_rejects_wrong_state_expired_flow_and_replay(self):
        self.save_flow()
        with patch('map.sso_views.client') as app:
            self.assertEqual(self.client.get(reverse('sso_callback'),{'state':'bad','code':'x'}).status_code,400)
            app.assert_not_called();self.assertEqual(self.callback().status_code,400)
        self.save_flow(at=time.time()-601);self.assertEqual(self.callback().status_code,400)

    def test_successful_callback_uses_stable_id_and_never_stores_tokens(self):
        self.save_flow()
        with patch('map.sso_views.client') as app,patch('map.sso_views.validate_token',return_value=self.claims):
            app.return_value.acquire_token_by_auth_code_flow.return_value={'id_token':'opaque-id-token','access_token':'private-access-token','refresh_token':'private-refresh-token'}
            self.assertRedirects(self.callback(),reverse('sso_waiting'))
        session=str(dict(self.client.session));self.assertNotIn('private-',session);self.assertNotIn('opaque-id-token',session)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code,302)
        self.assertNotIn('opaque-id-token',str(EntraIdentity.objects.get().group_ids))

    def test_provider_errors_never_expose_secrets(self):
        self.save_flow()
        with patch('map.sso_views.client',side_effect=RuntimeError('sso-test-secret access-token-private')):
            response=self.callback()
        self.assertEqual(response.status_code,502);self.assertNotContains(response,'sso-test-secret',status_code=502)
        self.assertNotContains(response,'access-token-private',status_code=502)

    def test_local_account_cannot_be_silently_replaced(self):
        self.save_flow();self.client.force_login(self.local)
        with patch('map.sso_views.client') as app:
            self.assertEqual(self.callback().status_code,400);app.assert_not_called()

    def test_only_admin_can_read_settings_and_secrets_are_not_rendered(self):
        self.client.force_login(self.local);self.assertEqual(self.client.get(reverse('sso_settings')).status_code,403)
        self.client.force_login(self.admin);response=self.client.get(reverse('sso_settings'))
        self.assertContains(response,'Gruppen-Objekt-ID');self.assertNotContains(response,'sso-test-secret')
        self.assertContains(response,'https://dev.map.example.org/accounts/microsoft/callback/')

    def test_admin_can_manually_approve_and_assign_stages(self):
        identity=self.identity();self.client.force_login(self.admin)
        response=self.client.post(reverse('sso_settings'),{'action':'identity','identity_id':identity.pk,'approved':'on','stages':[self.other.pk]})
        self.assertEqual(response.status_code,302);identity.refresh_from_db();self.assertTrue(identity.approved)
        from map.access import stage_ids
        self.assertEqual(stage_ids(identity.user,'change'),{self.other.pk});self.assertTrue(SSOAudit.objects.exists())

    def test_invalid_identity_id_is_not_a_server_error(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('sso_settings'),{'action':'identity','identity_id':'invalid'}).status_code,404)

    def test_pending_user_cannot_open_data_routes(self):
        identity=self.identity();self.signin(identity)
        for url in ['/dashboard/','/admin/','/verwaltung/benutzer/','/verwaltung/email/']:
            self.assertRedirects(self.client.get(url),reverse('sso_waiting'))

    def test_session_expires_on_configuration_change_or_block(self):
        identity=self.identity(user=self.local);self.signin(identity)
        self.config.revision=uuid.uuid4();self.config.save()
        self.assertRedirects(self.client.get(reverse('dashboard')),reverse('login'))
        self.config.refresh_from_db();self.signin(identity);identity.blocked=True;identity.save()
        self.assertRedirects(self.client.get(reverse('dashboard')),reverse('login'))

    def test_login_is_prominent_and_local_login_still_works(self):
        response=self.client.get(reverse('login'));self.assertContains(response,'Mit Microsoft anmelden');self.assertContains(response,'Lokale Anmeldung')
        self.assertTrue(self.client.login(username='local',password='Strong-Password-12345'))

    def test_start_is_post_only_and_rate_limit_is_not_shared_by_empty_username(self):
        flow={'auth_uri':'https://login.microsoftonline.com/'+str(self.tenant)+'/oauth2/v2.0/authorize','state':'state','nonce':'nonce'}
        with patch('map.sso_views.client') as app, patch('map.services.throttle',return_value=True) as throttle:
            app.return_value.initiate_auth_code_flow.return_value=flow
            response=self.client.post(reverse('sso_start'))
            self.assertEqual(response.status_code,302);self.assertTrue(response['Location'].startswith('https://login.microsoftonline.com/'))
            self.assertTrue(throttle.call_args.args[0].startswith('sso-start:'))
        self.assertIn('entra_flow',self.client.session)

    def test_missing_or_expired_config_has_clear_error(self):
        self.config.secret_expires_on=timezone.localdate()-timedelta(days=1);self.config.save()
        self.assertContains(self.client.post(reverse('sso_start')),'abgelaufen',status_code=400)

    def test_settings_secret_is_encrypted(self):
        form=SSOSettingsForm({'enabled':'on','tenant_id':str(self.tenant),'client_id':str(self.client_id),'client_secret':'replacement-secret',
             'secret_expires_on':str(timezone.localdate()+timedelta(days=90)),'notification_email':'admins@example.org'},instance=self.config)
        self.assertTrue(form.is_valid(),form.errors);config=form.save()
        self.assertNotIn('replacement-secret',config.client_secret_encrypted)
        self.assertEqual(decrypt_client_secret(config.client_secret_encrypted),'replacement-secret')

    def test_admin_saves_mappings_and_invalidates_old_sessions(self):
        self.client.force_login(self.admin)
        revision=self.config.revision
        response=self.client.post(reverse('sso_settings'),{'action':'settings','enabled':'on','tenant_id':str(self.tenant),
            'client_id':str(self.client_id),'secret_expires_on':str(self.config.secret_expires_on),'notification_email':'alerts@example.org',
            'mapping-TOTAL_FORMS':'1','mapping-INITIAL_FORMS':'0','mapping-MIN_NUM_FORMS':'0','mapping-MAX_NUM_FORMS':'100',
            'mapping-0-stage':str(self.stage.pk),'mapping-0-group_id':str(self.group)})
        self.assertEqual(response.status_code,302)
        self.config.refresh_from_db();self.assertNotEqual(self.config.revision,revision)
        self.assertTrue(EntraStageMapping.objects.filter(group_id=self.group,stage=self.stage).exists())

    def test_real_msal_flow_has_pkce_nonce_and_tenant_bound_endpoints(self):
        import msal
        from urllib.parse import urlsplit,parse_qs
        tenant_url='https://login.microsoftonline.com/'+str(self.tenant)
        class HTTP:
            def get(self,url,**kwargs):
                result=Mock();result.status_code=200;result.headers={}
                result.json.return_value={'authorization_endpoint':tenant_url+'/oauth2/v2.0/authorize',
                    'token_endpoint':tenant_url+'/oauth2/v2.0/token','issuer':tenant_url+'/v2.0',
                    'jwks_uri':tenant_url+'/discovery/v2.0/keys'}
                import json
                result.text=json.dumps(result.json.return_value)
                return result
        app=msal.ConfidentialClientApplication(str(self.client_id),client_credential='test',authority=tenant_url,
            http_client=HTTP(),instance_discovery=False,exclude_scopes=['offline_access'])
        with self.assertWarnsRegex(UserWarning, 'form_post'):
            flow=app.initiate_auth_code_flow(scopes=[],redirect_uri='https://dev.map.example.org/accounts/microsoft/callback/')
        query=parse_qs(urlsplit(flow['auth_uri']).query)
        self.assertEqual(query['code_challenge_method'],['S256']);self.assertTrue(flow['code_verifier'])
        self.assertEqual(query['nonce'],[hashlib.sha256(flow['nonce'].encode('ascii')).hexdigest()])
        self.assertNotIn('offline_access',query['scope'][0]);self.assertIn('openid',query['scope'][0])

    def test_test_login_keeps_admin_and_reports_group_ids_without_tokens(self):
        self.client.force_login(self.admin);self.save_flow('test',user=self.admin)
        with patch('map.sso_views.client') as app,patch('map.sso_views.validate_token',return_value=dict(self.claims,groups=[str(self.group)])):
            app.return_value.acquire_token_by_auth_code_flow.return_value={'id_token':'private-token'}
            self.assertRedirects(self.callback(),reverse('sso_settings'))
        self.assertEqual(int(self.client.session['_auth_user_id']),self.admin.pk)
        self.assertEqual(self.client.session['entra_test']['groups'],[str(self.group)])
        self.assertEqual(EntraIdentity.objects.count(),0)

    def test_no_external_redirect_and_no_missing_state_callback(self):
        self.assertEqual(self.client.get(reverse('sso_callback'),{'code':'x'}).status_code,400)
        self.assertEqual(self.client.get(reverse('sso_start')).status_code,405)
        self.save_flow()
        with patch('map.sso_views.client') as app,patch('map.sso_views.validate_token',return_value=self.claims):
            app.return_value.acquire_token_by_auth_code_flow.return_value={'id_token':'private'}
            response=self.client.get(reverse('sso_callback'),{'state':'expected-state','code':'x','next':'https://evil.invalid/'})
            self.assertEqual(response['Location'],reverse('sso_waiting'))

    def test_signed_id_tokens_validate_signature_audience_issuer_and_nonce(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        flow={'nonce':'nonce'};now=int(time.time())
        claims=dict(self.claims,sub='subject',aud=str(self.client_id),iss='https://login.microsoftonline.com/'+str(self.tenant)+'/v2.0',
            iat=now,nbf=now,exp=now+300,nonce=hashlib.sha256(b'nonce').hexdigest())
        with patch('jwt.PyJWKClient') as jwks:
            jwks.return_value.get_signing_key_from_jwt.return_value=SimpleNamespace(key=key.public_key())
            raw=jwt.encode(claims,key,algorithm='RS256',headers={'kid':'test-key'})
            self.assertEqual(validate_token(raw,self.config,flow)['oid'],claims['oid'])
            for changes in [{'aud':'wrong'},{'iss':'https://attacker.invalid/'},{'exp':now-100},{'nonce':'wrong'},{'tid':str(uuid.uuid4())}]:
                with self.assertRaises(Exception):validate_token(jwt.encode(dict(claims,**changes),key,algorithm='RS256'),self.config,flow)
            wrong=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            with self.assertRaises(jwt.InvalidSignatureError):validate_token(jwt.encode(claims,wrong,algorithm='RS256'),self.config,flow)

    def test_readable_username_preserves_email_case_and_collision_is_safe(self):
        self.claims['email']='MaxMustermann@example.org'
        identity=self.identity();self.assertEqual(identity.user.username,'MaxMustermann#SSO')
        self.claims['oid']=str(uuid.uuid4())
        self.assertEqual(self.identity().user.username,'MaxMustermann-2#SSO')

    def test_pending_logout_refreshes_csrf_and_rejects_missing_token(self):
        from django.test import Client
        identity=self.identity();self.signin(identity)
        strict=Client(enforce_csrf_checks=True);strict.cookies=self.client.cookies
        self.assertEqual(strict.post(reverse('logout')).status_code,403)
        response=strict.get(reverse('logout'),{'fresh':'1'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(strict.post(reverse('logout'),{'csrfmiddlewaretoken':response.json()['csrfToken']}).status_code,302)
        self.assertNotIn('_auth_user_id',strict.session)

    def test_disabled_sso_can_still_logout(self):
        identity=self.identity();self.signin(identity)
        self.config.enabled=False;self.config.save()
        self.assertEqual(self.client.post(reverse('logout')).status_code,302)
        self.assertNotIn('_auth_user_id',self.client.session)
