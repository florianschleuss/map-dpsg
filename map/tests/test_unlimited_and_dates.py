import json
from django.test import TestCase,override_settings
from django.core.exceptions import ValidationError
from .test_pools_delete_smtp import EventFixture
from map.forms import EventSettingsForm,RegistrationForm
from map.setup_forms import CapacityForm
from map.services import rebalance,register
from map.widgets import QuickDateWidget

@override_settings(ALLOWED_HOSTS=['testserver'])
class UnlimitedTests(EventFixture,TestCase):
    def test_default_has_a_real_limit_and_explicit_unlimited_can_exceed_stored_numbers(self):
        self.assertEqual(self.event.capacity_mode,'per_group')
        self.event.capacity_mode='unlimited';self.event.capacity=1;self.event.save()
        for i in range(4):self.assertEqual(self.reg('Kind '+str(i),self.a).status,'confirmed')
        self.event.full_clean()

    def test_switching_to_unlimited_promotes_existing_waiters(self):
        self.reg('Erstes',self.a);waiting=self.reg('Wartend',self.a)
        self.assertEqual(waiting.status,'waitlisted')
        self.event.capacity_mode='unlimited';self.event.save();rebalance(self.event.pk)
        waiting.refresh_from_db();self.assertEqual(waiting.status,'confirmed')

    def test_unlimited_settings_need_stages_but_no_numbers(self):
        data=self.settings_data();data.update(capacity_mode='unlimited',group_limits=json.dumps({str(self.a.pk):None,str(self.b.pk):None}))
        form=EventSettingsForm(data,instance=self.event,actor=self.admin)
        self.assertTrue(form.is_valid(),form.errors);form.save()
        self.event.refresh_from_db();self.assertEqual(self.event.capacity_mode,'unlimited');self.assertFalse(self.event.waitlist_enabled)
        data['group_limits']='{}';self.assertFalse(EventSettingsForm(data,instance=self.event,actor=self.admin).is_valid())

    def test_limited_mode_still_rejects_shrinking_below_occupied(self):
        self.event.capacity_mode='unlimited';self.event.save()
        for i in range(3):self.reg('Kind '+str(i),self.a)
        form=EventSettingsForm(self.settings_data(),instance=self.event,actor=self.admin)
        self.assertFalse(form.is_valid())

    def test_wizard_accepts_unlimited_without_capacity_and_no_waitlist(self):
        form=CapacityForm({'capacity_mode':'unlimited','confirmation_hours':48,'waitlist_enabled':'on'})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(form.cleaned_data['waitlist_enabled']);self.assertEqual(form.cleaned_data['capacity_mode'],'unlimited')
        self.assertEqual(CapacityForm().fields['capacity_mode'].initial,'per_group')

    def test_public_page_never_displays_fake_free_places_for_unlimited(self):
        self.event.capacity_mode='unlimited';self.event.save()
        response=self.client.get('/events/'+self.event.slug+'/')
        self.assertContains(response,'Ohne Teilnahmelimit');self.assertNotContains(response,'Insgesamt 2 Plätze');self.assertNotContains(response,'frei /')

    def test_optional_date_widget_uses_shared_calendar_without_clock(self):
        from datetime import date
        html=QuickDateWidget().render('day',date(2027,3,1))
        self.assertIn('data-date-only="true"',html);self.assertIn('map-calendar',html);self.assertIn('value="2027-03-01"',html)
