from .migration_helpers import migrate_latest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from map.default_roles import sync_default_roles
from map.apps import MapConfig
from django.apps import apps

class StageRoleMigrationTests(TransactionTestCase):
    def test_upgrade_seeds_existing_stages_without_adopting_unrelated_roles(self):
        try:
            executor=MigrationExecutor(connection);executor.migrate([('map','0009_microsoft_oauth')])
            old=executor.loader.project_state([('map','0009_microsoft_oauth')]).apps
            Stage=old.get_model('map','ScoutGroup');User=old.get_model('auth','User');Group=old.get_model('auth','Group');Profile=old.get_model('map','LeaderProfile');Job=old.get_model('map','EmailJob')
            stage=Stage.objects.create(name='Bestehende Stufe');user=User.objects.create(username='bestehende-leitung9')
            profile=Profile.objects.create(user=user,is_leader=True);profile.stages.add(stage)
            unrelated=Group.objects.create(name='Stufe: Bestehende Stufe ['+str(stage.pk)+']');user.groups.add(unrelated)
            job=Job.objects.create(recipient='old@example.org',subject='Bestehender Auftrag',body='Bestehender Text',next_attempt=timezone.now())
            migrate_latest(connection)
            # This is the same receiver invoked after the production migrate command.
            sync_default_roles(apps.get_app_config('map'))
            from map.models import StageRole,LeaderProfile,EmailJob
            from django.contrib.auth.models import Group as CurrentGroup
            binding=StageRole.objects.get(stage_id=stage.pk)
            self.assertNotEqual(binding.group_id,unrelated.pk);self.assertEqual(binding.group.permissions.count(),4)
            self.assertEqual(CurrentGroup.objects.get(pk=unrelated.pk).permissions.count(),0)
            self.assertTrue(LeaderProfile.objects.get(user_id=user.pk).stages.filter(pk=stage.pk).exists())
            self.assertEqual(EmailJob.objects.get(pk=job.pk).body,'Bestehender Text')
        finally:
            migrate_latest(connection)
