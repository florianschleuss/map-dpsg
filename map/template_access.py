"""Shared standards and accessible event forms, without cross-stage disclosure."""
from django.db.models import Q
from .models import FormTemplate

def available_templates(user):
    from .access import can_templates
    from .roles import visible_events
    if not user or not user.is_authenticated or not user.is_active:return FormTemplate.objects.none()
    if can_templates(user):return FormTemplate.objects.all()
    return FormTemplate.objects.filter(Q(created_by=user)|Q(created_by__isnull=True)|Q(event__in=visible_events(user))).distinct()
