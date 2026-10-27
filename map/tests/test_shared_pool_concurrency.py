from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.db import connection,connections
from django.test import TransactionTestCase
from django.utils import timezone
from map.models import ScoutGroup,FormTemplate,Event,EventGroup,Registration
from map.services import register

@skipUnless(connection.vendor=='postgresql','PostgreSQL row locking required')
class SharedPoolConcurrencyTests(TransactionTestCase):
    def test_simultaneous_requests_respect_one_total_pool(self):
        now=timezone.now();a=ScoutGroup.objects.create(name='A');b=ScoutGroup.objects.create(name='B');template=FormTemplate.objects.create(name='Leer')
        event=Event.objects.create(group=a,form_template=template,title='Pool',slug='parallel-pool',published=True,confirmation_required=False,capacity=2,capacity_mode='shared',waitlist_mode='shared',starts_at=now+timedelta(days=3),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=1))
        EventGroup.objects.create(event=event,group=a,capacity=1);EventGroup.objects.create(event=event,group=b,capacity=1);barrier=Barrier(4)
        def submit(index):
            try:
                barrier.wait(timeout=15)
                return register(event.pk,f'Poolkind {index}','eltern@example.org',{},group_id=a.pk if index%2 else b.pk).status
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=4) as pool:statuses=list(pool.map(submit,range(4)))
        self.assertCountEqual(statuses,['confirmed','confirmed','waitlisted','waitlisted'])
        self.assertEqual(Registration.objects.filter(event=event,status='confirmed').count(),2)
