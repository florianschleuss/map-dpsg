from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from map.models import EmailJob
from map.mailer import decrypt_password
from map.people import PersonForm
from map.account_security import can_edit_person,technical_admin

@override_settings(SECURE_SSL_REDIRECT=False,PUBLIC_URL='https://map.example.org',PASSWORD_RESET_TIMEOUT=3600)
class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.User=get_user_model();self.root=self.User.objects.create_superuser(username='tech-root10',email='root@example.org',password='Strong-root-pass-593!')
        self.admin=self.User.objects.create_user(username='business-admin10',email='admin@example.org');self.admin.groups.add(Group.objects.get(name='Admin'))
        self.user=self.User.objects.create_user(username='reset-user10',email='person@example.org',password='Original-password-593!')
        self.url=reverse('send_password_reset',args=[self.user.pk]);self.client.force_login(self.admin)
    def queued_reset(self):
        self.assertEqual(self.client.post(self.url,{'confirm_reset':'yes'}).status_code,302);return EmailJob.objects.get(reset_user=self.user,sent_at__isnull=True)
    def test_admin_can_queue_password_reset_for_regular_account(self):
        job=self.queued_reset();self.assertEqual(job.recipient,self.user.email);self.assertIsNone(job.event_id);self.assertTrue(job.body_encrypted)
    def test_reset_link_and_token_are_not_exposed_in_queue_body(self):
        job=self.queued_reset();token=decrypt_password(job.reset_token_encrypted)
        self.assertNotIn(token,job.body);self.assertNotIn('/konto/passwort/',job.body);self.assertNotEqual(job.body_encrypted,decrypt_password(job.body_encrypted))
        self.assertIn('/konto/passwort/',decrypt_password(job.body_encrypted))
        response=self.client.get(reverse('mail_queue'));self.assertNotContains(response,token)
    def test_trigger_requires_post_and_explicit_confirmation(self):
        self.assertEqual(self.client.get(self.url).status_code,405);self.client.post(self.url,{})
        self.assertFalse(EmailJob.objects.exists())
    def test_trigger_requires_user_management_permission(self):
        self.client.force_login(self.user);self.assertEqual(self.client.post(self.url,{'confirm_reset':'yes'}).status_code,403)
    def test_missing_email_and_inactive_user_are_reported_without_queueing(self):
        self.user.email='';self.user.save();response=self.client.post(self.url,{'confirm_reset':'yes'},follow=True);self.assertContains(response,'E-Mail-Adresse');self.assertFalse(EmailJob.objects.exists())
        self.user.email='person@example.org';self.user.is_active=False;self.user.save();self.client.post(self.url,{'confirm_reset':'yes'});self.assertFalse(EmailJob.objects.exists())
    def test_new_request_replaces_only_unsent_reset_jobs(self):
        first=self.queued_reset();self.queued_reset();self.assertEqual(EmailJob.objects.filter(reset_user=self.user).count(),1);self.assertFalse(EmailJob.objects.filter(pk=first.pk).exists())
    def test_password_link_completes_flow_and_invalidates_old_token(self):
        job=self.queued_reset();token=decrypt_password(job.reset_token_encrypted);uid=urlsafe_base64_encode(force_bytes(self.user.pk));url=reverse('password_reset_confirm',kwargs={'uidb64':uid,'token':token})
        self.client.logout();response=self.client.get(url);self.assertEqual(response.status_code,302)
        set_url=response.url;response=self.client.post(set_url,{'new_password1':'New-strong-password-912!','new_password2':'New-strong-password-912!'})
        self.assertEqual(response.status_code,302);self.assertEqual(response.url,reverse('password_reset_complete'));self.user.refresh_from_db();self.assertTrue(self.user.check_password('New-strong-password-912!'));self.assertFalse(default_token_generator.check_token(self.user,token))
    def test_expired_token_does_not_show_password_form(self):
        job=self.queued_reset();token=decrypt_password(job.reset_token_encrypted);uid=urlsafe_base64_encode(force_bytes(self.user.pk))
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            response=self.client.get(reverse('password_reset_confirm',kwargs={'uidb64':uid,'token':token}));self.assertContains(response,'ungültig');self.assertNotContains(response,'name="new_password1"')
    def test_worker_discards_stale_reset_without_sending(self):
        job=self.queued_reset();self.user.set_password('Changed-before-send-593!');self.user.save()
        with patch('map.management.commands.process_queue.send_mail') as send:call_command('process_queue')
        send.assert_not_called();job.refresh_from_db();self.assertEqual(job.last_error,'PasswordResetExpired');self.assertEqual(job.body_encrypted,'');self.assertEqual(job.reset_token_encrypted,'')
    def test_worker_decrypts_only_for_send_and_clears_secret_after_acceptance(self):
        job=self.queued_reset()
        with patch('map.management.commands.process_queue.send_mail',return_value=1) as send:call_command('process_queue')
        self.assertIn('/konto/passwort/',send.call_args.args[1]);job.refresh_from_db();self.assertIsNotNone(job.sent_at);self.assertEqual(job.body_encrypted,'');self.assertEqual(job.reset_token_encrypted,'')
    def test_reset_posts_require_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.root);self.assertEqual(client.post(self.url,{'confirm_reset':'yes'}).status_code,403)
    def test_business_admin_cannot_modify_or_reset_technical_account(self):
        self.assertFalse(can_edit_person(self.admin,self.root))
        self.assertEqual(self.client.get(reverse('person_edit',args=[self.root.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse('send_password_reset',args=[self.root.pk]),{'confirm_reset':'yes'}).status_code,403)
        self.assertEqual(self.client.get('/admin/auth/user/'+str(self.root.pk)+'/password/').status_code,403)
    def test_only_technical_admin_gets_technical_status_control(self):
        self.assertIn('technical_admin',PersonForm(instance=self.user,actor=self.root).fields)
        self.assertNotIn('technical_admin',PersonForm(instance=self.user,actor=self.admin).fields)
    def test_forged_technical_admin_flag_is_rejected(self):
        form=PersonForm({'username':self.user.username,'is_active':'on','technical_admin':'on'},instance=self.user,actor=self.admin)
        self.assertFalse(form.is_valid());self.user.refresh_from_db();self.assertFalse(self.user.is_superuser)
    def test_technical_admin_can_promote_and_demote_another_account(self):
        form=PersonForm({'username':self.user.username,'email':self.user.email,'is_active':'on','technical_admin':'on'},instance=self.user,actor=self.root)
        self.assertTrue(form.is_valid(),form.errors);form.save();self.user.refresh_from_db();self.assertTrue(self.user.is_superuser);self.assertTrue(self.user.is_staff)
        form=PersonForm({'username':self.user.username,'email':self.user.email,'is_active':'on'},instance=self.user,actor=self.root)
        self.assertTrue(form.is_valid(),form.errors);form.save();self.user.refresh_from_db();self.assertFalse(self.user.is_superuser)
    def test_last_technical_admin_cannot_be_demoted_even_with_business_admin_remaining(self):
        form=PersonForm({'username':self.root.username,'email':self.root.email,'is_active':'on'},instance=self.root,actor=self.root)
        self.assertTrue(form.is_valid(),form.errors)
        with self.assertRaises(ValidationError):form.save()
        self.root.refresh_from_db();self.assertTrue(self.root.is_superuser)
    def test_password_reset_template_is_protected_from_business_admin(self):
        self.assertEqual(self.client.get(reverse('email_template_edit',args=['password_reset'])).status_code,403)
        self.client.force_login(self.root);self.assertEqual(self.client.get(reverse('email_template_edit',args=['password_reset'])).status_code,200)
    def test_token_recipient_comes_from_saved_account_not_posted_address(self):
        self.client.post(self.url,{'confirm_reset':'yes','email':'attacker@example.org'});self.assertEqual(EmailJob.objects.get(reset_user=self.user).recipient,self.user.email)

    def test_account_promoted_during_form_validation_is_not_modified_by_business_admin(self):
        original=PersonForm.is_valid;target_id=self.user.pk
        def validate_then_promote(form):
            valid=original(form);self.User.objects.filter(pk=target_id).update(is_superuser=True,is_staff=True);return valid
        with patch.object(PersonForm,'is_valid',validate_then_promote):
            response=self.client.post(reverse('person_edit',args=[self.user.pk]),{'username':self.user.username,'email':self.user.email,'is_active':'on'})
        self.assertEqual(response.status_code,403);self.user.refresh_from_db();self.assertTrue(self.user.is_superuser)
    def test_recent_password_change_is_not_overwritten_by_unrelated_account_edit(self):
        original=PersonForm.is_valid;target_id=self.user.pk
        def validate_then_reset(form):
            valid=original(form);current=self.User.objects.get(pk=target_id);current.set_password('Concurrent-reset-912!');current.save(update_fields=['password']);return valid
        with patch.object(PersonForm,'is_valid',validate_then_reset):
            response=self.client.post(reverse('person_edit',args=[self.user.pk]),{'username':self.user.username,'email':self.user.email,'is_active':'on'})
        self.assertEqual(response.status_code,302);self.user.refresh_from_db();self.assertTrue(self.user.check_password('Concurrent-reset-912!'))
