from datetime import timedelta,time
import uuid
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from map.models import LeaderProfile,ScoutGroup,EmailJob,EventPermission
from map.demo_events import create_dummy_event
from map.sso_models import EntraIdentity
from map.user_deletion import deletion_context
from rooms.models import RoomBooking,Room
from rooms.forms import local_datetime

@override_settings(ALLOWED_HOSTS=['testserver'],PUBLIC_URL='https://dev.example.invalid',MAP_PRODUCTION=False)
class UserDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User=get_user_model()
        cls.root=User.objects.create_superuser('delete-root','root@example.invalid','strong-delete-password-123')
        cls.admin=User.objects.create_user('delete-admin','admin@example.invalid');cls.admin.groups.add(Group.objects.get(name='Admin'))
        cls.target=User.objects.create_user('delete-target','target@example.invalid','strong-delete-password-123')
        cls.outsider=User.objects.create_user('delete-outsider')
        cls.stage=ScoutGroup.objects.create(name='Delete-Stufe')
        profile=LeaderProfile.objects.create(user=cls.target,is_leader=True);profile.stages.add(cls.stage)

    def url(self,user=None):return reverse('person_delete',args=[(user or self.target).pk])
    def token(self,actor=None,user=None):return deletion_context(actor or self.root,user or self.target)['delete_account_token']
    def delete(self,user=None,actor=None,**extra):
        actor=actor or self.root;user=user or self.target;self.client.force_login(actor)
        return self.client.post(self.url(user),{'confirm_delete':'yes','delete_token':self.token(actor,user),**extra})

    def test_get_only_confirms_and_post_requires_explicit_confirmation(self):
        self.client.force_login(self.root)
        self.assertContains(self.client.get(self.url()),'Benutzer endgültig löschen')
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())
        self.client.post(self.url(),{'delete_token':self.token()})
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())
        self.assertEqual(self.delete().status_code,302);self.assertFalse(get_user_model().objects.filter(pk=self.target.pk).exists())

    def test_unauthorized_and_csrf_requests_cannot_delete(self):
        self.client.force_login(self.outsider);self.assertEqual(self.client.post(self.url(),{'confirm_delete':'yes'}).status_code,403)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.root)
        self.assertEqual(strict.post(self.url(),{'confirm_delete':'yes','delete_token':self.token()}).status_code,403)
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())

    def test_self_delete_and_technical_account_by_business_admin_are_blocked(self):
        self.client.force_login(self.root)
        self.assertContains(self.client.get(self.url(self.root)),'Dein eigenes Konto')
        self.assertEqual(self.delete(user=self.root).status_code,302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url(self.root),{'confirm_delete':'yes','delete_token':'fake'}).status_code,403)
        self.assertTrue(get_user_model().objects.filter(pk=self.root.pk).exists())

    def test_last_active_admin_remains_when_actor_only_has_user_management_permission(self):
        self.root.is_active=False;self.root.save()
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label='auth',codename='change_user'))
        self.outsider=get_user_model().objects.get(pk=self.outsider.pk)
        self.client.force_login(self.outsider)
        self.assertContains(self.client.get(self.url(self.admin)),'aktives Admin-Konto')
        self.client.post(self.url(self.admin),{'confirm_delete':'yes','delete_token':'fake'})
        self.assertTrue(get_user_model().objects.filter(pk=self.admin.pk).exists())

    def test_stale_or_wrong_actor_confirmation_is_rejected(self):
        token=self.token();self.target.username='renamed-target';self.target.save()
        self.client.force_login(self.root);self.client.post(self.url(),{'confirm_delete':'yes','delete_token':token})
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())
        token=self.token(self.root,self.target);self.client.force_login(self.admin)
        self.client.post(self.url(),{'confirm_delete':'yes','delete_token':token})
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())

    def test_removes_identity_permissions_and_reset_jobs_but_preserves_operational_data(self):
        event=create_dummy_event(self.root,'delete-fixtures')
        EventPermission.objects.create(event=event,user=self.target,role='editor')
        EntraIdentity.objects.create(user=self.target,tenant_id=uuid.uuid4(),object_id=uuid.uuid4())
        EmailJob.objects.create(reset_user=self.target,recipient=self.target.email,subject='Reset',body='Test',next_attempt=timezone.now())
        day=timezone.localdate()+timedelta(days=3)
        room=RoomBooking.objects.create(creator=self.target,decided_by=self.target,starts_at=local_datetime(day,time(9)),ends_at=local_datetime(day,time(17)),grouping='Test',purpose='Test',contact_person='Kontakt bleibt',contact='Kontakttext bleibt')
        room.rooms.add(Room.objects.first());template=event.form_template;template.created_by=self.target;template.save()
        from map.template_access import available_templates
        self.assertFalse(available_templates(self.outsider).filter(pk=template.pk).exists())
        target_id=self.target.pk;self.delete()
        self.assertFalse(EntraIdentity.objects.filter(user_id=target_id).exists())
        self.assertFalse(LeaderProfile.objects.filter(user_id=target_id).exists())
        self.assertFalse(EventPermission.objects.filter(user_id=target_id).exists())
        self.assertFalse(EmailJob.objects.filter(reset_user_id=target_id).exists())
        room.refresh_from_db();self.assertIsNone(room.creator_id);self.assertIsNone(room.decided_by_id);self.assertEqual(room.contact_person,'Kontakt bleibt')
        self.assertEqual(event.registrations.count(),29);template.refresh_from_db();self.assertEqual(template.created_by_id,self.root.pk)
        self.assertFalse(available_templates(self.outsider).filter(pk=template.pk).exists())

    def test_existing_session_loses_access_after_deletion(self):
        session_client=Client();session_client.force_login(self.target)
        self.delete();response=session_client.get(reverse('dashboard'));self.assertEqual(response.status_code,302)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_technical_status_is_rechecked_at_deletion_time(self):
        token=self.token(self.admin,self.target)
        get_user_model().objects.filter(pk=self.target.pk).update(is_superuser=True,is_staff=True)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.url(),{'confirm_delete':'yes','delete_token':token}).status_code,403)

    def test_person_editor_has_checkbox_text_wrapper_and_deletion_dialog(self):
        self.client.force_login(self.root);response=self.client.get(reverse('person_edit',args=[self.target.pk]))
        self.assertContains(response,'map-reset-confirmation');self.assertContains(response,'<span>Passwort-Link an die gespeicherte E-Mail-Adresse senden.</span>',html=True)
        self.assertContains(response,'data-open-dialog="delete-account-');self.assertContains(response,'Benutzer endgültig löschen')
