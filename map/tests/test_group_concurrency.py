from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from map.models import ScoutGroup, FormTemplate, Event, EventGroup, Registration
from map.services import register

@skipUnless(connection.vendor=='postgresql','PostgreSQL row locking required')
class GroupConcurrencyTests(TransactionTestCase):
    def test_simultaneous_requests_respect_each_group_limit(self):
        now=timezone.now();a=ScoutGroup.objects.create(name='A');b=ScoutGroup.objects.create(name='B');template=FormTemplate.objects.create(name='Leer')
        event=Event.objects.create(group=a,form_template=template,title='Lager',slug='parallel-gruppen',published=True,confirmation_required=False,capacity=2,starts_at=now+timedelta(days=3),registration_opens=now-timedelta(days=1),registration_closes=now+timedelta(days=1))
        sa=EventGroup.objects.create(event=event,group=a,capacity=1);sb=EventGroup.objects.create(event=event,group=b,capacity=1);barrier=Barrier(4)
        def submit(value):
            index,group=value
            try:
                barrier.wait(timeout=15)
                return group,register(event.pk,f'Kind {index}','eltern@example.org',{},group_id=group).status
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(submit,[(1,a.pk),(2,a.pk),(3,b.pk),(4,b.pk)]))
        for group in [a,b]:self.assertCountEqual([status for key,status in results if key==group.pk],['confirmed','waitlisted'])
        for slot in [sa,sb]:self.assertEqual(Registration.objects.filter(event_group=slot,status='confirmed').count(),1)
