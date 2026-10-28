from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase,skipUnlessDBFeature
from django.utils import timezone
from map.models import LeaderProfile
from rooms.models import Room,RoomBooking
from rooms.services import save_booking,decide


class ApprovalConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_overlapping_approvals_require_second_confirmation(self):
        User=get_user_model();board=User.objects.create_user('board-concurrent');board.groups.add(Group.objects.get(name='Vorstand'))
        leader=User.objects.create_user('leader-concurrent');LeaderProfile.objects.create(user=leader,is_leader=True)
        room=Room.objects.get(name='Raum 1');start=timezone.now()+timedelta(days=1)
        data={'starts_at':start,'ends_at':start+timedelta(hours=2),'all_day':False,'rooms':[room],'grouping':'Test',
            'purpose':'Gleichzeitig','contact_person':'Test','contact':'Test'}
        first=save_booking(leader,data);second=save_booking(leader,data);barrier=Barrier(2)
        def approve(pk):
            try:
                actor=User.objects.get(pk=board.pk);barrier.wait(timeout=10)
                try:decide(actor,pk,'approve',1);return 'approved'
                except ValidationError:return 'confirmation-required'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(approve,[first.pk,second.pk]))
        self.assertCountEqual(results,['approved','confirmation-required'])
        self.assertEqual(RoomBooking.objects.filter(status='approved').count(),1)
