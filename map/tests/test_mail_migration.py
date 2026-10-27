from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from map.models import ScoutGroup,FormTemplate,Event,Registration,EmailJob
from map.services import register

class LegacyEmailMigrationTests(TransactionTestCase):
    def test_old_signed_email_links_attach_jobs_to_their_event(self):
        now=timezone.now();group=ScoutGroup.objects.create(name='Stufe');template=FormTemplate.objects.create(name='Leer')
        event=Event.objects.create(group=group,form_template=template,title='Altes Lager',slug='altes-lager-mail',published=True,confirmation_required=False,starts_at=now+timedelta(days=3),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=1))
        row=register(event.pk,'Kind','eltern@example.org',{})
        job_id=EmailJob.objects.get(event=event).pk
        try:
            MigrationExecutor(connection).migrate([('map','0005_role_permissions')])
            MigrationExecutor(connection).migrate([('map','0011_costs_reset')])
            self.assertEqual(EmailJob.objects.get(pk=job_id).event_id,event.pk)
        finally:
            MigrationExecutor(connection).migrate([('map','0011_costs_reset')])
