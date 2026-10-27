import json
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase,Client,override_settings,RequestFactory
from django.urls import reverse
from django.utils import timezone
from map.models import ScoutGroup,FormTemplate,Event,EventGroup,EventPermission,EmailJob,EmailTemplate,LeaderProfile,Registration
from map.forms import EventSettingsForm
from map.setup_forms import TemplateForm
from map.services import register,token_for
from map.mail_templates import system_content
from map.template_access import available_templates
from map.request_security import login_allowed,client_address

@override_settings(SECURE_SSL_REDIRECT=False,MAP_TRUSTED_PROXY_HOSTS=[],MAP_TRUSTED_PROXY_NETWORKS=[],PUBLIC_URL='https://testserver',DEBUG=False)
class MvpAuditTests(TestCase):
    def setUp(self):
        users=get_user_model();self.admin=users.objects.create_superuser('auditadmin','admin@example.org','Strong-Audit-Pass-901!')
        self.leader=users.objects.create_user('auditleader');self.foreign=users.objects.create_user('auditforeign')
        self.stage=ScoutGroup.objects.create(name='Audit Wös');self.other_stage=ScoutGroup.objects.create(name='Audit Juffis')
        profile=LeaderProfile.objects.create(user=self.leader,is_leader=True);profile.stages.add(self.stage)
        self.template=FormTemplate.objects.create(name='Eigenes Formular',created_by=self.leader)
        self.secret_template=FormTemplate.objects.create(name='Fremdes privates Formular',created_by=self.foreign)
        now=timezone.now()
        self.event=Event.objects.create(title='Auditlager',slug='auditlager',group=self.stage,form_template=self.template,published=True,capacity=100,starts_at=now+timedelta(days=10),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=8),confirmation_required=False)
        EventGroup.objects.create(event=self.event,group=self.stage,capacity=100)
        self.client.force_login(self.leader)
    def data(self,**extra):
        data={'title':self.event.title,'description':'','group_limits':json.dumps({str(self.stage.pk):100}),'starts_at':self.event.starts_at.isoformat(),'registration_opens':self.event.registration_opens.isoformat(),'registration_closes':self.event.registration_closes.isoformat(),'confirmation_hours':'48','form_template':self.template.pk,'cost_mode':'free'}
        data.update(extra);return data
    def test_rotating_usernames_cannot_bypass_ip_login_limit(self):
        factory=RequestFactory()
        for index in range(60):self.assertTrue(login_allowed(factory.post('/accounts/login/',{'username':'name'+str(index)},REMOTE_ADDR='198.51.100.9')))
        self.assertFalse(login_allowed(factory.post('/accounts/login/',{'username':'another'},REMOTE_ADDR='198.51.100.9')))
    def test_distributed_attempts_at_same_account_are_limited(self):
        factory=RequestFactory()
        for index in range(30):self.assertTrue(login_allowed(factory.post('/accounts/login/',{'username':'target'},REMOTE_ADDR='198.51.100.'+str(index+1))))
        self.assertFalse(login_allowed(factory.post('/accounts/login/',{'username':'target'},REMOTE_ADDR='203.0.113.9')))
    def test_proxy_dns_is_only_used_as_explicitly_configured(self):
        request=RequestFactory().get('/',REMOTE_ADDR='172.18.0.2',HTTP_X_FORWARDED_FOR='198.51.100.7')
        self.assertEqual(client_address(request),'172.18.0.2')
        with override_settings(MAP_TRUSTED_PROXY_HOSTS=['caddy']),patch('map.request_security.proxy_addresses',return_value=('172.18.0.2',)):
            self.assertEqual(client_address(request),'198.51.100.7')
    def test_login_limiter_returns_german_page_and_retry_header(self):
        self.client.logout()
        with patch('map.request_security.login_allowed',return_value=False):response=self.client.post('/accounts/login/',{'username':'x','password':'y'})
        self.assertEqual(response.status_code,429);self.assertEqual(response['Retry-After'],'900');self.assertContains(response,'Bitte kurz warten',status_code=429)
    def test_recipient_limit_prevents_name_rotation_mail_flood(self):
        self.client.logout();url=reverse('event',args=[self.event.slug])
        for index in range(10):
            response=self.client.post(url,{'child_name':'Kind '+str(index),'email':'same@example.org','consent':'on'})
            self.assertEqual(response.status_code,200)
        response=self.client.post(url,{'child_name':'Noch ein Kind','email':'same@example.org','consent':'on'})
        self.assertEqual(response.status_code,429);self.assertEqual(Registration.objects.count(),10);self.assertEqual(EmailJob.objects.count(),10)
    def test_extreme_confirmation_period_is_form_error(self):
        for value in ['0','2147483647']:
            form=EventSettingsForm(self.data(confirmation_hours=value),instance=self.event,actor=self.leader)
            self.assertFalse(form.is_valid());self.assertIn('confirmation_hours',form.errors)
    def test_old_invalid_period_cannot_break_public_registration(self):
        self.event.confirmation_required=True;self.event.confirmation_hours=2147483647;self.event.save()
        row=register(self.event.pk,'Kind','parent@example.org',{})
        self.assertLessEqual(row.confirmation_deadline-timezone.now(),timedelta(hours=8760))
    def test_editor_cannot_move_registration_deadline_past_start(self):
        form=EventSettingsForm(self.data(registration_closes=(self.event.starts_at+timedelta(days=1)).isoformat()),instance=self.event,actor=self.leader)
        self.assertFalse(form.is_valid());self.assertIn('registration_closes',form.errors)
    def test_unicode_group_identifier_gives_form_error_not_exception(self):
        for key in ['²','١٢','9'*100]:
            response=self.client.post(reverse('event_settings',args=[self.event.pk]),self.data(group_limits=json.dumps({key:20})))
            self.assertEqual(response.status_code,200);self.assertTrue(response.context['form'].errors)
    def test_private_foreign_template_cannot_be_selected_or_read_from_library(self):
        self.assertFalse(available_templates(self.leader).filter(pk=self.secret_template.pk).exists())
        form=TemplateForm(actor=self.leader)
        self.assertNotIn(str(self.secret_template.pk),form.fields['schema_json'].widget.get_context('schema_json','[]',{})['widget']['templates_data'])
        response=self.client.get(reverse('template_options',args=[self.event.pk]))
        self.assertNotIn(self.secret_template.pk,[item['id'] for item in response.json()['templates']])
    def test_forged_private_template_selection_is_rejected(self):
        response=self.client.post(reverse('event_settings',args=[self.event.pk]),self.data(form_template=self.secret_template.pk))
        self.assertEqual(response.status_code,200);self.assertIn('form_template',response.context['form'].errors)
        self.event.refresh_from_db();self.assertEqual(self.event.form_template_id,self.template.pk)
    def test_shared_standard_and_global_manager_access_are_preserved(self):
        standard=FormTemplate.objects.create(name='Gemeinsamer Standard')
        self.assertTrue(available_templates(self.leader).filter(pk=standard.pk).exists())
        self.leader.groups.add(Group.objects.get(name='Manager'))
        self.assertTrue(available_templates(self.leader).filter(pk=self.secret_template.pk).exists())
    def test_accessible_event_template_remains_available(self):
        self.event.form_template=self.secret_template;self.event.save()
        self.assertTrue(available_templates(self.leader).filter(pk=self.secret_template.pk).exists())
    def test_personal_page_referrer_policy_does_not_disclose_token_path(self):
        row=register(self.event.pk,'Kind','parent@example.org',{})
        self.client.logout();response=self.client.get(reverse('manage',args=[token_for(row,'manage')]))
        self.assertEqual(response['Referrer-Policy'],'strict-origin');self.assertEqual(response['Cache-Control'],'no-store')
    def test_strict_origin_referer_still_allows_csrf_protected_edit(self):
        row=register(self.event.pk,'Kind','parent@example.org',{});url=reverse('manage',args=[token_for(row,'manage')])
        client=Client(enforce_csrf_checks=True);client.get(url,secure=True)
        response=client.post(url,{'action':'save','csrfmiddlewaretoken':client.cookies['csrftoken'].value},secure=True,HTTP_REFERER='https://testserver/')
        self.assertEqual(response.status_code,302)
    def test_foreign_origin_cannot_cancel_registration(self):
        row=register(self.event.pk,'Kind','parent@example.org',{});url=reverse('manage',args=[token_for(row,'manage')])
        client=Client(enforce_csrf_checks=True);client.get(url,secure=True)
        response=client.post(url,{'action':'cancel','cancel_confirm':'yes','csrfmiddlewaretoken':client.cookies['csrftoken'].value},secure=True,HTTP_ORIGIN='https://evil.invalid')
        self.assertEqual(response.status_code,403);row.refresh_from_db();self.assertEqual(row.status,'confirmed')
    def test_native_ids_and_queue_ids_are_bounded(self):
        self.client.force_login(self.admin)
        for path in ['/admin/auth/user/²/change/','/admin/auth/group/²/change/','/admin/map/event/²/change/']:
            self.assertEqual(self.client.get(path).status_code,404)
        for value in ['²','9'*100]:self.assertEqual(self.client.post(reverse('mail_queue'),{'action':'retry','job_id':value}).status_code,400)
    def test_corrupt_stored_mail_template_does_not_break_registration(self):
        EmailTemplate.objects.create(key='registration',subject='Kaputt',body='{unknown}')
        with self.assertLogs('map.mail',level='WARNING'):
            row=register(self.event.pk,'Kind','parent@example.org',{})
        self.assertEqual(EmailJob.objects.get(registration=row).subject,'Anmeldung eingegangen – Auditlager')
    def test_corrupt_template_can_be_opened_for_repair(self):
        EmailTemplate.objects.create(key='registration',subject='Kaputt',body='{unknown}')
        self.client.force_login(self.admin)
        response=self.client.get(reverse('email_template_edit',args=['registration']))
        self.assertEqual(response.status_code,200);self.assertContains(response,'gespeicherte Vorlage ist ungültig')
    def test_large_registration_list_is_paginated(self):
        for index in range(51):register(self.event.pk,'Kind '+str(index),'parent@example.org',{})
        response=self.client.get(reverse('event_admin',args=[self.event.pk]))
        self.assertEqual(response.context['registration_count'],51);self.assertEqual(len(response.context['rows']),50)
        self.assertContains(response,'Nächste Seite')
        response=self.client.get(reverse('event_admin',args=[self.event.pk]),{'page':2})
        self.assertEqual(len(response.context['rows']),1)
    def test_generic_error_pages_do_not_leak_exception_details(self):
        self.client.logout();response=self.client.get('/missing-audit-page/')
        self.assertEqual(response.status_code,404);self.assertContains(response,'Seite nicht gefunden',status_code=404)
        from map.error_views import csrf_failure,server_error
        request=RequestFactory().get('/')
        self.assertNotIn('PRIVATE-SECRET',csrf_failure(request,'PRIVATE-SECRET').content.decode())
        self.assertEqual(server_error(request).status_code,500)
    def test_login_next_parameter_cannot_redirect_to_foreign_site(self):
        self.client.logout()
        response=self.client.post('/accounts/login/?next=https://evil.invalid/',{'username':'auditadmin','password':'Strong-Audit-Pass-901!'})
        self.assertEqual(response.status_code,302);self.assertEqual(response['Location'],'/dashboard/')

    def test_custom_credentials_are_redacted_from_error_reports(self):
        from django.views.debug import SafeExceptionReporterFilter
        self.client.force_login(self.admin)
        cases=[(reverse('person_new'),{'new_password':'PRIVATE-PASSWORD-123!'},['new_password']),
               (reverse('mail_settings'),{'enabled':'on','provider':'microsoft_graph','password':'PRIVATE-SMTP-123!','client_secret':'PRIVATE-APP-123!'},['password','client_secret'])]
        for url,data,fields in cases:
            response=self.client.post(url,data)
            self.assertEqual(response.status_code,200)
            filtered=SafeExceptionReporterFilter().get_post_parameters(response.wsgi_request)
            for field in fields:self.assertNotEqual(filtered[field],data[field])
