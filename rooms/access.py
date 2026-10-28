from django.core.exceptions import PermissionDenied
from map.roles import is_admin


def board(user):
    if not user.is_authenticated or not user.is_active:return False
    from map.access import codes_for
    return is_admin(user) or user.groups.filter(name='Vorstand').exists() or ('rooms','manage_bookings') in codes_for(user)


def can_use(user):
    if not user.is_authenticated or not user.is_active:return False
    if board(user):return True
    from map.models import LeaderProfile
    from map.sso import automatic_stage_ids
    from map.access import codes_for
    return LeaderProfile.objects.filter(user=user,is_leader=True).exists() or bool(automatic_stage_ids(user)) or bool(codes_for(user)&{('rooms','view_roombooking'),('rooms','add_roombooking')})


def can_request(user):
    if not can_use(user):return False
    if board(user):return True
    from map.models import LeaderProfile
    from map.sso import automatic_stage_ids
    from map.access import codes_for
    return LeaderProfile.objects.filter(user=user,is_leader=True).exists() or bool(automatic_stage_ids(user)) or ('rooms','add_roombooking') in codes_for(user)


def can_configure(user):
    from map.access import codes_for
    return board(user) or (can_use(user) and ('rooms','configure_rooms') in codes_for(user))


def require_user(user):
    if not can_use(user):raise PermissionDenied


def can_edit(user,booking):return can_request(user) and (board(user) or booking.creator_id==user.pk)
