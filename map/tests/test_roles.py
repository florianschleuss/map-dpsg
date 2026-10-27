from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from map.roles import is_admin, can_manage, can_read_all
from map.services import permitted

@override_settings(SECURE_SSL_REDIRECT=False)
class RoleTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='rolle',password='Strong-pass-593!')
    def assign(self,name):
        self.user.groups.add(Group.objects.get_or_create(name=name)[0])
    def test_default_role_migration_creates_all_groups(self):
        self.assertEqual(set(Group.objects.filter(name__in=['Admin','Manager','Read-Only']).values_list('name',flat=True)),{'Admin','Manager','Read-Only'})
    def test_admin_group_grants_administration_without_staff_flag(self):
        self.assign('Admin');self.assertTrue(is_admin(self.user))
        self.assertTrue(self.user.has_perm('auth.change_user'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code,200)
        self.assertContains(self.client.get('/dashboard/'),'Benutzergruppen')
    def test_manager_has_global_edit_but_no_user_administration(self):
        self.assign('Manager');self.assertTrue(can_manage(self.user));self.assertFalse(is_admin(self.user))
        self.assertTrue(permitted(self.user,object(),True))
        self.assertFalse(self.user.has_perm('auth.change_user'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code,302)
        self.assertNotContains(self.client.get('/dashboard/'),'href="/admin/auth/user/"')
        self.assertEqual(self.client.get('/admin/veranstaltung-anlegen/').status_code,302)
    def test_read_only_can_read_globally_but_cannot_create_events(self):
        self.assign('Read-Only');self.assertTrue(can_read_all(self.user));self.assertFalse(can_manage(self.user))
        self.assertTrue(permitted(self.user,object()))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/veranstaltung-anlegen/').status_code,403)
        self.assertNotContains(self.client.get('/dashboard/'),'Veranstaltung anlegen')
    def test_inactive_admin_has_no_permissions(self):
        self.assign('Admin');self.user.is_active=False
        self.assertFalse(is_admin(self.user));self.assertFalse(can_read_all(self.user))
    def test_login_has_no_area_selector_and_contains_imprint(self):
        response=self.client.get('/accounts/login/')
        self.assertNotContains(response,'name="area"')
        self.assertNotContains(response,'https://dpsg.de')
        self.assertContains(response,'Dein Pfadfinderstamm')
        self.assertContains(response,'/impressum/')
        self.assertContains(response,'map/logo.svg')
