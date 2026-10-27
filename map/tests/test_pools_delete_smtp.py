import json
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import ScoutGroup, Event, EventGroup, FormTemplate, FormModule, Registration, EventPermission, AuditLog, EmailJob, MailConfiguration
from map.services import register, cancel, rebalance, token_for
from map.forms import EventSettingsForm
from map.deletion import delete_event
from map.mail_admin import MailConfigurationForm
from map.mailer import encrypt_password, decrypt_password, send_mail

class EventFixture:
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='admin7',email='admin@example.org',password='Strong-admin-593!')
        self.manager=get_user_model().objects.create_user(username='manager7')
        self.manager.groups.add(Group.objects.get(name='Manager'))
        self.reader=get_user_model().objects.create_user(username='reader7')
        self.reader.groups.add(Group.objects.get(name='Read-Only'))
        self.a=ScoutGroup.objects.create(name='Wölflinge');self.b=ScoutGroup.objects.create(name='Rover')
        self.template=FormTemplate.objects.create(name='Formular')
        now=timezone.now()
        self.event=Event.objects.create(group=self.a,form_template=self.template,title='SoLa',slug='sola7',capacity=2,published=True,confirmation_required=False,starts_at=now+timedelta(days=24),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=20))
        self.sa=EventGroup.objects.create(event=self.event,group=self.a,capacity=1)
        self.sb=EventGroup.objects.create(event=self.event,group=self.b,capacity=1)
    def reg(self,name,group): return register(self.event.pk,name,'eltern@example.org',{},group_id=group.pk)
    def settings_data(self):
        date=lambda value:timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')
        return {'title':self.event.title,'description':'','group_limits':json.dumps({str(self.a.pk):1,str(self.b.pk):1}),'starts_at':date(self.event.starts_at),'registration_opens':date(self.event.registration_opens),'registration_closes':date(self.event.registration_closes),'published':'on','waitlist_enabled':'on','show_availability':'on','confirmation_hours':'48','form_template':str(self.template.pk),'capacity_mode':'per_group','waitlist_mode':'per_group'}

@override_settings(SECURE_SSL_REDIRECT=False)
class PoolTests(EventFixture,TestCase):
    def test_shared_pool_allows_multiple_children_from_one_stage(self):
        self.event.capacity_mode='shared';self.event.capacity=3;self.event.save()
        for i in range(3):self.assertEqual(self.reg('Kind '+str(i),self.a).status,'confirmed')
        self.assertEqual(self.reg('Weiteres Kind',self.b).status,'waitlisted')
    def test_shared_pool_promotes_oldest_waiter_across_stages(self):
        self.event.capacity_mode='shared';self.event.capacity=1;self.event.save()
        first=self.reg('Erstes',self.a);older=self.reg('Zweites',self.b);newer=self.reg('Drittes',self.a)
        cancel(first.pk);older.refresh_from_db();newer.refresh_from_db()
        self.assertEqual(older.status,'confirmed');self.assertEqual(newer.status,'waitlisted')
    def test_shared_waitlist_respects_stage_limits_and_skips_ineligible_front(self):
        self.event.waitlist_mode='shared';self.event.save()
        a=self.reg('A',self.a);self.reg('B',self.b)
        first=self.reg('B Warteliste',self.b);second=self.reg('A Warteliste',self.a)
        cancel(a.pk);first.refresh_from_db();second.refresh_from_db()
        self.assertEqual(first.status,'waitlisted');self.assertEqual(second.status,'confirmed')
    def test_pool_settings_keep_the_selected_total_instead_of_summing_stage_fields(self):
        data=self.settings_data();data.update(capacity_mode='shared',shared_capacity='5',waitlist_mode='shared')
        form=EventSettingsForm(data,instance=self.event,actor=self.admin)
        self.assertTrue(form.is_valid(),form.errors);form.save();self.event.refresh_from_db()
        self.assertEqual(self.event.capacity,5);self.assertEqual(self.event.capacity_mode,'shared')
    def test_pool_cannot_shrink_below_occupied_total(self):
        self.event.capacity_mode='shared';self.event.save();self.reg('A',self.a);self.reg('B',self.b)
        data=self.settings_data();data.update(capacity_mode='shared',shared_capacity='1')
        form=EventSettingsForm(data,instance=self.event,actor=self.admin)
        self.assertFalse(form.is_valid())
    def test_parent_page_can_hide_all_capacity_numbers(self):
        self.event.show_availability=False;self.event.save()
        response=self.client.get(reverse('event',args=[self.event.slug]))
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'Plätze je Stufe')
        self.assertNotContains(response,'Plätze insgesamt')
        self.assertNotContains(response,'Insgesamt 2 Plätze')
        self.assertContains(response,'Ein Kind anmelden')
    def test_parent_shared_pool_displays_total_and_not_ignored_stage_quotas(self):
        self.event.capacity_mode='shared';self.event.capacity=7;self.event.save()
        response=self.client.get(reverse('event',args=[self.event.slug]))
        self.assertContains(response,'Gemeinsamer Platzpool');self.assertContains(response,'7 Plätze insgesamt')
        self.assertNotContains(response,'Plätze je Stufe')
    def test_final_form_renders_module_headings(self):
        FormModule.objects.create(template=self.template,title='Kontakt im Notfall')
        response=self.client.get(reverse('event',args=[self.event.slug]))
        self.assertContains(response,'<h3>Kontakt im Notfall</h3>',html=True)
    def test_dashboard_has_metrics_and_modal_not_expanding_qr_details(self):
        self.reg('Kind',self.a);self.client.force_login(self.manager)
        response=self.client.get('/dashboard/')
        self.assertContains(response,'Plätze belegt oder reserviert')
        self.assertContains(response,'bis zur Veranstaltung')
        self.assertContains(response,'<dialog')
        self.assertNotContains(response,'QR-Code anzeigen und herunterladen')
    def test_event_detail_has_export_at_table_header_and_no_template_editor(self):
        self.client.force_login(self.manager);response=self.client.get(reverse('event_admin',args=[self.event.pk]))
        text=response.content.decode();self.assertLess(text.index('Einträge'),text.index('CSV exportieren'))
        self.assertNotContains(response,'data-template-picker')
        self.assertNotContains(response,'Neue Formularvorlage anlegen')
        response=self.client.get(reverse('event_settings',args=[self.event.pk]))
        self.assertContains(response,'data-template-picker')
        self.assertContains(response,'Neue Formularvorlage anlegen')
    def test_template_refresh_requires_event_edit_rights(self):
        url=reverse('template_options',args=[self.event.pk]);self.client.force_login(self.reader)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.manager);response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['templates'][0]['id'],self.template.pk)
    def test_privacy_page_is_public_and_links_from_footer(self):
        response=self.client.get('/datenschutz/')
        for text in ['Welche Daten','Notfallkontakt','SMTP','Hosting','bis die Veranstaltung','Sicherungen']:
            self.assertContains(response,text)
        self.assertContains(self.client.get('/accounts/login/'),'href="/datenschutz/"')

@override_settings(SECURE_SSL_REDIRECT=False)
class DeletionTests(EventFixture,TestCase):
    def test_delete_removes_registrations_jobs_rights_audit_and_exclusive_template(self):
        row=self.reg('Kind',self.a);EventPermission.objects.create(event=self.event,user=self.reader,role='viewer')
        AuditLog.objects.create(event=self.event,actor=self.admin,action='edit event settings')
        token=token_for(row,'manage');event_id=self.event.pk;template_id=self.template.pk
        self.assertTrue(EmailJob.objects.filter(event=self.event).exists())
        delete_event(event_id,self.manager)
        for model in [Event,Registration,EmailJob,EventPermission,AuditLog,EventGroup]:self.assertEqual(model.objects.count(),0)
        self.assertFalse(FormTemplate.objects.filter(pk=template_id).exists())
        self.assertEqual(ScoutGroup.objects.count(),2)
        self.assertEqual(self.client.get('/manage/'+token+'/').status_code,400)
    def test_stale_resend_after_deletion_does_not_recreate_email_data(self):
        from map.services import queue_message
        row=self.reg('Kind',self.a)
        delete_event(self.event.pk,self.manager)
        queue_message(row,'Veraltete Anfrage')
        self.assertEqual(EmailJob.objects.count(),0)
    def test_shared_template_and_other_event_are_preserved(self):
        other=Event.objects.create(group=self.a,form_template=self.template,title='Anderes Lager',slug='anderes-lager',capacity=3,starts_at=self.event.starts_at,registration_opens=self.event.registration_opens,registration_closes=self.event.registration_closes)
        delete_event(self.event.pk,self.manager)
        self.assertTrue(Event.objects.filter(pk=other.pk).exists());self.assertTrue(FormTemplate.objects.filter(pk=self.template.pk).exists())
    def test_delete_requires_post_explicit_confirmation_and_write_rights(self):
        url=reverse('event_delete',args=[self.event.pk]);self.client.force_login(self.reader)
        self.assertEqual(self.client.post(url,{'confirm_delete':'delete'}).status_code,403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(url).status_code,200);self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
        self.assertEqual(self.client.post(url,{}).status_code,400)
        self.assertEqual(self.client.post(url,{'confirm_delete':'delete'}).status_code,302)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())
    def test_delete_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.manager)
        self.assertEqual(client.post(reverse('event_delete',args=[self.event.pk]),{'confirm_delete':'delete'}).status_code,403)
    def test_native_admin_logs_with_child_names_are_removed(self):
        row=self.reg('Privater Kindname',self.a)
        LogEntry.objects.create(user=self.admin,content_type=ContentType.objects.get_for_model(Registration),object_id=str(row.pk),object_repr=str(row),action_flag=CHANGE,change_message='')
        delete_event(self.event.pk,self.manager)
        self.assertFalse(LogEntry.objects.filter(object_repr__contains='Privater Kindname').exists())
    def test_repeated_service_deletion_is_safe(self):
        pk=self.event.pk;delete_event(pk,self.manager);delete_event(pk,self.manager)
        self.assertFalse(Event.objects.filter(pk=pk).exists())

@override_settings(SECURE_SSL_REDIRECT=False,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SMTPTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='mailadmin',email='admin@example.org',password='Strong-admin-pass-593!')
        self.manager=get_user_model().objects.create_user(username='mailmanager');self.manager.groups.add(Group.objects.get(name='Manager'))
    def data(self,**updates):
        data={'enabled':'on','host':'smtp.example.org','port':'587','security':'starttls','username':'mail-user','from_email':'anmeldung@example.org','password':'Dummy-Secret-593!'};data.update(updates);return data
    def test_encryption_round_trip_is_not_plaintext(self):
        encrypted=encrypt_password('Dummy-Secret-593!')
        self.assertNotIn('Dummy-Secret-593!',encrypted);self.assertEqual(decrypt_password(encrypted),'Dummy-Secret-593!')
    def test_password_is_preserved_when_field_is_empty(self):
        form=MailConfigurationForm(self.data());self.assertTrue(form.is_valid(),form.errors);config=form.save();old=config.password_encrypted
        form=MailConfigurationForm(self.data(password=''),instance=config);self.assertTrue(form.is_valid(),form.errors);form.save();config.refresh_from_db()
        self.assertEqual(config.password_encrypted,old)
    def test_password_is_not_rendered_back_to_browser(self):
        form=MailConfigurationForm(self.data());self.assertTrue(form.is_valid());form.save();self.client.force_login(self.admin)
        response=self.client.get(reverse('mail_settings'));self.assertNotContains(response,'Dummy-Secret-593!');self.assertContains(response,'verschlüsselt gespeichert')
    def test_manager_cannot_access_smtp_or_queue(self):
        self.client.force_login(self.manager)
        for name in ['mail_settings','mail_queue']:self.assertEqual(self.client.get(reverse(name)).status_code,403)
    def test_external_smtp_requires_transport_encryption_and_valid_port(self):
        self.assertFalse(MailConfigurationForm(self.data(security='plain')).is_valid())
        self.assertFalse(MailConfigurationForm(self.data(port='0')).is_valid())
    def test_configured_sender_and_starttls_used(self):
        form=MailConfigurationForm(self.data());self.assertTrue(form.is_valid());form.save()
        connection=MagicMock()
        with patch('map.mailer.get_connection',return_value=connection) as connect,patch('map.mailer.django_send_mail',return_value=1) as send:
            send_mail('Betreff','Nachricht','fallback@example.org',['target@example.org'])
            self.assertTrue(connect.call_args.kwargs['use_tls']);self.assertFalse(connect.call_args.kwargs['use_ssl'])
            self.assertEqual(connect.call_args.kwargs['password'],'Dummy-Secret-593!')
            from email.utils import parseaddr
            self.assertEqual(parseaddr(send.call_args.args[2])[1],'anmeldung@example.org')
            from email.header import decode_header,make_header
            self.assertIn('Anmeldungsverwaltung',str(make_header(decode_header(parseaddr(send.call_args.args[2])[0]))))
            self.assertIn('font-size:12px',send.call_args.kwargs['html_message'])
    def test_disabled_configuration_uses_existing_backend(self):
        send_mail('Test','Text','map@example.org',['target@example.org'])
        self.assertEqual(len(mail.outbox),1)
    def test_admin_can_save_and_test_without_exposing_provider_errors(self):
        self.client.force_login(self.admin)
        data=self.data(action='test',test_recipient='target@example.org')
        with patch('map.mail_admin.send_mail',return_value=1) as send:
            response=self.client.post(reverse('mail_settings'),data)
            self.assertEqual(response.status_code,302);self.assertEqual(send.call_count,1)
        self.assertTrue(MailConfiguration.objects.get(pk=1).enabled)
    def test_testmail_without_recipient_does_not_save_or_send(self):
        self.client.force_login(self.admin)
        with patch('map.mail_admin.send_mail') as send:
            response=self.client.post(reverse('mail_settings'),self.data(action='test'))
            self.assertEqual(response.status_code,200);self.assertFalse(send.called);self.assertFalse(MailConfiguration.objects.exists())
    def test_smtp_and_retry_posts_are_csrf_protected(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        for name in ['mail_settings','mail_queue']:self.assertEqual(client.post(reverse(name),{}).status_code,403)
