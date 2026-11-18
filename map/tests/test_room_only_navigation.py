from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.utils import timezone
from map.models import ScoutGroup, FormTemplate, Event, EventPermission, LeaderProfile
from map.roles import default_module, can_use_events

@override_settings(SECURE_SSL_REDIRECT=False)
class RoomOnlyNavigationTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('gemeindebuero',password='Test-Only-Password-12345')
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='rooms',codename__in=['view_roombooking','add_roombooking']))
        self.stage=ScoutGroup.objects.create(name='Teststufe')
        self.template=FormTemplate.objects.create(name='Testformular')
        now=timezone.now()
        self.event=Event.objects.create(title='Vertrauliches Lager',slug='secret-event',group=self.stage,form_template=self.template,starts_at=now+timedelta(days=5),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=3))
        self.client.force_login(self.user)

    def test_room_only_user_lands_in_rooms_and_has_no_events_tab(self):
        self.assertEqual(default_module(self.user),'rooms:index')
        self.assertRedirects(self.client.get('/dashboard/'),'/raeume/')
        response=self.client.get('/',follow=True)
        self.assertEqual(response.request['PATH_INFO'],'/raeume/')
        self.assertNotContains(response,'>Veranstaltungen</a>')
        self.assertContains(response,'href="/raeume/"')
        self.assertNotContains(response,'Vertrauliches Lager')

    def test_local_login_default_and_safe_next(self):
        self.client.logout()
        response=self.client.post('/accounts/login/',{'username':'gemeindebuero','password':'Test-Only-Password-12345'})
        self.assertRedirects(response,'/raeume/')
        self.client.logout()
        response=self.client.post('/accounts/login/?next=/raeume/neu/',{'username':'gemeindebuero','password':'Test-Only-Password-12345','next':'/raeume/neu/'})
        self.assertRedirects(response,'/raeume/neu/')

    def test_direct_event_routes_still_deny_access(self):
        self.assertEqual(self.client.get('/dashboard/events/'+str(self.event.pk)+'/').status_code,403)
        self.assertEqual(self.client.get('/admin/veranstaltung-anlegen/').status_code,403)
        self.assertEqual(self.client.get('/raeume/neu/').status_code,200)

    def test_global_event_reader_keeps_events_tab(self):
        self.user.groups.add(Group.objects.get(name='Read-Only'))
        self.assertTrue(can_use_events(self.user))
        response=self.client.get('/dashboard/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'>Veranstaltungen</a>')

    def test_stage_permission_keeps_events_even_without_current_events(self):
        other=ScoutGroup.objects.create(name='Andere Stufe')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='map',codename='view_stage_'+str(other.pk)))
        self.assertTrue(can_use_events(self.user))
        self.assertEqual(default_module(self.user),'dashboard')

    def test_leader_stage_and_direct_event_grants_are_preserved(self):
        profile=LeaderProfile.objects.create(user=self.user,is_leader=True);profile.stages.add(self.stage)
        self.assertTrue(can_use_events(self.user))
        profile.stages.clear();profile.is_leader=False;profile.save()
        EventPermission.objects.create(user=self.user,event=self.event,role='viewer')
        self.assertTrue(can_use_events(self.user))

    def test_unprivileged_user_keeps_existing_empty_dashboard(self):
        user=get_user_model().objects.create_user('no-rights')
        self.assertEqual(default_module(user),'dashboard')
