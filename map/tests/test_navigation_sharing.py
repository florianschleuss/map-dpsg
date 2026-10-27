from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.utils import timezone
from map.models import ScoutGroup, Event, EventPermission, FormTemplate
from map.forms import RegistrationForm
from map.setup_forms import BasicsForm, DatesForm
from map.services import permitted
from map.default_roles import sync_default_roles
from map.apps import MapConfig
from map.sharing import registration_url

@override_settings(SECURE_SSL_REDIRECT=False,PUBLIC_URL='https://map.example.org')
class NavigationSharingTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='hauptadmin',email='admin@example.org',password='Strong-admin-pass-593!')
        self.manager=get_user_model().objects.create_user(username='manager')
        self.manager.groups.add(Group.objects.get(name='Manager'))
        self.reader=get_user_model().objects.create_user(username='leser')
        self.reader.groups.add(Group.objects.get(name='Read-Only'))
        self.outsider=get_user_model().objects.create_user(username='ohnezugang')
        self.group=ScoutGroup.objects.create(name='Pfadfinder')
        self.template=FormTemplate.objects.create(name='Lagerformular')
        now=timezone.now()
        self.event=Event.objects.create(title='Test SoLA',slug='test-sola',group=self.group,form_template=self.template,published=True,starts_at=now+timedelta(days=30),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=20))
    def test_profile_has_no_template_menu(self):
        self.client.force_login(self.admin)
        response=self.client.get('/dashboard/')
        self.assertNotContains(response,'href="/admin/map/formtemplate/"')
        self.assertContains(response,'Benutzergruppen')
    def test_breadcrumbs_follow_event_and_template(self):
        self.client.force_login(self.manager)
        response=self.client.get('/dashboard/events/'+str(self.event.pk)+'/')
        self.assertContains(response,'Navigationspfad')
        self.assertContains(response,'Dashboard')
        self.assertContains(response,'Test SoLA')
        response=self.client.get('/admin/formularbaukasten/'+str(self.template.pk)+'/?event='+str(self.event.pk))
        self.assertContains(response,'Formularvorlage')
        self.assertContains(response,'Test SoLA')
    def test_tab_title_contains_no_map(self):
        response=self.client.get('/accounts/login/')
        title=response.content.decode().split('<title>')[1].split('</title>')[0]
        self.assertNotIn('MAP',title)
    def test_manager_cannot_create_groups_via_wizard(self):
        form=BasicsForm({'title':'Lager','new_group_name':'Unbefugt','groups':[str(self.group.pk)]})
        self.assertFalse(form.is_valid())
        self.assertNotIn('new_group_name',BasicsForm().fields)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/admin/map/scoutgroup/add/').status_code,302)
    def test_date_defaults_are_now_not_nine_oclock(self):
        form=DatesForm()
        now=timezone.now()
        for name in ['starts_at','registration_opens','registration_closes']:
            self.assertLess(abs((form.initial[name]-now).total_seconds()),61)
        html=str(form['starts_at'])
        for value in ['00:00','09:00','17:00','now']: self.assertIn('data-time="'+value+'"',html)
    def test_yes_and_no_are_both_valid_but_unanswered_is_not(self):
        schema=[{'title':'Datenschutz','fields':[{'key':'photo','label':'Fotoabend','type':'select','required':True,'choices':['Ja','Nein']}]}]
        for answer in ['Ja','Nein']:
            form=RegistrationForm({'child_name':'Kind','email':'eltern@example.org','consent':'on','answer_photo':answer},modules=schema)
            self.assertTrue(form.is_valid(),form.errors)
            self.assertEqual(form.answers()['photo'],answer)
            self.assertEqual(form.fields['answer_photo'].widget.input_type,'radio')
        form=RegistrationForm({'child_name':'Kind','email':'eltern@example.org','consent':'on'},modules=schema)
        self.assertFalse(form.is_valid())
    def test_textareas_start_as_one_line(self):
        schema=[{'title':'Verpflegung','fields':[{'key':'food_notes','label':'Hinweise','type':'textarea'}]}]
        field=RegistrationForm(modules=schema).fields['answer_food_notes']
        self.assertEqual(field.widget.attrs['rows'],1)
        self.assertIn('data-autogrow',field.widget.attrs)
    def test_default_role_permissions_are_real_and_idempotent(self):
        from django.apps import apps
        sync_default_roles(apps.get_app_config('map'))
        manager=Group.objects.get(name='Manager')
        before=set(manager.permissions.values_list('pk',flat=True))
        self.assertTrue(manager.permissions.filter(codename='change_event').exists())
        self.assertFalse(manager.permissions.filter(content_type__app_label='auth').exists())
        self.assertFalse(manager.permissions.filter(codename='add_scoutgroup').exists())
        readonly=Group.objects.get(name='Read-Only')
        self.assertTrue(readonly.permissions.filter(codename='view_registration').exists())
        self.assertFalse(readonly.permissions.exclude(codename__startswith='view_').exists())
        self.assertTrue(Group.objects.get(name='Admin').permissions.filter(codename='change_user').exists())
        sync_default_roles(apps.get_app_config('map'))
        self.assertEqual(before,set(manager.permissions.values_list('pk',flat=True)))
    def test_read_only_overrides_stale_event_editor_permission(self):
        EventPermission.objects.create(event=self.event,user=self.reader,role='editor')
        self.assertFalse(permitted(self.reader,self.event,True))
    def test_dashboard_exposes_share_controls_only_for_published_events(self):
        self.client.force_login(self.reader)
        response=self.client.get('/dashboard/')
        self.assertContains(response,'Link kopieren')
        self.assertContains(response,'QR-Code als Bild kopieren')
        self.assertContains(response,registration_url(self.event))
        self.event.published=False;self.event.save()
        self.assertNotContains(self.client.get('/dashboard/'),'data-copy-qr')
    def test_qr_is_png_and_encodes_only_public_registration_link(self):
        import qrcode
        self.client.force_login(self.reader)
        with patch.object(qrcode.QRCode,'add_data',autospec=True,wraps=None) as add:
            response=self.client.get('/dashboard/events/'+str(self.event.pk)+'/qr.png')
            self.assertEqual(add.call_args.args[1],registration_url(self.event))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'image/png')
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))
    def test_qr_requires_permission_and_publication(self):
        url='/dashboard/events/'+str(self.event.pk)+'/qr.png'
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.manager)
        self.event.published=False;self.event.save()
        self.assertEqual(self.client.get(url).status_code,404)
    def test_all_native_management_pages_use_common_shell(self):
        self.client.force_login(self.admin)
        for url in ['/admin/auth/user/','/admin/auth/group/','/admin/map/scoutgroup/','/admin/auth/group/'+str(Group.objects.get(name='Manager').pk)+'/change/']:
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertTemplateUsed(response,'map_ui/header.html')
            self.assertContains(response,'Navigationspfad')
            self.assertContains(response,'Impressum')
