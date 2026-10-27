import json
from datetime import timedelta
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings, RequestFactory
from django.utils import timezone
from map.models import ScoutGroup, FormTemplate, Event, EventGroup, EventPermission, Registration, FormField
from map.services import register, cancel, confirm, rebalance
from map.group_limits import apply_limits, validate_limits
from map.form_schema import STANDARD_SCHEMA, persist_schema, validate_builder_schema
from map.forms import EventSettingsForm, RegistrationForm, template_schema
from map.setup_forms import AccessForm, BasicsForm, CapacityForm, TemplateForm, group_entries
from map.widgets import QuickDateTimeWidget

@override_settings(SECURE_SSL_REDIRECT=False)
class GroupBuilderTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='leitung',email='leitung@example.org',password='Test-Passwort-593!')
        self.member=get_user_model().objects.create_user(username='team',password='Team-Passwort-294!')
        self.a=ScoutGroup.objects.create(name='Wölflinge');self.b=ScoutGroup.objects.create(name='Jungpfadfinder')
        self.template=persist_schema(STANDARD_SCHEMA,'Standard')
        now=timezone.now()
        self.event=Event.objects.create(group=self.a,form_template=self.template,title='Gemeinsames Lager',slug='gemeinsames-lager',published=True,capacity=2,confirmation_required=False,starts_at=now+timedelta(days=30),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=20))
        self.sa=EventGroup.objects.create(event=self.event,group=self.a,capacity=1)
        self.sb=EventGroup.objects.create(event=self.event,group=self.b,capacity=1)
    def reg(self,name,group):return register(self.event.pk,name,'eltern@example.org',{'phone':'0123'},group_id=group.pk)
    def event_data(self,limits):
        date=lambda value:timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')
        return {'title':self.event.title,'description':'','group_limits':json.dumps(limits),'starts_at':date(self.event.starts_at),'registration_opens':date(self.event.registration_opens),'registration_closes':date(self.event.registration_closes),'published':'on','waitlist_enabled':'on','confirmation_hours':'48','form_template':str(self.template.pk)}
    def test_each_group_has_its_own_capacity(self):
        self.assertEqual(self.reg('Kind A',self.a).status,'confirmed')
        self.assertEqual(self.reg('Kind A2',self.a).status,'waitlisted')
        self.assertEqual(self.reg('Kind B',self.b).status,'confirmed')
    def test_group_is_required_when_multiple_groups_participate(self):
        with self.assertRaises(ValidationError):register(self.event.pk,'Kind','eltern@example.org',{})
    def test_foreign_group_is_rejected(self):
        other=ScoutGroup.objects.create(name='Andere Gruppe')
        with self.assertRaises(ValidationError):self.reg('Kind',other)
    def test_disabled_group_is_rejected(self):
        self.sa.enabled=False;self.sa.save()
        with self.assertRaises(ValidationError):self.reg('Kind',self.a)
    def test_duplicate_cannot_bypass_check_by_selecting_another_group(self):
        self.reg('Anna Kind',self.a)
        with self.assertRaises(ValidationError):self.reg('ANNA KIND',self.b)
    def test_cancellation_promotes_only_same_group(self):
        first_b=self.reg('B1',self.b);waiting_b=self.reg('B2',self.b)
        first_a=self.reg('A1',self.a);waiting_a=self.reg('A2',self.a)
        cancel(first_a.pk)
        waiting_a.refresh_from_db();waiting_b.refresh_from_db();first_b.refresh_from_db()
        self.assertEqual(waiting_a.status,'confirmed');self.assertEqual(waiting_b.status,'waitlisted');self.assertEqual(first_b.status,'confirmed')
    def test_expiry_promotes_only_same_group(self):
        self.event.confirmation_required=True;self.event.save()
        first=self.reg('A1',self.a);waiting=self.reg('A2',self.a);other=self.reg('B1',self.b)
        confirm(waiting.pk)
        Registration.objects.filter(pk=first.pk).update(confirmation_deadline=timezone.now()-timedelta(seconds=1))
        rebalance(self.event.pk)
        first.refresh_from_db();waiting.refresh_from_db();other.refresh_from_db()
        self.assertEqual(first.status,'expired');self.assertEqual(waiting.status,'confirmed');self.assertEqual(other.status,'pending')
    def test_full_group_does_not_use_other_groups_free_slots(self):
        self.event.waitlist_enabled=False;self.event.save();self.reg('A1',self.a)
        with self.assertRaises(ValidationError):self.reg('A2',self.a)
        self.assertEqual(self.reg('B1',self.b).status,'confirmed')
    def test_limit_cannot_be_reduced_below_occupied_places(self):
        self.sa.capacity=2;self.sa.save();self.reg('A1',self.a);self.reg('A2',self.a)
        with self.assertRaises(ValidationError):validate_limits(self.event,{str(self.a.pk):1,str(self.b.pk):1})
    def test_group_with_waitlisted_registration_cannot_be_removed(self):
        self.reg('A1',self.a);self.reg('A2',self.a)
        with self.assertRaises(ValidationError):apply_limits(self.event,[self.b],{str(self.b.pk):1})
    def test_historical_registration_is_preserved_when_group_is_removed(self):
        row=self.reg('A1',self.a);cancel(row.pk)
        apply_limits(self.event,[self.b],{str(self.b.pk):2})
        self.sa.refresh_from_db();row.refresh_from_db();self.event.refresh_from_db()
        self.assertFalse(self.sa.enabled);self.assertEqual(row.event_group_id,self.sa.pk);self.assertEqual(self.event.capacity,2)
    def test_event_form_saves_group_limits_and_total(self):
        form=EventSettingsForm(self.event_data({str(self.a.pk):3,str(self.b.pk):4}),instance=self.event,actor=self.admin)
        self.assertTrue(form.is_valid(),form.errors);form.save();self.event.refresh_from_db();self.sa.refresh_from_db();self.sb.refresh_from_db()
        self.assertEqual(self.event.capacity,7);self.assertEqual(self.sa.capacity,3);self.assertEqual(self.sb.capacity,4)
    def test_editor_cannot_grant_permissions_through_event_settings(self):
        EventPermission.objects.create(event=self.event,user=self.member,role='viewer')
        data=self.event_data({str(self.a.pk):1,str(self.b.pk):1});data['editors']=[str(self.member.pk)]
        form=EventSettingsForm(data,instance=self.event,actor=self.member)
        self.assertNotIn('editors',form.fields);self.assertTrue(form.is_valid(),form.errors);form.save()
        self.assertEqual(EventPermission.objects.get(event=self.event,user=self.member).role,'viewer')
    def test_main_administration_can_assign_checkbox_permissions(self):
        data=self.event_data({str(self.a.pk):1,str(self.b.pk):1});data['viewers']=[str(self.member.pk)]
        form=EventSettingsForm(data,instance=self.event,actor=self.admin)
        self.assertTrue(form.is_valid(),form.errors);form.save()
        self.assertEqual(EventPermission.objects.get(event=self.event,user=self.member).role,'viewer')
    def test_invalid_quota_values_are_rejected(self):
        for value in [0,-1,True,1.5,'20']:
            with self.subTest(value=value),self.assertRaises(ValidationError):validate_limits(self.event,{str(self.a.pk):value})
    def test_registration_form_asks_for_group_and_no_privacy_text(self):
        form=RegistrationForm(modules=[],event=self.event)
        self.assertTrue(form.fields['group_id'].required)
        self.assertNotIn('Datenschutzhinweis',form.fields['consent'].label)
        self.assertNotIn('privacy_text',EventSettingsForm(instance=self.event).fields)
    def test_person_choices_are_checkboxes_with_requested_labels(self):
        from django.forms import CheckboxSelectMultiple
        form=AccessForm()
        self.assertIsInstance(form.fields['viewers'].widget,CheckboxSelectMultiple)
        self.assertIsInstance(form.fields['editors'].widget,CheckboxSelectMultiple)
        self.assertEqual(form.fields['viewers'].label,'Personen mit Leserechten')
    def test_multigroup_basics_and_individual_capacity_fields(self):
        basics=BasicsForm({'title':'Lager','groups':[str(self.a.pk),str(self.b.pk)]})
        self.assertTrue(basics.is_valid(),basics.errors)
        capacity=CapacityForm(entries=group_entries(basics.cleaned_data))
        self.assertNotIn('capacity',capacity.fields)
        self.assertIn('capacity_'+str(self.a.pk),capacity.fields);self.assertIn('capacity_'+str(self.b.pk),capacity.fields)
    def test_builder_edits_do_not_change_existing_registration_snapshot(self):
        row=self.reg('A1',self.a);before=row.schema_snapshot
        changed=[{'title':'Neu','fields':[{'key':'different','label':'Andere Frage','type':'text','required':False}]}]
        persist_schema(changed,self.template.name,self.template)
        row.refresh_from_db();self.assertEqual(row.schema_snapshot,before)
        self.assertEqual(template_schema(self.template)[0]['title'],'Neu')
    def test_builder_view_requires_main_administration(self):
        url='/admin/formularbaukasten/'+str(self.template.pk)+'/'
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.member);self.assertEqual(self.client.get(url).status_code,403)
    def test_builder_can_save_an_empty_additional_form(self):
        self.client.force_login(self.admin)
        response=self.client.post('/admin/formularbaukasten/neu/',{'name':'Nur Grundangaben','schema_json':'[]'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(FormTemplate.objects.get(name='Nur Grundangaben').modules.count(),0)
    def test_builder_and_event_editor_render_library_and_calendar(self):
        self.client.force_login(self.admin)
        response=self.client.get('/admin/formularbaukasten/'+str(self.template.pk)+'/')
        self.assertEqual(response.status_code,200);self.assertContains(response,'Bausteinbibliothek');self.assertContains(response,'map/builder.js')
        response=self.client.get('/admin/map/event/'+str(self.event.pk)+'/change/')
        self.assertEqual(response.status_code,200);self.assertContains(response,'9 Uhr');self.assertContains(response,'17 Uhr');self.assertContains(response,'Jetzt');self.assertContains(response,'Speichern');self.assertNotContains(response,'value="Sichern"')
    def test_parent_page_has_group_choice_and_central_privacy_link(self):
        legacy_notice='Alter veranstaltungsspezifischer Datenschutzhinweis'
        self.event.privacy_text=legacy_notice
        self.event.save(update_fields=['privacy_text'])
        response=self.client.get('/events/'+self.event.slug+'/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Gruppe des Kindes')
        self.assertContains(response,self.a.name)
        self.assertContains(response,self.b.name)
        self.assertContains(response,'href="/datenschutz/"')
        self.assertNotContains(response,'name="privacy_text"')
        self.assertNotContains(response,legacy_notice)
    def test_schema_validation_rejects_bad_or_duplicate_keys(self):
        with self.assertRaises(ValidationError):validate_builder_schema([{'title':'Abschnitt','fields':[{'key':'x','label':'Frage','type':'text'},{'key':'x','label':'Andere','type':'text'}]}])
    def test_export_contains_group_and_german_question_labels(self):
        self.reg('A1',self.a);self.client.force_login(self.admin)
        response=self.client.get('/dashboard/events/'+str(self.event.pk)+'/export/')
        text=response.content.decode('utf-8-sig');self.assertIn('Gruppe',text.splitlines()[0]);self.assertIn('Telefon für Rückfragen',text.splitlines()[0]);self.assertIn(self.a.name,text)

    def test_native_event_admin_saves_group_limits_without_raw_legacy_fields(self):
        self.client.force_login(self.admin)
        data=self.event_data({str(self.a.pk):2,str(self.b.pk):1});data['_save']='Speichern'
        response=self.client.post('/admin/map/event/'+str(self.event.pk)+'/change/',data)
        self.assertEqual(response.status_code,302)
        self.event.refresh_from_db();self.sa.refresh_from_db();self.sb.refresh_from_db()
        self.assertEqual(self.event.capacity,3);self.assertEqual(self.sa.capacity,2);self.assertEqual(self.sb.capacity,1)
    def test_wizard_creates_multiple_group_limits_and_a_form_copy(self):
        self.client.force_login(self.admin)
        response=self.client.get('/admin/veranstaltung-anlegen/')
        url=response.url;draft_id=url.split('entwurf=')[1]
        def post(step,**data):
            data.update(draft_id=draft_id,step=str(step))
            response=self.client.post(url,data)
            self.assertEqual(response.status_code,302, getattr(response,'content',b'')[:1000])
        post(1,title='Mehrere Gruppen',groups=[str(self.a.pk),str(self.b.pk)])
        date=lambda value:timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')
        post(2,starts_at=date(self.event.starts_at),registration_opens=date(self.event.registration_opens),registration_closes=date(self.event.registration_closes))
        post(3,**{'capacity_'+str(self.a.pk):'2','capacity_'+str(self.b.pk):'3','waitlist_enabled':'on','confirmation_required':'on','confirmation_hours':'24'})
        schema=[{'title':'Anreise','fields':[{'key':'arrival','label':'Wie reist du an?','type':'text','required':True}]}]
        post(4,form_template=str(self.template.pk),schema_json=json.dumps(schema))
        post(5,viewers=[str(self.member.pk)])
        post(6,cost_mode='free')
        post(7,acknowledge='on')
        event=Event.objects.exclude(pk=self.event.pk).get()
        self.assertEqual(event.capacity,5);self.assertFalse(event.published)
        self.assertEqual(event.group_slots.get(group=self.a).capacity,2);self.assertEqual(event.group_slots.get(group=self.b).capacity,3)
        self.assertNotEqual(event.form_template_id,self.template.pk);self.assertEqual(FormField.objects.filter(module__template=self.template,key='phone').count(),1)
        self.assertEqual(EventPermission.objects.get(event=event,user=self.member).role,'viewer')
    def test_builder_is_csrf_protected(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post('/admin/formularbaukasten/neu/',{'name':'Test','schema_json':'[]'}).status_code,403)
    def test_builder_return_link_cannot_redirect_to_external_site(self):
        self.client.force_login(self.admin)
        response=self.client.post('/admin/formularbaukasten/'+str(self.template.pk)+'/?zurueck=https://evil.example/',{'name':self.template.name,'schema_json':json.dumps(STANDARD_SCHEMA)})
        self.assertEqual(response.status_code,302);self.assertNotIn('evil.example',response.url)

    def test_missing_group_limits_show_form_error_instead_of_server_error(self):
        self.client.force_login(self.admin)
        data=self.event_data({str(self.a.pk):1,str(self.b.pk):1});data.pop('group_limits');data['_save']='Speichern'
        response=self.client.post('/admin/map/event/'+str(self.event.pk)+'/change/',data)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'errorlist')

    def test_legacy_event_editor_includes_cost_fields(self):
        self.client.force_login(self.admin)
        response=self.client.get('/admin/map/event/'+str(self.event.pk)+'/change/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'name="cost_mode"')
        self.assertContains(response,'name="payment_method"')

    def test_legacy_event_editor_rejects_invalid_costs_without_saving_limits(self):
        self.client.force_login(self.admin)
        data=self.event_data({str(self.a.pk):2,str(self.b.pk):1})
        data.update(cost_mode='fixed',cost_amount='-1',payment_method='cash')
        response=self.client.post('/admin/map/event/'+str(self.event.pk)+'/change/',data)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)
        self.event.refresh_from_db();self.sa.refresh_from_db();self.sb.refresh_from_db()
        self.assertEqual(self.event.capacity,2)
        self.assertEqual(self.sa.capacity,1);self.assertEqual(self.sb.capacity,1)
