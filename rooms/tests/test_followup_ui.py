from datetime import timedelta
from django.test import override_settings
from django.urls import reverse
from .test_bookings import RoomBookingTests
from rooms.forms import BookingForm
from rooms.services import save_booking,decide

@override_settings(ALLOWED_HOSTS=['testserver'])
class RoomFollowupTests(RoomBookingTests.__bases__[0]):
    setUpTestData=classmethod(RoomBookingTests.setUpTestData.__func__)
    payload=RoomBookingTests.payload
    form_data=RoomBookingTests.form_data
    def test_past_booking_without_contact_can_be_saved_and_approved(self):
        day=self.day-timedelta(days=60)
        data=self.form_data(start_date=str(day),end_date=str(day),contact='')
        form=BookingForm(data);self.assertTrue(form.is_valid(),form.errors)
        row=save_booking(self.leader,form.cleaned_data);self.assertEqual(row.contact,'')
        decide(self.board,row.pk,'approve',row.version);row.refresh_from_db();self.assertEqual(row.status,'approved')
        self.client.force_login(self.board)
        response=self.client.get(reverse('rooms:new'))
        self.assertContains(response,'Kontakt/zusätzliche Angaben');self.assertContains(response,'data-date-only="true"')

    def test_decision_menu_uses_top_layer_and_preserves_server_permissions(self):
        row=save_booking(self.leader,self.payload());self.client.force_login(self.board)
        response=self.client.get(reverse('rooms:index'))
        self.assertContains(response,'popover="auto"');self.assertContains(response,'popovertarget="room-decision-')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('rooms:index')),'popovertarget="room-decision-')
        self.assertEqual(self.client.post(reverse('rooms:detail',args=[row.pk]),{'action':'approve','version':row.version}).status_code,403)
