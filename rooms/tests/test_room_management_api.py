from datetime import datetime,time,timedelta
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from map.models import LeaderProfile,EmailJob
from rooms.models import Room,RoomBooking,BookingChange,RoomSettings
from rooms.forms import BookingForm,local_datetime
from rooms.services import save_booking

@override_settings(ALLOWED_HOSTS=['testserver'])
class RoomManagementAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=get_user_model().objects.create_superuser('catalogue-admin','admin@example.invalid','test-admin-pass-123')
        cls.leader=get_user_model().objects.create_user('catalogue-leader','leader@example.invalid')
        LeaderProfile.objects.create(user=cls.leader,is_leader=True)
        cls.board=get_user_model().objects.create_user('catalogue-board');cls.board.groups.add(Group.objects.get(name='Vorstand'))
        cls.day=timezone.localdate()+timedelta(days=10)

    def booking(self,rooms,status='approved',start=None,end=None):
        row=RoomBooking.objects.create(creator=self.leader,starts_at=start or local_datetime(self.day,time(9)),ends_at=end or local_datetime(self.day,time(17)),
            grouping='PRIVATE GROUP',purpose='PRIVATE PURPOSE',contact_person='PRIVATE PERSON',contact='private-contact@example.invalid',status=status)
        row.rooms.set(rooms);return row

    def enable(self):RoomSettings.objects.filter(pk=1).update(public_api_enabled=True)
    def api(self,**params):return self.client.get(reverse('room_occupancy_api'),{'start':str(self.day),'end':str(self.day),**params})

    def test_only_admin_can_create_rename_archive_and_delete_rooms(self):
        for user in [self.leader,self.board]:
            self.client.force_login(user);self.assertEqual(self.client.post(reverse('rooms:catalogue'),{'action':'save','name':'Neu','position':7}).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('rooms:catalogue'),{'action':'save','name':'Neu','position':7}).status_code,302)
        room=Room.objects.get(name='Neu')
        self.client.post(reverse('rooms:catalogue')+'?edit='+str(room.pk),{'action':'save','name':'Umbenannt','position':8})
        room.refresh_from_db();self.assertEqual(room.name,'Umbenannt')
        self.client.post(reverse('rooms:catalogue'),{'action':'delete','room_id':room.pk})
        self.assertTrue(Room.objects.filter(pk=room.pk).exists())
        self.client.post(reverse('rooms:catalogue'),{'action':'delete','room_id':room.pk,'confirm':'yes'})
        self.assertFalse(Room.objects.filter(pk=room.pk).exists())

    def test_deleting_referenced_room_archives_without_changing_history(self):
        room=Room.objects.first();row=self.booking([room]);self.client.force_login(self.admin)
        self.client.post(reverse('rooms:catalogue'),{'action':'delete','room_id':room.pk,'confirm':'yes'})
        room.refresh_from_db();self.assertFalse(room.active);self.assertTrue(row.rooms.filter(pk=room.pk).exists())
        self.assertNotIn(room,BookingForm().fields['rooms'].queryset)
        self.assertIn(room,BookingForm(booking=row).fields['rooms'].queryset)
        data={'starts_at':local_datetime(self.day,time(9)),'ends_at':local_datetime(self.day,time(17)),'all_day':False,'rooms':[room],'grouping':'Test','purpose':'Test','contact_person':'Test','contact':'Test'}
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):save_booking(self.leader,data)
        self.client.post(reverse('rooms:catalogue'),{'action':'restore','room_id':room.pk})
        room.refresh_from_db();self.assertFalse(room.active)

    def test_deleted_default_room_is_not_recreated_on_next_migration_signal(self):
        room=Room.objects.get(name='Raum 1');room.delete()
        from rooms.apps import seed
        from django.apps import apps
        seed(apps.get_app_config('rooms'))
        self.assertFalse(Room.objects.filter(name='Raum 1').exists())

    def test_catalogue_requires_csrf_and_escapes_room_name(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.admin)
        self.assertEqual(strict.post(reverse('rooms:catalogue'),{'action':'save','name':'X','position':1}).status_code,403)
        Room.objects.create(name='<script>ROOM</script>')
        self.client.force_login(self.admin);response=self.client.get(reverse('rooms:catalogue'))
        self.assertContains(response,'&lt;script&gt;ROOM&lt;/script&gt;');self.assertNotContains(response,'<script>ROOM</script>')

    def test_api_is_opt_in_get_only_and_no_details_are_exposed(self):
        self.assertEqual(self.api().status_code,404);self.enable();self.booking([Room.objects.first()])
        response=self.api();self.assertEqual(response.status_code,200)
        self.assertEqual(response['Access-Control-Allow-Origin'],'*')
        payload=response.json();self.assertEqual(payload['days'][0]['occupancy'],'partial')
        for value in ['PRIVATE','private-contact','09:00','17:00','purpose','contact_person','booking_id']:
            self.assertNotIn(value,response.content.decode())
        self.assertEqual(self.client.post(reverse('room_occupancy_api')).status_code,405)

    def test_api_full_partial_status_union_and_archived_rooms(self):
        self.enable();rooms=list(Room.objects.all());self.booking(rooms[:3]);self.booking(rooms[3:],'pending')
        day=self.api().json()['days'][0]
        self.assertEqual(day,{'date':str(self.day),'occupancy':'partial','statuses':['approved','pending'],'approved':'partial','pending':'partial','rooms':[r.name for r in rooms],'approved_rooms':[r.name for r in rooms[:3]],'pending_rooms':[r.name for r in rooms[3:]]})
        self.booking(rooms,'cancelled');self.booking(rooms,'rejected')
        self.assertEqual(self.api().json()['days'][0],day)
        Room.objects.filter(pk__in=[r.pk for r in rooms[3:]]).update(active=False)
        day=self.api().json()['days'][0];self.assertEqual(day['approved'],'partial');self.assertEqual(day['pending'],'none')

    def test_midnight_end_is_exclusive_and_multiday_is_expanded(self):
        self.enable();self.booking([Room.objects.first()],start=local_datetime(self.day,time.min),end=local_datetime(self.day+timedelta(days=2),time.min))
        days=self.api(end=str(self.day+timedelta(days=3))).json()['days']
        self.assertEqual([d['date'] for d in days],[str(self.day),str(self.day+timedelta(days=1))])

    def test_pending_change_is_aggregated_separately_from_valid_booking(self):
        self.enable();rooms=list(Room.objects.all());row=self.booking([rooms[0]])
        change=BookingChange.objects.create(booking=row,requested_by=self.leader,status='pending',starts_at=row.starts_at,ends_at=row.ends_at,grouping='SECRET',purpose='SECRET')
        change.rooms.set(rooms[1:]);self.assertEqual(self.api().json()['days'][0]['occupancy'],'partial')
        self.assertNotIn('SECRET',self.api().content.decode())

    def test_invalid_and_unbounded_ranges_are_client_errors(self):
        self.enable()
        for params in [{'start':'9999-12-31'},{'start':'bad'},{'end':str(self.day-timedelta(days=1))},{'end':str(self.day+timedelta(days=366))}]:
            self.assertEqual(self.api(**params).status_code,400)
        self.assertEqual(self.api().json()['days'],[])

    def test_room_settings_have_no_booking_tabs_and_profile_has_only_two_modules(self):
        self.client.force_login(self.admin)
        response=self.client.get(reverse('rooms:settings'))
        self.assertNotContains(response,'aria-label="Raumbuchung"')
        self.assertNotContains(response,'Offene Raumanfragen')
        self.assertNotContains(response,'Alle Einstellungen')
        self.assertContains(response,'Raumeinstellungen');self.assertContains(response,'Veranstaltungseinstellungen')

    def test_api_handles_dst_calendar_days_and_does_not_count_next_midnight(self):
        from datetime import date
        self.enable();first=date(2027,3,27);last=date(2027,3,29)
        self.booking([Room.objects.first()],start=local_datetime(first,time.min),end=local_datetime(last,time.min))
        payload=self.api(start=str(first),end=str(last)).json()
        self.assertEqual([day['date'] for day in payload['days']],['2027-03-27','2027-03-28'])

    def test_room_referenced_only_by_a_proposed_change_is_retained(self):
        rooms=list(Room.objects.all());row=self.booking([rooms[0]])
        change=BookingChange.objects.create(booking=row,requested_by=self.leader,starts_at=row.starts_at,ends_at=row.ends_at,grouping='Test',purpose='Test')
        change.rooms.add(rooms[1]);self.client.force_login(self.admin)
        self.client.post(reverse('rooms:catalogue'),{'action':'delete','room_id':rooms[1].pk,'confirm':'yes'})
        rooms[1].refresh_from_db();self.assertFalse(rooms[1].active)
        self.assertTrue(change.rooms.filter(pk=rooms[1].pk).exists())

    def test_full_requires_continuous_full_day_and_combines_adjacent_bookings(self):
        self.enable();rooms=list(Room.objects.all());low=local_datetime(self.day,time.min);high=local_datetime(self.day+timedelta(days=1),time.min)
        self.booking(rooms,start=low,end=local_datetime(self.day,time(12)))
        self.booking(rooms,start=local_datetime(self.day,time(12)),end=high,status='pending')
        day=self.api().json()['days'][0]
        self.assertEqual(day['occupancy'],'full');self.assertEqual(day['approved'],'partial');self.assertEqual(day['pending'],'partial')
        self.assertEqual(day['rooms'],[r.name for r in rooms])

    def test_until_18_and_even_a_small_gap_remain_partial(self):
        self.enable();rooms=list(Room.objects.all());low=local_datetime(self.day,time.min);high=local_datetime(self.day+timedelta(days=1),time.min)
        self.booking(rooms,start=low,end=local_datetime(self.day,time(18)))
        self.assertEqual(self.api().json()['days'][0]['occupancy'],'partial')
        self.booking(rooms,start=local_datetime(self.day,time(18,1)),end=high)
        self.assertEqual(self.api().json()['days'][0]['occupancy'],'partial')

    def test_room_names_are_unioned_once_across_bookings_and_statuses(self):
        self.enable();rooms=list(Room.objects.all());self.booking(rooms[:2]);self.booking(rooms[1:3],status='pending')
        day=self.api().json()['days'][0]
        self.assertEqual(day['rooms'],[r.name for r in rooms[:3]])
        self.assertEqual(day['approved_rooms'],[r.name for r in rooms[:2]])
        self.assertEqual(day['pending_rooms'],[r.name for r in rooms[1:3]])

    def test_middle_days_can_be_full_while_boundary_days_are_partial(self):
        self.enable();rooms=list(Room.objects.all())
        self.booking(rooms,start=local_datetime(self.day,time(12)),end=local_datetime(self.day+timedelta(days=2),time(18)))
        days=self.api(end=str(self.day+timedelta(days=2))).json()['days']
        self.assertEqual([day['occupancy'] for day in days],['partial','full','partial'])

    def test_full_day_uses_actual_dst_day_duration(self):
        from datetime import date
        self.enable();rooms=list(Room.objects.all())
        for day in [date(2027,3,28),date(2027,10,31)]:
            self.booking(rooms,start=local_datetime(day,time.min),end=local_datetime(day+timedelta(days=1),time.min))
            self.assertEqual(self.api(start=str(day),end=str(day)).json()['days'][0]['occupancy'],'full')
