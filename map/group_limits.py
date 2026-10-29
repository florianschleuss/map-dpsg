from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Event, EventGroup
ACTIVE = ['pending', 'confirmed', 'waitlisted']

def validate_limits(event, limits, pooled=None):
    pooled=(getattr(event,'capacity_mode','per_group') in ['shared','unlimited']) if pooled is None else pooled
    if not limits: raise ValidationError('Bitte mindestens eine Gruppe mit einem Platzlimit auswählen.')
    for key, capacity in limits.items():
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1 or capacity > 2147483647:
            raise ValidationError('Für jede ausgewählte Gruppe ist eine gültige ganze Platzzahl ab 1 erforderlich.')
    if sum(limits.values()) > 2147483647: raise ValidationError('Die Gesamtzahl der Plätze ist zu groß.')
    if event.pk:
        for slot in event.group_slots.all():
            active = slot.registrations.filter(status__in=ACTIVE)
            if str(slot.group_id) not in limits and active.exists():
                raise ValidationError(f'Die Gruppe „{slot.group}“ hat noch aktive Anmeldungen und kann nicht entfernt werden.')
            occupied = slot.registrations.filter(status__in=['pending', 'confirmed']).count()
            if not pooled and str(slot.group_id) in limits and limits[str(slot.group_id)] < occupied:
                raise ValidationError(f'Für „{slot.group}“ sind bereits {occupied} Plätze reserviert oder bestätigt.')

@transaction.atomic
def apply_limits(event, groups, limits):
    Event.objects.select_for_update().get(pk=event.pk)
    validate_limits(event, limits)
    if event.capacity_mode=='shared' and event.capacity < event.registrations.filter(status__in=['pending','confirmed']).count():
        raise ValidationError('Der Gesamtpool darf nicht kleiner als die bereits belegten oder reservierten Plätze sein.')
    selected = {group.pk:group for group in groups}
    for slot in event.group_slots.all():
        if slot.group_id not in selected:
            slot.enabled = False
            slot.save(update_fields=['enabled'])
    for group in groups:
        EventGroup.objects.update_or_create(event=event,group=group,defaults={'capacity':limits[str(group.pk)],'enabled':True})
    event.group = groups[0]
    if event.capacity_mode != 'shared': event.capacity = sum(limits.values())
    event.save(update_fields=['group','capacity'])
