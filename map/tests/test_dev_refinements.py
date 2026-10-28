import importlib
import uuid
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from map.models import ScoutGroup,EmailJob,LeaderProfile
from map.sso_models import EntraIdentity
from map.demo_events import create_dummy_event

@override_settings(MAP_PRODUCTION=False,ALLOWED_HOSTS=['testserver'])
class DevRefinementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=get_user_model().objects.create_superuser('demo-admin','admin@example.org','strong-test-password-123')
        cls.stage=ScoutGroup.objects.create(name='Dummy-Stufe')
        cls.leader=get_user_model().objects.create_user('demo-leader','leader@example.org','strong-test-password-123')
        profile=LeaderProfile.objects.create(user=cls.leader,is_leader=True);profile.stages.add(cls.stage)

    def test_dummy_uses_normal_forms_is_private_idempotent_and_sends_no_mail(self):
        event=create_dummy_event(self.leader,'same-nonce')
        self.assertFalse(event.published);self.assertIn('[TEST]',event.title)
        self.assertEqual(create_dummy_event(self.leader,'same-nonce').pk,event.pk)
        self.assertEqual(EmailJob.objects.count(),0)
        self.assertEqual(event.group_slots.first().group_id,self.stage.pk)
        from collections import Counter
        self.assertEqual(Counter(event.registrations.values_list('status',flat=True)),{'confirmed':12,'pending':8,'waitlisted':4,'cancelled':3,'expired':2})
        self.assertEqual(event.registrations.filter(payment_received_at__isnull=False).count(),6)
        self.assertEqual(event.registrations.count(),29)
        self.assertTrue(all(r.schema_snapshot and r.answers for r in event.registrations.all()))
        self.client.force_login(self.leader)
        self.assertEqual(self.client.get(reverse('event_admin',args=[event.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('event_statistics',args=[event.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('export_excel',args=[event.pk])).status_code,200)
        self.assertEqual(EmailJob.objects.count(),0)


    @override_settings(MAP_PRODUCTION=True)
    def test_dummy_is_unavailable_in_production(self):
        with self.assertRaises(PermissionDenied):create_dummy_event(self.admin,'prod')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('dummy_event'),{'nonce':'prod'}).status_code,403)

    def test_migration_renames_only_automatic_accounts_and_keeps_identity_and_roles(self):
        user=get_user_model().objects.create_user('entra_'+uuid.uuid4().hex,'MaxMustermann@example.org')
        role=Group.objects.create(name='Unchanged manual role');user.groups.add(role)
        identity=EntraIdentity.objects.create(user=user,tenant_id=uuid.uuid4(),object_id=uuid.uuid4())
        from django.apps import apps
        from django.db import connection
        migration=importlib.import_module('map.migrations.0014_readable_sso_names')
        migration.rename(apps,type('Editor',(),{'connection':connection})())
        user.refresh_from_db();identity.refresh_from_db()
        self.assertEqual(user.username,'MaxMustermann#SSO');self.assertFalse(user.has_usable_password())
        self.assertEqual(identity.user_id,user.pk);self.assertTrue(user.groups.filter(pk=role.pk).exists())

    def test_people_form_accepts_sso_suffix_but_rejects_other_hash_names(self):
        from map.sso_names import validate_portal_username
        from django.core.exceptions import ValidationError
        validate_portal_username('MaxMustermann#SSO')
        with self.assertRaises(ValidationError):validate_portal_username('Max#bad')

    def test_sso_user_can_be_edited_in_people_form(self):
        from map.people import PersonForm
        user=get_user_model().objects.create_user('MaxMustermann#SSO','MaxMustermann@example.org')
        form=PersonForm({'username':user.username,'email':user.email,'first_name':'Max','last_name':'Mustermann','is_active':'on'},instance=user,actor=self.admin)
        self.assertTrue(form.is_valid(),form.errors.as_text())
        saved=form.save();self.assertEqual(saved.username,'MaxMustermann#SSO')
        self.assertFalse(saved.has_usable_password())

    def test_queue_only_user_can_open_central_settings_without_admin_links(self):
        from django.contrib.auth.models import Permission
        user=get_user_model().objects.create_user('queue-only')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='map',codename='view_emailjob'))
        self.client.force_login(user)
        response=self.client.get(reverse('module_settings'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,reverse('mail_queue'))
        self.assertNotContains(response,reverse('sso_settings'))
