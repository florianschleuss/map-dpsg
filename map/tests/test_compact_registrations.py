"""Compact participant list, original form order and cancellation separation."""
from types import SimpleNamespace
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_reports_ui as fixtures
from map.models import Registration
from map.registration_presentation import answer_sections

@override_settings(SECURE_SSL_REDIRECT=False)
class CompactRegistrationTests(TestCase):
    setUp=fixtures.ReportsUiTests.setUp
    def page(self,**query):return self.client.get(reverse('event_admin',args=[self.event.pk]),query)
    def test_answer_order_uses_snapshot_modules_and_fields_not_json_order(self):
        schema=[{'title':'Kontakt','fields':[{'key':'z','label':'Telefon'},{'key':'a','label':'Anschrift'}]},{'title':'Teilnahme','fields':[{'key':'food','label':'Verpflegung'},{'key':'consent','label':'Fotoentscheidung'}]}]
        row=SimpleNamespace(schema_snapshot=schema,answers={'consent':False,'food':'Vegan','a':'Musterweg','z':'0123'})
        result=answer_sections(row)
        self.assertEqual([s['title'] for s in result],['Kontakt','Teilnahme'])
        self.assertEqual([a['label'] for s in result for a in s['answers']],['Telefon','Anschrift','Verpflegung','Fotoentscheidung'])
        self.assertEqual(result[1]['answers'][1]['value'],'Nein')
    def test_legacy_extra_answers_remain_visible_after_form_fields(self):
        row=SimpleNamespace(schema_snapshot=[{'title':'Fragen','fields':[{'key':'a','label':'Frage A'},{'key':'empty','label':'Optional'}]}],answers={'legacy':'Zusatz','a':0})
        sections=answer_sections(row)
        self.assertEqual(sections[0]['answers'][0]['value'],0)
        self.assertEqual(sections[0]['answers'][1]['value'],'Nicht angegeben')
        self.assertEqual(sections[-1]['title'],'Weitere gespeicherte Angaben')
        self.assertEqual(sections[-1]['answers'][0]['value'],'Zusatz')
    def test_cancelled_entries_are_separate_even_if_created_first(self):
        self.row.status='cancelled';self.row.save(update_fields=['status'])
        other=Registration.objects.create(event=self.event,event_group=self.row.event_group,child_name='Bea Aktiv',email='bea@example.org',identity='unique-active',status='confirmed',answers={},schema_snapshot=[])
        response=self.page()
        self.assertEqual([r.pk for r in response.context['rows']],[other.pk])
        self.assertEqual([r.pk for r in response.context['cancelled_rows']],[self.row.pk])
        self.assertEqual(response.context['registration_count'],2)
        text=response.content.decode()
        self.assertLess(text.index('Bea Aktiv'),text.index('id="cancelled-registrations"'))
        self.assertIn('belegen keinen Teilnahmeplatz',text)
    def test_cancelled_list_has_independent_pagination(self):
        for index in range(51):Registration.objects.create(event=self.event,event_group=self.row.event_group,child_name='Storno '+str(index),email='test@example.org',identity='cancelled-'+str(index),status='cancelled',answers={},schema_snapshot=[])
        response=self.page(cancelled_page=2)
        self.assertEqual(len(response.context['rows']),1)
        self.assertEqual(len(response.context['cancelled_rows']),1)
        self.assertEqual(response.context['cancelled_count'],51)
        self.assertEqual(response.context['registration_count'],52)
    def test_each_status_has_explicit_text_and_css_class(self):
        for status,label in Registration.STATUS:
            self.row.status=status;self.row.save(update_fields=['status'])
            response=self.page()
            self.assertContains(response,'map-registration-status-'+status)
            self.assertContains(response,label)
    def test_viewer_has_details_but_no_edit_or_payment_controls(self):
        self.client.force_login(self.reader)
        response=self.page()
        self.assertContains(response,'Details und Aktionen für Alex')
        self.assertNotContains(response,'Anmeldedaten bearbeiten')
        self.assertNotContains(response,'Zahlungseingang bestätigen')
    def test_unknown_user_cannot_read_any_list(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.page().status_code,403)
    def test_html_in_answers_is_not_trusted(self):
        self.row.answers={'food':'<script>private()</script>'};self.row.save(update_fields=['answers'])
        response=self.page()
        self.assertNotContains(response,'<script>private()</script>')
        self.assertContains(response,'&lt;script&gt;private()&lt;/script&gt;')
