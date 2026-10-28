def is_admin(user):
    return bool(user.is_authenticated and user.is_active and (user.is_superuser or user.groups.filter(name='Admin').exists()))

def can_manage(user):
    return is_admin(user) or bool(user.is_authenticated and user.is_active and user.groups.filter(name='Manager').exists())

def can_read_all(user):
    from .access import granted
    return can_manage(user) or bool(user.is_authenticated and user.is_active and user.groups.filter(name='Read-Only').exists()) or any(granted(user,'map.'+action+'_event') for action in ['view','change','delete'])

def portal_context(request):
    from .navigation import breadcrumbs
    from .access import can_users,can_roles,can_stages,can_queue,can_mail_settings,can_mail_templates
    user=request.user
    from rooms.access import can_use,can_request,board,can_configure
    room_access=can_use(user)
    pending=getattr(request,'sso_waiting',False)
    from .demo_events import can_create_dummy
    import secrets
    dummy=can_create_dummy(user) and not pending
    if dummy and not request.session.get('dummy_event_nonce'):request.session['dummy_event_nonce']=secrets.token_hex(16)
    room_context={'room_can_use':room_access and not pending,'room_can_request':can_request(user),'room_is_board':board(user),'room_can_configure':can_configure(user),
                  'map_pending_access':pending,'map_can_dummy':dummy,'map_dummy_nonce':request.session.get('dummy_event_nonce',''),
                  'map_can_settings':not pending and any([is_admin(user),can_configure(user),can_users(user),can_roles(user),can_stages(user),can_mail_settings(user),can_mail_templates(user),can_queue(user)])}
    return {**room_context,'map_is_admin':is_admin(user),'map_can_manage':can_create_events(user),'map_breadcrumbs':breadcrumbs(request),
            'map_can_users':can_users(user),'map_can_roles':can_roles(user),'map_can_stages':can_stages(user),
            'map_can_system_settings':not pending and any([is_admin(user),can_users(user),can_roles(user),can_stages(user),can_queue(user),can_mail_settings(user),can_mail_templates(user)]),'map_can_queue':can_queue(user),'map_can_mail_settings':can_mail_settings(user),'map_can_mail_templates':can_mail_templates(user)}

def is_read_only(user):
    return bool(user.is_authenticated and user.is_active and user.groups.filter(name='Read-Only').exists() and not can_manage(user))

def leader_stage_ids(user):
    # Compatibility name: creation rights can also come from explicit stage grants.
    from .access import stage_ids
    return stage_ids(user,'add')

def can_create_any(user):
    from .access import granted
    return can_manage(user) or (not is_read_only(user) and granted(user,'map.add_event'))

def can_create_events(user):
    return can_create_any(user) or bool(leader_stage_ids(user))

def event_stage_ids(event):
    stages=set(event.group_slots.filter(enabled=True).values_list('group_id',flat=True))
    return stages or {event.group_id}

def require_creation_stages(user,stages):
    from django.core.exceptions import ValidationError
    ids={stage.pk for stage in stages}
    if not ids: raise ValidationError('Bitte mindestens eine Stufe auswählen.')
    if not can_create_any(user) and not ids.issubset(leader_stage_ids(user)):
        raise ValidationError('Du darfst Veranstaltungen nur für deine aktuell zugeordneten oder zusätzlich freigegebenen Stufen anlegen.')

def visible_events(user):
    from django.db.models import Q
    from .models import Event
    if not user.is_authenticated or not user.is_active: return Event.objects.none()
    if can_read_all(user): return Event.objects.all()
    from .access import stage_ids
    stages=stage_ids(user,'view')
    return Event.objects.filter(Q(eventpermission__user=user)|Q(group_slots__enabled=True,group_slots__group_id__in=stages)|Q(group_slots__isnull=True,group_id__in=stages)).distinct()

def can_delete_event(user,event):
    from .access import granted,stage_ids
    if not user.is_authenticated or not user.is_active or is_read_only(user):return False
    if can_manage(user) or granted(user,'map.delete_event'):return True
    if event.eventpermission_set.filter(user=user,role='editor').exists():return True
    stages=event_stage_ids(event)
    return bool(stages and stages.issubset(stage_ids(user,'delete')))
