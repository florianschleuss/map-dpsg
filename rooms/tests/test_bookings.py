from datetime import datetime,time,timedelta,timezone as utc
from io import BytesIO
from unittest.mock import patch
import zipfile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from django.core.exceptions import ValidationError,PermissionDenied
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from django.utils import timezone
from map.models import LeaderProfile,EmailJob
from rooms.models import Room,RoomBooking,BookingChange,RoomSettings,RoomNotification,RoomEmailTemplate,RoomAudit
from rooms.forms import BookingForm,local_datetime
from rooms.services import save_booking,decide,cancel,withdraw,conflicts,conflict_token
from rooms.notifications import job_current,EVENTS,defaults,validate_template
from rooms.presentation import ical_bytes


@override_settings(PUBLIC_URL='https://dev.example.org',ALLOWED_HOSTS=['testserver'])
class RoomBookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User=get_user_model()
        cls.leader=User.objects.create_user('room-leader','leader@example.org','A-strong-room-pass-123')
        cls.other=User.objects.create_user('room-other','other@example.org','A-strong-room-pass-123')
        cls.board=User.objects.create_user('room-board','board@example.org','A-strong-room-pass-123')
        cls.outsider=User.objects.create_user('room-outsider','outsider@example.org','A-strong-room-pass-123')
        cls.admin=User.objects.create_superuser('room-admin','admin@example.org','A-strong-room-pass-123')
        LeaderProfile.objects.create(user=cls.leader,is_leader=True);LeaderProfile.objects.create(user=cls.other,is_leader=True)
        cls.board.groups.add(Group.objects.get(name='Vorstand'))
        cls.room=Room.objects.get(name='Raum 1');cls.garden=Room.objects.get(name='Garten')
        cls.day=timezone.localdate()+timedelta(days=10)
        RoomSettings.objects.update_or_create(pk=1,defaults={'notification_emails':'board-notices@example.org'})

    def payload(self,**overrides):
        data={'starts_at':local_datetime(self.day,time(9)),'ends_at':local_datetime(self.day,time(17)),
            'all_day':False,'rooms':[self.room],'grouping':'Externe Testgruppe','purpose':'Gruppenabend',
            'contact_person':'Alex Extern','contact':'0123 / extern@example.org'}
        data.update(overrides);return data

    def booking(self,actor=None,**kwargs):return save_booking(actor or self.leader,self.payload(**kwargs))

    def approve(self,booking,**kwargs):return decide(self.board,booking.pk,'approve',booking.version,**kwargs)

    def form_data(self,**overrides):
        data={'start_date':str(self.day),'end_date':str(self.day),'start_time':'09:00','end_time':'17:00','rooms':[self.room.pk],
            'grouping':'Externe Testgruppe','purpose':'Gruppenabend','contact_person':'Alex Extern','contact':'0123 / extern@example.org'}
        data.update(overrides);return data

    def test_six_rooms_and_board_role_are_available(self):
        self.assertEqual(list(Room.objects.values_list('name',flat=True)),['Raum 1','Raum 2','Raum 3','Raum 4','Raum 5','Garten'])
        self.assertTrue(self.board.has_perm('rooms.manage_bookings'));self.assertFalse(self.board.has_perm('map.change_event'))

    def test_new_booking_is_pending_and_external_contact_is_supported(self):
        booking=self.booking(rooms=[self.room,self.garden])
        self.assertEqual(booking.status,'pending');self.assertEqual(booking.rooms.count(),2)
        self.assertEqual(booking.contact,'0123 / extern@example.org');self.assertTrue(RoomAudit.objects.filter(booking=booking).exists())

    def test_every_leader_can_read_all_details_but_not_edit_other_people(self):
        row=self.booking();self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('rooms:detail',args=[row.pk])),'extern@example.org')
        self.assertEqual(self.client.get(reverse('rooms:edit',args=[row.pk])).status_code,403)
        with self.assertRaises(PermissionDenied):save_booking(self.other,self.payload(version=row.version),row.pk)

    def test_outsiders_cannot_read_create_or_export(self):
        row=self.booking();self.client.force_login(self.outsider)
        for url in [reverse('rooms:index'),reverse('rooms:new'),reverse('rooms:detail',args=[row.pk]),reverse('rooms:export',args=['excel']),reverse('rooms:export',args=['ical'])]:
            self.assertEqual(self.client.get(url).status_code,403)
        with self.assertRaises(PermissionDenied):self.booking(self.outsider)

    def test_view_only_grant_does_not_allow_creating(self):
        self.outsider.user_permissions.add(Permission.objects.get(content_type__app_label='rooms',codename='view_roombooking'))
        self.client.force_login(self.outsider);self.assertEqual(self.client.get(reverse('rooms:index')).status_code,200)
        self.assertEqual(self.client.get(reverse('rooms:new')).status_code,403)
        with self.assertRaises(PermissionDenied):self.booking(self.outsider)

    def test_past_times_are_allowed_but_negative_intervals_are_rejected(self):
        form=BookingForm(self.form_data(start_date=str(self.day-timedelta(days=30)),end_date=str(self.day-timedelta(days=30))))
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(BookingForm(self.form_data(end_time='08:00')).is_valid())
        self.booking(starts_at=timezone.now()-timedelta(hours=1))

    def test_all_day_multiday_end_is_exclusive_and_no_time_is_required(self):
        form=BookingForm(self.form_data(all_day='on',end_date=str(self.day+timedelta(days=2)),start_time='',end_time=''))
        self.assertTrue(form.is_valid(),form.errors);row=save_booking(self.leader,form.cleaned_data)
        self.assertEqual(timezone.localtime(row.ends_at).date(),self.day+timedelta(days=3))
        self.assertTrue(row.all_day)

    def test_ambiguous_and_nonexistent_dst_times_are_rejected(self):
        with self.assertRaises(ValidationError):local_datetime(datetime(2027,3,28).date(),time(2,30))
        with self.assertRaises(ValidationError):local_datetime(datetime(2027,10,31).date(),time(2,30))

    def test_overlaps_include_pending_and_approved_and_are_allowed(self):
        first=self.booking();second=self.booking(self.other,purpose='Parallel')
        overlap=conflicts([self.room.pk],second.starts_at,second.ends_at,second.pk)
        self.assertEqual([row['booking'].pk for row in overlap],[first.pk]);self.assertEqual(overlap[0]['status'],'pending')
        self.approve(first);second.refresh_from_db()
        with self.assertRaises(ValidationError):self.approve(second)
        overlap=conflicts([self.room.pk],second.starts_at,second.ends_at,second.pk)
        self.approve(second,confirm=True,token=conflict_token(overlap));second.refresh_from_db();self.assertEqual(second.status,'approved')

    def test_conflict_confirmation_must_match_current_approved_set(self):
        first=self.booking();self.approve(first);second=self.booking()
        stale=conflict_token(conflicts([self.room.pk],second.starts_at,second.ends_at,second.pk))
        third=self.booking();matches=conflicts([self.room.pk],third.starts_at,third.ends_at,third.pk)
        self.approve(third,confirm=True,token=conflict_token(matches))
        with self.assertRaises(ValidationError):self.approve(second,confirm=True,token=stale)

    def test_adjacent_different_rooms_and_inactive_bookings_do_not_conflict(self):
        first=self.booking();first=self.approve(first)
        self.assertEqual(conflicts([self.room.pk],first.ends_at,first.ends_at+timedelta(hours=1)),[])
        self.assertEqual(conflicts([self.garden.pk],first.starts_at,first.ends_at),[])
        cancel(self.leader,first.pk,first.version);self.assertEqual(conflicts([self.room.pk],first.starts_at,first.ends_at),[])

    def test_approved_change_keeps_old_occupancy_until_approval(self):
        row=self.booking();row=self.approve(row);old_start=row.starts_at
        row=save_booking(self.leader,self.payload(version=row.version,starts_at=old_start+timedelta(days=1),ends_at=row.ends_at+timedelta(days=1),rooms=[self.garden]),row.pk)
        row.refresh_from_db();self.assertEqual(row.starts_at,old_start);self.assertEqual(list(row.rooms.all()),[self.room]);self.assertEqual(row.status,'approved')
        change=row.changes.get(status='pending');decide(self.board,row.pk,'approve',row.version,change_id=change.pk)
        row.refresh_from_db();self.assertEqual(row.starts_at,old_start+timedelta(days=1));self.assertEqual(list(row.rooms.all()),[self.garden])

    def test_rejected_change_preserves_approved_original_and_reason(self):
        row=self.approve(self.booking());row=save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        change=row.changes.get(status='pending');decide(self.board,row.pk,'reject',row.version,reason='Raum wird benötigt',change_id=change.pk)
        row.refresh_from_db();change.refresh_from_db();self.assertEqual(row.status,'approved');self.assertEqual(list(row.rooms.all()),[self.room])
        self.assertEqual(change.status,'rejected');self.assertEqual(change.decision_reason,'Raum wird benötigt')
        self.assertTrue(RoomAudit.objects.filter(booking=row,after__decision_reason='Raum wird benötigt').exists())
        message=EmailJob.objects.filter(room_booking=row,subject__startswith='Änderung abgelehnt').first().body
        self.assertIn('Status des Änderungsantrags: Abgelehnt',message)
        self.assertIn('Aktuelle Buchungsfassung:',message)
        self.assertIn('Räume: Raum 1',message)
        self.assertIn('Vorgeschlagene Räume: Garten',message)

    def test_contact_updates_are_immediate_and_not_overwritten_by_pending_change(self):
        row=self.approve(self.booking());row=save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        row=save_booking(self.leader,self.payload(version=row.version,contact_person='Neue Person',contact='Neu'),row.pk)
        self.assertEqual(row.contact,'Neu');self.assertEqual(row.status,'approved');self.assertEqual(row.changes.filter(status='pending').count(),1)
        change=row.changes.get(status='pending');decide(self.board,row.pk,'approve',row.version,change_id=change.pk)
        row.refresh_from_db();self.assertEqual(row.contact_person,'Neue Person')

    def test_pending_proposals_are_included_in_conflicts(self):
        row=self.approve(self.booking());save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        overlap=conflicts([self.garden.pk],row.starts_at,row.ends_at)
        self.assertEqual(len(overlap),1);self.assertTrue(overlap[0]['proposal']);self.assertEqual(overlap[0]['status'],'pending')

    def test_replacing_proposal_preserves_its_history(self):
        row=self.approve(self.booking());row=save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        row=save_booking(self.leader,self.payload(version=row.version,purpose='Anderer Zweck'),row.pk)
        self.assertEqual(row.changes.filter(status='pending').count(),1);self.assertEqual(row.changes.filter(status='cancelled').count(),1)

    def test_cancel_and_withdraw_are_owned_actions_and_board_can_manage_all(self):
        row=self.approve(self.booking());row=save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        with self.assertRaises(PermissionDenied):withdraw(self.other,row.pk,row.version)
        withdraw(self.leader,row.pk,row.version);row.refresh_from_db();self.assertEqual(row.status,'approved')
        cancel(self.board,row.pk,row.version);row.refresh_from_db();self.assertEqual(row.status,'cancelled')

    def test_cancellation_cancels_all_pending_changes(self):
        row=self.approve(self.booking());row=save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        cancel(self.leader,row.pk,row.version);self.assertFalse(row.changes.filter(status='pending').exists())

    def test_leader_cannot_approve_and_stale_forms_cannot_overwrite(self):
        row=self.booking()
        with self.assertRaises(PermissionDenied):decide(self.leader,row.pk,'approve',row.version)
        old=row.version;row=save_booking(self.leader,self.payload(version=old,contact='neu'),row.pk)
        with self.assertRaises(ValidationError):save_booking(self.leader,self.payload(version=old),row.pk)
        with self.assertRaises(ValidationError):cancel(self.leader,row.pk,old)

    def test_csrf_required_for_new_decisions_and_cancellation(self):
        row=self.booking();strict=Client(enforce_csrf_checks=True);strict.force_login(self.board)
        self.assertEqual(strict.post(reverse('rooms:detail',args=[row.pk]),{'action':'approve','version':row.version}).status_code,403)
        self.assertEqual(strict.post(reverse('rooms:new'),self.form_data()).status_code,403)

    def test_new_request_decisions_and_cancel_queue_email_without_internal_notifications(self):
        row=self.booking()
        self.assertTrue(EmailJob.objects.filter(room_booking=row,recipient='board-notices@example.org').exists())
        self.assertFalse(RoomNotification.objects.filter(booking=row).exists())
        self.assertFalse(RoomNotification.objects.filter(booking=row).exists())
        row=self.approve(row);self.assertTrue(EmailJob.objects.filter(room_booking=row,recipient=self.leader.email,subject__contains='genehmigt').exists())
        cancel(self.leader,row.pk,row.version);self.assertTrue(EmailJob.objects.filter(room_booking=row,subject__contains='storniert').exists())

    def test_obsolete_mail_is_not_sent_after_cancellation(self):
        row=self.booking();old_job=EmailJob.objects.filter(room_booking=row).first()
        cancel(self.leader,row.pk,row.version);old_job.refresh_from_db();self.assertFalse(job_current(old_job))
        from django.core.management import call_command
        with patch('map.management.commands.process_queue.send_mail',return_value=1) as sender:
            call_command('process_queue',verbosity=0)
        old_job.refresh_from_db();self.assertEqual(old_job.last_error,'RoomNotificationObsolete');self.assertIsNone(old_job.sent_at)

    def test_internal_notifications_route_removed(self):
        self.client.force_login(self.leader)
        self.assertEqual(self.client.get('/raeume/benachrichtigungen/').status_code,404)

    def test_filters_and_all_table_columns(self):
        self.booking();self.booking(self.other,rooms=[self.garden],grouping='Andere Gruppe')
        self.client.force_login(self.leader);response=self.client.get(reverse('rooms:index'),{'rooms':[self.room.pk],'grouping':'Externe','status':'pending'})
        self.assertContains(response,'Externe Testgruppe');self.assertNotContains(response,'Andere Gruppe')
        for column in ['Zeitraum','Räume','Gruppierung','Veranstaltung','Ansprechperson','Status','Konflikte','Aktionen']:self.assertContains(response,column)

    def test_board_pending_overview_includes_changes_and_is_board_only(self):
        row=self.approve(self.booking());save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        self.client.force_login(self.leader);self.assertEqual(self.client.get(reverse('rooms:pending')).status_code,403)
        self.client.force_login(self.board);self.assertContains(self.client.get(reverse('rooms:pending')),'Änderungsantrag offen')

    def test_month_and_week_calendars_render_multiday_booking_and_proposals(self):
        row=self.approve(self.booking());save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        self.client.force_login(self.leader)
        for mode in ['month','week']:
            response=self.client.get(reverse('rooms:calendar'),{'date':str(self.day),'view':mode})
            self.assertEqual(response.status_code,200);self.assertContains(response,'Änderungsantrag · nicht freigegeben');self.assertContains(response,'Gruppenabend')

    def test_excel_is_valid_and_untrusted_cells_are_never_formulas(self):
        row=self.booking(purpose='=HYPERLINK("bad")');self.client.force_login(self.leader)
        response=self.client.get(reverse('rooms:export',args=['excel']))
        self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            xml=archive.read('xl/worksheets/sheet1.xml').decode();self.assertIn('inlineStr',xml);self.assertNotIn('<f>',xml)
            self.assertIn('Raumbuchungen',archive.read('xl/workbook.xml').decode())

    def test_ical_all_day_and_escape_folding_preserve_valid_structure(self):
        row=self.booking(all_day=True,starts_at=local_datetime(self.day,time.min),ends_at=local_datetime(self.day+timedelta(days=2),time.min),purpose='Ä'*100+'\nEND:VEVENT')
        raw=ical_bytes([row]);self.assertIn(b'DTSTART;VALUE=DATE:',raw);self.assertIn(b'DTEND;VALUE=DATE:',raw)
        self.assertEqual(raw.count(b'\r\nEND:VEVENT\r\n'),1)
        self.assertTrue(all(len(line)<=75 for line in raw.split(b'\r\n')));raw.decode('utf-8')

    def test_xss_is_escaped_in_contact_and_details(self):
        row=self.booking(contact='<script>alert(1)</script>');self.client.force_login(self.other)
        response=self.client.get(reverse('rooms:detail',args=[row.pk]));self.assertNotContains(response,'<script>alert');self.assertContains(response,'&lt;script&gt;')

    def test_room_settings_and_templates_are_separate_and_board_only(self):
        self.client.force_login(self.leader)
        self.assertEqual(self.client.get(reverse('rooms:settings')).status_code,403)
        self.assertEqual(self.client.get(reverse('rooms:templates')).status_code,403)
        self.client.force_login(self.board);self.assertEqual(self.client.get(reverse('rooms:settings')).status_code,200)
        response=self.client.get(reverse('rooms:templates'));self.assertContains(response,'Neuer Änderungsantrag')
        self.assertEqual(self.client.get(reverse('mail_settings')).status_code,403)

    def test_all_room_mail_templates_are_distinct_and_validate_placeholders(self):
        self.assertEqual(len({defaults(key)[1] for key in EVENTS}),len(EVENTS))
        for key in EVENTS:validate_template(*defaults(key))
        for body in ['{booking_url} {creator.__class__}','{booking_url} {contact!r}','Ohne Link']:
            with self.assertRaises(ValueError):validate_template('Betreff',body)

    def test_custom_room_templates_do_not_modify_registration_templates(self):
        self.client.force_login(self.board)
        response=self.client.post(reverse('rooms:template_edit',args=['request']),{'action':'save','subject':'Raum: {purpose}','body':'Eigener Raumtext\n{booking_url}'})
        self.assertEqual(response.status_code,302);row=self.booking();self.assertTrue(EmailJob.objects.filter(room_booking=row,body__startswith='Eigener Raumtext').exists())

    def test_system_theme_assets_and_module_settings_are_available(self):
        self.client.force_login(self.board)
        response=self.client.get(reverse('module_settings'));self.assertContains(response,'Raumbuchung');self.assertContains(response,'map/theme.js');self.assertContains(response,'data-map-theme-toggle')
        response=self.client.get(reverse('rooms:new'));self.assertContains(response,'Alle Räume auswählen');self.assertContains(response,'Ganztägig')
        from map.people import PersonForm
        form=PersonForm(instance=self.leader,actor=self.admin)
        self.assertIn('room_rights',form.fields)
        self.assertTrue(form.fields['room_rights'].queryset.filter(codename='manage_bookings').exists())
        self.assertFalse(form.fields['global_rights'].queryset.filter(content_type__app_label='rooms').exists())

    def test_edit_and_decision_work_through_the_actual_views(self):
        row=self.approve(self.booking());self.client.force_login(self.leader)
        response=self.client.post(reverse('rooms:edit',args=[row.pk]),self.form_data(rooms=[self.garden.pk],version=row.version,action='save'))
        self.assertRedirects(response,reverse('rooms:detail',args=[row.pk]))
        row.refresh_from_db();self.assertEqual(list(row.rooms.all()),[self.room])
        self.client.force_login(self.board)
        response=self.client.post(reverse('rooms:detail',args=[row.pk]),{'action':'approve','version':row.version,'reason':'Passt'})
        self.assertRedirects(response,reverse('rooms:detail',args=[row.pk]));row.refresh_from_db();self.assertEqual(list(row.rooms.all()),[self.garden])

    def test_filter_and_exports_distinguish_proposed_from_current_rooms(self):
        row=self.approve(self.booking());save_booking(self.leader,self.payload(version=row.version,rooms=[self.garden]),row.pk)
        self.client.force_login(self.leader)
        response=self.client.get(reverse('rooms:index'),{'rooms':[self.garden.pk],'status':'pending'})
        self.assertContains(response,'Änderungsantrag offen')
        response=self.client.get(reverse('rooms:calendar'),{'rooms':[self.garden.pk],'date':str(self.day)})
        self.assertContains(response,'Änderungsantrag · nicht freigegeben');self.assertNotContains(response,'Raum 1</span>')
        response=self.client.get(reverse('rooms:export',args=['ical']),{'rooms':[self.garden.pk]})
        self.assertNotIn(b'BEGIN:VEVENT',response.content)

    def test_mail_queue_can_be_filtered_by_module_without_changing_other_jobs(self):
        row=self.booking();EmailJob.objects.create(recipient='system@example.org',subject='Systemauftrag',body='System',next_attempt=timezone.now())
        self.client.force_login(self.admin)
        response=self.client.get(reverse('mail_queue'),{'module':'rooms'})
        self.assertContains(response,'Raumbuchung:');self.assertNotContains(response,'Systemauftrag')
        self.assertContains(self.client.get(reverse('mail_queue'),{'module':'system'}),'Systemauftrag')

    def test_invalid_date_boundaries_show_errors_instead_of_server_error(self):
        self.assertFalse(BookingForm(self.form_data(all_day='on',end_date='9999-12-31')).is_valid())
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(reverse('rooms:index'),{'end':'9999-12-31'}),'außerhalb')

    def test_live_conflicts_are_automatic_advisory_and_do_not_create_records(self):
        row=self.booking(purpose='<script>alert(1)</script>')
        self.client.force_login(self.other)
        before=(RoomBooking.objects.count(),EmailJob.objects.count())
        response=self.client.post(reverse('rooms:live_conflicts'),self.form_data())
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['count'],1)
        self.assertIn('&lt;script&gt;',response.json()['html']);self.assertNotIn('<script>',response.json()['html'])
        self.assertEqual(before,(RoomBooking.objects.count(),EmailJob.objects.count()))
        self.assertEqual(self.client.post(reverse('rooms:live_conflicts'),self.form_data(booking_id=row.pk)).status_code,403)
        self.client.force_login(self.leader)
        self.assertEqual(self.client.post(reverse('rooms:live_conflicts'),self.form_data(booking_id=row.pk)).json()['count'],0)

    def test_live_conflicts_require_access_complete_period_and_csrf(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(reverse('rooms:live_conflicts'),self.form_data()).status_code,403)
        self.client.force_login(self.leader)
        self.assertEqual(self.client.post(reverse('rooms:live_conflicts'),self.form_data(end_time='')).status_code,400)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.leader)
        self.assertEqual(strict.post(reverse('rooms:live_conflicts'),self.form_data()).status_code,403)
