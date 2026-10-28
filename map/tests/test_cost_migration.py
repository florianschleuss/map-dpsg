from .migration_helpers import migrate_latest
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

class CostMigrationTests(TransactionTestCase):
    def test_existing_events_registrations_and_jobs_are_preserved_with_free_defaults(self):
        try:
            executor=MigrationExecutor(connection);executor.migrate([('map','0010_permissions_mail_templates')])
            old=executor.loader.project_state([('map','0010_permissions_mail_templates')]).apps
            Stage=old.get_model('map','ScoutGroup');Template=old.get_model('map','FormTemplate');Event=old.get_model('map','Event');Registration=old.get_model('map','Registration');Job=old.get_model('map','EmailJob')
            stage=Stage.objects.create(name='Alte Kostenstufe');template=Template.objects.create(name='AltKosten');now=timezone.now()
            event=Event.objects.create(group=stage,form_template=template,title='Altes Lager',slug='alt-kosten10',starts_at=now+timedelta(days=10),registration_opens=now,registration_closes=now+timedelta(days=9))
            row=Registration.objects.create(event=event,child_name='Bestand',email='old@example.org',identity='old-id',status='confirmed',token_nonce='keep-nonce',answers={'note':'behalten'})
            job=Job.objects.create(event=event,recipient='old@example.org',subject='Alte Mail',body='Alter Inhalt',next_attempt=now)
            migrate_latest(connection)
            from map.models import Event as CurrentEvent,Registration as CurrentRegistration,EmailJob
            current=CurrentEvent.objects.get(pk=event.pk);self.assertEqual(current.cost_mode,'free');self.assertEqual(current.payment_method,'none');self.assertFalse(current.costs_configured)
            current_row=CurrentRegistration.objects.get(pk=row.pk);self.assertIsNone(current_row.payment_received_at);self.assertEqual(current_row.token_nonce,'keep-nonce');self.assertEqual(current_row.answers,{'note':'behalten'})
            current_job=EmailJob.objects.get(pk=job.pk);self.assertEqual(current_job.body,'Alter Inhalt');self.assertEqual(current_job.body_encrypted,'');self.assertIsNone(current_job.reset_user_id)
        finally:migrate_latest(connection)
