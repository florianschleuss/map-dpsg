"""Advisory weekly sessions must never become reservations."""
from datetime import date,time,timedelta
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.core.exceptions import ValidationError
from rooms.models import GroupSession,RoomBooking,RoomSettings
from rooms.group_sessions import GroupSessionForm
from rooms.forms import local_datetime
from rooms.services import conflicts,save_booking,decide,conflict_token
from rooms.tests import test_bookings as booking_fixtures

@override_settings(SECURE_SSL_REDIRECT=False,ALLOWED_HOSTS=['testserver'],PUBLIC_URL='https://example.org')
class GroupSessionTests(TestCase):
    setUpTestData=classmethod(booking_fixtures.RoomBookingTests.setUpTestData.__func__)
    payload=booking_fixtures.RoomBookingTests.payload
    form_data=booking_fixtures.RoomBookingTests.form_data

    def setUp(self):
        self.day=date(2027,2,1) # Monday
        self.session=GroupSession.objects.create(weekday=0,start_time=time(17),end_time=time(19),group_name='Wölflinge Gruppe 2')
        self.session.rooms.add(self.room)

    def session_data(self,**extra):
        data={'action':'save','weekday':'0','start_time':'17:00','end_time':'19:00','rooms':[self.room.pk],'group_name':'Wölflinge Gruppe 2','version':'1'}
        data.update(extra);return data

    def hits(self,first,last,rooms=None,recurring=False):
        return conflicts([r.pk for r in (rooms or [self.room])],first,last,recurring=recurring)

    def test_only_approvers_can_list_create_edit_or_delete(self):
        paths=[reverse('rooms:group_sessions'),reverse('rooms:group_session_edit',args=[self.session.pk])]
        for user in [self.leader,self.other,self.outsider]:
            self.client.force_login(user)
            for path in paths:
                self.assertEqual(self.client.get(path).status_code,403)
                self.assertEqual(self.client.post(path,self.session_data()).status_code,403)
                self.assertEqual(self.client.post(path,{'action':'delete','confirm':'yes','version':'1'}).status_code,403)
        self.assertTrue(GroupSession.objects.filter(pk=self.session.pk).exists())
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label='rooms',codename='manage_bookings'))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(paths[0]).status_code,200)
        for user in [self.board,self.admin]:
            self.client.force_login(user);self.assertContains(self.client.get(paths[0]),'Wölflinge Gruppe 2')

    def test_create_edit_and_stale_version(self):
        self.client.force_login(self.board)
        response=self.client.post(reverse('rooms:group_sessions'),self.session_data(group_name='Neue Gruppe'))
        self.assertEqual(response.status_code,302)
        row=GroupSession.objects.get(group_name='Neue Gruppe')
        self.assertEqual(row.updated_by,self.board)
        url=reverse('rooms:group_session_edit',args=[row.pk])
        self.assertEqual(self.client.post(url,self.session_data(group_name='Umbenannt')).status_code,302)
        row.refresh_from_db();self.assertEqual(row.version,2)
        response=self.client.post(url,self.session_data(group_name='Veralteter Stand'))
        self.assertContains(response,'zwischenzeitlich geändert');row.refresh_from_db();self.assertEqual(row.group_name,'Umbenannt')

    def test_delete_requires_explicit_confirmation_and_current_version(self):
        self.client.force_login(self.board);url=reverse('rooms:group_session_edit',args=[self.session.pk])
        self.client.post(url,{'action':'delete','version':'1'})
        self.assertTrue(GroupSession.objects.filter(pk=self.session.pk).exists())
        self.client.post(url,{'action':'delete','version':'0','confirm':'yes'})
        self.assertTrue(GroupSession.objects.filter(pk=self.session.pk).exists())
        self.client.post(url,{'action':'delete','version':'1','confirm':'yes'})
        self.assertFalse(GroupSession.objects.filter(pk=self.session.pk).exists())

    def test_csrf_is_required(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.board)
        self.assertEqual(client.post(reverse('rooms:group_sessions'),self.session_data()).status_code,403)

    def test_validation_of_weekday_rooms_name_and_time_order(self):
        for extra in [{'weekday':'8'},{'rooms':[]},{'group_name':''},{'end_time':'17:00'},{'end_time':'16:00'},{'start_time':'not-time'},{'group_name':'x'*161}]:
            self.assertFalse(GroupSessionForm(self.session_data(**extra)).is_valid(),extra)
        self.garden.active=False;self.garden.save()
        self.assertFalse(GroupSessionForm(self.session_data(rooms=[self.garden.pk])).is_valid())

    def test_advisory_on_same_weekday_time_and_room_only(self):
        self.assertEqual(len(self.hits(local_datetime(self.day,time(18)),local_datetime(self.day,time(20)))),1)
        self.assertFalse(self.hits(local_datetime(self.day,time(19)),local_datetime(self.day,time(20))))
        self.assertFalse(self.hits(local_datetime(self.day,time(16)),local_datetime(self.day,time(17))))
        self.assertFalse(self.hits(local_datetime(self.day+timedelta(days=1),time(18)),local_datetime(self.day+timedelta(days=1),time(20))))
        self.assertFalse(self.hits(local_datetime(self.day,time(18)),local_datetime(self.day,time(20)),rooms=[self.garden]))

    def test_multi_day_all_day_and_exclusive_midnight(self):
        self.assertTrue(self.hits(local_datetime(self.day-timedelta(days=1),time(23)),local_datetime(self.day+timedelta(days=1),time.min)))
        self.assertFalse(self.hits(local_datetime(self.day-timedelta(days=1),time.min),local_datetime(self.day,time.min)))
        self.assertTrue(self.hits(local_datetime(self.day,time.min),local_datetime(self.day+timedelta(days=1),time.min)))
        self.assertTrue(self.hits(local_datetime(self.day,time(20)),local_datetime(self.day+timedelta(days=8),time.min)))

    def test_weekly_booking_checks_actual_occurrences_and_deduplicates(self):
        self.assertEqual(len(self.hits(local_datetime(self.day,time(18)),local_datetime(self.day+timedelta(days=28),time(20)),recurring=True)),1)
        self.assertFalse(self.hits(local_datetime(self.day+timedelta(days=1),time(18)),local_datetime(self.day+timedelta(days=29),time(20)),recurring=True))

    def test_local_times_survive_summer_time_change(self):
        self.session.weekday=0;self.session.save()
        for day in [date(2027,3,22),date(2027,3,29)]:
            self.assertTrue(self.hits(local_datetime(day,time(18)),local_datetime(day,time(20))))

    def test_rule_reports_each_shared_room_once_and_escapes_group_text(self):
        self.session.rooms.add(self.garden);self.session.group_name='<script>alert(1)</script>';self.session.save()
        rows=self.hits(local_datetime(self.day,time(18)),local_datetime(self.day,time(20)),rooms=[self.room,self.garden])
        self.assertEqual(len(rows),1);self.assertEqual(set(rows[0]['rooms']),{'Raum 1','Garten'})
        self.client.force_login(self.leader)
        response=self.client.post(reverse('rooms:live_conflicts'),self.form_data(start_time='18:00',end_time='20:00'))
        self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>alert(1)</script>')

    def test_advisory_allows_submission_and_approval_without_confirmation(self):
        booking=save_booking(self.leader,self.payload(starts_at=local_datetime(self.day,time(18)),ends_at=local_datetime(self.day,time(20))))
        decide(self.board,booking.pk,'approve',booking.version)
        booking.refresh_from_db();self.assertEqual(booking.status,'approved')
        self.assertEqual(GroupSession.objects.count(),1)

    def test_real_approved_booking_still_requires_confirmation(self):
        first=save_booking(self.leader,self.payload(starts_at=local_datetime(self.day,time(18)),ends_at=local_datetime(self.day,time(20))))
        decide(self.board,first.pk,'approve',first.version)
        other=save_booking(self.other,self.payload(starts_at=first.starts_at,ends_at=first.ends_at))
        with self.assertRaises(ValidationError):decide(self.board,other.pk,'approve',other.version)
        rows=conflicts([self.room.pk],other.starts_at,other.ends_at,other.pk)
        self.assertEqual(len(rows),2)
        decide(self.board,other.pk,'approve',other.version,confirm=True,token=conflict_token(rows))

    def test_details_and_proposed_changes_show_advisory_without_crashing(self):
        row=save_booking(self.leader,self.payload(starts_at=local_datetime(self.day,time(18)),ends_at=local_datetime(self.day,time(20))))
        decide(self.board,row.pk,'approve',row.version);row.refresh_from_db()
        save_booking(self.leader,self.payload(starts_at=row.starts_at,ends_at=local_datetime(self.day,time(21)),version=row.version),row.pk)
        self.client.force_login(self.leader)
        response=self.client.get(reverse('rooms:detail',args=[row.pk]));self.assertContains(response,'Gruppenstunde: Wölflinge Gruppe 2')
        self.assertEqual(self.client.get(reverse('rooms:index')).status_code,200)

    def test_rules_never_appear_in_occupancy_calendar_or_exports(self):
        self.client.force_login(self.board)
        for name,args in [('index',[]),('calendar',[]),('export',['ical']),('export',['excel'])]:
            response=self.client.get(reverse('rooms:'+name,args=args),{'date':str(self.day),'include_past':'on'})
            self.assertEqual(response.status_code,200)
            if name!='export':self.assertNotContains(response,'Wölflinge Gruppe 2')
            elif args==['ical']:self.assertNotIn(b'BEGIN:VEVENT',response.content)
            else:
                import zipfile,io
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    self.assertNotIn('Wölflinge Gruppe 2',''.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xml')))
        RoomSettings.objects.update_or_create(pk=1,defaults={'public_api_enabled':True})
        response=self.client.get(reverse('room_occupancy_api'),{'start':str(self.day),'end':str(self.day+timedelta(days=6))})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('Wölflinge',response.content.decode());self.assertEqual(RoomBooking.objects.count(),0)

    def test_room_used_in_rule_is_archived_instead_of_silently_removing_rule(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('rooms:catalogue'),{'action':'delete','room_id':self.room.pk,'confirm':'yes'})
        self.room.refresh_from_db();self.assertFalse(self.room.active)
        self.assertTrue(self.session.rooms.filter(pk=self.room.pk).exists())

    def test_tabs_and_filter_disclosure_follow_permissions(self):
        self.client.force_login(self.board)
        response=self.client.get(reverse('rooms:group_sessions'))
        self.assertContains(response,'aria-current="page">Gruppenstunden')
        self.client.force_login(self.leader)
        response=self.client.get(reverse('rooms:index'))
        self.assertNotContains(response,'href="'+reverse('rooms:group_sessions')+'"')
        self.assertContains(response,'data-room-filter-details')

    def test_month_calendar_keeps_additional_bookings_accessible(self):
        for i in range(3):save_booking(self.leader,self.payload(purpose='Kalendertermin '+str(i)))
        self.client.force_login(self.board)
        response=self.client.get(reverse('rooms:calendar'),{'date':str(self.day)})
        self.assertContains(response,'+ 2 weitere')
        self.assertContains(response,'Kalendertermin 0 - Externe Testgruppe')
        for i in range(3):self.assertContains(response,'Kalendertermin '+str(i))
        self.assertContains(response,'data-filter-compact')
