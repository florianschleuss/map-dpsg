from datetime import timedelta
from django.test import override_settings
from django.urls import reverse
from .test_bookings import RoomBookingTests
from rooms.models import RoomBooking
from rooms.services import save_booking,cancel

@override_settings(ALLOWED_HOSTS=['testserver'])
class RoomFilterTests(RoomBookingTests.__bases__[0]):
    setUpTestData=classmethod(RoomBookingTests.setUpTestData.__func__)
    payload=RoomBookingTests.payload
    def test_cancelled_is_retained_but_hidden_by_default(self):
        kept=save_booking(self.leader,self.payload(purpose='Aktive Anfrage'))
        old=save_booking(self.leader,self.payload(purpose='Stornierte Anfrage'));cancel(self.leader,old.pk,old.version)
        self.client.force_login(self.leader)
        for params,expected in [({},[kept.pk]),({'status':'all'},[kept.pk,old.pk]),({'status':'cancelled'},[old.pk])]:
            response=self.client.get(reverse('rooms:index'),params)
            self.assertEqual(response.status_code,200)
            self.assertEqual(set(row.pk for row in response.context['page']),set(expected))
        self.assertTrue(RoomBooking.objects.filter(pk=old.pk,status='cancelled').exists())
        self.assertEqual(self.client.get(reverse('rooms:detail',args=[old.pk])).status_code,200)

    def test_export_and_date_filters_allow_explicit_all_statuses(self):
        row=save_booking(self.leader,self.payload());cancel(self.leader,row.pk,row.version)
        self.client.force_login(self.leader)
        response=self.client.get(reverse('rooms:export',args=['ical']))
        self.assertNotIn(b'BEGIN:VEVENT',response.content)
        response=self.client.get(reverse('rooms:export',args=['ical']),{'status':'all','start':str(self.day),'end':str(self.day)})
        self.assertIn(b'STATUS:CANCELLED',response.content)
        response=self.client.get(reverse('rooms:calendar'),{'status':'all','date':str(self.day)})
        self.assertTrue(any(cell['items'] for week in response.context['weeks'] for cell in week))

    def test_my_filter_is_retained_and_invalid_status_does_not_list_everything(self):
        save_booking(self.leader,self.payload());self.client.force_login(self.leader)
        self.assertContains(self.client.get(reverse('rooms:index'),{'mine':'1'}),'name="mine" value="1"')
        response=self.client.get(reverse('rooms:index'),{'status':'invalid'})
        self.assertEqual(response.context['page'].paginator.count,0)
