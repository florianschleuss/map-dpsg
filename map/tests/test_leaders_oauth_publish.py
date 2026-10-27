from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase,Client,RequestFactory,override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import ScoutGroup,LeaderProfile,Event,EventGroup,EventPermission,FormTemplate,MailConfiguration,AuditLog
from map.roles import can_create_events,visible_events,require_creation_stages
from map.services import permitted
from map.setup_forms import BasicsForm,AccessForm
from map.mail_admin import MailConfigurationForm,mail_error_message
from map.mailer import encrypt_password,decrypt_client_secret,test_credentials,send_mail
from map.microsoft_mail import MicrosoftMailError

@override_settings(SECURE_SSL_REDIRECT=False)
class LeaderAndPublicationTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.admin=User.objects.create_superuser(username='admin8',email='admin@example.org',password='Strong-admin-pass-593!')
        self.leader=User.objects.create_user(username='leader8')
        self.other=User.objects.create_user(username='other8')
        self.a=ScoutGroup.objects.create(name='Wölflinge');self.b=ScoutGroup.objects.create(name='Rover')
        self.profile=LeaderProfile.objects.create(user=self.leader,is_leader=True);self.profile.stages.add(self.a)
        self.template=FormTemplate.objects.create(name='Formular')
        now=timezone.now()
        self.event=Event.objects.create(title='Nur Wölflinge',slug='only-a8',group=self.a,form_template=self.template,starts_at=now+timedelta(days=30),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=20))
        EventGroup.objects.create(event=self.event,group=self.a,capacity=20)
        self.foreign=Event.objects.create(title='Nur Rover',slug='only-b8',group=self.b,form_template=self.template,starts_at=self.event.starts_at,registration_opens=self.event.registration_opens,registration_closes=self.event.registration_closes)
        EventGroup.objects.create(event=self.foreign,group=self.b,capacity=20)
    def login(self,user=None):self.client.force_login(user or self.leader)
    def test_assigned_leader_can_read_edit_and_create(self):
        self.assertTrue(can_create_events(self.leader));self.assertTrue(permitted(self.leader,self.event,True))
        self.assertEqual(set(visible_events(self.leader).values_list('pk',flat=True)),{self.event.pk})
        require_creation_stages(self.leader,[self.a])
        with self.assertRaises(ValidationError):require_creation_stages(self.leader,[self.b])
    def creation_data(self):
        return [{'title':'Neues Stufenlager','description':'Für unsere Stufe','groups':ScoutGroup.objects.filter(pk=self.a.pk)}, {'starts_at':self.event.starts_at,'registration_opens':self.event.registration_opens,'registration_closes':self.event.registration_closes}, {'capacity':20,'waitlist_enabled':True,'confirmation_required':False,'confirmation_hours':48}, {'form_template':self.template}, {'viewers':[],'editors':[]}]
    def test_creation_service_accepts_assigned_leader(self):
        from map.event_wizard import create_event
        event=create_event(self.creation_data(),False,'leader-create-8',self.leader)
        self.assertFalse(event.published);self.assertTrue(permitted(self.leader,event,True))
        self.assertFalse(EventPermission.objects.filter(event=event,user=self.leader).exists())
    def test_creation_rechecks_stage_rights_after_draft_was_validated(self):
        from map.event_wizard import create_event
        data=self.creation_data();self.profile.stages.set([self.b])
        with self.assertRaises(ValidationError):create_event(data,False,'stale-create-8',self.leader)
        self.assertFalse(Event.objects.filter(title='Neues Stufenlager').exists())
    def test_creation_cannot_add_other_stages_via_forged_cleaned_data(self):
        from map.event_wizard import create_event
        data=self.creation_data();data[0]['groups']=ScoutGroup.objects.all()
        with self.assertRaises(ValidationError):create_event(data,False,'forged-create-8',self.leader)
    def test_leader_cannot_read_foreign_stage(self):
        self.assertFalse(permitted(self.leader,self.foreign));self.login()
        self.assertEqual(self.client.get(reverse('event_admin',args=[self.foreign.pk])).status_code,403)
    def test_mixed_event_is_visible_but_edit_needs_all_stages(self):
        EventGroup.objects.create(event=self.event,group=self.b,capacity=10)
        self.assertTrue(permitted(self.leader,self.event));self.assertFalse(permitted(self.leader,self.event,True))
        self.profile.stages.add(self.b);self.assertTrue(permitted(self.leader,self.event,True))
    def test_explicit_editor_can_edit_collaborative_event(self):
        EventGroup.objects.create(event=self.event,group=self.b,capacity=10)
        EventPermission.objects.create(event=self.event,user=self.leader,role='editor')
        self.assertTrue(permitted(self.leader,self.event,True))
    def test_leader_revocation_removes_automatic_rights(self):
        self.profile.is_leader=False;self.profile.save()
        self.assertFalse(can_create_events(self.leader));self.assertFalse(permitted(self.leader,self.event))
    def test_stage_removal_takes_effect_without_new_login(self):
        self.profile.stages.clear();self.assertFalse(permitted(self.leader,self.event));self.assertFalse(can_create_events(self.leader))
    def test_readonly_overrides_stage_write_and_explicit_editor(self):
        self.leader.groups.add(Group.objects.get(name='Read-Only'))
        EventPermission.objects.create(event=self.event,user=self.leader,role='editor')
        self.assertTrue(permitted(self.leader,self.event));self.assertFalse(permitted(self.leader,self.event,True));self.assertFalse(can_create_events(self.leader))
    def test_wizard_group_selection_rejects_forged_stage(self):
        form=BasicsForm({'title':'Fremde Stufe','groups':[self.b.pk]},actor=self.leader)
        self.assertFalse(form.is_valid());self.assertIn('groups',form.errors)
    def test_wizard_lists_only_assigned_stages(self):
        form=BasicsForm(actor=self.leader)
        self.assertEqual(list(form.fields['groups'].queryset),[self.a])
        self.login();self.assertEqual(self.client.get('/admin/veranstaltung-anlegen/').status_code,302)
    def test_nonadmin_cannot_grant_event_access_in_wizard(self):
        form=AccessForm({'editors':[self.other.pk]},actor=self.leader)
        self.assertFalse(form.is_valid())
    def test_native_user_form_uses_leader_status_and_no_staff_field(self):
        self.login(self.admin)
        response=self.client.get(reverse('admin:auth_user_change',args=[self.leader.pk]))
        self.assertEqual(response.status_code,200)
        form=response.context['form']
        self.assertIn('is_leader',form.fields)
        self.assertIn('leader_stages',form.fields)
        self.assertTrue(form.initial['is_leader'])
        self.assertEqual(set(form.initial['leader_stages']),{self.a.pk})
        self.assertContains(response,'name="is_leader"')
        self.assertContains(response,'name="leader_stages"')
        self.assertNotContains(response,'name="is_staff"')
    def test_admin_user_save_persists_leader_profile_and_stages(self):
        User=get_user_model();modeladmin=admin.site._registry[User]
        request=RequestFactory().post('/');request.user=self.admin
        form=SimpleNamespace(cleaned_data={'is_leader':True,'leader_stages':[self.b]})
        modeladmin.save_model(request,self.other,form,True)
        profile=LeaderProfile.objects.get(user=self.other)
        self.assertTrue(profile.is_leader);self.assertEqual(list(profile.stages.all()),[self.b]);self.assertFalse(self.other.is_staff)
    def test_leader_cannot_open_user_admin(self):
        self.login();self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code,302)
    def test_dashboard_shows_publish_button_for_own_draft(self):
        self.login();response=self.client.get(reverse('dashboard'))
        self.assertContains(response,reverse('publish_event',args=[self.event.pk]));self.assertContains(response,'Veröffentlichen')
        self.assertNotContains(response,self.foreign.title)
    def test_publish_is_post_only_and_idempotent(self):
        self.login();url=reverse('publish_event',args=[self.event.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url,{'return_to':'dashboard'}).url,reverse('dashboard'))
        self.event.refresh_from_db();self.assertTrue(self.event.published)
        self.client.post(url);self.assertEqual(AuditLog.objects.filter(event=self.event,action='Veranstaltung veröffentlicht').count(),1)
    def test_reader_and_outsider_cannot_publish(self):
        self.leader.groups.add(Group.objects.get(name='Read-Only'))
        for actor in [self.leader,self.other]:
            self.login(actor);self.assertEqual(self.client.post(reverse('publish_event',args=[self.event.pk])).status_code,403)
    def test_publish_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.leader)
        self.assertEqual(client.post(reverse('publish_event',args=[self.event.pk])).status_code,403)
    def test_foreign_unused_template_cannot_be_edited(self):
        unused=FormTemplate.objects.create(name='Fremde ungenutzte Vorlage');self.login();self.assertEqual(self.client.get(reverse('map_form_builder',args=[unused.pk])).status_code,403)
    def test_owned_unused_template_can_be_edited(self):
        unused=FormTemplate.objects.create(name='Eigene ungenutzte Vorlage',created_by=self.leader);self.login()
        self.assertEqual(self.client.get(reverse('map_form_builder',args=[unused.pk])).status_code,200)
    def test_shared_template_cannot_be_changed_without_all_event_rights(self):
        self.login();self.assertEqual(self.client.get(reverse('map_form_builder',args=[self.template.pk])).status_code,403)
    def test_new_template_requires_accessible_event_context(self):
        self.login();url=reverse('map_form_builder_new')
        self.assertEqual(self.client.get(url+'?event='+str(self.foreign.pk)).status_code,403)
        self.assertEqual(self.client.get(url+'?event='+str(self.event.pk)).status_code,200)

@override_settings(SECURE_SSL_REDIRECT=False,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MicrosoftConfigurationTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='msadmin8',email='admin@example.org',password='Strong-admin-pass-593!')
        self.client.force_login(self.admin)
    def data(self,**updates):
        result={'enabled':'on','provider':'microsoft_graph','from_email':'map@example.org','tenant_id':'11111111-1111-1111-1111-111111111111','client_id':'22222222-2222-2222-2222-222222222222','client_secret':'Dummy-App-Secret-8!','client_secret_expires_on':'2027-12-01'}
        result.update(updates);return result
    def config(self):
        form=MailConfigurationForm(self.data());self.assertTrue(form.is_valid(),form.errors);return form.save()
    def test_graph_needs_no_smtp_host(self):
        config=self.config();self.assertEqual(config.host,'');self.assertEqual(config.provider,'microsoft_graph')
    def test_secret_is_encrypted_preserved_and_never_rendered(self):
        config=self.config();encrypted=config.client_secret_encrypted
        self.assertNotIn('Dummy-App-Secret-8!',encrypted);self.assertEqual(decrypt_client_secret(encrypted),'Dummy-App-Secret-8!')
        form=MailConfigurationForm(self.data(client_secret=''),instance=config);self.assertTrue(form.is_valid(),form.errors);form.save();config.refresh_from_db();self.assertEqual(config.client_secret_encrypted,encrypted)
        self.assertNotContains(self.client.get(reverse('mail_settings')),'Dummy-App-Secret-8!')
    def test_missing_or_invalid_ids_and_secret_are_form_errors(self):
        for fields in [{'tenant_id':''},{'client_id':'not-a-uuid'},{'client_secret':''}]:self.assertFalse(MailConfigurationForm(self.data(**fields)).is_valid())
    def test_active_secret_cannot_be_cleared_without_replacement(self):
        config=self.config();form=MailConfigurationForm(self.data(client_secret='',clear_client_secret='on'),instance=config)
        self.assertFalse(form.is_valid())
    def test_credentials_probe_only_requests_token(self):
        config=self.config()
        with patch('map.microsoft_mail.access_token',return_value='token') as token,patch('map.microsoft_mail.send_graph') as send:
            message=test_credentials(config)
        self.assertTrue(token.call_args.kwargs['fresh']);send.assert_not_called();self.assertIn('noch nicht bestätigt',message)
    def test_credentials_button_works_without_test_recipient(self):
        with patch('map.mail_admin.test_credentials',return_value='Anmeldung erfolgreich.') as check,patch('map.mail_admin.send_mail') as send:
            response=self.client.post(reverse('mail_settings'),self.data(action='check'))
        self.assertEqual(response.status_code,302);check.assert_called_once();send.assert_not_called()
        self.assertTrue(MailConfiguration.objects.get(pk=1).enabled)
    def test_probe_failure_is_german_and_does_not_expose_secret(self):
        with patch('map.mail_admin.test_credentials',side_effect=MicrosoftMailError('ms_secret_expired',7000222)):
            response=self.client.post(reverse('mail_settings'),self.data(action='check'),follow=True)
        self.assertContains(response,'abgelaufen');self.assertNotContains(response,'Dummy-App-Secret-8!')
        self.assertContains(response,'map-alert-error')
    def test_graph_sender_uses_saved_secret_and_postbox(self):
        self.config()
        with patch('map.microsoft_mail.send_graph',return_value=1) as send,patch('map.mailer.get_connection') as smtp:
            self.assertEqual(send_mail('Betreff','Text','fallback@example.org',['a@example.org']),1)
        self.assertEqual(send.call_args.args[0].from_email,'map@example.org');self.assertEqual(send.call_args.args[1],'Dummy-App-Secret-8!');smtp.assert_not_called()
    def test_provider_error_messages_are_controlled(self):
        self.assertIn('Postfach',mail_error_message(MicrosoftMailError('ms_mailbox_permission')))
        self.assertNotIn('PRIVATE',mail_error_message(RuntimeError('PRIVATE')))
    def test_secrets_cannot_be_decrypted_after_key_change(self):
        config=self.config()
        with override_settings(SECRET_KEY='different-key'):
            with self.assertRaises(ValidationError):decrypt_client_secret(config.client_secret_encrypted)
    def test_disabled_settings_do_not_claim_credentials_were_checked(self):
        self.assertIn('keine eigenen Zugangsdaten geprüft',test_credentials(MailConfiguration(enabled=False)))
    def test_german_buttons_and_privacy_sections_render(self):
        response=self.client.get(reverse('mail_settings'))
        for label in ['Zugangsdaten prüfen','Testmail senden','Microsoft 365']:self.assertContains(response,label)
        response=self.client.get(reverse('privacy'))
        for label in ['map-privacy-summary','privacy-2','Leitendenstatus','Microsoft Graph']:self.assertContains(response,label)
