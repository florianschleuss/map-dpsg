from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from map.event_wizard import SESSION_KEY, create_event, validate_draft, DatesForm
from map.models import ScoutGroup, FormTemplate, Event, EventPermission, FormField

@override_settings(SECURE_SSL_REDIRECT=False)
class PortalAndWizardTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='leitung',email='leitung@example.org',password='Starkes-Test-Passwort-593!')
        self.member=get_user_model().objects.create_user(username='team',password='Starkes-Team-Passwort-294!')
        self.group=ScoutGroup.objects.create(name='Neuer Stamm')
        self.route='/admin/veranstaltung-anlegen/'
    def start(self):
        self.client.force_login(self.admin)
        response=self.client.get(self.route)
        self.assertEqual(response.status_code,302)
        self.url=response.url
        self.draft_id=self.url.split('entwurf=')[1]
        return self.draft_id
    def post(self,step,**data):
        data.update(draft_id=self.draft_id,step=str(step))
        return self.client.post(self.url,data)
    def basic_steps(self,template=None):
        now=timezone.localtime(timezone.now())
        self.assertEqual(self.post(1,title='Sommerlager',description='Gemeinsam unterwegs',groups=[str(self.group.pk)]).status_code,302)
        self.assertEqual(self.post(2,starts_at=(now+timedelta(days=30)).strftime('%Y-%m-%dT%H:%M'),registration_opens=(now-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),registration_closes=(now+timedelta(days=20)).strftime('%Y-%m-%dT%H:%M')).status_code,302)
        self.assertEqual(self.post(3,capacity='12',waitlist_enabled='on',confirmation_required='on',confirmation_hours='48').status_code,302)
        self.assertEqual(self.post(4,form_template=str(template.pk) if template else '',privacy_text='Verantwortlich ist der Stamm. Kontakt, Zweck und Aufbewahrung sind hier erläutert.').status_code,302)
        self.assertEqual(self.post(5,editors=[str(self.member.pk)]).status_code,302)
        self.assertEqual(self.post(6,cost_mode='free').status_code,302)
    def test_anonymous_root_has_no_event_catalog(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,'/accounts/login/')
        self.assertEqual(Event.objects.count(),0)
    def test_authenticated_root_goes_to_private_dashboard(self):
        self.client.force_login(self.member)
        self.assertRedirects(self.client.get('/'),'/dashboard/')
    def test_wizard_requires_main_administration(self):
        self.assertEqual(self.client.get(self.route).status_code,302)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.route).status_code,403)
        self.member.is_staff=True;self.member.save()
        self.assertEqual(self.client.get(self.route).status_code,403)
    def test_no_database_records_before_finish(self):
        self.start();self.basic_steps()
        self.assertEqual(Event.objects.count(),0)
        self.assertEqual(ScoutGroup.objects.count(),1)
        self.assertEqual(FormTemplate.objects.count(),0)
        self.assertContains(self.client.get(self.url),'Prüfen und anlegen')
    def test_finish_creates_unpublished_event_form_and_access(self):
        self.start();self.basic_steps()
        response=self.post(7,acknowledge='on')
        self.assertEqual(response.status_code,302)
        event=Event.objects.get()
        self.assertFalse(event.published)
        self.assertEqual(event.capacity,12)
        self.assertEqual(event.group.name,'Neuer Stamm')
        self.assertEqual(EventPermission.objects.get(event=event,user=self.member).role,'editor')
        field=FormField.objects.get(module__template=event.form_template,key='food')
        self.assertEqual(len(field.choices.splitlines()),3)
        self.assertEqual(self.client.get('/events/'+event.slug+'/').status_code,404)
    def test_finish_can_publish_and_direct_parent_link_works(self):
        self.start();self.basic_steps()
        self.post(7,acknowledge='on',published='on')
        event=Event.objects.get()
        self.client.logout()
        response=self.client.get('/events/'+event.slug+'/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Ein Kind anmelden')
        self.assertNotContains(response,'Öffentliche Veranstaltungen')
        self.assertEqual(self.client.get('/').status_code,302)
    def test_repeated_finish_is_idempotent(self):
        self.start();self.basic_steps()
        state=self.client.session[SESSION_KEY][self.draft_id]
        cleaned,invalid,_=validate_draft(state)
        self.assertIsNone(invalid)
        first=create_event(cleaned,False,self.draft_id,self.admin)
        second=create_event(cleaned,False,self.draft_id,self.admin)
        self.assertEqual(first.pk,second.pk)
        self.assertEqual(Event.objects.count(),1)
        self.assertEqual(ScoutGroup.objects.count(),1)
    def test_dates_must_be_in_order(self):
        now=timezone.now()
        form=DatesForm({'starts_at':now.isoformat(),'registration_opens':now.isoformat(),'registration_closes':(now+timedelta(days=1)).isoformat()})
        self.assertFalse(form.is_valid())
        self.assertIn('registration_closes',form.errors)
    def test_group_or_new_group_is_required(self):
        self.start()
        response=self.post(1,title='Lager')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Bitte mindestens eine')
    def test_existing_template_is_reused(self):
        template=FormTemplate.objects.create(name='Eigene Vorlage')
        self.start();self.basic_steps(template)
        self.post(7,acknowledge='on')
        self.assertEqual(Event.objects.get().form_template_id,template.pk)
        self.assertEqual(FormTemplate.objects.count(),1)
    def test_a_user_cannot_have_both_roles(self):
        self.start();self.basic_steps()
        self.post(7,action='back')
        self.post(6,action='back')
        response=self.post(5,viewers=[str(self.member.pk)],editors=[str(self.member.pk)])
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'entweder zum Lesen oder zum Bearbeiten')
    def test_missing_acknowledgment_does_not_save(self):
        self.start();self.basic_steps()
        self.assertEqual(self.post(7,published='on').status_code,200)
        self.assertFalse(Event.objects.exists())
    def test_stale_step_does_not_change_state(self):
        self.start()
        self.post(1,title='Lager',groups=[str(self.group.pk)])
        self.post(1,title='Andere Veranstaltung',groups=[str(self.group.pk)])
        state=self.client.session[SESSION_KEY][self.draft_id]
        self.assertEqual(state['data']['0']['title'],'Lager')
        self.assertEqual(state['step'],1)
    def test_foreign_draft_cannot_be_read(self):
        self.start()
        other=Client();other.force_login(self.admin)
        response=other.get(self.url)
        self.assertEqual(response.status_code,302)
        self.assertNotEqual(response.url,self.url)
    def test_wizard_has_csrf_protection(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(self.route,{}).status_code,403)
    def test_admin_help_and_labels_are_german_even_for_english_browser(self):
        self.client.force_login(self.admin)
        response=self.client.get('/dashboard/',HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertEqual(response['Content-Language'],'de')
        self.assertContains(response,'Wie funktioniert MAP?')
        self.assertContains(response,'Veranstaltungen')
        self.assertContains(response,'Benutzergruppen')
        self.assertContains(response,'Veranstaltung anlegen')
        self.assertContains(response,'<details',html=False)
        self.assertNotContains(response,'Recent actions')
        self.assertNotContains(response,'Öffentliche Veranstaltungen')

    def test_translated_readonly_admin_pages_do_not_expose_editable_raw_fields(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from map.models import Registration, EmailJob, AuditLog
        request=RequestFactory().get('/admin/')
        request.user=self.admin
        for model in [Registration,EmailJob,AuditLog]:
            manager=admin.site._registry[model]
            self.assertEqual(list(manager.get_fields(request)),list(manager.readonly_fields))
            self.assertEqual(list(manager.get_form(request).base_fields),[])
