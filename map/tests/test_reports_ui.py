from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
import zipfile
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from map.models import ScoutGroup,Event,EventGroup,EventPermission,EmailTemplate,EmailJob
from map.form_schema import persist_schema
from map.services import register,registration_message_context
from map.mail_templates import system_content
from map.mailer import send_mail

@override_settings(SECURE_SSL_REDIRECT=False,PUBLIC_URL='https://example.org',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='noreply@example.org')
class ReportsUiTests(TestCase):
    def setUp(self):
        users=get_user_model()
        self.admin=users.objects.create_superuser('reportsadmin','admin@example.org','Strong-pass-192!')
        self.reader=users.objects.create_user('reportsreader')
        self.outsider=users.objects.create_user('reportsoutsider')
        stage=ScoutGroup.objects.create(name='Wös Berichte')
        form=persist_schema([{'title':'Verpflegung','fields':[{'key':'food','label':'Essen','type':'select','choices':['Vegan','Vegetarisch'],'required':True}]}],'Berichtsformular')
        now=timezone.now()
        self.event=Event.objects.create(group=stage,form_template=form,title='Berichtslager',slug='berichtslager',published=True,capacity=10,confirmation_required=False,starts_at=now+timedelta(days=10),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=5))
        EventGroup.objects.create(event=self.event,group=stage,capacity=10)
        EventPermission.objects.create(event=self.event,user=self.reader,role='viewer')
        self.row=register(self.event.pk,'Alex','parent@example.org',{'food':'Vegan'})
        self.client.force_login(self.admin)
    def test_details_replace_answer_column_and_exports_are_next_to_count(self):
        response=self.client.get(reverse('event_admin',args=[self.event.pk]))
        self.assertContains(response,'Details und Aktionen für Alex');self.assertContains(response,'Vegan')
        self.assertNotContains(response,'<th>Antworten</th>')
        text=response.content.decode();self.assertLess(text.index('1 Eintrag'),text.index('Excel herunterladen'))
        self.assertContains(response,reverse('event_statistics',args=[self.event.pk]))
    def test_statistics_default_only_counts_confirmed(self):
        waiting=register(self.event.pk,'Sam','parent@example.org',{'food':'Vegetarisch'})
        waiting.status='waitlisted';waiting.save(update_fields=['status'])
        response=self.client.get(reverse('event_statistics',args=[self.event.pk]))
        self.assertEqual(response.status_code,200);self.assertEqual(response.context['total'],1)
        self.assertEqual(response.context['questions'][0]['options'][0]['count'],1)
        self.assertEqual(response.context['questions'][0]['options'][1]['count'],0)
    def test_statistics_explicit_all_scope_includes_cancelled(self):
        self.row.status='cancelled';self.row.save(update_fields=['status'])
        response=self.client.get(reverse('event_statistics',args=[self.event.pk]),{'umfang':'all'})
        self.assertEqual(response.context['total'],1)
    def test_invalid_scope_falls_back_to_confirmed(self):
        response=self.client.get(reverse('event_statistics',args=[self.event.pk]),{'umfang':'anything'})
        self.assertEqual(response.context['scope'],'confirmed')
    def test_viewer_can_read_statistics_and_export(self):
        self.client.force_login(self.reader)
        for name in ['event_statistics','export_excel']:self.assertEqual(self.client.get(reverse(name,args=[self.event.pk])).status_code,200)
    def test_unauthorized_account_cannot_read_statistics_or_excel(self):
        self.client.force_login(self.outsider)
        for name in ['event_statistics','export_excel']:self.assertEqual(self.client.get(reverse(name,args=[self.event.pk])).status_code,403)
    def test_anonymous_cannot_read_statistics_or_excel(self):
        self.client.logout()
        for name in ['event_statistics','export_excel']:self.assertEqual(self.client.get(reverse(name,args=[self.event.pk])).status_code,302)
    def test_excel_is_real_workbook_and_has_no_bank_information(self):
        response=self.client.get(reverse('export_excel',args=[self.event.pk]))
        self.assertEqual(response.status_code,200)
        self.assertIn('spreadsheetml.sheet',response['Content-Type'])
        self.assertIn('.xlsx',response['Content-Disposition'])
        archive=zipfile.ZipFile(BytesIO(response.content))
        data=archive.read('xl/worksheets/sheet1.xml').decode()
        self.assertIn('Vegan',data);self.assertIn('Alex',data);self.assertNotIn('IBAN',data)
        self.assertEqual(response['Cache-Control'],'no-store')
    def test_statistics_and_excel_reject_mutating_http_method(self):
        for name in ['event_statistics','export_excel']:self.assertEqual(self.client.post(reverse(name,args=[self.event.pk])).status_code,405)
    def test_registration_screen_explains_spam_and_contact(self):
        self.client.logout()
        response=self.client.post(reverse('event',args=[self.event.slug]),{'child_name':'Neues Kind','email':'neues@example.org','consent':'on','answer_food':'Vegan'})
        self.assertContains(response,'Spam-Ordner');self.assertContains(response,'Leitenden der Veranstaltung')
    def test_english_browser_still_gets_german_server_errors(self):
        self.client.logout()
        response=self.client.post(reverse('event',args=[self.event.slug]),{'child_name':'Kind','email':'invalid','consent':'on','answer_food':'Vegan'},HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertEqual(response['Content-Language'],'de')
        self.assertNotContains(response,'Enter a valid email address')
        self.assertContains(response,'gültige E-Mail-Adresse')
    def test_consent_includes_binding_registration(self):
        response=self.client.get(reverse('event',args=[self.event.slug]))
        self.assertContains(response,'melde das Kind verbindlich an')
    def test_email_confirmation_for_waitlist_does_not_promise_place(self):
        self.row.status='waitlisted';self.row.email_verified=True
        context=registration_message_context(self.row,'E-Mail bestätigt')
        _,body=system_content('confirmed',context)
        self.assertIn('keine Platzzusage',body);self.assertNotIn('Die Teilnahme ist bestätigt.',body)
    def test_existing_custom_mail_keeps_text_and_gets_footer(self):
        EmailTemplate.objects.create(key='registration',subject='Eigener Betreff',body='Eigener Text {confirmation_section}\n{manage_url}')
        subject,body=system_content('registration',registration_message_context(self.row,'Ihre Anmeldung'))
        self.assertEqual(subject,'Eigener Betreff');self.assertIn('Eigener Text',body);self.assertIn('Bitte antworte nicht',body)
    def test_smtp_message_has_plain_and_html_alternative(self):
        send_mail('Test','Nachricht','No Reply <noreply@example.org>',['target@example.org'])
        message=mail.outbox[-1]
        self.assertIn('automatisch erstellt',message.body)
        from email.utils import parseaddr
        from email.header import decode_header,make_header
        self.assertIn('Anmeldungsverwaltung',str(make_header(decode_header(parseaddr(message.from_email)[0]))))
        self.assertTrue(message.alternatives)
        self.assertIn('font-size:12px',message.alternatives[0][0])
    def test_preview_can_use_waitlist_scenario_without_sending(self):
        with patch('map.mailer.send_mail') as send:
            from map.email_content import default_content
            subject,body=default_content('confirmed')
            response=self.client.post(reverse('email_template_edit',args=['confirmed']),{'action':'preview','subject':subject,'body':body,'preview_status':'waitlisted'})
        self.assertEqual(response.status_code,200);self.assertContains(response,'keine Platzzusage');send.assert_not_called()
