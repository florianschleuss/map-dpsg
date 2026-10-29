from datetime import timedelta,time,date
from unittest.mock import patch
from django.test import override_settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone
from .test_bookings import RoomBookingTests
from rooms.forms import BookingForm,local_datetime
from rooms.models import RoomBooking,BookingChange
from rooms.services import save_booking,decide,cancel,conflicts,conflict_token
from rooms.recurrence import intervals
from rooms.presentation import ical_bytes,period

# Reuse fixture helpers, not inherited test methods.
class WeeklyBookingTests(RoomBookingTests.__bases__[0]):
    setUpTestData=classmethod(RoomBookingTests.setUpTestData.__func__)
    payload=RoomBookingTests.payload
    form_data=RoomBookingTests.form_data
    @override_settings(ALLOWED_HOSTS=['testserver'],PUBLIC_URL='https://example.org')
    def test_weekly_form_create_edit_and_compact_decisions(self):
        data=self.form_data(recurring='on',weekday=str(self.day.weekday()),end_date=str(self.day+timedelta(days=21)))
        form=BookingForm(data);self.assertTrue(form.is_valid(),form.errors)
        row=save_booking(self.leader,form.cleaned_data);self.assertTrue(row.recurring)
        self.assertEqual(len(list(intervals(row))),4)
        self.client.force_login(self.board)
        response=self.client.get(reverse('rooms:pending'));self.assertContains(response,'data-room-row=');self.assertContains(response,'room-icon-action');self.assertContains(response,'room-decision-menu')
        self.assertNotContains(response,'Details / Entscheiden')
        self.assertEqual(self.client.post(reverse('rooms:detail',args=[row.pk]),{'action':'approve','version':row.version}).status_code,302)
        row.refresh_from_db();self.assertEqual(row.status,'approved')
        data.update(start_time='10:00',version=row.version)
        form=BookingForm(data,booking=row);self.assertTrue(form.is_valid(),form.errors)
        save_booking(self.leader,form.cleaned_data,row.pk);row.refresh_from_db()
        self.assertEqual(timezone.localtime(row.starts_at).hour,9)
        change=row.changes.get(status='pending');self.assertTrue(change.recurring)
        decide(self.board,row.pk,'approve',row.version,change_id=change.pk);row.refresh_from_db()
        self.assertEqual(timezone.localtime(row.starts_at).hour,10)
        cancel(self.leader,row.pk,row.version);row.refresh_from_db();self.assertEqual(row.status,'cancelled')

    def series(self):
        return save_booking(self.leader,self.payload(recurring=True,ends_at=local_datetime(self.day+timedelta(days=21),time(17))))

    def test_conflicts_use_actual_occurrences_and_adjacent_times(self):
        row=self.series()
        for offset,expected in [(0,1),(1,0),(7,1),(14,1),(21,1),(28,0)]:
            day=self.day+timedelta(days=offset)
            self.assertEqual(len(conflicts([self.room.pk],local_datetime(day,time(10)),local_datetime(day,time(11)))),expected)
        self.assertEqual(conflicts([self.room.pk],local_datetime(self.day,time(17)),local_datetime(self.day,time(18))),[])
        self.assertEqual(conflicts([self.garden.pk],row.starts_at,row.ends_at,recurring=True),[])
        self.assertEqual(conflicts([self.room.pk],row.starts_at+timedelta(days=1),row.ends_at+timedelta(days=1),recurring=True),[])

    def test_approved_conflicts_require_explicit_confirmation(self):
        row=self.series();decide(self.board,row.pk,'approve',row.version)
        other=save_booking(self.other,self.payload(starts_at=local_datetime(self.day+timedelta(days=7),time(10)),ends_at=local_datetime(self.day+timedelta(days=7),time(11))))
        with self.assertRaises(ValidationError):decide(self.board,other.pk,'approve',other.version)
        rows=conflicts([self.room.pk],other.starts_at,other.ends_at,other.pk)
        decide(self.board,other.pk,'approve',other.version,confirm=True,token=conflict_token(rows))

    @override_settings(ALLOWED_HOSTS=['testserver'])
    def test_public_api_and_calendar_do_not_fill_gaps(self):
        from rooms.models import RoomSettings
        row=self.series();RoomSettings.objects.filter(pk=1).update(public_api_enabled=True)
        response=self.client.get('/api/v1/rooms/occupancy/',{'start':str(self.day),'end':str(self.day+timedelta(days=21))})
        self.assertEqual(response.status_code,200)
        days=response.json()['days'];self.assertEqual([d['date'] for d in days],[str(self.day+timedelta(days=i)) for i in [0,7,14,21]])
        self.assertTrue(all(d['occupancy']=='partial' and self.room.name in d['rooms'] for d in days))
        self.client.force_login(self.leader)
        response=self.client.get(reverse('rooms:calendar'),{'date':str(self.day),'view':'week'})
        cells=[cell for week in response.context['weeks'] for cell in week]
        self.assertEqual(sum(bool(cell['items']) for cell in cells),1)
        response=self.client.get(reverse('rooms:index'),{'start':str(self.day+timedelta(days=1)),'end':str(self.day+timedelta(days=1))})
        self.assertEqual(response.context['page'].paginator.count,0)

    @override_settings(PUBLIC_URL='https://example.org')
    def test_ical_has_each_occurrence_and_readable_series_label(self):
        row=self.series();text=ical_bytes([row]).decode()
        self.assertEqual(text.count('BEGIN:VEVENT'),4)
        self.assertEqual(len({s for s in text.splitlines() if s.startswith('UID:')}),4)
        self.assertIn('Jeden ',period(row))

    def test_defaults_and_invalid_recurrence(self):
        self.assertFalse(BookingForm().initial.get('recurring',False))
        for changes in [dict(weekday=''),dict(all_day='on'),dict(end_time='08:00'),dict(end_date=str(self.day-timedelta(days=1))),dict(end_date=str(self.day+timedelta(days=4000)))]:
            data=self.form_data(recurring='on',weekday=str(self.day.weekday()),end_date=str(self.day+timedelta(days=14)));data.update(changes)
            self.assertFalse(BookingForm(data).is_valid(),changes)

    @override_settings(TIME_ZONE='Europe/Berlin')
    def test_local_hours_stay_stable_across_dst(self):
        from types import SimpleNamespace
        item=SimpleNamespace(recurring=True,all_day=False,starts_at=local_datetime(date(2027,3,21),time(9)),ends_at=local_datetime(date(2027,4,4),time(17)))
        values=list(intervals(item));self.assertEqual(len(values),3)
        self.assertEqual([timezone.localtime(a).hour for a,b in values],[9,9,9])
        self.assertNotEqual(values[0][0].utcoffset(),values[-1][0].utcoffset())
        item.starts_at=local_datetime(date(2027,3,21),time(2,30));item.ends_at=local_datetime(date(2027,4,4),time(4))
        with self.assertRaises(ValidationError):list(intervals(item))

    @override_settings(ALLOWED_HOSTS=['testserver'],PUBLIC_URL='https://example.org')
    def test_filtered_exports_and_live_conflicts_include_weekday(self):
        row=self.series();self.client.force_login(self.leader)
        day=self.day+timedelta(days=7)
        response=self.client.get(reverse('rooms:export',args=['ical']),{'start':str(day),'end':str(day)})
        self.assertEqual(response.status_code,200);self.assertEqual(response.content.count(b'BEGIN:VEVENT'),1)
        response=self.client.get(reverse('rooms:export',args=['excel']))
        self.assertEqual(response.status_code,200);self.assertTrue(response.content.startswith(b'PK'))
        data=self.form_data(recurring='on',weekday=str((self.day.weekday()+1)%7),end_date=str(self.day+timedelta(days=21)))
        response=self.client.post(reverse('rooms:live_conflicts'),data)
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['count'],0)
        data['weekday']=str(self.day.weekday())
        self.assertEqual(self.client.post(reverse('rooms:live_conflicts'),data).json()['count'],1)

    def test_pending_weekly_change_uses_new_weekday_and_keeps_original(self):
        row=self.series();decide(self.board,row.pk,'approve',row.version);row.refresh_from_db()
        start=row.starts_at+timedelta(days=1);end=row.ends_at+timedelta(days=1)
        save_booking(self.leader,self.payload(recurring=True,starts_at=start,ends_at=end,version=row.version),row.pk)
        row.refresh_from_db();self.assertNotEqual(row.starts_at,start)
        found=conflicts([self.room.pk],start,start+timedelta(hours=1))
        self.assertTrue(any(item['proposal'] for item in found))
        day=self.day+timedelta(days=2)
        self.assertFalse(conflicts([self.room.pk],local_datetime(day,time(10)),local_datetime(day,time(11))))
