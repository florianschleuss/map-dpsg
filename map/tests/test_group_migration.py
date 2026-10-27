from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

class ExistingDataMigrationTests(TransactionTestCase):
    def test_existing_registrations_keep_group_capacity_and_private_links(self):
        executor=MigrationExecutor(connection)
        executor.migrate([('map','0001_initial')])
        old=executor.loader.project_state([('map','0001_initial')]).apps
        Group=old.get_model('map','ScoutGroup');Template=old.get_model('map','FormTemplate');Event=old.get_model('map','Event');Registration=old.get_model('map','Registration')
        now=timezone.now();group=Group.objects.create(name='Bisheriger Stamm');template=Template.objects.create(name='Vorlage')
        event=Event.objects.create(group=group,form_template=template,title='Bestehende Veranstaltung',slug='alt',capacity=17,starts_at=now+timedelta(days=30),registration_opens=now,registration_closes=now+timedelta(days=20))
        row=Registration.objects.create(event=event,child_name='Anna',email='eltern@example.org',identity='existing',status='confirmed',answers={'phone':'01234'},schema_snapshot=[],token_nonce='preserve-this-private-nonce',email_verified=True)
        row_id,event_id,group_id=row.pk,event.pk,group.pk
        try:
            executor=MigrationExecutor(connection);executor.migrate([('map','0002_event_groups')])
            new=executor.loader.project_state([('map','0002_event_groups')]).apps
            slot=new.get_model('map','EventGroup').objects.get(event_id=event_id)
            migrated=new.get_model('map','Registration').objects.get(pk=row_id)
            self.assertEqual(slot.group_id,group_id);self.assertEqual(slot.capacity,17);self.assertTrue(slot.enabled)
            self.assertEqual(migrated.event_group_id,slot.pk);self.assertEqual(migrated.token_nonce,'preserve-this-private-nonce');self.assertEqual(migrated.answers,{'phone':'01234'});self.assertEqual(migrated.status,'confirmed')
        finally:
            MigrationExecutor(connection).migrate([('map','0011_costs_reset')])
