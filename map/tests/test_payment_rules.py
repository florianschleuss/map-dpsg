import unittest
from decimal import Decimal
from types import SimpleNamespace
from map.payment_rules import normalized_costs,normalize_iban,epc_payload,payment_visible,cost_label,transfer_data

IBAN='DE89370400440532013000'
class PaymentRuleTests(unittest.TestCase):
    def data(self,**updates):
        value={'cost_mode':'fixed','cost_amount':'25.50','payment_method':'transfer','bank_account_holder':'Beispielstamm','bank_iban':IBAN,'bank_bic':'','cost_text':'','payment_note':'','payment_due':None};value.update(updates);return value
    def event(self,**updates):
        values=self.data();values.update(payment_released_at=None,cost_amount=Decimal('25.50'));values.update(updates);return SimpleNamespace(**values)
    def test_free_clears_all_payment_details(self):
        data=normalized_costs(self.data(cost_mode='free'));self.assertEqual(data['payment_method'],'none');self.assertIsNone(data['cost_amount']);self.assertEqual(data['bank_iban'],'')
    def test_fixed_uses_exact_decimal(self):self.assertEqual(normalized_costs(self.data())['cost_amount'],Decimal('25.50'))
    def test_fixed_rejects_missing_zero_negative_nan_and_fractional_cents(self):
        for amount in [None,'0','-1','NaN','Infinity','1.001','1000000','not-a-number']:
            with self.subTest(amount=amount),self.assertRaises(ValueError):normalized_costs(self.data(cost_amount=amount))
    def test_custom_requires_text_and_leaves_transfer_amount_empty(self):
        with self.assertRaises(ValueError):normalized_costs(self.data(cost_mode='custom',cost_text=''))
        data=normalized_costs(self.data(cost_mode='custom',cost_text='Beitrag nach Absprache'));self.assertIsNone(data['cost_amount'])
        payload=epc_payload(data['bank_account_holder'],data['bank_iban'],'',data['cost_amount'],'Lager - Kind');self.assertEqual(payload.split('\n')[7],'')
    def test_invalid_payment_method_is_rejected(self):
        with self.assertRaises(ValueError):normalized_costs(self.data(payment_method='credit_card'))
    def test_cash_needs_no_bank_account(self):
        data=normalized_costs(self.data(payment_method='cash',bank_iban=''));self.assertEqual(data['bank_iban'],'')
    def test_bank_and_reminder_need_valid_account_holder_and_iban(self):
        for method in ['transfer','reminder']:
            for updates in [{'bank_account_holder':''},{'bank_iban':'not-an-iban'}]:
                with self.assertRaises(ValueError):normalized_costs(self.data(payment_method=method,**updates))
    def test_iban_is_normalized_and_checksum_checked(self):
        self.assertEqual(normalize_iban('de89 3704 0044 0532 0130 00'),IBAN)
        with self.assertRaises(ValueError):normalize_iban('DE88370400440532013000')
    def test_invalid_iban_country_length_is_rejected(self):
        with self.assertRaises(ValueError):normalize_iban(IBAN+'0')
    def test_bic_is_normalized_and_validated(self):
        self.assertEqual(normalized_costs(self.data(bank_bic='cobadeffxxx'))['bank_bic'],'COBADEFFXXX')
        with self.assertRaises(ValueError):normalized_costs(self.data(bank_bic='invalid'))
    def test_non_eea_account_requires_bic(self):
        with self.assertRaises(ValueError):normalized_costs(self.data(bank_iban='GB82WEST12345698765432'))
        self.assertEqual(normalized_costs(self.data(bank_iban='GB82WEST12345698765432',bank_bic='DABAIE2D'))['bank_bic'],'DABAIE2D')
    def test_epc_has_correct_fields_amount_and_unstructured_reference(self):
        fields=epc_payload('Stamm',IBAN,'',Decimal('25.50'),'Sommerlager - Alex').split('\n')
        self.assertEqual(fields[:4],['BCD','002','1','SCT']);self.assertEqual(fields[6],IBAN);self.assertEqual(fields[7],'EUR25.50');self.assertEqual(fields[9],'');self.assertEqual(fields[10],'Sommerlager - Alex')
    def test_epc_never_ends_with_separator(self):self.assertFalse(epc_payload('Stamm',IBAN,'',None,'Lager').endswith('\n'))
    def test_epc_collapses_newline_injection(self):
        fields=epc_payload('Stamm\nFremde Daten',IBAN,'',1,'Lager\r\nKind').split('\n');self.assertEqual(len(fields),11);self.assertEqual(fields[5],'Stamm Fremde Daten');self.assertEqual(fields[10],'Lager Kind')
    def test_epc_validates_amount_without_float_rounding(self):
        for amount in ['NaN','0','-1','2.001','bad']:
            with self.assertRaises(ValueError):epc_payload('Stamm',IBAN,'',amount,'Kind')
    def test_payload_respects_utf8_budget(self):
        payload=epc_payload('Ä'*70,IBAN,'',10,'Ü'*140);self.assertLessEqual(len(payload.encode()),331);self.assertLessEqual(len(payload.split('\n')[10]),140)
    def test_reference_retains_event_and_child_and_matches_qr(self):
        reference,payload=transfer_data('Sommerlager','Alex Kind','Stamm',IBAN,'',25);self.assertEqual(reference,'Sommerlager - Alex Kind');self.assertEqual(payload.split('\n')[10],reference)
    def test_long_reference_retains_parts_of_both_names(self):
        reference,payload=transfer_data('Ä'*200,'Ö'*160,'Ü'*70,IBAN,'',25);self.assertIn('Ä',reference);self.assertIn('Ö',reference);self.assertLessEqual(len(payload.encode()),331);self.assertLessEqual(len(reference),140)
    def test_payment_details_hidden_until_confirmed_status(self):
        event=self.event()
        for status in ['pending','waitlisted','cancelled','expired']:self.assertFalse(payment_visible(event,SimpleNamespace(status=status)),status)
        self.assertTrue(payment_visible(event,SimpleNamespace(status='confirmed')))
    def test_email_verified_waitlist_is_still_not_payment_eligible(self):self.assertFalse(payment_visible(self.event(),SimpleNamespace(status='waitlisted',email_verified=True)))
    def test_reminder_needs_manual_release_even_when_confirmed(self):
        event=self.event(payment_method='reminder');row=SimpleNamespace(status='confirmed');self.assertFalse(payment_visible(event,row));event.payment_released_at='released';self.assertTrue(payment_visible(event,row))
    def test_cash_and_free_never_expose_transfer_details(self):
        row=SimpleNamespace(status='confirmed');self.assertFalse(payment_visible(self.event(payment_method='cash'),row));self.assertFalse(payment_visible(self.event(cost_mode='free'),row))
    def test_german_cost_labels(self):
        self.assertEqual(cost_label(self.event()),'25,50 € pro Person');self.assertEqual(cost_label(self.event(cost_mode='free')),'Kostenlos');self.assertEqual(cost_label(self.event(cost_mode='custom',cost_text='Nach Absprache')),'Nach Absprache')

if __name__=='__main__':unittest.main(verbosity=2)
