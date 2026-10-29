import hashlib
import json
import unicodedata
from datetime import timedelta
from .security_rules import bounded_confirmation_hours
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone
from .models import Event, EventGroup, Registration, EmailJob, Throttle, AuditLog
from .forms import template_schema

ACTIVE = ['pending', 'confirmed', 'waitlisted']

def identity(name, email):
    normalize = lambda value: ' '.join(unicodedata.normalize('NFKC', value).casefold().split())
    return hashlib.sha256(json.dumps([normalize(name), normalize(email)], ensure_ascii=False).encode()).hexdigest()

def permitted(user, event, edit=False):
    from .roles import can_manage, can_read_all, is_read_only, leader_stage_ids, event_stage_ids
    if not user.is_authenticated or not user.is_active: return False
    if edit and is_read_only(user): return False
    from .access import granted,stage_ids
    if ((can_manage(user) or granted(user,'map.change_event')) if edit else can_read_all(user)): return True
    if event.eventpermission_set.filter(user=user,role__in=['editor'] if edit else ['viewer','editor']).exists(): return True
    stages=stage_ids(user,'change' if edit else 'view')
    if not stages: return False
    assigned=event_stage_ids(event)
    return bool(assigned and assigned.issubset(stages)) if edit else bool(assigned & stages)


def require_permission(user, event, edit=False):
    if not permitted(user, event, edit): raise PermissionDenied

def token_for(registration, action):
    return signing.dumps({'id': registration.pk, 'nonce': registration.token_nonce, 'action': action}, salt='map-link', compress=True)

def resolve_token(token, action):
    try:
        data = signing.loads(token, salt='map-link', max_age=settings.TOKEN_MAX_AGE)
        if data['action'] != action: raise signing.BadSignature
        return Registration.objects.select_related('event').get(pk=data['id'], token_nonce=data['nonce'])
    except (signing.BadSignature, Registration.DoesNotExist, KeyError, TypeError):
        raise ValidationError('Dieser Link ist ungültig oder abgelaufen. Bitte einen neuen Link anfordern.')

@transaction.atomic
def queue_message(registration, subject='Ihre Anmeldung'):
    event=Event.objects.select_for_update().filter(pk=registration.event_id).first()
    if event is None: return
    current=Registration.objects.filter(pk=registration.pk,event=event).first()
    if current is None: return
    registration=current;registration.event=event
    from .email_content import NOTIFICATION_KEYS
    from .mail_templates import system_content
    template_key=NOTIFICATION_KEYS.get(subject,'registration')
    from .mail_policy import enabled
    if not enabled('map',template_key):return
    rendered_subject,body=system_content(template_key,registration_message_context(registration,subject))
    from .payment_rules import payment_visible
    from .payments import payment_fingerprint
    EmailJob.objects.create(template_scope='map',template_key=template_key,event=event,registration=registration,payment_fingerprint=payment_fingerprint(event) if payment_visible(event,registration) else '',recipient=registration.email,subject=rendered_subject,body=body,next_attempt=timezone.now())


def registration_message_context(registration,subject):
    event=registration.event
    links={action:settings.PUBLIC_URL.rstrip('/')+'/'+action+'/'+token_for(registration,action)+'/' for action in ['manage','confirm']}
    confirmation=''
    if not registration.email_verified and registration.status in ACTIVE:
        deadline=timezone.localtime(registration.confirmation_deadline).strftime('%d.%m.%Y, %H:%M Uhr') if registration.confirmation_deadline else 'siehe Bestätigungsfrist'
        confirmation='E-Mail bestätigen (Frist: '+deadline+'):\n'+links['confirm']+'\n\n'
    from .email_content import status_explanation
    guidance=status_explanation(registration.status,registration.email_verified)
    from .payments import payment_text
    from .payment_rules import cost_label
    return {'event_title':event.title,'child_name':registration.child_name,'status':registration.get_status_display(),
        'stage':registration.event_group.group.name if registration.event_group_id else event.group.name,
        'status_guidance':guidance,'notification':subject,'confirmation_section':confirmation,'manage_url':links['manage'],'valid_days':settings.TOKEN_MAX_AGE//86400,
        'cost_summary':cost_label(event),'payment_section':payment_text(registration)}


def throttle(value, limit=12, seconds=3600):
    key = hashlib.sha256((settings.SECRET_KEY + value).encode()).hexdigest()
    with transaction.atomic():
        row, _ = Throttle.objects.get_or_create(key=key, defaults={'window_start': timezone.now()})
        row = Throttle.objects.select_for_update().get(pk=row.pk)
        if row.window_start < timezone.now() - timedelta(seconds=seconds):
            row.window_start, row.count = timezone.now(), 0
        row.count += 1
        row.save()
        return row.count <= limit

def ensure_group_slots(event):
    """Caller holds the event row lock. Also supports old fixtures and management code."""
    slots = list(event.group_slots.select_related('group').all())
    if not slots:
        slots = [EventGroup.objects.create(event=event, group_id=event.group_id, capacity=event.capacity)]
    fallback = next((slot for slot in slots if slot.group_id == event.group_id), slots[0])
    event.registrations.filter(event_group__isnull=True).update(event_group=fallback)
    return slots

def _rebalance(event):
    slots = ensure_group_slots(event)
    now = timezone.now()
    for row in event.registrations.filter(status__in=['pending', 'waitlisted'], email_verified=False, confirmation_deadline__lte=now):
        row.status = 'expired'
        row.save(update_fields=['status', 'updated_at'])
        queue_message(row, 'Bestätigungsfrist abgelaufen')
    if event.capacity_mode in ['shared','unlimited'] or event.waitlist_mode == 'shared':
        active_slots={slot.pk:slot for slot in slots if slot.enabled}
        occupied_total=event.registrations.filter(status__in=['pending','confirmed']).count()
        occupied_by={pk:slot.registrations.filter(status__in=['pending','confirmed']).count() for pk,slot in active_slots.items()}
        from .capacity import choose_promotions
        waiting=list(event.registrations.filter(status='waitlisted',event_group_id__in=active_slots).order_by('created_at','pk'))
        selected=choose_promotions(event.capacity_mode,event.capacity,{pk:slot.capacity for pk,slot in active_slots.items()},occupied_by,[(row.pk,row.event_group_id) for row in waiting],occupied_total)
        by_id={row.pk:row for row in waiting}
        for row_id in selected:
            row=by_id[row_id]
            row.status='confirmed' if row.email_verified else 'pending'
            row.save(update_fields=['status','updated_at'])
            queue_message(row,'Ein Platz ist frei geworden')
        return
    for slot in slots:
        if not slot.enabled: continue
        occupied = slot.registrations.filter(status__in=['pending', 'confirmed']).count()
        free = max(0, slot.capacity - occupied)
        for row in slot.registrations.filter(status='waitlisted').order_by('created_at', 'pk')[:free]:
            row.status = 'confirmed' if row.email_verified else 'pending'
            row.save(update_fields=['status', 'updated_at'])
            queue_message(row, 'Ein Platz in deiner Gruppe ist frei geworden')

@transaction.atomic
def rebalance(event_id):
    event = Event.objects.select_for_update().get(pk=event_id)
    _rebalance(event)

@transaction.atomic
def register(event_id, name, email, answers, schema=None, group_id=None):
    event = Event.objects.select_for_update(of=('self',)).select_related('form_template').get(pk=event_id)
    now = timezone.now()
    if not event.published or not event.registration_opens <= now <= event.registration_closes:
        raise ValidationError('Die Anmeldung ist derzeit geschlossen.')
    _rebalance(event)
    key = identity(name, email)
    if event.registrations.filter(identity=key, status__in=ACTIVE).exists():
        raise ValidationError('Für diese Angaben ist keine neue Anmeldung möglich. Nutzen Sie „Link erneut senden“.')
    slots = list(event.group_slots.filter(enabled=True).select_related('group'))
    if group_id is None:
        if len(slots) != 1: raise ValidationError('Bitte die Gruppe des Kindes auswählen.')
        slot = slots[0]
    else:
        slot = next((item for item in slots if str(item.group_id) == str(group_id)), None)
        if slot is None: raise ValidationError('Diese Gruppe nimmt an der Veranstaltung nicht teil.')
    full = False if event.capacity_mode=='unlimited' else (event.registrations.filter(status__in=['pending','confirmed']).count() >= event.capacity) if event.capacity_mode=='shared' else (slot.registrations.filter(status__in=['pending', 'confirmed']).count() >= slot.capacity)
    if full and not event.waitlist_enabled: raise ValidationError('Alle Plätze sind belegt.' if event.capacity_mode=='shared' else 'Alle Plätze dieser Gruppe sind belegt.')
    row = Registration.objects.create(event=event, event_group=slot, child_name=name.strip(), email=email.strip().lower(), identity=key,
          answers=answers, schema_snapshot=template_schema(event.form_template) if schema is None else schema, email_verified=not event.confirmation_required,
          confirmation_deadline=now + timedelta(hours=bounded_confirmation_hours(event.confirmation_hours)) if event.confirmation_required else None,
          status='waitlisted' if full else ('pending' if event.confirmation_required else 'confirmed'))
    queue_message(row)
    return row

@transaction.atomic
def confirm(registration_id):
    initial = Registration.objects.get(pk=registration_id)
    event = Event.objects.select_for_update().get(pk=initial.event_id)
    _rebalance(event)
    row = Registration.objects.get(pk=registration_id)
    if row.status not in ACTIVE: raise ValidationError('Diese Anmeldung ist nicht mehr aktiv.')
    if row.email_verified: return row
    row.email_verified = True
    if row.status == 'pending': row.status = 'confirmed'
    row.save()
    queue_message(row, 'E-Mail bestätigt')
    return row

@transaction.atomic
def cancel(registration_id, actor=None):
    initial = Registration.objects.get(pk=registration_id)
    event = Event.objects.select_for_update().get(pk=initial.event_id)
    row = Registration.objects.get(pk=registration_id)
    if row.status in ACTIVE:
        row.status = 'cancelled'
        row.save()
        queue_message(row, 'Anmeldung storniert')
        _rebalance(event)
        if actor: AuditLog.objects.create(actor=actor, event=event, action=f'cancel registration {row.pk}')
    return row

@transaction.atomic
def edit_registration(registration_id, answers, actor=None):
    initial = Registration.objects.get(pk=registration_id)
    Event.objects.select_for_update().get(pk=initial.event_id)
    row = Registration.objects.get(pk=registration_id)
    if row.status not in ACTIVE: raise ValidationError('Diese Anmeldung ist nicht mehr aktiv.')
    row.answers = answers
    row.save()
    queue_message(row, 'Anmeldung geändert')
    if actor: AuditLog.objects.create(actor=actor, event=row.event, action=f'edit registration {row.pk}')
    return row
