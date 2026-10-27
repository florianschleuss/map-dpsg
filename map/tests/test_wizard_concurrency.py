from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connection,connections,close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone
from map.models import ScoutGroup,Event,FormTemplate
from map.event_wizard import create_event

@skipUnless(connection.vendor=='postgresql','PostgreSQL row locking required')
class WizardConcurrencyTests(TransactionTestCase):
    def test_parallel_final_submission_creates_exactly_one_event(self):
        actor=get_user_model().objects.create_superuser('parallelwizard','admin@example.org','Strong-parallel-pass-592!')
        stage=ScoutGroup.objects.create(name='Parallelstufe')
        now=timezone.now();barrier=Barrier(2)
        cleaned=[{'title':'Paralleler Entwurf','description':'','groups':[stage]},
                 {'starts_at':now+timedelta(days=20),'registration_opens':now,'registration_closes':now+timedelta(days=10)},
                 {'capacity':10,'capacity_mode':'per_group','waitlist_mode':'per_group','show_availability':True,'waitlist_enabled':True,'confirmation_required':True,'confirmation_hours':48},
                 {'form_template':None,'schema_json':[]},{'viewers':[],'editors':[]}]
        def submit(_):
            close_old_connections()
            try:
                user=get_user_model().objects.get(pk=actor.pk)
                barrier.wait(timeout=10)
                return create_event(cleaned,False,'a'*32,user).pk
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(submit,[1,2]))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(Event.objects.count(),1);self.assertEqual(FormTemplate.objects.count(),1)
