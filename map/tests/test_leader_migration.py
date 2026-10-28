from .migration_helpers import migrate_latest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

class LeaderMigrationTests(TransactionTestCase):
    def test_existing_staff_and_mail_settings_are_preserved_without_stage_grants(self):
        try:
            executor=MigrationExecutor(connection);executor.migrate([('map','0007_mail_configuration')])
            old=executor.loader.project_state([('map','0007_mail_configuration')]).apps
            User=old.get_model('auth','User');Mail=old.get_model('map','MailConfiguration')
            staff=User.objects.create(username='existing-staff8',is_staff=True)
            regular=User.objects.create(username='existing-regular8',is_staff=False)
            Mail.objects.update_or_create(pk=1,defaults={'enabled':True,'host':'smtp.old.example.org','username':'old-user','password_encrypted':'preserve-encrypted-value','from_email':'old@example.org'})
            executor=MigrationExecutor(connection);executor.migrate([('map','0009_microsoft_oauth')])
            new=executor.loader.project_state([('map','0009_microsoft_oauth')]).apps
            Profile=new.get_model('map','LeaderProfile');NewUser=new.get_model('auth','User');NewMail=new.get_model('map','MailConfiguration')
            profile=Profile.objects.get(user_id=staff.pk)
            self.assertTrue(profile.is_leader);self.assertEqual(profile.stages.count(),0)
            self.assertFalse(Profile.objects.filter(user_id=regular.pk).exists());self.assertTrue(NewUser.objects.get(pk=staff.pk).is_staff)
            config=NewMail.objects.get(pk=1)
            self.assertEqual(config.provider,'smtp');self.assertEqual(config.host,'smtp.old.example.org');self.assertEqual(config.password_encrypted,'preserve-encrypted-value');self.assertEqual(config.client_secret_encrypted,'')
        finally:
            migrate_latest(connection)
