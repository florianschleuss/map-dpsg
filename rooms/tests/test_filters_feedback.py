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

    def test_past_is_hidden_but_ongoing_and_future_remain_visible(self):
        from django.utils import timezone
        now=timezone.now()
        past=save_booking(self.leader,self.payload(starts_at=now-timedelta(days=3),ends_at=now-timedelta(days=2)))
        ongoing=save_booking(self.leader,self.payload(starts_at=now-timedelta(hours=1),ends_at=now+timedelta(hours=1)))
        future=save_booking(self.leader,self.payload())
        self.client.force_login(self.leader)
        def ids(params):return {row.pk for row in self.client.get(reverse('rooms:index'),params).context['page']}
        self.assertEqual(ids({}),{ongoing.pk,future.pk})
        self.assertEqual(ids({'include_past':'on'}),{past.pk,ongoing.pk,future.pk})
        day=(now-timedelta(days=3)).date()
        self.assertIn(past.pk,ids({'start':str(day),'end':str(day+timedelta(days=1))}))
        self.assertTrue(RoomBooking.objects.filter(pk=past.pk).exists())

    def test_explicit_historical_calendar_and_exports_can_include_past(self):
        from django.utils import timezone
        now=timezone.now();past=save_booking(self.leader,self.payload(starts_at=now-timedelta(days=3),ends_at=now-timedelta(days=2)))
        self.client.force_login(self.leader)
        default=self.client.get(reverse('rooms:export',args=['ical']))
        self.assertNotIn(b'BEGIN:VEVENT',default.content)
        history=self.client.get(reverse('rooms:export',args=['ical']),{'include_past':'on'})
        self.assertIn(b'BEGIN:VEVENT',history.content)
        response=self.client.get(reverse('rooms:calendar'),{'date':str((now-timedelta(days=3)).date())})
        self.assertTrue(any(item['booking'].pk==past.pk for week in response.context['weeks'] for day in week for item in day['items']))
