from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.db import connection, connections, close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone
from map.models import ScoutGroup, FormTemplate, Event, Registration
from map.services import register

@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row locking required')
class CapacityConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_requests_do_not_overbook(self):
        now=timezone.now()
        group=ScoutGroup.objects.create(name='Test')
        template=FormTemplate.objects.create(name='Empty')
        event=Event.objects.create(group=group,form_template=template,title='Test',slug='test',published=True,capacity=1,confirmation_required=False,starts_at=now+timedelta(days=3),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=1))
        barrier=Barrier(2)
        def submit(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return register(event.pk,f'Child {index}','parent@example.org',{}).status
            finally:
                # Persistent connections are thread-local. Always close them before this worker exits.
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(submit,[1,2]))
        self.assertCountEqual(results,['confirmed','waitlisted'])
        self.assertEqual(Registration.objects.filter(event=event,status='confirmed').count(),1)
