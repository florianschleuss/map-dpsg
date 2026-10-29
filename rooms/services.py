"""Permission checks and serialized room scheduling transitions."""
import hashlib,json
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from .models import Room,RoomBooking,BookingChange,RoomAudit
from .access import require_user,can_edit,board,can_request

FIELDS=['starts_at','ends_at','all_day','grouping','purpose','recurring']


def lock_schedule():
    # All mutation paths take these locks in one stable order. Overlaps remain allowed.
    list(Room.objects.select_for_update().order_by('pk').values_list('pk',flat=True))


def snapshot(item):
    result={name:getattr(item,name).isoformat() if hasattr(getattr(item,name),'isoformat') else getattr(item,name) for name in FIELDS}
    result.update(rooms=list(item.rooms.values_list('name',flat=True)),status=item.status,decision_reason=item.decision_reason)
    if isinstance(item,RoomBooking):result.update(contact_person=item.contact_person,contact=item.contact,version=item.version)
    else:result.update(contact_person=item.booking.contact_person,contact=item.booking.contact,version=item.booking.version)
    return result


def audit(booking,actor,action,before=None,after=None):
    RoomAudit.objects.create(booking=booking,actor=actor,action=action,before=before or {},after=after or snapshot(booking))


def conflicts(room_ids,start,end,exclude=None,recurring=False):
    from types import SimpleNamespace
    from .recurrence import overlaps
    target=SimpleNamespace(starts_at=start,ends_at=end,all_day=False,recurring=recurring)
    ids=list(room_ids);result=[]
    if not ids:return result
    rows=RoomBooking.objects.filter(status__in=['pending','approved'],starts_at__lt=end,ends_at__gt=start,rooms__pk__in=ids).exclude(pk=exclude).distinct().prefetch_related('rooms')
    for row in rows:
        if not overlaps(target,row):continue
        result.append({'booking':row,'entry':row,'proposal':False,'status':row.status,'rooms':[r.name for r in row.rooms.all() if r.pk in ids]})
    changes=BookingChange.objects.filter(status='pending',booking__status='approved',starts_at__lt=end,ends_at__gt=start,rooms__pk__in=ids).exclude(booking_id=exclude).distinct().select_related('booking').prefetch_related('rooms')
    for change in changes:
        if not overlaps(target,change):continue
        result.append({'booking':change.booking,'entry':change,'proposal':True,'status':'pending','rooms':[r.name for r in change.rooms.all() if r.pk in ids]})
    from .presentation import period
    for item in result:item['period']=period(item['entry'])
    return sorted(result,key=lambda c:(c['entry'].starts_at,c['booking'].pk,c['proposal']))


def conflict_token(rows):
    items=sorted((row['booking'].pk,row['booking'].version) for row in rows if row['status']=='approved')
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()


def future(item):
    past=timezone.localtime(item.starts_at).date()<timezone.localdate() if item.all_day else item.starts_at<timezone.now()
    if past:raise ValidationError('Dieser Zeitraum liegt inzwischen in der Vergangenheit. Bitte die Anfrage bearbeiten oder ablehnen.')
    if item.ends_at<=item.starts_at:raise ValidationError('Das Ende muss nach dem Beginn liegen.')
    from .recurrence import intervals
    list(intervals(item))


def version_check(booking,version):
    if booking.version!=version:raise ValidationError('Die Buchung wurde zwischenzeitlich geändert. Bitte neu laden und erneut prüfen.')


@transaction.atomic
def save_booking(actor,data,booking_id=None):
    data=dict(data);data.setdefault('recurring',False)
    require_user(actor);lock_schedule()
    if not can_request(actor):raise PermissionDenied
    booking=RoomBooking.objects.select_for_update().get(pk=booking_id) if booking_id else None
    if booking and not can_edit(actor,booking):raise PermissionDenied
    if booking and booking.status=='cancelled':raise ValidationError('Stornierte Buchungen können nicht bearbeitet werden. Bitte eine neue Anfrage anlegen.')
    room_ids={room.pk for room in data['rooms']}
    if not room_ids or Room.objects.filter(pk__in=room_ids).count()!=len(room_ids):raise ValidationError('Bitte gültige Räume auswählen.')
    retained=set(booking.rooms.values_list('pk',flat=True)) if booking else set()
    if Room.objects.filter(pk__in=room_ids-retained,active=False).exists():raise ValidationError('Archivierte Räume können nicht neu ausgewählt werden.')
    candidate=RoomBooking(**{name:data[name] for name in FIELDS})
    if booking:
        version_check(booking,data.get('version'));before=snapshot(booking)
        changed=any(getattr(booking,name)!=data[name] for name in FIELDS) or room_ids!=set(booking.rooms.values_list('pk',flat=True))
        if changed:future(candidate)
        contacts_changed=booking.contact_person!=data['contact_person'] or booking.contact!=data['contact']
        booking.contact_person=data['contact_person'];booking.contact=data['contact']
        if booking.status=='approved' and changed:
            for old in booking.changes.filter(status='pending'):
                old_snapshot=snapshot(old)
                old.status='cancelled';old.decision_reason='Durch neuen Änderungsantrag ersetzt.';old.decided_by=actor;old.decided_at=timezone.now();old.save()
                audit(booking,actor,'Änderungsantrag ersetzt',old_snapshot,snapshot(old))
            change=BookingChange.objects.create(booking=booking,requested_by=actor,**{name:data[name] for name in FIELDS})
            change.rooms.set(room_ids);booking.version+=1;booking.save()
            audit(booking,actor,'Änderungsantrag eingereicht',before,snapshot(change))
            from .notifications import notify
            notify(booking,'change_request',change)
            return booking
        if not changed and not contacts_changed:return booking
        if changed:
            for name in FIELDS:setattr(booking,name,data[name])
            if booking.status=='rejected':booking.status='pending';booking.decision_reason='';booking.decided_at=None;booking.decided_by=None
        booking.version+=1;booking.save();booking.rooms.set(room_ids)
        audit(booking,actor,'Buchung bearbeitet' if changed else 'Ansprechperson / Kontakt aktualisiert',before)
        from .notifications import notify
        notify(booking,'request' if booking.status=='pending' else 'contact_updated')
        return booking
    future(candidate)
    booking=RoomBooking.objects.create(creator=actor,contact_person=data['contact_person'],contact=data['contact'],**{name:data[name] for name in FIELDS})
    booking.rooms.set(room_ids);audit(booking,actor,'Buchungsanfrage eingereicht')
    from .notifications import notify
    notify(booking,'request')
    return booking


@transaction.atomic
def decide(actor,booking_id,action,version,reason='',confirm=False,token='',change_id=None):
    if not board(actor):raise PermissionDenied
    if action not in ['approve','reject']:raise ValidationError('Unbekannte Entscheidung.')
    lock_schedule();booking=RoomBooking.objects.select_for_update().get(pk=booking_id);version_check(booking,version)
    target=BookingChange.objects.select_for_update().get(pk=change_id,booking=booking) if change_id else booking
    if target.status!='pending' or (change_id and booking.status!='approved'):raise ValidationError('Diese Anfrage ist nicht mehr offen. Bitte neu laden.')
    before=snapshot(target)
    if action=='approve':
        future(target)
        overlaps=conflicts(target.rooms.values_list('pk',flat=True),target.starts_at,target.ends_at,exclude=booking.pk,recurring=target.recurring)
        if any(c['status']=='approved' for c in overlaps) and (not confirm or token!=conflict_token(overlaps)):
            raise ValidationError('Es gibt genehmigte Überschneidungen. Bitte die aktuelle Konfliktliste prüfen und die zusätzliche Bestätigung setzen.')
    target.status='approved' if action=='approve' else 'rejected'
    target.decision_reason=reason;target.decided_by=actor;target.decided_at=timezone.now();target.save()
    if change_id and action=='approve':
        for name in FIELDS:setattr(booking,name,getattr(target,name))
        booking.rooms.set(target.rooms.all())
    booking.version+=1;booking.save()
    audit(booking,actor,('Änderungsantrag ' if change_id else 'Buchung ')+('genehmigt' if action=='approve' else 'abgelehnt'),before,snapshot(target))
    from .notifications import notify
    notify(booking,('change_' if change_id else '')+('approved' if action=='approve' else 'rejected'),target if change_id else None)
    return booking


@transaction.atomic
def cancel(actor,booking_id,version):
    require_user(actor);lock_schedule();booking=RoomBooking.objects.select_for_update().get(pk=booking_id)
    if not can_edit(actor,booking):raise PermissionDenied
    version_check(booking,version)
    if booking.status=='cancelled':return booking
    before=snapshot(booking);booking.status='cancelled';booking.version+=1;booking.save()
    for change in booking.changes.filter(status='pending'):
        change.status='cancelled';change.decided_by=actor;change.decided_at=timezone.now();change.save()
    audit(booking,actor,'Buchung storniert',before)
    from .notifications import notify
    notify(booking,'cancelled')
    return booking


@transaction.atomic
def withdraw(actor,booking_id,version):
    require_user(actor);lock_schedule();booking=RoomBooking.objects.select_for_update().get(pk=booking_id)
    if not can_edit(actor,booking):raise PermissionDenied
    version_check(booking,version)
    change=booking.changes.select_for_update().filter(status='pending').first()
    if not change:raise ValidationError('Es gibt keinen offenen Änderungsantrag.')
    before=snapshot(change);change.status='cancelled';change.decided_by=actor;change.decided_at=timezone.now();change.save()
    booking.version+=1;booking.save();audit(booking,actor,'Änderungsantrag zurückgezogen',before,snapshot(change))
    from .notifications import notify
    notify(booking,'change_withdrawn',change)
