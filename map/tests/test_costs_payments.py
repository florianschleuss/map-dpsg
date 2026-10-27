from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import Event,EventGroup,ScoutGroup,FormTemplate,Registration,EmailJob,PaymentBatch,AuditLog
from map.cost_forms import CostForm
from map.forms import EventSettingsForm
from map.services import register,confirm,token_for
from map.payments import payment_details,payment_text

IBAN='DE89370400440532013000'
@override_settings(SECURE_SSL_REDIRECT=False,PUBLIC_URL='https://map.example.org')
class CostAndPaymentTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='kostenadmin',email='admin@example.org',password='Strong-admin-pass-593!')
        self.reader=get_user_model().objects.create_user(username='kostenleser');self.reader.groups.add(Group.objects.get(name='Read-Only'))
        self.stage=ScoutGroup.objects.create(name='Kostenstufe');self.template=FormTemplate.objects.create(name='LeerKosten')
        now=timezone.now();self.event=Event.objects.create(group=self.stage,form_template=self.template,title='Sommerlager Kosten',slug='sommerlager-kosten',published=True,capacity=10,confirmation_required=True,starts_at=now+timedelta(days=30),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=20),cost_mode='fixed',cost_amount=Decimal('25.50'),payment_method='transfer',bank_account_holder='Beispielstamm',bank_iban=IBAN,costs_configured=True)
        self.slot=EventGroup.objects.create(event=self.event,group=self.stage,capacity=10)
    def signup(self,name='Alex Kosten'):
        return register(self.event.pk,name,'parent@example.org',{})
    def confirmed(self,name='Alex Kosten'):
        return confirm(self.signup(name).pk)
    def method(self,value):self.event.payment_method=value;self.event.save(update_fields=['payment_method'])
    def form_data(self,**updates):
        data={'cost_mode':'fixed','cost_amount':'25,50','payment_method':'transfer','bank_account_holder':'Stamm','bank_iban':IBAN};data.update(updates);return data
    def test_cost_form_accepts_german_amount_and_normalizes_iban(self):
        form=CostForm(self.form_data(bank_iban='DE89 3704 0044 0532 0130 00'));self.assertTrue(form.is_valid(),form.errors);self.assertEqual(form.cleaned_data['cost_amount'],Decimal('25.50'));self.assertEqual(form.cleaned_data['bank_iban'],IBAN)
    def test_one_cent_is_valid_decimal_minimum(self):
        form=CostForm(self.form_data(cost_amount='0,01'));self.assertTrue(form.is_valid(),form.errors)
    def test_free_and_cash_need_no_bank_details(self):
        for data in [{'cost_mode':'free'},{'cost_mode':'fixed','cost_amount':'10','payment_method':'cash'}]:
            form=CostForm(data);self.assertTrue(form.is_valid(),form.errors)
    def test_custom_needs_cost_description(self):
        form=CostForm(self.form_data(cost_mode='custom'));self.assertFalse(form.is_valid())
    def test_public_registration_shows_cost_but_no_bank_details(self):
        response=self.client.get(reverse('event',args=[self.event.slug]));self.assertContains(response,'25,50');self.assertNotContains(response,IBAN);self.assertNotContains(response,'Beispielstamm</dd>')
    def test_pending_parent_page_and_mail_hide_bank_details(self):
        row=self.signup();response=self.client.get(reverse('manage',args=[token_for(row,'manage')]))
        self.assertNotContains(response,IBAN);self.assertNotIn(IBAN,EmailJob.objects.get(event=self.event).body);self.assertFalse(payment_details(row)['visible'])
    def test_confirmation_exposes_bank_details_and_mail_instructions(self):
        row=self.confirmed();response=self.client.get(reverse('manage',args=[token_for(row,'manage')]))
        self.assertContains(response,IBAN);self.assertContains(response,'Sommerlager Kosten - Alex Kosten');self.assertTrue(payment_details(row)['visible']);self.assertIn(IBAN,EmailJob.objects.filter(event=self.event).latest('pk').body)
    def test_verified_waitlist_never_sees_transfer_details(self):
        self.slot.capacity=1;self.slot.save();self.event.capacity=1;self.event.save(update_fields=['capacity']);self.confirmed('Erstes Kind')
        row=confirm(self.signup('Wartelistenkind').pk);self.assertEqual(row.status,'waitlisted');self.assertTrue(row.email_verified)
        response=self.client.get(reverse('manage',args=[token_for(row,'manage')]));self.assertNotContains(response,IBAN)
        self.assertEqual(self.client.get(reverse('payment_qr',args=[token_for(row,'manage')])).status_code,403)
    def test_cash_hint_is_available_before_confirmation(self):
        self.method('cash');row=self.signup();response=self.client.get(reverse('event',args=[self.event.slug]))
        self.assertContains(response,'bar zur Veranstaltung');self.assertIn('bar zur Veranstaltung',payment_text(row));self.assertFalse(payment_details(row)['visible'])
    def test_reminder_hides_account_until_manual_release(self):
        self.method('reminder');row=self.confirmed();self.assertNotIn(IBAN,payment_text(row));self.assertFalse(payment_details(row)['visible'])
        self.event.payment_released_at=timezone.now();self.event.save(update_fields=['payment_released_at']);row.refresh_from_db();self.assertIn(IBAN,payment_text(row))
    def test_qr_is_private_and_contains_valid_png(self):
        row=self.confirmed();url=reverse('payment_qr',args=[token_for(row,'manage')]);response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertEqual(response['Content-Type'],'image/png');self.assertTrue(response.content.startswith(b'\x89PNG'));self.assertEqual(response['Cache-Control'],'no-store')
        self.assertEqual(self.client.get(reverse('payment_qr',args=['invalid'])).status_code,404)
    def test_pending_cancelled_and_expired_qr_are_denied(self):
        row=self.signup()
        for status in ['pending','waitlisted','cancelled','expired']:
            Registration.objects.filter(pk=row.pk).update(status=status)
            self.assertEqual(self.client.get(reverse('payment_qr',args=[token_for(row,'manage')])).status_code,403)
    def test_custom_cost_qr_has_no_inferred_amount(self):
        self.event.cost_mode='custom';self.event.cost_amount=None;self.event.cost_text='Nach Absprache';self.event.save()
        row=self.confirmed();self.assertIsNone(payment_details(row)['amount'])
    def test_fees_are_frozen_after_first_registration(self):
        self.signup();self.event.cost_amount=Decimal('50.00')
        with self.assertRaises(ValidationError):self.event.full_clean()
    def test_bank_details_can_be_corrected_after_signup(self):
        self.signup();self.event.bank_account_holder='Korrigierter Name';self.event.full_clean();self.event.save();self.assertEqual(Event.objects.get(pk=self.event.pk).bank_account_holder,'Korrigierter Name')
    def test_settings_disable_frozen_fee_controls(self):
        self.signup();form=EventSettingsForm(instance=self.event,actor=self.admin)
        for name in ['cost_mode','cost_amount','cost_text','payment_method']:self.assertTrue(form.fields[name].disabled)
    def test_reminder_batch_only_targets_confirmed_unpaid(self):
        self.method('reminder');open_row=self.confirmed('Offen');paid=self.confirmed('Bezahlt');paid.payment_received_at=timezone.now();paid.save(update_fields=['payment_received_at']);self.signup('Unbestätigt')
        self.client.force_login(self.admin);url=reverse('request_payments',args=[self.event.pk]);response=self.client.get(url);self.assertEqual(response.context['eligible_count'],1)
        token=response.context['batch_token'];before=EmailJob.objects.count()
        self.assertEqual(self.client.post(url,{'batch_token':token,'confirm_send':'yes'}).status_code,302)
        self.assertEqual(EmailJob.objects.count(),before+1);self.assertEqual(PaymentBatch.objects.get(event=self.event).recipient_count,1)
        self.event.refresh_from_db();self.assertIsNotNone(self.event.payment_released_at)
        self.assertIn(IBAN,EmailJob.objects.latest('pk').body)
        self.client.post(url,{'batch_token':token,'confirm_send':'yes'});self.assertEqual(EmailJob.objects.count(),before+1)
    def test_reminder_requires_confirmation_and_valid_token(self):
        self.method('reminder');self.confirmed();self.client.force_login(self.admin);url=reverse('request_payments',args=[self.event.pk]);before=EmailJob.objects.count()
        self.client.post(url,{'confirm_send':'yes','batch_token':'invalid'});self.client.post(url,{})
        self.assertEqual(EmailJob.objects.count(),before);self.assertFalse(PaymentBatch.objects.exists())
    def test_reader_cannot_trigger_reminders_or_mark_paid(self):
        row=self.confirmed();self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse('request_payments',args=[self.event.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse('record_payment',args=[row.pk]),{'action':'received'}).status_code,403)
    def test_recording_payment_is_manual_and_reversible(self):
        row=self.confirmed();self.client.force_login(self.admin);url=reverse('record_payment',args=[row.pk])
        self.assertEqual(self.client.post(url,{'action':'received'}).status_code,302);row.refresh_from_db();self.assertIsNotNone(row.payment_received_at);self.assertEqual(row.payment_received_by,self.admin)
        self.client.post(url,{'action':'undo'});row.refresh_from_db();self.assertIsNone(row.payment_received_at)
    def test_pending_row_cannot_be_marked_paid(self):
        row=self.signup();self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('record_payment',args=[row.pk]),{'action':'received'}).status_code,403)
    def test_financial_posts_are_csrf_protected(self):
        row=self.confirmed();client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        for name,pk in [('request_payments',self.event.pk),('record_payment',row.pk)]:self.assertEqual(client.post(reverse(name,args=[pk]),{}).status_code,403)
    def test_cancelled_mail_does_not_ask_for_cash_or_transfer(self):
        self.method('cash');row=self.signup();row.status='cancelled';self.assertNotIn('Geld bar',payment_text(row));self.assertNotIn(IBAN,payment_text(row))
    def test_unpaid_status_is_exported_without_bank_details(self):
        self.confirmed();self.client.force_login(self.admin);response=self.client.get(reverse('export_csv',args=[self.event.pk]));self.assertContains(response,'Zahlungseingang manuell bestätigt');self.assertNotContains(response,IBAN)
    def test_later_confirmation_after_release_gets_payment_details(self):
        self.method('reminder');self.event.payment_released_at=timezone.now();self.event.save(update_fields=['payment_released_at']);self.confirmed()
        self.assertIn(IBAN,EmailJob.objects.latest('pk').body)

    def test_worker_drops_request_after_cancellation_instead_of_sending_bank_data(self):
        self.method('reminder');row=self.confirmed();EmailJob.objects.all().delete();self.client.force_login(self.admin);url=reverse('request_payments',args=[self.event.pk]);token=self.client.get(url).context['batch_token'];self.client.post(url,{'batch_token':token,'confirm_send':'yes'})
        job=EmailJob.objects.get(payment_request=True);Registration.objects.filter(pk=row.pk).update(status='cancelled')
        from django.core.management import call_command
        with patch('map.management.commands.process_queue.send_mail') as send:call_command('process_queue')
        send.assert_not_called();job.refresh_from_db();self.assertEqual(job.last_error,'PaymentRequestObsolete');self.assertNotIn(IBAN,job.body)
    def test_worker_drops_request_if_paid_or_bank_data_changed(self):
        self.method('reminder');row=self.confirmed();EmailJob.objects.all().delete();self.client.force_login(self.admin);url=reverse('request_payments',args=[self.event.pk]);token=self.client.get(url).context['batch_token'];self.client.post(url,{'batch_token':token,'confirm_send':'yes'})
        self.event.bank_account_holder='Neuer Kontoinhaber';self.event.save(update_fields=['bank_account_holder'])
        from django.core.management import call_command
        with patch('map.management.commands.process_queue.send_mail') as send:call_command('process_queue')
        send.assert_not_called();self.assertEqual(EmailJob.objects.get(payment_request=True).last_error,'PaymentRequestObsolete')

@override_settings(SECURE_SSL_REDIRECT=False)
class WizardCostTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='wizardcost10',email='admin@example.org',password='Strong-admin-pass-593!');self.stage=ScoutGroup.objects.create(name='Wizardkosten');self.client.force_login(self.admin)
        self.url=self.client.get('/admin/veranstaltung-anlegen/').url;self.draft_id=self.url.split('entwurf=')[1]
        now=timezone.localtime(timezone.now())
        self.post(1,title='Kostenlager',groups=[self.stage.pk]);self.post(2,starts_at=(now+timedelta(days=30)).isoformat(),registration_opens=(now-timedelta(days=1)).isoformat(),registration_closes=(now+timedelta(days=20)).isoformat());self.post(3,capacity='20',confirmation_hours='48');self.post(4);self.post(5)
    def post(self,step,**data):return self.client.post(self.url,dict(data,draft_id=self.draft_id,step=str(step)))
    def test_new_cost_step_saves_fixed_contribution_and_bank_details(self):
        response=self.client.get(self.url);self.assertContains(response,'Kosten und Bezahlung');self.assertContains(response,'Sieben kurze Schritte')
        self.assertEqual(self.post(6,cost_mode='fixed',cost_amount='25,50',payment_method='transfer',bank_account_holder='Stamm',bank_iban=IBAN).status_code,302)
        self.assertEqual(self.post(7,acknowledge='on').status_code,302)
        event=Event.objects.get();self.assertEqual(event.cost_amount,Decimal('25.50'));self.assertEqual(event.bank_iban,IBAN);self.assertTrue(event.costs_configured)
    def test_cost_input_survives_back_navigation_without_decimal_shift(self):
        self.post(6,cost_mode='fixed',cost_amount='25,50',payment_method='cash',action='back');self.post(5)
        response=self.client.get(self.url);self.assertEqual(response.context['form'].initial['cost_amount'],'25,50')
